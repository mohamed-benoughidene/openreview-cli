from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from openreview_cli.gateway.registry import ModelRegistry

if TYPE_CHECKING:
    import pytest

MODELS_JSON = {
    "providers": {
        "openai": {
            "name": "OpenAI",
            "env_key": "OPENAI_API_KEY",
            "auth_required": True,
            "models": {
                "gpt-4o": {
                    "slots": ["reasoning", "extraction"],
                    "context": 128000,
                    "recommended": True,
                    "status": "active",
                },
                "gpt-4o-mini": {
                    "slots": ["reasoning"],
                    "context": 128000,
                    "recommended": False,
                    "status": "active",
                },
            },
        },
        "anthropic": {
            "name": "Anthropic",
            "env_key": "ANTHROPIC_API_KEY",
            "auth_required": True,
            "models": {
                "claude-3-opus": {
                    "slots": ["reasoning", "extraction"],
                    "context": 200000,
                    "recommended": True,
                    "status": "active",
                },
            },
        },
    },
}


class _MockResponse:
    def __init__(self, text: str) -> None:
        self.text = text
        self._parsed = json.loads(text)

    def json(self) -> Any:
        return self._parsed

    def raise_for_status(self) -> None:
        pass


def test_load_valid_json(tmp_path: Path) -> None:
    registry_path = tmp_path / "models.json"
    registry_path.write_text(json.dumps(MODELS_JSON))
    registry = ModelRegistry(registry_path)
    registry.load()
    assert "openai" in registry._providers
    assert "anthropic" in registry._providers
    assert len(registry._providers["openai"].models) == 2
    assert len(registry._providers["anthropic"].models) == 1
    assert registry._providers["openai"].name == "OpenAI"
    assert registry._providers["openai"].env_key == "OPENAI_API_KEY"
    assert registry._providers["openai"].auth_required is True


def test_load_non_existent_file(tmp_path: Path) -> None:
    registry_path = tmp_path / "nonexistent.json"
    registry = ModelRegistry(registry_path)
    registry.load()
    assert registry._providers == {}


def test_list_providers(tmp_path: Path) -> None:
    registry_path = tmp_path / "models.json"
    registry_path.write_text(json.dumps(MODELS_JSON))
    registry = ModelRegistry(registry_path)
    registry.load()
    providers = registry.list_providers()
    assert len(providers) == 2
    names = {p["name"] for p in providers}
    assert names == {"OpenAI", "Anthropic"}
    for p in providers:
        if p["name"] == "OpenAI":
            assert p["env_key"] == "OPENAI_API_KEY"
            assert p["auth_required"] is True
            assert p["model_count"] == 2
        elif p["name"] == "Anthropic":
            assert p["env_key"] == "ANTHROPIC_API_KEY"
            assert p["auth_required"] is True
            assert p["model_count"] == 1


def test_list_models_known_provider(tmp_path: Path) -> None:
    registry_path = tmp_path / "models.json"
    registry_path.write_text(json.dumps(MODELS_JSON))
    registry = ModelRegistry(registry_path)
    registry.load()
    models = registry.list_models("openai")
    assert len(models) == 2
    model_ids = {m["model_id"] for m in models}
    assert model_ids == {"gpt-4o", "gpt-4o-mini"}
    for m in models:
        if m["model_id"] == "gpt-4o":
            assert m["slots"] == ["reasoning", "extraction"]
            assert m["context"] == 128000
            assert m["recommended"] is True


def test_list_models_unknown_provider(tmp_path: Path) -> None:
    registry_path = tmp_path / "models.json"
    registry_path.write_text(json.dumps(MODELS_JSON))
    registry = ModelRegistry(registry_path)
    registry.load()
    models = registry.list_models("nonexistent")
    assert models == []


def test_refresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_path = tmp_path / "models.json"
    registry = ModelRegistry(registry_path)

    def mock_get(url: str, **kwargs: Any) -> _MockResponse:
        return _MockResponse(json.dumps(MODELS_JSON))

    monkeypatch.setattr(httpx, "get", mock_get)
    count = registry.refresh("https://example.com/models.json")
    assert count == 3
    assert registry_path.exists()
    assert json.loads(registry_path.read_text()) == MODELS_JSON
    assert len(registry.list_providers()) == 2


def test_discover_ollama(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_path = tmp_path / "models.json"
    registry = ModelRegistry(registry_path)
    ollama_data = {
        "models": [
            {
                "name": "llama3:latest",
                "details": {"parameter_size": "7B"},
            },
            {
                "name": "mistral:latest",
                "details": {"parameter_size": "7B"},
            },
        ]
    }

    def mock_get(url: str, **kwargs: Any) -> _MockResponse:
        return _MockResponse(json.dumps(ollama_data))

    monkeypatch.setattr(httpx, "get", mock_get)
    models = registry.discover_ollama("http://localhost:11434")
    assert len(models) == 2
    assert models[0]["model_id"] == "llama3:latest"
    assert models[0]["note"] == "Ollama local — 7B"
    assert models[1]["model_id"] == "mistral:latest"
    assert models[1]["note"] == "Ollama local — 7B"


def test_discover_ollama_unreachable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_path = tmp_path / "models.json"
    registry = ModelRegistry(registry_path)

    def mock_get(url: str, **kwargs: Any) -> None:
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx, "get", mock_get)
    models = registry.discover_ollama("http://localhost:11434")
    assert models == []
