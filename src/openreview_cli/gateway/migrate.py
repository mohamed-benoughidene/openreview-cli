from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

import yaml

from openreview_cli.config.auth import key_to_env
from openreview_cli.gateway.router import VALID_SLOTS
from openreview_cli.gateway.v2_config import V2Config

logger = logging.getLogger(__name__)

# Providers that default to local (no env key needed)
_LOCAL_PROVIDERS: frozenset[str] = frozenset({"ollama"})

# Default base URLs for local providers
_LOCAL_BASE_URLS: dict[str, str] = {
    "ollama": "http://localhost:11434",
}

# Slots that always get migrated from v1
_V1_SLOTS: list[str] = sorted(VALID_SLOTS - {"grounding"})

# New slot added in v2 with a default
_V2_NEW_SLOTS: list[str] = ["grounding"]


def _parse_primary(primary: str) -> tuple[str, str]:
    """Split 'provider/model' into (provider, model)."""
    if "/" in primary:
        provider, model = primary.split("/", 1)
        return provider, model
    return "", primary


def _collect_providers(v1_config: dict[str, Any]) -> set[str]:
    """Scan v1 gateway.models slots, collect unique provider names."""
    providers: set[str] = set()
    models = v1_config.get("gateway", {}).get("models", {})
    for slot_name in _V1_SLOTS:
        slot = models.get(slot_name, {})
        primary = slot.get("primary", "")
        if primary and "/" in primary:
            providers.add(primary.split("/", 1)[0])
        fallback = slot.get("fallback")
        if fallback and "/" in fallback:
            providers.add(fallback.split("/", 1)[0])
    return providers


def _build_providers_section(providers: set[str]) -> dict[str, dict[str, Any]]:
    """Build the v2 providers dict from a set of provider names."""
    result: dict[str, dict[str, Any]] = {}
    for provider in sorted(providers):
        entry: dict[str, Any] = {
            "name": provider,
            "env_key": key_to_env(provider),
            "enabled": True,
        }
        if provider in _LOCAL_PROVIDERS:
            entry["base_url"] = _LOCAL_BASE_URLS.get(provider, "http://localhost:11434")
        result[provider] = entry
    return result


def _build_slots_section(
    v1_config: dict[str, Any], providers: set[str]
) -> dict[str, dict[str, Any]]:
    """Build v2 slots from v1 gateway.models."""
    models = v1_config.get("gateway", {}).get("models", {})
    slots: dict[str, dict[str, Any]] = {}

    for slot_name in _V1_SLOTS:
        v1_slot = models.get(slot_name, {})
        primary = v1_slot.get("primary", "")
        fallback = v1_slot.get("fallback")

        provider, model = _parse_primary(primary)
        if not provider and providers:
            # Infer provider from available providers if model string has no /
            # ponytail: if model string has no provider prefix, pick first provider
            provider = sorted(providers)[0]

        slot_entry: dict[str, Any] = {
            "provider": provider,
            "model": model,
        }

        if fallback:
            fb_provider, fb_model = _parse_primary(fallback)
            if not fb_provider and providers:
                fb_provider = sorted(providers)[0]
            slot_entry["fallback"] = {
                "provider": fb_provider,
                "model": fb_model,
            }

        slots[slot_name] = slot_entry

    # Add grounding slot with same provider/model as reasoning
    reasoning = slots.get("reasoning", {})
    slots["grounding"] = {
        "provider": reasoning.get("provider", ""),
        "model": reasoning.get("model", ""),
    }

    return slots


def _build_fallback_section(v1_config: dict[str, Any]) -> dict[str, Any]:
    """Build v2 fallback config from v1 gateway.fallback."""
    v1_fallback = v1_config.get("gateway", {}).get("fallback", {})
    return {
        "retries": v1_fallback.get("retries", 2),
        "timeout": v1_fallback.get("timeout", 60),
        "on_failure": v1_fallback.get("on_failure", "error"),
    }


def _build_cost_limits_section(v1_config: dict[str, Any]) -> dict[str, Any] | None:
    """Build v2 cost_limits from v1 gateway.cost_limits."""
    v1_costs = v1_config.get("gateway", {}).get("cost_limits", {})
    if not v1_costs:
        # Provide sensible defaults
        return {"per_session_cents": 100, "daily_cents": 1000}
    return {
        "per_session_cents": v1_costs.get("per_review_cents", 100),
        "daily_cents": v1_costs.get("daily_cents", 1000),
    }


def migrate_config(
    v1_path: str,
    v2_path: str,
    *,
    auth_path: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Migrate v1 config to v2 provider-first format.

    Args:
        v1_path: Path to existing v1 config.yml.
        v2_path: Path to write v2 config.yml.
        auth_path: Path to auth.json (not touched, only used for validation in tests).
        dry_run: If True, validate but do not write files.

    Returns:
        dict with keys: status ('migrated'|'noop'|'dry_run'), providers_added,
        slots_migrated, backup path, reason (if noop).
    """
    v1 = Path(v1_path)
    v2 = Path(v2_path)

    # Read config
    with open(v1) as f:
        config: dict[str, Any] = yaml.safe_load(f)

    if not config:
        return {"status": "noop", "reason": "empty config file"}

    # Detect v2
    if config.get("version") == 2:
        logger.debug("Config already v2 — no-op")
        return {"status": "noop", "reason": "already v2"}

    # Extract providers from v1 slot model strings
    providers = _collect_providers(config)
    if not providers:
        return {"status": "noop", "reason": "no providers found in config"}

    # Build v2 sections
    providers_section = _build_providers_section(providers)
    slots_section = _build_slots_section(config, providers)
    fallback_section = _build_fallback_section(config)
    cost_limits = _build_cost_limits_section(config)

    # Assemble v2 config dict (matching V2Config model field names)
    v2_config_dict: dict[str, Any] = {
        "version": 2,
        "providers": providers_section,
        "slots": slots_section,
        "default_model": None,
        "fallback": fallback_section,
        "cost_limits": cost_limits,
    }

    # Validate with V2Config Pydantic model
    V2Config.model_validate(v2_config_dict)

    if dry_run:
        return {
            "status": "dry_run",
            "providers_added": sorted(providers),
            "slots_migrated": _V1_SLOTS + _V2_NEW_SLOTS,
            "dry_run": True,
        }

    # Backup v1 FIRST (before overwriting)
    backup_path = v1.with_suffix(".v1.bak")
    v1.rename(backup_path)

    # Atomic write v2 to v2_path
    fd, tmp_name = tempfile.mkstemp(dir=v2.parent, suffix=".tmp")
    try:
        with open(fd, "w") as f:
            yaml.dump(v2_config_dict, f, default_flow_style=False, sort_keys=False)
        Path(tmp_name).rename(v2)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        # Restore backup on failure
        if backup_path.exists():
            backup_path.rename(v1)
        raise

    # Do NOT touch auth.json — auth_path param is only used for test validation

    return {
        "status": "migrated",
        "providers_added": sorted(providers),
        "slots_migrated": _V1_SLOTS + _V2_NEW_SLOTS,
        "backup": str(backup_path),
    }
