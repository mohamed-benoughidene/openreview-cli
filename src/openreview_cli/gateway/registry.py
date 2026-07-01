from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import httpx

from openreview_cli.gateway.models import ModelEntry, ProviderInfo


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
            self._providers[name] = ProviderInfo(
                name=info["name"],
                env_key=info.get("env_key"),
                auth_required=info.get("auth_required", True),
                models=models,
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
