from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from openreview_cli.gateway.errors import AllProvidersFailedError, SlotNotConfiguredError
from openreview_cli.gateway.router import Gateway


class _MockMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _MockChoice:
    def __init__(self, content: str) -> None:
        self.message = _MockMessage(content)


class _MockCompletionResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_MockChoice(content)]


class _MockEmbeddingResponse:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _MockRerankResponse:
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results


def _gateway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config_text: str, auth_text: str | None = None
) -> Gateway:
    import uuid

    import openreview_cli.gateway.cost as cost_mod

    monkeypatch.setattr(cost_mod, "db_log_cost", lambda *a, **kw: str(uuid.uuid4()))
    monkeypatch.setattr(
        cost_mod,
        "db_get_session_cost",
        lambda *a, **kw: {"prompt_tokens": 0, "completion_tokens": 0, "cost_cents": 0},
    )
    monkeypatch.setattr(cost_mod, "completion_cost", lambda r: 0.0)
    config_path = tmp_path / "config.yml"
    config_path.write_text(config_text)
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(auth_text or json.dumps({"openai": "sk-test", "anthropic": "sk-ant-test"}))
    return Gateway(config_path, auth_path, tmp_path / "data.db")


COMMON_CONFIG = """\
gateway:
  models:
    reasoning:
      primary: openai/gpt-4
      fallback: anthropic/claude-3
      params:
        temperature: 0.7
        max_tokens: 2048
      extra_params:
        top_p: 0.9
    extraction:
      primary: openai/gpt-4o
    embedding:
      primary: openai/text-embedding-3-small
    reranking:
      primary: cohere/rerank-english-v3.0
  fallback:
    retries: 2
    retry_delay: 0.01
    timeout: 5
"""


class TestChat:
    def test_returns_response_text(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import openreview_cli.gateway.router as router_mod

        monkeypatch.setattr(
            router_mod, "completion", lambda **kw: _MockCompletionResponse("Hello!")
        )
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        result = gw.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert result == "Hello!"

    def test_raises_slot_not_configured_for_invalid_slot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        with pytest.raises(SlotNotConfiguredError, match="Invalid slot"):
            gw.chat("nonexistent", [{"role": "user", "content": "Hi"}])

    def test_raises_slot_not_configured_when_no_primary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = """\
gateway:
  models:
    reasoning:
      primary: ""
  fallback:
    retries: 1
    retry_delay: 0.01
    timeout: 5
"""
        gw = _gateway(tmp_path, monkeypatch, config)
        with pytest.raises(SlotNotConfiguredError, match="no primary model"):
            gw.chat("reasoning", [{"role": "user", "content": "Hi"}])

    def test_falls_back_to_fallback_model(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import openreview_cli.gateway.router as router_mod

        call_log: list[str] = []

        def failing_then_ok(**kw: Any) -> _MockCompletionResponse:
            call_log.append(kw["model"])
            if len(call_log) <= 3:
                msg = "primary failed"
                raise RuntimeError(msg)
            return _MockCompletionResponse("from fallback")

        monkeypatch.setattr(router_mod, "completion", failing_then_ok)
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        result = gw.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert result == "from fallback"
        assert call_log[-1] == "anthropic/claude-3"

    def test_raises_all_providers_failed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import openreview_cli.gateway.router as router_mod

        def always_fail(**kw: Any) -> Any:
            raise RuntimeError("always fails")

        monkeypatch.setattr(router_mod, "completion", always_fail)
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        with pytest.raises(AllProvidersFailedError):
            gw.chat("reasoning", [{"role": "user", "content": "Hi"}])


class TestEmbed:
    def test_returns_vectors(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import openreview_cli.gateway.router as router_mod

        monkeypatch.setattr(
            router_mod,
            "embedding",
            lambda **kw: _MockEmbeddingResponse(
                [{"embedding": [0.1, 0.2, 0.3]}, {"embedding": [0.4, 0.5, 0.6]}]
            ),
        )
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        result = gw.embed("embedding", ["hello", "world"])
        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


class TestRerank:
    def test_returns_ranked_results(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import litellm

        monkeypatch.setattr(
            litellm,
            "rerank",
            lambda **kw: _MockRerankResponse(
                [{"index": 1, "relevance_score": 0.95}, {"index": 0, "relevance_score": 0.85}]
            ),
        )
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        result = gw.rerank("reranking", "test query", ["doc a", "doc b"])
        assert result == [
            {"index": 1, "relevance_score": 0.95},
            {"index": 0, "relevance_score": 0.85},
        ]


class TestHealthCheck:
    def test_returns_status_per_slot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config = """\
gateway:
  models:
    reasoning:
      primary: openai/gpt-4
"""
        gw = _gateway(tmp_path, monkeypatch, config, "{}")
        result = gw.health_check()
        for slot in ("reasoning", "extraction", "embedding", "reranking", "graph"):
            assert slot in result
            assert "status" in result[slot]
        assert result["reasoning"]["status"] == "missing_api_key"


class TestGetLitellmKwargs:
    def test_returns_correct_kwargs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert kwargs["model"] == "openai/gpt-4"
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 2048
        assert kwargs["top_p"] == 0.9
