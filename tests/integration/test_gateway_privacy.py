from pathlib import Path

import pytest
import respx

from openreview_cli.gateway.engine import route_request


@pytest.fixture
def temp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    return config_dir


@respx.mock(assert_all_mocked=True)
def test_network_isolation_custom_endpoints(
    temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch, respx_mock: respx.MockRouter
) -> None:
    # 1. Configure slots to use custom providers or custom API bases
    config_path = temp_config_dir / "openreview" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_content = """
version: 1
gateway:
  models:
    reasoning:
      primary: openai/gpt-4o
    extraction:
      primary: anthropic/claude-3
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

    # Set custom API bases and keys
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    monkeypatch.setenv("OPENAI_API_BASE", "https://custom-openai.internal/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("ANTHROPIC_API_BASE", "https://custom-anthropic.internal")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")

    # 2. Mock only the custom URLs using respx
    openai_route = respx_mock.post("https://custom-openai.internal/v1/chat/completions").respond(
        status_code=200,
        json={
            "choices": [{"message": {"content": "custom openai response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        },
    )

    anthropic_route = respx_mock.post("https://custom-anthropic.internal/v1/messages").respond(
        status_code=200,
        json={
            "content": [{"type": "text", "text": "custom anthropic response"}],
            "id": "msg_123",
            "role": "assistant",
            "model": "claude-3",
            "usage": {"input_tokens": 10, "output_tokens": 10},
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "type": "message",
        },
    )

    # 3. Route requests through gateway
    # Reasoning -> OpenAI
    resp_reasoning = route_request(
        slot="reasoning",
        messages=[{"role": "user", "content": "ping"}],
    )
    assert resp_reasoning.content == "custom openai response"

    # Extraction -> Anthropic
    resp_extraction = route_request(
        slot="extraction",
        messages=[{"role": "user", "content": "ping"}],
    )
    assert resp_extraction.content == "custom anthropic response"

    # Verify that the correct API endpoints were called
    assert openai_route.called
    assert anthropic_route.called

    # Since respx is in assert_all_mocked=True mode, any other HTTP requests
    # would have caused a respx.MockError and failed the test.
    # Therefore, we confirm 100% network isolation to configured URLs.
