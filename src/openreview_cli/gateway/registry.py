from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx
import yaml

from openreview_cli.config.loader import add_custom_provider as _loader_add_custom_provider
from openreview_cli.gateway.errors import (
    EnvKeyCollisionError,
    ProviderNameCollisionError,
)
from openreview_cli.gateway.models import Capability, ModelEntry, ProviderInfo

try:
    import platformdirs

    def _config_dir() -> Path:
        return Path(platformdirs.user_config_dir("openreview"))
except Exception:  # pragma: no cover - platformdirs is a hard dependency
    from openreview_cli.config.paths import get_config_dir as _config_dir


def _build_provider(name: str, info: dict[str, Any]) -> ProviderInfo:
    models_raw = info.pop("models", {})
    models = {k: ModelEntry(**v) for k, v in models_raw.items()}
    caps_raw = info.pop("capabilities", None)
    caps = Capability(**caps_raw) if caps_raw else Capability()
    env_key = info.get("env_key") or info.get("api_key_env")
    creds_raw = info.pop("credentials", [])
    return ProviderInfo(
        name=info.get("name", name),
        env_key=env_key,
        auth_required=info.get("auth_required", True),
        base_url=info.get("base_url"),
        is_local=info.get("is_local", False),
        source=info.get("source", "bundled"),
        capabilities=caps,
        models=models,
        credentials=creds_raw,
    )


def load_registry() -> dict[str, ProviderInfo]:
    """Single source of truth: bundled + user overlays + custom providers."""
    config_dir = _config_dir()
    user_models = config_dir / "models.json"
    bundled = Path(__file__).resolve().parent / "models.json"

    merged: dict[str, ProviderInfo] = {}
    if bundled.exists():
        raw = json.loads(bundled.read_text())
        for name, info in raw.get("providers", {}).items():
            merged[name] = _build_provider(name, info)

    # Overlay user file: only entries not in bundled, or user-edited entries.
    # ponytail: manual hand-edits to models.json are an accepted limitation —
    # the app always sets source correctly; we don't guard against human edits.
    if user_models.exists():
        raw = json.loads(user_models.read_text())
        for name, info in raw.get("providers", {}).items():
            # Never overwrite a bundled entry with a user copy unless user-edited.
            if name in merged and info.get("source", "bundled") == "bundled":
                continue
            merged[name] = _build_provider(name, info)

    # Custom providers from config.yml.
    config_yml = config_dir / "config.yml"
    if config_yml.exists():
        cfg = yaml.safe_load(config_yml.read_text()) or {}
        for provider in cfg.get("gateway", {}).get("custom_providers", []) or []:
            if isinstance(provider, dict) and provider.get("name"):
                custom = dict(provider)
                custom["source"] = "custom"
                merged[custom["name"]] = _build_provider(custom["name"], custom)

    return merged


def add_custom_provider(
    name: str,
    base_url: str,
    capabilities: dict[str, Any] | None = None,
    api_key_env: str | None = None,
) -> ProviderInfo:
    """Register a custom provider: collision-check then persist to config.yml."""
    derived_env = api_key_env or (re.sub(r"[^A-Z0-9]", "_", name.upper()) + "_API_KEY")

    existing = load_registry()
    for p in existing.values():
        if p.name.lower() == name.lower():
            raise ProviderNameCollisionError(name, "a provider with this name already exists")
        if (p.env_key or "").upper() == derived_env.upper():
            raise EnvKeyCollisionError(name, derived_env, existing=p.name)

    config_path = _config_dir() / "config.yml"
    _loader_add_custom_provider(config_path, name, base_url, derived_env, capabilities)
    return _build_provider(
        name,
        {
            "name": name,
            "base_url": base_url,
            "env_key": derived_env,
            "source": "custom",
            "capabilities": capabilities,
            "models": {},
        },
    )


class ModelRegistry:
    def __init__(self, registry_path: Path) -> None:
        self._path = registry_path
        self._providers: dict[str, ProviderInfo] = {}

    def load(self) -> None:
        if not self._path.exists():
            self._providers = {}
            return
        with open(self._path) as f:
            raw = json.load(f)
        providers_raw = raw.get("providers", {})
        self._providers = {}
        for name, info in providers_raw.items():
            models_raw = info.pop("models", {})
            models = {k: ModelEntry(**v) for k, v in models_raw.items()}
            creds_raw = info.pop("credentials", [])
            self._providers[name] = ProviderInfo(
                name=info["name"],
                env_key=info.get("env_key"),
                auth_required=info.get("auth_required", True),
                models=models,
                credentials=creds_raw,
            )

    def list_providers(self) -> list[dict[str, Any]]:
        return [
            {
                "name": p.name,
                "env_key": p.env_key,
                "auth_required": p.auth_required,
                "model_count": len(p.models),
            }
            for p in self._providers.values()
        ]

    def list_models(self, provider: str) -> list[dict[str, Any]]:
        p = self._providers.get(provider)
        if not p:
            return []
        return [
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
            for mid, m in p.models.items()
        ]

    def refresh(self, remote_url: str) -> int:
        resp = httpx.get(remote_url, timeout=10)
        resp.raise_for_status()
        self._path.write_text(resp.text)
        self.load()
        return sum(len(p.models) for p in self._providers.values())

    def discover_ollama(self, base_url: str = "http://localhost:11434") -> list[dict[str, Any]]:
        try:
            resp = httpx.get(f"{base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            models: list[dict[str, Any]] = []
            for model in data.get("models", []):
                name = model.get("name", "")
                details = model.get("details", {})
                models.append(
                    {
                        "model_id": name,
                        "slots": ["reasoning", "extraction", "graph"],
                        "ram": None,
                        "recommended": False,
                        "status": "available",
                        "note": f"Ollama local — {details.get('parameter_size', 'unknown')}",
                    }
                )
        except Exception:
            models = []
        return models
