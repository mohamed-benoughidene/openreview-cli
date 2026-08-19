"""D-10: privacy tier enforced at the real Gateway dispatch boundary.

These tests exercise the REAL ``Gateway`` class (not ``TierRouter``) and
prove that ``maximum``/``balanced`` tier rules block cloud calls *before*
any litellm dispatch, while ``performance`` and local providers pass through.

The dispatch path is patched to raise ``AssertionError`` if reached, so a
green test also proves the network call never happened.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from openreview_cli.gateway.errors import NoMatchingProviderError, PIIUnavailableError
from openreview_cli.gateway.models import ProviderInfo
from openreview_cli.gateway.router import Gateway


@pytest.fixture(autouse=True)
def _reset_pii_flag_after() -> Generator[None, None, None]:
    """Reset the process-global PII flag between tests (test isolation)."""
    yield
    from openreview_cli.gateway.router import reset_pii_available

    reset_pii_available()


def _config(tier: str, slot: str, primary: str) -> dict[str, Any]:
    return {
        "privacy": {"tier": tier},
        "gateway": {"models": {slot: {"primary": primary}}},
    }


def _cloud_info(name: str = "openai") -> ProviderInfo:
    return ProviderInfo(name=name, base_url="https://api.openai.com/v1", is_local=False)


def _local_info(name: str = "ollama") -> ProviderInfo:
    return ProviderInfo(name=name, base_url="http://localhost:11434/v1", is_local=True)


def _make_gateway(
    monkeypatch: pytest.MonkeyPatch, config: dict[str, Any], tmp_path: Path
) -> Gateway:
    """Construct a real Gateway via __init__, stubbing only the slow/dangerous bits."""
    import openreview_cli.gateway.router as router_mod

    monkeypatch.setattr(router_mod, "load_config", lambda path: config)
    monkeypatch.setattr(router_mod, "load_auth", lambda path: {})
    monkeypatch.setattr(router_mod, "CostTracker", lambda path: MagicMock())
    monkeypatch.setattr(
        "openreview_cli.prompts.store.PromptStore", MagicMock(resolve=lambda slot: None)
    )
    return Gateway(tmp_path / "config.yml", tmp_path / "auth.json", tmp_path / "data.db")


def _assert_dispatch_not_reached(*args: Any, **kw: Any) -> Any:
    raise AssertionError("dispatch reached — tier enforcement did not block the call")


def _chat_response(content: str = "ok") -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class TestMaximumTierEnforcement:
    def test_cloud_chat_raises_and_does_not_dispatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gw = _make_gateway(monkeypatch, _config("maximum", "reasoning", "openai/gpt-4"), tmp_path)
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _cloud_info())
        monkeypatch.setattr(gw, "_call_with_fallback", _assert_dispatch_not_reached)

        with pytest.raises(NoMatchingProviderError) as exc_info:
            gw.chat("reasoning", [{"role": "user", "content": "hi"}])

        assert "MAXIMUM" in str(exc_info.value)
        assert "local provider" in str(exc_info.value)

    def test_cloud_embed_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        gw = _make_gateway(
            monkeypatch, _config("maximum", "embedding", "openai/text-embedding-3-small"), tmp_path
        )
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _cloud_info())
        monkeypatch.setattr(gw, "_call_with_fallback", _assert_dispatch_not_reached)

        with pytest.raises(NoMatchingProviderError) as exc_info:
            gw.embed("embedding", ["hello"])

        assert "MAXIMUM" in str(exc_info.value)

    def test_cloud_rerank_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import litellm

        gw = _make_gateway(
            monkeypatch, _config("maximum", "reranking", "cohere/rerank-english-v3.0"), tmp_path
        )
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _cloud_info(name="cohere"))
        monkeypatch.setattr(litellm, "rerank", _assert_dispatch_not_reached)

        with pytest.raises(NoMatchingProviderError) as exc_info:
            gw.rerank("reranking", "query", ["doc a"])

        assert "MAXIMUM" in str(exc_info.value)

    def test_local_embed_proceeds(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        gw = _make_gateway(
            monkeypatch, _config("maximum", "embedding", "ollama/nomic-embed-text"), tmp_path
        )
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _local_info())
        monkeypatch.setattr(
            gw, "_get_litellm_kwargs", lambda slot: {"model": "ollama/nomic-embed-text"}
        )

        def _fake_fallback(slot: str, call_fn: Any, call_kwargs: dict[str, Any]) -> Any:
            return SimpleNamespace(data=[{"embedding": [0.1, 0.2]}])

        monkeypatch.setattr(gw, "_call_with_fallback", _fake_fallback)
        monkeypatch.setattr(
            "openreview_cli.prompts.store.PromptStore", MagicMock(resolve=lambda slot: None)
        )

        result = gw.embed("embedding", ["hello"])

        assert result == [[0.1, 0.2]]


class TestBalancedTierEnforcement:
    def test_cloud_embed_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        gw = _make_gateway(
            monkeypatch, _config("balanced", "embedding", "openai/text-embedding-3-small"), tmp_path
        )
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _cloud_info())
        monkeypatch.setattr(gw, "_call_with_fallback", _assert_dispatch_not_reached)

        with pytest.raises(NoMatchingProviderError) as exc_info:
            gw.embed("embedding", ["hello"])

        assert "BALANCED" in str(exc_info.value)

    def test_cloud_llm_allowed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from openreview_cli.gateway.router import mark_pii_available

        mark_pii_available()
        gw = _make_gateway(monkeypatch, _config("balanced", "reasoning", "openai/gpt-4"), tmp_path)
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _cloud_info())
        monkeypatch.setattr(gw, "_get_litellm_kwargs", lambda slot: {"model": "openai/gpt-4"})
        monkeypatch.setattr(gw, "_call_with_fallback", lambda *a, **k: _chat_response("ok"))
        monkeypatch.setattr(
            "openreview_cli.prompts.store.PromptStore", MagicMock(resolve=lambda slot: None)
        )

        result = gw.chat("reasoning", [{"role": "user", "content": "hi"}])

        assert result == "ok"


class TestPerformanceTierEnforcement:
    def test_cloud_embed_allowed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from openreview_cli.gateway.router import mark_pii_available

        mark_pii_available()
        gw = _make_gateway(
            monkeypatch,
            _config("performance", "embedding", "openai/text-embedding-3-small"),
            tmp_path,
        )
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _cloud_info())
        monkeypatch.setattr(
            gw, "_get_litellm_kwargs", lambda slot: {"model": "openai/text-embedding-3-small"}
        )

        def _fake_fallback(slot: str, call_fn: Any, call_kwargs: dict[str, Any]) -> Any:
            return SimpleNamespace(data=[{"embedding": [0.1, 0.2]}])

        monkeypatch.setattr(gw, "_call_with_fallback", _fake_fallback)
        monkeypatch.setattr(
            "openreview_cli.prompts.store.PromptStore", MagicMock(resolve=lambda slot: None)
        )

        result = gw.embed("embedding", ["hello"])

        assert result == [[0.1, 0.2]]


class TestProviderClassification:
    def test_unclassifiable_nonlocal_fails_closed_under_maximum(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Bedrock/vertex-style providers (base_url=None, is_local=False) are
        unclassifiable, but maximum tier must still block them (fail closed)."""
        gw = _make_gateway(
            monkeypatch, _config("maximum", "reasoning", "bedrock/anthropic.claude"), tmp_path
        )
        bedrock = ProviderInfo(name="bedrock", base_url=None, is_local=False)
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: bedrock)
        monkeypatch.setattr(gw, "_call_with_fallback", _assert_dispatch_not_reached)

        with pytest.raises(NoMatchingProviderError) as exc_info:
            gw.chat("reasoning", [{"role": "user", "content": "hi"}])

        assert "MAXIMUM" in str(exc_info.value)


class TestBalancedTierPiiGate:
    def test_cloud_llm_without_strip_raises_pii_unavailable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Balanced tier + cloud LLM + no PII strip → blocked before dispatch."""
        from openreview_cli.gateway.router import reset_pii_available

        reset_pii_available()
        gw = _make_gateway(monkeypatch, _config("balanced", "reasoning", "openai/gpt-4"), tmp_path)
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _cloud_info())
        monkeypatch.setattr(gw, "_call_with_fallback", _assert_dispatch_not_reached)

        with pytest.raises(PIIUnavailableError):
            gw.chat("reasoning", [{"role": "user", "content": "hi"}])

    def test_cloud_llm_after_strip_allowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Balanced tier + cloud LLM + successful strip → allowed."""
        from openreview_cli.gateway.router import mark_pii_available

        mark_pii_available()
        gw = _make_gateway(monkeypatch, _config("balanced", "reasoning", "openai/gpt-4"), tmp_path)
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _cloud_info())
        monkeypatch.setattr(gw, "_get_litellm_kwargs", lambda slot: {"model": "openai/gpt-4"})
        monkeypatch.setattr(gw, "_call_with_fallback", lambda *a, **k: _chat_response("ok"))
        monkeypatch.setattr(
            "openreview_cli.prompts.store.PromptStore", MagicMock(resolve=lambda slot: None)
        )

        assert gw.chat("reasoning", [{"role": "user", "content": "hi"}]) == "ok"

    def test_performance_cloud_embed_without_strip_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Performance tier + cloud embed + no strip → blocked."""
        from openreview_cli.gateway.router import reset_pii_available

        reset_pii_available()
        gw = _make_gateway(
            monkeypatch,
            _config("performance", "embedding", "openai/text-embedding-3-small"),
            tmp_path,
        )
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _cloud_info())
        monkeypatch.setattr(gw, "_call_with_fallback", _assert_dispatch_not_reached)

        with pytest.raises(PIIUnavailableError):
            gw.embed("embedding", ["hello"])


class TestCloudCallCounter:
    def test_cloud_call_increments_module_counter_and_reset_zeroes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from openreview_cli.gateway.router import get_total_cloud_calls, reset_total_cloud_calls

        reset_total_cloud_calls()
        gw = _make_gateway(
            monkeypatch,
            _config("performance", "embedding", "openai/text-embedding-3-small"),
            tmp_path,
        )
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _cloud_info())

        gw._record_cloud_call("embedding")
        assert get_total_cloud_calls() == 1

        gw._record_cloud_call("embedding")
        assert get_total_cloud_calls() == 2

        reset_total_cloud_calls()
        assert get_total_cloud_calls() == 0

    def test_local_call_does_not_increment_module_counter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from openreview_cli.gateway.router import get_total_cloud_calls, reset_total_cloud_calls

        reset_total_cloud_calls()
        gw = _make_gateway(
            monkeypatch, _config("maximum", "embedding", "ollama/nomic-embed-text"), tmp_path
        )
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _local_info())

        gw._record_cloud_call("embedding")

        assert get_total_cloud_calls() == 0
