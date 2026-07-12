"""Gateway wrapper for TUI domain layer."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")

from openreview_cli.config.auth import has_key as _has_key
from openreview_cli.config.auth import save_key as _save_key
from openreview_cli.config.loader import load_config, set_config_value
from openreview_cli.config.paths import get_config_dir, get_data_dir
from openreview_cli.gateway.registry import ModelRegistry
from openreview_cli.gateway.router import VALID_SLOTS, Gateway

_PATHS: dict[str, Path] = {
    "config": get_config_dir() / "config.yml",
    "auth": get_config_dir() / "auth.json",
    "data": get_data_dir() / "openreview.db",
    "registry": get_config_dir() / "models.json",
}

_REGISTRY = ModelRegistry(_PATHS["registry"])
_REGISTRY.load()


def _safe(fn: Callable[..., T], default: T) -> T:
    try:
        return fn()
    except Exception:
        return default


def gateway_health_check() -> dict[str, Any]:
    """Run gateway health check, return slot->status dict."""
    from openreview_cli.config.auth import ensure_auth

    return _safe(
        lambda: (
            ensure_auth(_PATHS["auth"].parent),
            Gateway(_PATHS["config"], _PATHS["auth"], _PATHS["data"]).health_check(),
        )[1],
        {},
    )


def get_slot_configs() -> dict[str, dict[str, Any]]:
    """Get all 6 slot configurations for display."""
    config = _safe(lambda: load_config(_PATHS["config"]), None)
    if config is None:
        return {}
    models = config.get("gateway", {}).get("models", {})
    result: dict[str, dict[str, Any]] = {}
    for slot in sorted(VALID_SLOTS):
        cfg = models.get(slot, {})
        primary = cfg.get("primary", "")
        provider = primary.split("/")[0] if "/" in primary else ""
        model_name = primary.split("/", 1)[1] if "/" in primary else primary
        result[slot] = {
            "provider": provider,
            "model": model_name,
            "configured": bool(primary),
        }
    return result


def list_providers() -> list[dict[str, Any]]:
    """List available providers from registry."""
    return _safe(lambda: _REGISTRY.list_providers(), [])


def list_models(provider: str) -> list[dict[str, Any]]:
    """List models for a given provider."""
    return _safe(lambda: _REGISTRY.list_models(provider), [])


def save_slot_config(slot: str, provider: str, model_name: str) -> None:
    """Save slot primary model config."""
    full = f"{provider}/{model_name}" if provider else model_name
    set_config_value(_PATHS["config"], f"gateway.models.{slot}.primary", full)


def provider_has_key(provider: str) -> bool:
    """Check if provider has a saved API key."""
    return _safe(lambda: _has_key(_PATHS["auth"], provider), False)


def save_api_key(provider: str, key: str) -> None:
    """Save API key for provider."""
    _save_key(_PATHS["auth"], provider, key)
