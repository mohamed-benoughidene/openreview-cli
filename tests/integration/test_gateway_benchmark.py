import timeit
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openreview_cli.gateway.engine import GatewayEngine


@pytest.fixture
def temp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    return config_dir


def test_routing_overhead_benchmark(temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = temp_config_dir / "openreview" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_content = """version: 1
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
    per_review_cents: 5000
    daily_cents: 50000
  fallback:
    retries: 0
    timeout: 30
    on_failure: error
"""
    config_path.write_text(config_content)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-openai")

    with patch("litellm.completion") as mock_completion:
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Benchmark reply"
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 10
        mock_resp.usage.completion_tokens = 10
        mock_resp.usage.total_tokens = 20
        mock_completion.return_value = mock_resp

        engine = GatewayEngine()
        engine.route_request(slot="reasoning", messages=[{"role": "user", "content": "warmup"}])

        import litellm

        direct = min(
            timeit.repeat(
                'litellm.completion(model="openai/gpt-4o", messages=[{"role": "user", "content": "ping"}], api_key="test-key-openai")',
                globals={"litellm": litellm},
                number=50,
                repeat=5,
            )
        )

        wrapped = min(
            timeit.repeat(
                "engine.route_request(slot='reasoning', messages=[{'role': 'user', 'content': 'ping'}])",
                globals={"engine": engine},
                number=50,
                repeat=5,
            )
        )

        per_call_overhead = ((wrapped - direct) / 50) * 1000
        print(f"\nPer-call Gateway Overhead: {per_call_overhead:.3f} ms")

        assert per_call_overhead < 75.0, f"Gateway overhead too high: {per_call_overhead:.3f} ms"
