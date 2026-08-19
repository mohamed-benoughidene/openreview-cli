"""Unit tests for the gateway recovery seam in ``call_gateway_chat``.

Proves that a failing ``gw.chat`` is routed through the recovery coordinator
and that an alternate provider's result is returned when fallback succeeds.
"""

from __future__ import annotations

import pytest

from openreview_cli.gateway.errors import RateLimitError
from openreview_cli.recovery.coordinator import RecoveryCoordinator
from openreview_cli.review._gateway import call_gateway_chat


class TestCallGatewayChatRecoverySeam:
    def test_fallback_to_alternate_provider_returns_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed primary chat falls back to the next provider and returns its result."""
        coordinator = RecoveryCoordinator(provider_list=["openai/gpt-4", "ollama/llama3.1"])

        calls: list[str] = []

        def fake_chat(
            self_obj: object,
            slot: str,
            messages: list[dict[str, str]],
            **kwargs: object,
        ) -> str:
            model = str(kwargs.get("model", ""))
            calls.append(model)
            if "ollama" in model:
                return "recovered result"
            raise RateLimitError("openai", "rate limited")

        monkeypatch.setattr(
            "openreview_cli.gateway.router.Gateway.chat",
            fake_chat,
        )

        result = call_gateway_chat(
            "extraction",
            [{"role": "user", "content": "hi"}],
            coordinator=coordinator,
            recovery_ctx=coordinator.create_context(),
            provider_list=["openai/gpt-4", "ollama/llama3.1"],
        )

        assert result == "recovered result"
        # Primary call uses the slot config (no model override); the fallback
        # retry injects the alternate provider's model string.
        assert len(calls) >= 2
        assert calls[0] == ""
        assert "ollama/llama3.1" in calls

    def test_recovery_exhausted_reraises_original(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When fallback also fails, the original error propagates."""
        coordinator = RecoveryCoordinator(provider_list=["openai/gpt-4", "ollama/llama3.1"])

        def fake_chat(
            self_obj: object,
            slot: str,
            messages: list[dict[str, str]],
            **kwargs: object,
        ) -> str:
            raise RateLimitError("openai", "all fail")

        monkeypatch.setattr(
            "openreview_cli.gateway.router.Gateway.chat",
            fake_chat,
        )

        with pytest.raises(RateLimitError):
            call_gateway_chat(
                "extraction",
                [{"role": "user", "content": "hi"}],
                coordinator=coordinator,
                recovery_ctx=coordinator.create_context(),
                provider_list=["openai/gpt-4", "ollama/llama3.1"],
            )

    def test_no_coordinator_preserves_direct_call_behavior(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without a coordinator, a direct call returns normally (no recovery path)."""

        def fake_chat(
            self_obj: object,
            slot: str,
            messages: list[dict[str, str]],
            **kwargs: object,
        ) -> str:
            return "direct"

        monkeypatch.setattr(
            "openreview_cli.gateway.router.Gateway.chat",
            fake_chat,
        )

        result = call_gateway_chat(
            "extraction",
            [{"role": "user", "content": "hi"}],
        )
        assert result == "direct"
