"""Unit tests for user_guided_recovery."""

import pytest

from openreview_cli.recovery.models import (
    ErrorCategory,
    RecoveryContext,
)
from openreview_cli.recovery.strategies.user_guided_recovery import (
    user_guided_recovery,
)


class TestUserGuidedRecovery:
    @pytest.mark.asyncio
    async def test_contains_two_or_more_suggestions(self) -> None:
        """Error message has ≥2 suggested actions (SC-07)."""
        ctx = RecoveryContext()
        event = await user_guided_recovery(
            ctx,
            stage_name="generate",
            error_metadata={
                "error_category": ErrorCategory.transient.value,
                "last_error": "Provider timeout after 4 retries",
                "provider_name": "ollama/llama3.1",
            },
        )
        lines = event.message.split("\n")
        suggestion_lines = [line for line in lines if line.startswith("  ") and line[2:3].isdigit()]
        assert len(suggestion_lines) >= 2

    @pytest.mark.asyncio
    async def test_local_only_unreachable_no_cloud_mention(self) -> None:
        """Local-only unreachable -> suggestions for local repair, no cloud."""
        ctx = RecoveryContext()
        event = await user_guided_recovery(
            ctx,
            stage_name="generate",
            error_metadata={
                "error_category": ErrorCategory.transient.value,
                "last_error": "ollama/llama3.1 is not running",
                "provider_name": "ollama/llama3.1",
            },
        )
        message = event.message
        # Should NOT mention cloud providers
        assert "openai" not in message.lower()
        assert "gpt" not in message.lower()
        # Should mention local repair options
        assert "start" in message.lower() or "ollama" in message.lower()

    @pytest.mark.asyncio
    async def test_cloud_only_unreachable(self) -> None:
        """Cloud-only unreachable -> connectivity check suggestions."""
        ctx = RecoveryContext()
        event = await user_guided_recovery(
            ctx,
            stage_name="generate",
            error_metadata={
                "error_category": ErrorCategory.permanent.value,
                "last_error": "openai/gpt-4 returned 500",
                "provider_name": "openai/gpt-4",
            },
        )
        message = event.message
        assert "connectivity" in message.lower() or "gateway setup" in message.lower()

    @pytest.mark.asyncio
    async def test_no_provider_configured(self) -> None:
        """No provider -> directs to setup wizard."""
        ctx = RecoveryContext()
        event = await user_guided_recovery(
            ctx,
            stage_name="generate",
            error_metadata={
                "error_category": ErrorCategory.transient.value,
                "last_error": "No provider available",
                "provider_name": "",
            },
        )
        message = event.message
        assert "gateway setup" in message.lower()

    @pytest.mark.asyncio
    async def test_memory_exhaustion(self) -> None:
        """Memory error -> reduce document size suggestion."""
        ctx = RecoveryContext()
        event = await user_guided_recovery(
            ctx,
            stage_name="chunk",
            error_metadata={
                "error_category": ErrorCategory.resource.value,
                "last_error": "Memory budget exceeded",
                "provider_name": "",
            },
        )
        message = event.message
        assert "reduce document" in message.lower() or "memory" in message.lower()

    @pytest.mark.asyncio
    async def test_strategy_attempt_log(self) -> None:
        """Message lists previously attempted strategies."""
        ctx = RecoveryContext()
        ctx.attempted_strategies = ["auto_retry", "provider_fallback"]
        event = await user_guided_recovery(
            ctx,
            stage_name="generate",
            error_metadata={
                "error_category": ErrorCategory.transient.value,
                "last_error": "All retries and fallbacks exhausted",
                "provider_name": "ollama/llama3.1",
            },
        )
        message = event.message
        assert "auto_retry" in message
        assert "provider_fallback" in message

    @pytest.mark.asyncio
    async def test_always_terminal(self) -> None:
        """Strategy always returns 'unrecoverable' outcome."""
        ctx = RecoveryContext()
        event = await user_guided_recovery(
            ctx,
            stage_name="generate",
            error_metadata={
                "error_category": ErrorCategory.unknown.value,
                "last_error": "Something went wrong",
            },
        )
        assert event.outcome == "unrecoverable"

    @pytest.mark.asyncio
    async def test_recovery_event_recorded(self) -> None:
        """Event appended to ctx.events."""
        ctx = RecoveryContext()
        event = await user_guided_recovery(
            ctx,
            stage_name="generate",
            error_metadata={
                "error_category": ErrorCategory.transient.value,
                "last_error": "Failure after all retries",
                "provider_name": "ollama/llama3.1",
            },
        )
        assert len(ctx.events) == 1
        assert ctx.events[0] is event
