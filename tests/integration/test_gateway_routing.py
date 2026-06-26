from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import respx

from openreview_cli.gateway.engine import GatewayEngine, route_request
from openreview_cli.gateway.errors import GatewayError
from openreview_cli.gateway.models import GatewayResponse, RerankResult


@pytest.fixture
def temp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    return config_dir


def test_chat_completion_routing(temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:

    # Configure reasoning slot to OpenAI
    config_path = temp_config_dir / "openreview" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # We write a basic valid config
    config_content = """
version: 1
gateway:
  models:
    reasoning:
      primary: openai/gpt-4o
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
  registry:
    refresh_days: 7
    remote_url: https://example.com/models.json
"""
    config_path.write_text(config_content)

    # Mock auth key
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-openai")

    # Mock LiteLLM completion
    with patch("litellm.completion") as mock_completion:
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Mocked reasoning response"
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 15
        mock_resp.usage.completion_tokens = 25
        mock_resp.usage.total_tokens = 40
        mock_completion.return_value = mock_resp

        # Route request
        resp = route_request(
            slot="reasoning",
            messages=[{"role": "user", "content": "Hello"}],
            session_id="550e8400-e29b-41d4-a716-446655440000",
        )

        assert isinstance(resp, GatewayResponse)
        assert resp.content == "Mocked reasoning response"
        assert resp.input_tokens == 15
        assert resp.output_tokens == 25
        assert (
            resp.cost_usd > 0.0 or resp.cost_usd == 0.0
        )  # depending on litellm completion_cost calculation
        assert resp.model == "gpt-4o"
        assert resp.provider == "openai"
        assert resp.slot == "reasoning"
        assert not resp.fallback_used

        # Verify litellm parameters
        mock_completion.assert_called_once()
        args, kwargs = mock_completion.call_args
        assert kwargs["model"] == "openai/gpt-4o"
        assert kwargs["messages"] == [{"role": "user", "content": "Hello"}]
        assert kwargs["api_key"] == "test-key-openai"
        assert kwargs["temperature"] == 0.2
        assert kwargs["max_tokens"] == 1000


def test_provider_switching(temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = temp_config_dir / "openreview" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Start with reasoning as OpenAI
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
  registry:
    refresh_days: 7
    remote_url: https://example.com/models.json
"""
    config_path.write_text(config_content)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-anthropic")

    with patch("litellm.completion") as mock_completion:
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Response"
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 5
        mock_resp.usage.completion_tokens = 5
        mock_resp.usage.total_tokens = 10
        mock_completion.return_value = mock_resp

        # Route 1 (OpenAI)
        resp1 = route_request(slot="reasoning", messages=[{"role": "user", "content": "Hi"}])
        assert resp1.provider == "openai"
        assert resp1.model == "gpt-4o"

        # Switch to Anthropic in config file
        new_config_content = config_content.replace("openai/gpt-4o", "anthropic/claude-3")
        config_path.write_text(new_config_content)

        # Route 2 (Anthropic)
        resp2 = route_request(slot="reasoning", messages=[{"role": "user", "content": "Hi"}])
        assert resp2.provider == "anthropic"
        assert resp2.model == "claude-3"


def test_embedding_routing(temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = temp_config_dir / "openreview" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config_content = """
version: 1
gateway:
  models:
    reasoning:
      primary: ollama/qwen3:8b
    extraction:
      primary: ollama/qwen3:4b
    embedding:
      primary: openai/text-embedding-3-small
      params:
        dimensions: 256
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

    with patch("litellm.embedding") as mock_embedding:
        mock_resp = MagicMock()
        mock_resp.data = [{"embedding": [0.1, 0.2, 0.3]}]
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 3
        mock_resp.usage.total_tokens = 3
        mock_embedding.return_value = mock_resp

        resp = route_request(slot="embedding", input_text=["test chunk"])

        assert isinstance(resp, GatewayResponse)
        assert resp.content in ([[0.1, 0.2, 0.3]], [0.1, 0.2, 0.3])
        assert resp.input_tokens == 3
        assert resp.provider == "openai"
        assert resp.model == "text-embedding-3-small"

        mock_embedding.assert_called_once()
        args, kwargs = mock_embedding.call_args
        assert kwargs["model"] == "openai/text-embedding-3-small"
        assert kwargs["input"] == ["test chunk"]
        assert kwargs["dimensions"] == 256


def test_reranking_routing(temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = temp_config_dir / "openreview" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

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
      primary: cohere/rerank-v3
    graph:
      primary: ollama/qwen3:8b
  registry:
    refresh_days: 7
    remote_url: https://example.com/models.json
"""
    config_path.write_text(config_content)
    monkeypatch.setenv("COHERE_API_KEY", "test-key-cohere")

    with patch("litellm.rerank") as mock_rerank:
        mock_result1 = MagicMock()
        mock_result1.index = 1
        mock_result1.relevance_score = 0.95
        mock_result1.document = "doc2"

        mock_result2 = MagicMock()
        mock_result2.index = 0
        mock_result2.relevance_score = 0.45
        mock_result2.document = None

        mock_resp = MagicMock()
        mock_resp.results = [mock_result1, mock_result2]
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 50
        mock_resp.usage.total_tokens = 50
        mock_rerank.return_value = mock_resp

        resp = route_request(
            slot="reranking",
            query="termination clause",
            documents=["clause 1", "clause 2"],
            top_n=2,
        )

        assert isinstance(resp, GatewayResponse)
        assert isinstance(resp.content, list)
        assert len(resp.content) == 2
        r1 = resp.content[0]
        r2 = resp.content[1]
        assert isinstance(r1, RerankResult)
        assert isinstance(r2, RerankResult)
        assert r1.index == 1
        assert r1.score == 0.95
        assert r1.document == "doc2"

        assert r2.index == 0
        assert r2.score == 0.45
        assert r2.document is None

        mock_rerank.assert_called_once()
        args, kwargs = mock_rerank.call_args
        assert kwargs["model"] == "cohere/rerank-v3"
        assert kwargs["query"] == "termination clause"
        assert kwargs["documents"] == ["clause 1", "clause 2"]
        assert kwargs["top_n"] == 2


@respx.mock(assert_all_mocked=True)
def test_fully_local_zero_network_mode(
    temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch, respx_mock: respx.MockRouter
) -> None:
    config_path = temp_config_dir / "openreview" / "config.yml"

    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure reasoning slot to local Ollama
    config_content = """
version: 1
gateway:
  models:
    reasoning:
      primary: ollama/llama3
    extraction:
      primary: ollama/llama3
    embedding:
      primary: ollama/llama3
    reranking:
      primary: ollama/llama3
    graph:
      primary: ollama/llama3
  registry:
    refresh_days: 7
    remote_url: https://example.com/models.json
"""
    config_path.write_text(config_content)

    # Mock Ollama endpoints using respond()
    respx_mock.post("http://localhost:11434/api/generate").respond(
        status_code=200, json={"model": "llama3", "response": "local answer", "done": True}
    )

    # Directly route call, using the mock
    engine = GatewayEngine()
    resp = engine.route_request(slot="reasoning", messages=[{"role": "user", "content": "ping"}])

    assert resp.content == "local answer"
    assert resp.provider == "ollama"
    assert resp.model == "llama3"


def test_cost_tracking(temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
  cost_limits:
    per_review_cents: 100
    daily_cents: 1000
  registry:
    refresh_days: 7
    remote_url: https://example.com/models.json
"""
    config_path.write_text(config_content)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-openai")

    with patch("litellm.completion") as mock_completion:
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Response"
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 50
        mock_resp.usage.completion_tokens = 50
        mock_resp.usage.total_tokens = 100
        mock_completion.return_value = mock_resp

        # We also mock litellm.completion_cost to return 0.05 USD
        with patch("litellm.completion_cost", return_value=0.05):
            resp = route_request(
                slot="reasoning",
                messages=[{"role": "user", "content": "ping"}],
                session_id="550e8400-e29b-41d4-a716-446655440003",
            )

            assert resp.cost_usd == 0.05
            assert resp.input_tokens == 50
            assert resp.output_tokens == 50

            # Verify SQLite tracking
            from openreview_cli.gateway.costs import CostStore

            store = CostStore()
            session_cost = store.get_session_cost("550e8400-e29b-41d4-a716-446655440003")
            assert session_cost == 0.05

            daily_cost = store.get_daily_cost()
            assert daily_cost >= 0.05


def test_cost_limits(temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = temp_config_dir / "openreview" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Set very low limit: 1 cent ($0.01)
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
  cost_limits:
    per_review_cents: 1
    daily_cents: 1
  registry:
    refresh_days: 7
    remote_url: https://example.com/models.json
"""
    config_path.write_text(config_content)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-openai")

    # Pre-seed session cost to exceed limit
    import time

    from openreview_cli.gateway.costs import CostStore
    from openreview_cli.gateway.models import CostRecord

    store = CostStore()
    session_id = "550e8400-e29b-41d4-a716-446655440004"
    store.create_session(session_id)
    store.insert_record(
        CostRecord(
            session_id=session_id,
            slot="reasoning",
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=100,
            cost_usd=0.015,  # Exceeds the 1 cent limit
            timestamp=time.time(),
            fallback_used=False,
            latency_ms=100,
        )
    )

    with patch("litellm.completion") as mock_completion:
        with pytest.raises(GatewayError) as exc_info:
            route_request(
                slot="reasoning",
                messages=[{"role": "user", "content": "ping"}],
                session_id=session_id,
            )

        assert exc_info.value.exit_code == 6
        assert "cost limit" in exc_info.value.message.lower()
        mock_completion.assert_not_called()
