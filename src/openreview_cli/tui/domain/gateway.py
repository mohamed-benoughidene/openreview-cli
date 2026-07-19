"""Gateway wrapper for TUI domain layer."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

T = TypeVar("T")

from openreview_cli.config.auth import has_key as _has_key
from openreview_cli.config.auth import save_key as _save_key
from openreview_cli.config.loader import load_config, set_config_value
from openreview_cli.config.paths import get_config_dir, get_data_dir
from openreview_cli.slots import VALID_SLOTS

if TYPE_CHECKING:
    from openreview_cli.gateway.models import ProviderInfo


_PATHS: dict[str, Path] = {
    "config": get_config_dir() / "config.yml",
    "auth": get_config_dir() / "auth.json",
    "data": get_data_dir() / "openreview.db",
}


@lru_cache(maxsize=1)
def _get_registry() -> dict[str, ProviderInfo]:
    """Lazily load the provider registry.

    Uses load_registry() (no litellm import) so the TUI import graph stays
    clean. The registry is only built when a provider/model list is requested.
    """
    from openreview_cli.gateway.registry import load_registry

    return load_registry()


def _safe(fn: Callable[..., T], default: T) -> T:
    try:
        return fn()
    except Exception:
        return default


def gateway_health_check() -> dict[str, Any]:
    """Run gateway health check, return slot->status dict."""
    from openreview_cli.config.auth import ensure_auth
    from openreview_cli.gateway.router import Gateway

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
    reg = _get_registry()
    return _safe(
        lambda: [
            {
                "name": n,
                "env_key": p.env_key,
                "auth_required": p.auth_required,
                "model_count": len(p.models),
            }
            for n, p in reg.items()
        ],
        [],
    )


def list_models(provider: str) -> list[dict[str, Any]]:
    """List models for a given provider."""
    reg = _get_registry()
    return _safe(
        lambda: [
            {
                "model_id": mid,
                "slots": m.slots,
                "context": m.context,
                "dimensions": m.dimensions,
                "ram": m.ram,
                "recommended": m.recommended,
                "status": m.status,
                "note": m.note,
            }
            for mid, m in reg[provider].models.items()
        ],
        [],
    )


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
