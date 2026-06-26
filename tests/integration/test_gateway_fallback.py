from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openreview_cli.gateway.engine import route_request
from openreview_cli.gateway.errors import GatewayError
from openreview_cli.gateway.models import GatewayResponse


@pytest.fixture
def temp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    return config_dir


def test_fallback_success(temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Setup config with a primary and fallback model
    config_path = temp_config_dir / "openreview" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config_content = """
version: 1
gateway:
  models:
    reasoning:
      primary: openai/gpt-4o
      fallback: anthropic/claude-3
      params:
        temperature: 0.2
        max_tokens: 1000
    extraction:
      primary: ollama/qwen3:4b
    embedding:
      primary: ollama/nomic-embed-text
    reranking:
      primary: ollama/qwen3-reranker-0.6b
    graph:
      primary: ollama/qwen3:8b
  fallback:
    retries: 1
    retry_delay: 0.001
    timeout: 30
    on_failure: error
  registry:
    refresh_days: 7
    remote_url: https://example.com/models.json
"""
    config_path.write_text(config_content)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-anthropic")

    # Mock completion call
    with patch("litellm.completion") as mock_completion:
        # Create a mock response for successful fallback call
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Fallback reasoning response"
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 20
        mock_resp.usage.completion_tokens = 30
        mock_resp.usage.total_tokens = 50

        # Primary fails (2 times: 1st try + 1 retry = 2 attempts), then fallback succeeds
        mock_completion.side_effect = [
            Exception("OpenAI Timeout"),
            Exception("OpenAI Timeout"),
            mock_resp,
        ]

        resp = route_request(slot="reasoning", messages=[{"role": "user", "content": "Hello"}])

        assert isinstance(resp, GatewayResponse)
        assert resp.content == "Fallback reasoning response"
        assert resp.model == "claude-3"
        assert resp.provider == "anthropic"
        assert resp.fallback_used is True
        assert mock_completion.call_count == 3


def test_retry_success(temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = temp_config_dir / "openreview" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config_content = """
version: 1
gateway:
  models:
    reasoning:
      primary: openai/gpt-4o
    extraction:
      primary: ollama/qwen3:4b
    embedding:
      primary: ollama/nomic-embed-text
    reranking:
      primary: ollama/qwen3-reranker-0.6b
    graph:
      primary: ollama/qwen3:8b
  fallback:
    retries: 2
    retry_delay: 0.001
    timeout: 30
    on_failure: error
  registry:
    refresh_days: 7
    remote_url: https://example.com/models.json
"""
    config_path.write_text(config_content)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-openai")

    with patch("litellm.completion") as mock_completion:
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Primary reasoning response"
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 10
        mock_resp.usage.completion_tokens = 10

        # 1st try fails, 2nd try (1st retry) succeeds
        mock_completion.side_effect = [Exception("Temporary OpenAI Rate Limit"), mock_resp]

        resp = route_request(slot="reasoning", messages=[{"role": "user", "content": "Hello"}])

        assert isinstance(resp, GatewayResponse)
        assert resp.content == "Primary reasoning response"
        assert resp.model == "gpt-4o"
        assert resp.fallback_used is False
        assert mock_completion.call_count == 2


def test_on_failure_modes(temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = temp_config_dir / "openreview" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    base_config = """
version: 1
gateway:
  models:
    reasoning:
      primary: openai/gpt-4o
    extraction:
      primary: ollama/qwen3:4b
    embedding:
      primary: ollama/nomic-embed-text
    reranking:
      primary: ollama/qwen3-reranker-0.6b
    graph:
      primary: ollama/qwen3:8b
  fallback:
    retries: 1
    retry_delay: 0.001
    timeout: 30
    on_failure: {on_failure}
  registry:
    refresh_days: 7
    remote_url: https://example.com/models.json
"""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-openai")

    # 1. Error Mode
    config_path.write_text(base_config.format(on_failure="error"))
    with patch("litellm.completion") as mock_completion:
        mock_completion.side_effect = Exception("Permanent Fail")

        with pytest.raises(GatewayError) as exc_info:
            route_request(slot="reasoning", messages=[{"role": "user", "content": "Hello"}])
        assert exc_info.value.exit_code == 7
        assert "Permanent Fail" in exc_info.value.message

    # 2. Skip Mode
    config_path.write_text(base_config.format(on_failure="skip"))
    with patch("litellm.completion") as mock_completion:
        mock_completion.side_effect = Exception("Permanent Fail")

        resp = route_request(slot="reasoning", messages=[{"role": "user", "content": "Hello"}])
        assert isinstance(resp, GatewayResponse)
        assert resp.content is None
        assert resp.model == "gpt-4o"
        assert resp.provider == "openai"

    # 3. Warn Mode
    config_path.write_text(base_config.format(on_failure="warn"))
    with patch("litellm.completion") as mock_completion:
        mock_completion.side_effect = Exception("Permanent Fail")

        with pytest.warns(UserWarning) as record:
            resp = route_request(slot="reasoning", messages=[{"role": "user", "content": "Hello"}])

        assert len(record) == 1
        assert "Slot 'reasoning' failed" in str(record[0].message)
        assert isinstance(resp, GatewayResponse)
        assert resp.content is None
        assert resp.model == "gpt-4o"
        assert resp.provider == "openai"
