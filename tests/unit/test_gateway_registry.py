import json
from pathlib import Path

import httpx
import pytest
import respx

from openreview_cli.gateway.registry import ModelRegistry, get_models_for_slot


def test_get_models_for_slot_filtering() -> None:
    # Embedding models for openai
    openai_embed = get_models_for_slot("openai", "embedding")
    assert openai_embed == ["text-embedding-3-small"]

    # Reasoning models for openai (not gpt-4o-mini, which is extraction/graph only)
    openai_reason = get_models_for_slot("openai", "reasoning")
    assert "gpt-4o" in openai_reason
    assert "gpt-4o-mini" not in openai_reason

    # Cohere: each model has a distinct slot
    cohere_embed = get_models_for_slot("cohere", "embedding")
    assert cohere_embed == ["embed-english-v3.0"]
    cohere_rerank = get_models_for_slot("cohere", "reranking")
    assert cohere_rerank == ["rerank-english-v3.0"]
    cohere_reason = get_models_for_slot("cohere", "reasoning")
    assert cohere_reason == ["command-r-plus"]

    # No Ollama model is tagged embedding except nomic-embed-text
    ollama_embed = get_models_for_slot("ollama", "embedding")
    assert ollama_embed == ["nomic-embed-text"]

    # No Anthropic model is compatible with embedding
    assert get_models_for_slot("anthropic", "embedding") == []

    # Custom provider has no registry entries
    assert get_models_for_slot("custom", "reasoning") == []


@pytest.fixture
def temp_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("openreview_cli.gateway.registry.get_cache_dir", lambda: cache_dir)
    return cache_dir


def test_registry_fallback_when_missing(temp_cache_dir: Path) -> None:
    # Ensure cache file does not exist
    cache_file = temp_cache_dir / "model_registry.json"
    if cache_file.exists():
        cache_file.unlink()

    registry = ModelRegistry()
    models = registry.get_all_models()
    assert len(models) > 0
    # verify some top models are in fallback
    openai_models = [m for m in models if m.provider == "openai"]
    assert any(m.model_id == "gpt-4o" for m in openai_models)


def test_registry_fallback_when_corrupted(temp_cache_dir: Path) -> None:
    cache_file = temp_cache_dir / "model_registry.json"
    cache_file.write_text("{invalid json")

    registry = ModelRegistry()
    models = registry.get_all_models()
    assert len(models) > 0
    assert any(m.provider == "openai" and m.model_id == "gpt-4o" for m in models)


def test_registry_load_valid_cache(temp_cache_dir: Path) -> None:
    cache_file = temp_cache_dir / "model_registry.json"
    test_data = [
        {
            "provider": "custom_prov",
            "model_id": "custom-model",
            "display_name": "Custom Model",
            "slot_compatibility": ["reasoning"],
            "context_window": 8000,
            "ram_required_mb": None,
            "pricing_input_usd_per_mtok": 1.0,
            "pricing_output_usd_per_mtok": 2.0,
            "is_local": False,
        }
    ]
    cache_file.write_text(json.dumps(test_data))

    registry = ModelRegistry()
    models = registry.get_all_models()
    assert len(models) == 1
    assert models[0].provider == "custom_prov"
    assert models[0].model_id == "custom-model"


@respx.mock
def test_registry_refresh_success(temp_cache_dir: Path) -> None:
    url = "https://example.com/models.json"
    mock_data = [
        {
            "provider": "remote_prov",
            "model_id": "remote-model",
            "display_name": "Remote Model",
            "slot_compatibility": ["extraction"],
            "context_window": 16000,
            "ram_required_mb": None,
            "pricing_input_usd_per_mtok": 0.5,
            "pricing_output_usd_per_mtok": 1.5,
            "is_local": False,
        }
    ]
    respx.get(url).mock(return_value=httpx.Response(200, json=mock_data))

    registry = ModelRegistry()
    # Before refresh, loads fallback/empty
    assert not any(m.provider == "remote_prov" for m in registry.get_all_models())

    # Refresh
    registry.refresh(url)

    # After refresh, should load remote models
    models = registry.get_all_models()
    assert any(m.provider == "remote_prov" and m.model_id == "remote-model" for m in models)

    # Verify cache file updated
    cache_file = temp_cache_dir / "model_registry.json"
    assert cache_file.exists()
    cached_content = json.loads(cache_file.read_text())
    assert cached_content[0]["provider"] == "remote_prov"


@respx.mock
def test_registry_refresh_failure_retains_cache(temp_cache_dir: Path) -> None:
    # First write some valid data to cache
    cache_file = temp_cache_dir / "model_registry.json"
    initial_data = [
        {
            "provider": "initial_prov",
            "model_id": "initial-model",
            "display_name": "Initial Model",
            "slot_compatibility": ["reasoning"],
            "context_window": 4000,
            "ram_required_mb": None,
            "pricing_input_usd_per_mtok": 1.0,
            "pricing_output_usd_per_mtok": 1.0,
            "is_local": False,
        }
    ]
    cache_file.write_text(json.dumps(initial_data))

    url = "https://example.com/models.json"
    respx.get(url).mock(return_value=httpx.Response(500))

    registry = ModelRegistry()
    assert any(m.provider == "initial_prov" for m in registry.get_all_models())

    # Try refreshing (should fail but retain cache)
    with pytest.raises(httpx.HTTPError):
        registry.refresh(url)

    # Re-read models, initial should still be there
    models = registry.get_all_models()
    assert any(m.provider == "initial_prov" for m in models)
    assert cache_file.exists()
    assert json.loads(cache_file.read_text()) == initial_data
