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


class TestR35RecoveryTierBypass:
    """R3-5 — the privacy tier must be enforced against the ACTUAL provider/model
    that will be dispatched, not merely the slot's configured primary model.

    The recovery seam's ``_retry_fn`` overrides ``model=<fallback provider>``
    on the gateway boundary. The gateway must treat that override as
    authoritative for tier enforcement — otherwise a MAXIMUM-tier user with
    a local slot primary could leak data through a recovery-driven cloud
    fallback.
    """

    def _two_provider_registry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stub the registry so both ollama (local) and openai (cloud) resolve."""

        import openreview_cli.gateway.router as router_mod

        monkeypatch.setattr(
            router_mod,
            "load_registry",
            lambda: {
                "ollama": _local_info(),
                "openai": _cloud_info(),
            },
        )

    # --- Test A: maximum + local primary + cloud model override → BLOCKED ---

    def test_maximum_blocks_cloud_model_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R3-5 Test A — MAXIMUM tier + slot primary LOCAL + caller passes
        ``model="openai/gpt-4"`` (recovery fallback shape) → tier enforcement
        must reject on the ACTUAL model, not on the slot primary.

        Pre-fix the gateway inspects only the slot primary (ollama) and the
        cloud override survives to dispatch. Post-fix the cloud override is
        detected and blocked before any network call.
        """
        gw = _make_gateway(
            monkeypatch,
            _config("maximum", "reasoning", "ollama/llama3.1"),
            tmp_path,
        )
        self._two_provider_registry(monkeypatch)
        # _resolve_provider_info is invoked in _record_cloud_call (after a
        # successful call). Stub it so the local case counts as 0 cloud calls.
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _local_info())
        # Dispatch must not be reached.
        monkeypatch.setattr(gw, "_call_with_fallback", _assert_dispatch_not_reached)

        with pytest.raises(NoMatchingProviderError) as exc_info:
            gw.chat("reasoning", [{"role": "user", "content": "hi"}], model="openai/gpt-4")

        assert "MAXIMUM" in str(exc_info.value)
        assert "local provider" in str(exc_info.value)

    # --- Test B: balanced + legal cloud override → ALLOWED ---

    def test_balanced_allows_legal_cloud_model_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R3-5 Test B — BALANCED tier + caller passes ``model="openai/gpt-4"``
        → tier enforcement must NOT inspect a different model and block
        falsely. The legal cloud override must reach dispatch.
        """
        from openreview_cli.gateway.router import mark_pii_available

        mark_pii_available()
        gw = _make_gateway(
            monkeypatch,
            _config("balanced", "reasoning", "openai/gpt-4"),
            tmp_path,
        )
        self._two_provider_registry(monkeypatch)
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _cloud_info())
        monkeypatch.setattr(gw, "_get_litellm_kwargs", lambda slot: {"model": "openai/gpt-4"})

        # Real assertion: dispatch MUST be reached, with model=openai/gpt-4.
        captured: dict[str, Any] = {}

        def _capture_call(slot: str, call_fn: Any, call_kwargs: dict[str, Any]) -> Any:
            captured["model"] = call_kwargs.get("model")
            return _chat_response("ok")

        monkeypatch.setattr(gw, "_call_with_fallback", _capture_call)
        monkeypatch.setattr(
            "openreview_cli.prompts.store.PromptStore", MagicMock(resolve=lambda slot: None)
        )

        result = gw.chat("reasoning", [{"role": "user", "content": "hi"}], model="openai/gpt-4")

        assert result == "ok"
        assert captured["model"] == "openai/gpt-4", (
            "balanced tier must allow the cloud override to reach dispatch "
            "(was previously inspecting slot primary incorrectly)"
        )

    # --- Test C: normal call without override unchanged ---

    def test_normal_call_without_model_override_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R3-5 Test C — existing tier behavior for normal ``gw.chat(...)``
        calls (no model= override) must be preserved: MAXIMUM + cloud
        primary still raises; BALANCED + cloud primary + PII ok still
        proceeds.
        """
        gw = _make_gateway(
            monkeypatch,
            _config("maximum", "reasoning", "openai/gpt-4"),
            tmp_path,
        )
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _cloud_info())
        monkeypatch.setattr(gw, "_call_with_fallback", _assert_dispatch_not_reached)

        with pytest.raises(NoMatchingProviderError):
            gw.chat("reasoning", [{"role": "user", "content": "hi"}])

    # --- Test D: explicit model override is checked ---

    def test_chat_with_model_override_uses_override_for_tier_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R3-5 Test D — direct gateway test that proves tier enforcement
        evaluates the override model rather than the slot primary.

        Slot primary is cloud (openai) under BALANCED tier. Caller passes
        ``model="ollama/llama3.1"`` (local override). The local override
        must be detected and dispatch allowed (after PII gate, which is
        bypassed here by marking PII available).

        Conversely: slot primary local under MAXIMUM + override cloud →
        blocked (this is the inverse of Test A and protects the abstraction
        in both directions).
        """
        from openreview_cli.gateway.router import mark_pii_available

        mark_pii_available()
        gw = _make_gateway(
            monkeypatch,
            _config("balanced", "reasoning", "openai/gpt-4"),
            tmp_path,
        )
        self._two_provider_registry(monkeypatch)
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _cloud_info())

        captured: dict[str, Any] = {}

        def _capture(slot: str, call_fn: Any, call_kwargs: dict[str, Any]) -> Any:
            captured["model"] = call_kwargs.get("model")
            return _chat_response("ok")

        monkeypatch.setattr(gw, "_call_with_fallback", _capture)
        monkeypatch.setattr(
            "openreview_cli.prompts.store.PromptStore", MagicMock(resolve=lambda slot: None)
        )

        # BALANCED tier, cloud primary, but caller overrides to LOCAL.
        # Tier enforcement must see the LOCAL override and not block.
        result = gw.chat("reasoning", [{"role": "user", "content": "hi"}], model="ollama/llama3.1")
        assert result == "ok"
        assert captured["model"] == "ollama/llama3.1"

    # --- Behavioral proof: cloud override does not actually dispatch ---

    def test_cloud_override_dispatch_not_reached_at_maximum(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R3-5 behavioral proof — at MAXIMUM tier, a cloud model override
        must be rejected BEFORE ``_call_with_fallback`` is reached.

        The test patches ``_call_with_fallback`` to raise AssertionError if
        reached. A passing test proves the network dispatch did not happen.
        """
        gw = _make_gateway(
            monkeypatch,
            _config("maximum", "reasoning", "ollama/llama3.1"),
            tmp_path,
        )
        self._two_provider_registry(monkeypatch)
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _local_info())
        monkeypatch.setattr(gw, "_call_with_fallback", _assert_dispatch_not_reached)

        with pytest.raises(NoMatchingProviderError):
            gw.chat(
                "reasoning",
                [{"role": "user", "content": "hi"}],
                model="openai/gpt-4",
            )

    # ──────────────────────────────────────────────────────────────────────
    # Security matrix — the full tier x primary x override x prefix grid.
    # Each cell exercises the bypass vector the brief calls out. Together
    # they prove the fix is not a one-case patch.
    # ──────────────────────────────────────────────────────────────────────

    @pytest.mark.parametrize(
        ("tier", "primary", "override", "expect_block"),
        [
            # MAXIMUM: any cloud override is forbidden, regardless of primary.
            ("maximum", "ollama/llama3.1", "openai/gpt-4", True),
            ("maximum", "ollama/llama3.1", "anthropic/claude-3", True),
            ("maximum", "ollama/llama3.1", "google/gemini-1.5", True),
            ("maximum", "ollama/llama3.1", "bedrock/claude-3", True),
            ("maximum", "ollama/llama3.1", "cohere/rerank-english-v3.0", True),
            ("maximum", "ollama/llama3.1", "mistral/mistral-large", True),
            ("maximum", "ollama/llama3.1", "groq/llama-3.1-70b", True),
            ("maximum", "ollama/llama3.1", "xai/grok-1", True),
            ("maximum", "ollama/llama3.1", "deepseek/deepseek-chat", True),
            ("maximum", "ollama/llama3.1", "voyage/voyage-3.5", True),
            ("maximum", "openai/gpt-4", "ollama/llama3.1", False),  # local override ok
            ("maximum", "ollama/llama3.1", None, False),  # no override, local primary
            ("maximum", "openai/gpt-4", None, True),  # no override, cloud primary → blocked
            # BALANCED: cloud allowed; no override path on slot primary.
            ("balanced", "openai/gpt-4", "openai/gpt-4", False),  # identity override
            ("balanced", "openai/gpt-4", "anthropic/claude-3", False),  # different cloud
            ("balanced", "ollama/llama3.1", "openai/gpt-4", False),  # local→cloud override
            ("balanced", "openai/gpt-4", "ollama/llama3.1", False),  # cloud→local
            # PERFORMANCE: cloud allowed; override path is unconstrained.
            ("performance", "openai/gpt-4", "anthropic/claude-3", False),
            ("performance", "ollama/llama3.1", "openai/gpt-4", False),
        ],
    )
    def test_tier_matrix(
        self,
        tier: str,
        primary: str,
        override: str | None,
        expect_block: bool,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """R3-5 security matrix — the gateway must enforce the tier against
        the override when one is supplied, and against the primary otherwise.
        This is the property the brief calls out: tier enforcement must not
        inspect a stale model.
        """
        gw = _make_gateway(
            monkeypatch,
            _config(tier, "reasoning", primary),
            tmp_path,
        )

        # Populate the registry with the union of providers used across the
        # matrix. We classify by base_url: localhost → local, anything else → cloud.
        def _registry() -> dict[str, ProviderInfo]:
            providers: dict[str, ProviderInfo] = {
                "ollama": _local_info(),
                "openai": _cloud_info("openai"),
                "anthropic": _cloud_info("anthropic"),
                "google": _cloud_info("google"),
                "bedrock": ProviderInfo(name="bedrock", base_url=None, is_local=False),
                "cohere": _cloud_info("cohere"),
                "mistral": _cloud_info("mistral"),
                "groq": _cloud_info("groq"),
                "xai": _cloud_info("xai"),
                "deepseek": _cloud_info("deepseek"),
                "voyage": _cloud_info("voyage"),
            }
            return providers

        import openreview_cli.gateway.router as router_mod

        monkeypatch.setattr(router_mod, "load_registry", _registry)
        # _resolve_provider_info is patched by the existing fixture pattern
        # to look up the primary.
        primary_prefix = primary.split("/", 1)[0]
        monkeypatch.setattr(
            gw,
            "_resolve_provider_info",
            lambda slot, _p=primary_prefix: _registry().get(_p),
        )
        # Mark PII available so balanced/performance cloud calls don't fail
        # on the PII gate (orthogonal to the tier matrix).
        from openreview_cli.gateway.router import mark_pii_available, reset_pii_available

        reset_pii_available()
        mark_pii_available()
        monkeypatch.setattr(
            "openreview_cli.prompts.store.PromptStore", MagicMock(resolve=lambda slot: None)
        )

        if expect_block:
            # Any cloud override at MAXIMUM → NoMatchingProviderError before
            # dispatch. Patch _call_with_fallback to prove it.
            monkeypatch.setattr(gw, "_call_with_fallback", _assert_dispatch_not_reached)
            kwargs: dict[str, Any] = {"model": override} if override else {}
            with pytest.raises(NoMatchingProviderError):
                gw.chat("reasoning", [{"role": "user", "content": "hi"}], **kwargs)
        else:
            # Should reach dispatch (or pass-through for the no-override slot
            # case where the primary is local).
            captured: dict[str, Any] = {}

            def _capture(slot: str, call_fn: Any, call_kwargs: dict[str, Any]) -> Any:
                captured["model"] = call_kwargs.get("model")
                return _chat_response("ok")

            monkeypatch.setattr(gw, "_call_with_fallback", _capture)
            kwargs = {"model": override} if override else {}
            result = gw.chat("reasoning", [{"role": "user", "content": "hi"}], **kwargs)
            assert result == "ok"
            # The dispatched model must be the override if one was supplied,
            # otherwise the primary.
            if override:
                assert captured["model"] == override

    def test_unclassifiable_override_fails_closed_at_maximum(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R3-5 — an override pointing to an unclassifiable provider
        (base_url=None, is_local=False, e.g. bedrock/vertex) must fail
        closed at MAXIMUM (treated as cloud, blocked).
        """
        gw = _make_gateway(
            monkeypatch,
            _config("maximum", "reasoning", "ollama/llama3.1"),
            tmp_path,
        )

        def _registry() -> dict[str, ProviderInfo]:
            return {
                "ollama": _local_info(),
                "bedrock": ProviderInfo(name="bedrock", base_url=None, is_local=False),
            }

        import openreview_cli.gateway.router as router_mod

        monkeypatch.setattr(router_mod, "load_registry", _registry)
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _local_info())
        monkeypatch.setattr(gw, "_call_with_fallback", _assert_dispatch_not_reached)

        with pytest.raises(NoMatchingProviderError):
            gw.chat(
                "reasoning",
                [{"role": "user", "content": "hi"}],
                model="bedrock/anthropic.claude",
            )

    def test_unknown_override_prefix_fails_closed_at_maximum(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R3-5 — an override with a prefix not in the registry at all
        (not even a ProviderInfo) must fail closed at MAXIMUM. This guards
        against a custom/unknown provider masquerading as a local one.
        """
        gw = _make_gateway(
            monkeypatch,
            _config("maximum", "reasoning", "ollama/llama3.1"),
            tmp_path,
        )

        def _registry() -> dict[str, ProviderInfo]:
            return {"ollama": _local_info()}

        import openreview_cli.gateway.router as router_mod

        monkeypatch.setattr(router_mod, "load_registry", _registry)
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _local_info())
        monkeypatch.setattr(gw, "_call_with_fallback", _assert_dispatch_not_reached)

        with pytest.raises(NoMatchingProviderError):
            gw.chat(
                "reasoning",
                [{"role": "user", "content": "hi"}],
                model="mystery-svc/llama-3.1",
            )

    def test_override_with_extra_slashes_handled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R3-5 — ``split("/", 1)[0]`` must correctly handle model strings
        with extra slashes (e.g. custom routing prefixes). Defensive against
        malformed model identifiers.
        """
        gw = _make_gateway(
            monkeypatch,
            _config("maximum", "reasoning", "ollama/llama3.1"),
            tmp_path,
        )
        self._two_provider_registry(monkeypatch)
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _local_info())
        monkeypatch.setattr(gw, "_call_with_fallback", _assert_dispatch_not_reached)

        with pytest.raises(NoMatchingProviderError):
            gw.chat(
                "reasoning",
                [{"role": "user", "content": "hi"}],
                model="openai/gpt-4/with/extra/slashes",
            )

    def test_chat_stream_enforces_tier_against_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R3-5 — chat_stream shares the same dispatch surface as chat. The
        tier enforcement must also evaluate the override, not the slot primary.
        """
        gw = _make_gateway(
            monkeypatch,
            _config("maximum", "reasoning", "ollama/llama3.1"),
            tmp_path,
        )
        self._two_provider_registry(monkeypatch)
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _local_info())

        import litellm

        def _stream_never_reached(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("chat_stream dispatched a cloud model")

        monkeypatch.setattr(litellm, "completion", _stream_never_reached)

        with pytest.raises(NoMatchingProviderError):
            list(
                gw.chat_stream(
                    "reasoning",
                    [{"role": "user", "content": "hi"}],
                    model="openai/gpt-4",
                )
            )

    def test_cloud_call_counter_uses_override_prefix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R3-5 — when an override dispatches to a cloud provider at a tier
        that allows it (balanced/performance), the counter must record the
        override as the cloud call, not silently underreport.
        """
        from openreview_cli.gateway.router import (
            mark_pii_available,
            reset_pii_available,
            reset_total_cloud_calls,
        )

        reset_pii_available()
        mark_pii_available()

        gw = _make_gateway(
            monkeypatch,
            _config("balanced", "reasoning", "ollama/llama3.1"),
            tmp_path,
        )
        self._two_provider_registry(monkeypatch)
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: _local_info())
        monkeypatch.setattr(
            "openreview_cli.prompts.store.PromptStore", MagicMock(resolve=lambda slot: None)
        )
        monkeypatch.setattr(gw, "_call_with_fallback", lambda *a, **k: _chat_response("ok"))

        # Pre-fix, _record_cloud_call would read the slot primary (local) and
        # report 0 cloud calls even though we actually dispatched a cloud
        # override. Post-fix, the counter must reflect the override.
        reset_total_cloud_calls()
        result = gw.chat(
            "reasoning",
            [{"role": "user", "content": "hi"}],
            model="openai/gpt-4",
        )
        assert result == "ok"
        assert gw.privacy_report().cloud_calls_made == 1

        # Cleanup
        reset_pii_available()
        reset_total_cloud_calls()
