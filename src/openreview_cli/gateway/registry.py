from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
import platformdirs
import yaml

from openreview_cli.config.loader import add_custom_provider as _loader_add_custom_provider
from openreview_cli.gateway.errors import (
    EnvKeyCollisionError,
    ProviderNameCollisionError,
)
from openreview_cli.gateway.models import Capability, ModelEntry, ProviderInfo


def _config_dir() -> Path:
    return Path(platformdirs.user_config_dir("openreview"))


logger = logging.getLogger(__name__)

_OLLAMA_DEFAULT_URL = "http://localhost:11434"
_OLLAMA_DEFAULT_PORT = 11434
# Bind-all addresses are valid for listening but cannot be connected to as a client.
_OLLAMA_UNSPECIFIED_HOSTS = {"0.0.0.0": "127.0.0.1", "::": "::1"}


def ollama_base_url_from_env(environ: Mapping[str, str] | None = None) -> str:
    """Resolve Ollama's base URL from ``OLLAMA_HOST``, mirroring Ollama's own rules.

    ``OLLAMA_HOST`` is ``host[:port]`` with an optional scheme (Ollama's format; its
    default is 127.0.0.1:11434). A value that already carries a scheme is used as
    given; otherwise ``http`` and the default port 11434 are applied. A bind-all
    address (0.0.0.0 / ::) is mapped to loopback. A malformed value is ignored (the
    default is kept) and logged, so a bad variable never breaks startup.
    """
    env = os.environ if environ is None else environ
    raw_value = env.get("OLLAMA_HOST")
    if raw_value is None:
        return _OLLAMA_DEFAULT_URL
    raw = raw_value.strip().strip("\"'").strip()
    if not raw:
        logger.warning("Ignoring empty OLLAMA_HOST; using %s", _OLLAMA_DEFAULT_URL)
        return _OLLAMA_DEFAULT_URL

    has_scheme = "://" in raw
    try:
        parts = urlsplit(raw if has_scheme else f"http://{raw}")
        host = parts.hostname
        port = parts.port  # raises ValueError on a non-numeric port
    except ValueError:
        host, port = None, None
    if not host:
        logger.warning("Ignoring invalid OLLAMA_HOST=%r; using %s", raw, _OLLAMA_DEFAULT_URL)
        return _OLLAMA_DEFAULT_URL

    host = _OLLAMA_UNSPECIFIED_HOSTS.get(host, host)
    if not has_scheme and port is None:
        port = _OLLAMA_DEFAULT_PORT
    if port is None:
        netloc = f"[{host}]" if ":" in host else host
    else:
        netloc = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
    scheme = parts.scheme if has_scheme else "http"
    return urlunsplit((scheme, netloc, parts.path.rstrip("/"), "", ""))


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

    # OLLAMA_HOST override (runtime). Applied last so it wins over the bundled and
    # user-overlay addresses; untouched when the variable is unset.
    if os.environ.get("OLLAMA_HOST") is not None and "ollama" in merged:
        resolved = ollama_base_url_from_env()
        current = merged["ollama"].base_url
        if resolved != current:
            logger.info("OLLAMA_HOST override: ollama base_url %s -> %s", current, resolved)
        merged["ollama"] = merged["ollama"].model_copy(update={"base_url": resolved})

    return merged


def discover_ollama(base_url: str | None = None) -> list[dict[str, Any]]:
    """Return locally installed Ollama models, or [] if the server is unreachable.

    ``base_url`` defaults to the ``OLLAMA_HOST``-resolved address.
    """
    if base_url is None:
        base_url = ollama_base_url_from_env()
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
                    "slots": ["extraction", "reasoning", "grounding"],
                    "ram": None,
                    "recommended": False,
                    "status": "available",
                    "note": f"Ollama local — {details.get('parameter_size', 'unknown')}",
                }
            )
    except Exception:
        models = []
    return models


def provider_credential_status(info: ProviderInfo, auth: dict[str, Any]) -> dict[str, Any]:
    """Per-field credential resolution for a provider. Never includes values.

    Resolution order matches router._apply_provider_credentials: environment
    variable first, then the auth.json dict (new dict form keyed by env_key).
    """
    stored = auth.get(info.name)
    stored_dict = stored if isinstance(stored, dict) else {}
    fields: list[dict[str, Any]] = []
    for f in info.credentials:
        resolved = bool(os.environ.get(f.env_key) or stored_dict.get(f.env_key))
        fields.append(
            {
                "env_key": f.env_key,
                "label": f.label,
                "secret": f.secret,
                "required": f.required,
                "litellm_param": f.litellm_param,
                "resolved": resolved,
            }
        )
    if fields:
        configured = all(f["resolved"] for f in fields if f["required"])
    elif info.env_key:
        # ponytail: legacy single-key providers — configured if env or stored string set
        configured = bool(stored or os.environ.get(info.env_key))
    else:
        configured = bool(stored)
    return {"configured": configured, "credentials": fields}


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


# ponytail: partial-fields loader, wizard-only; unify with load_registry() if touched again
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

    def discover_ollama(self, base_url: str | None = None) -> list[dict[str, Any]]:
        return discover_ollama(base_url)
