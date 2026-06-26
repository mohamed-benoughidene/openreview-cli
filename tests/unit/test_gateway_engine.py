from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openreview_cli.gateway.engine import GatewayEngine, get_litellm_model_string
from openreview_cli.gateway.errors import GatewayError


@pytest.fixture
def temp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    return config_dir


def test_error_on_unconfigured_slot(temp_config_dir: Path) -> None:
    config_path = temp_config_dir / "openreview" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write config with a missing/unconfigured slot. Wait, loader.py validates that all 5 slot keys are present in models.
    # But what if a slot model primary string is empty or invalid/unconfigured?
    # Actually, SlotConfig primary must be non-empty. So if we have a config where a slot has no valid setup, or if we request
    # a slot name not in models.
    # Wait, let's look at what loader.py does: it requires all 5 slots to be in config.yml.
    # But what if they are configured as an empty/none or unconfigured/placeholder?
    # Or what if we query a slot that does not exist in the models dict?
    config_content = """
version: 1
gateway:
  models:
    reasoning:
      primary: ollama/qwen3:8b
    extraction:
      primary: ollama/qwen3:4b
    embedding:
      primary: ollama/nomic-embed-text
    reranking:
      primary: ollama/qwen3-reranker-0.6b
    graph:
      primary: ollama/qwen3:8b
  registry:
    refresh_days: 7
    remote_url: https://example.com/models.json
"""
    config_path.write_text(config_content)

    engine = GatewayEngine()
    with pytest.raises(GatewayError) as exc_info:
        engine.route_request(slot="nonexistent_slot", messages=[])

    assert exc_info.value.exit_code == 7
    assert "nonexistent_slot" in exc_info.value.message


def test_parameter_injection_and_merge(
    temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = temp_config_dir / "openreview" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config_content = """
version: 1
gateway:
  models:
    reasoning:
      primary: openai/gpt-4o
      params:
        temperature: 0.2
        max_tokens: 1000
        top_p: 0.95
        stop: ["stop_sequence"]
    extraction:
      primary: ollama/qwen3:4b
    embedding:
      primary: ollama/nomic-embed-text
    reranking:
      primary: ollama/qwen3-reranker-0.6b
    graph:
      primary: ollama/qwen3:8b
  registry:
    refresh_days: 7
    remote_url: https://example.com/models.json
"""
    config_path.write_text(config_content)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-openai")

    engine = GatewayEngine()

    with patch("litellm.completion") as mock_completion:
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Response"
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 5
        mock_resp.usage.completion_tokens = 5
        mock_resp.usage.total_tokens = 10
        mock_completion.return_value = mock_resp

        # Override temperature and max_tokens via kwargs
        engine.route_request(
            slot="reasoning",
            messages=[{"role": "user", "content": "Hi"}],
            temperature=0.5,
            max_tokens=2000,
            extra_param="custom_value",
        )

        mock_completion.assert_called_once()
        args, kwargs = mock_completion.call_args
        # kwargs should contain overridden temperature, max_tokens, and original top_p/stop, and extra_param
        assert kwargs["temperature"] == 0.5
        assert kwargs["max_tokens"] == 2000
        assert kwargs["top_p"] == 0.95
        assert kwargs["stop"] == ["stop_sequence"]
        assert kwargs["extra_param"] == "custom_value"


ALL_PROVIDERS = [
    ("openai", "gpt-4o"),
    ("anthropic", "claude-3-5-sonnet-latest"),
    ("google", "gemini-1.5-pro"),
    ("ollama", "llama3.1:8b"),
    ("openrouter", "openai/gpt-4o-mini"),
    ("cohere", "command-r-plus"),
    ("huggingface", "HuggingFaceH4/zephyr-7b-beta"),
    ("custom", "my-model"),
]


@pytest.mark.parametrize("provider,model_id", ALL_PROVIDERS)
def test_get_litellm_model_string_for_all_providers(provider: str, model_id: str) -> None:
    result = get_litellm_model_string(provider, model_id)
    assert "/" in result


@pytest.mark.parametrize("provider", [p[0] for p in ALL_PROVIDERS])
def test_provider_resolves_api_key_from_env(provider: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from openreview_cli.config.auth import get_api_key, key_to_env

    monkeypatch.setenv(key_to_env(provider), f"test-key-{provider}")
    assert get_api_key(provider) == f"test-key-{provider}"


@pytest.mark.parametrize("provider,model_id", ALL_PROVIDERS)
def test_provider_engine_constructs_litellm_kwargs_correctly(
    provider: str, model_id: str, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = temp_config_dir / "openreview" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        f"""version: 1
gateway:
  models:
    reasoning:
      primary: {provider}/{model_id}
    extraction:
      primary: ollama/qwen3:4b
    embedding:
      primary: ollama/nomic-embed-text
    reranking:
      primary: ollama/qwen3-reranker-0.6b
    graph:
      primary: ollama/qwen3:8b
  fallback:
    retries: 0
    timeout: 30
    on_failure: error
  cost_limits:
    per_review_cents: 500
    daily_cents: 5000
"""
    )

    from openreview_cli.config.auth import key_to_env

    monkeypatch.setenv(key_to_env(provider), f"test-key-{provider}")
    engine = GatewayEngine()

    with patch("litellm.completion") as mock_completion:
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "ok"
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 5
        mock_resp.usage.completion_tokens = 5
        mock_resp.usage.total_tokens = 10
        mock_completion.return_value = mock_resp

        resp = engine.route_request(slot="reasoning", messages=[{"role": "user", "content": "Hi"}])
        assert resp.content == "ok"
        assert resp.provider == provider
        assert resp.model == model_id
        mock_completion.assert_called_once()
        _, call_kwargs = mock_completion.call_args
        if provider != "ollama":
            assert call_kwargs.get("api_key") == f"test-key-{provider}"
