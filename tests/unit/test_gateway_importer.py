import json
from pathlib import Path

import pytest

from openreview_cli.gateway.importer import import_config, validate_import_config


def test_validate_import_config_valid() -> None:
    valid_data = {
        "reasoning": {
            "provider": "openai",
            "model": "gpt-4o",
            "fallback": "anthropic/claude-3-5-sonnet-20241022",
            "params": {"temperature": 0.1},
        },
        "extraction": {"provider": "openai", "model": "gpt-4o-mini"},
        "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
        "reranking": {"provider": "cohere", "model": "rerank-3.5"},
        "graph": {"provider": "ollama", "model": "qwen3:8b"},
        "api_key_env": {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"},
    }
    errors = validate_import_config(valid_data)
    assert len(errors) == 0


def test_validate_import_config_missing_slots() -> None:
    # missing extraction and graph
    invalid_data = {
        "reasoning": {"provider": "openai", "model": "gpt-4o"},
        "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
        "reranking": {"provider": "cohere", "model": "rerank-3.5"},
    }
    errors = validate_import_config(invalid_data)
    assert len(errors) > 0
    err_str = "".join(errors).lower()
    assert "extraction" in err_str
    assert "graph" in err_str


def test_validate_import_config_bad_providers() -> None:
    invalid_data = {
        "reasoning": {"provider": "invalid-prov", "model": "gpt-4o"},
        "extraction": {"provider": "openai", "model": "gpt-4o-mini"},
        "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
        "reranking": {"provider": "cohere", "model": "rerank-3.5"},
        "graph": {"provider": "ollama", "model": "qwen3:8b"},
    }
    errors = validate_import_config(invalid_data)
    assert len(errors) > 0
    assert any("unrecognized provider" in err.lower() for err in errors)


def test_validate_import_config_invalid_env_vars() -> None:
    invalid_data = {
        "reasoning": {"provider": "openai", "model": "gpt-4o"},
        "extraction": {"provider": "openai", "model": "gpt-4o-mini"},
        "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
        "reranking": {"provider": "cohere", "model": "rerank-3.5"},
        "graph": {"provider": "ollama", "model": "qwen3:8b"},
        "api_key_env": {
            "openai": "sk-123456789",  # Inline key
            "anthropic": "INVALID ENV VAR!",  # spaces/chars
        },
    }
    errors = validate_import_config(invalid_data)
    assert len(errors) > 0
    err_str = "".join(errors).lower()
    assert "inline api key" in err_str or "invalid environment variable name" in err_str


def test_import_config_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_OPENAI_KEY", "env-secret-openai")
    monkeypatch.setenv("TEST_ANTHROPIC_KEY", "env-secret-anthropic")

    import_data = {
        "reasoning": {"provider": "openai", "model": "gpt-4o"},
        "extraction": {"provider": "openai", "model": "gpt-4o-mini"},
        "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
        "reranking": {"provider": "cohere", "model": "rerank-3.5"},
        "graph": {"provider": "ollama", "model": "qwen3:8b"},
        "api_key_env": {"openai": "TEST_OPENAI_KEY", "anthropic": "TEST_ANTHROPIC_KEY"},
    }

    summary = import_config(import_data, tmp_path)
    assert summary["reasoning"] == "openai/gpt-4o"
    assert summary["embedding"] == "ollama/nomic-embed-text"

    # Verify config.yml
    config_file = tmp_path / "config.yml"
    assert config_file.exists()
    import yaml

    config = yaml.safe_load(config_file.read_text())
    assert config["gateway"]["models"]["reasoning"]["primary"] == "openai/gpt-4o"

    # Verify auth.json
    auth_file = tmp_path / "auth.json"
    assert auth_file.exists()
    auth = json.loads(auth_file.read_text())
    assert auth["openai"] == "env-secret-openai"
    assert auth["anthropic"] == "env-secret-anthropic"


def test_import_config_missing_env_var(tmp_path: Path) -> None:
    import_data = {
        "reasoning": {"provider": "openai", "model": "gpt-4o"},
        "extraction": {"provider": "openai", "model": "gpt-4o-mini"},
        "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
        "reranking": {"provider": "cohere", "model": "rerank-3.5"},
        "graph": {"provider": "ollama", "model": "qwen3:8b"},
        "api_key_env": {"openai": "NON_EXISTENT_VAR_12345"},
    }

    with pytest.raises(ValueError) as exc:
        import_config(import_data, tmp_path)
    assert "NON_EXISTENT_VAR_12345" in str(exc.value)
