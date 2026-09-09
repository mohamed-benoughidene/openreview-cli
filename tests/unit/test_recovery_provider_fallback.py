"""Unit tests for provider_fallback."""

import pytest

from openreview_cli.recovery.models import (
    PRIVACY_TIER_STANDARD,
    PRIVACY_TIER_STRICT,
    RecoveryContext,
    RecoveryError,
)
from openreview_cli.recovery.strategies.provider_fallback import (
    provider_fallback,
)


class TestProviderFallback:
    @pytest.mark.asyncio
    async def test_all_providers_exhausted(self) -> None:
        """All providers fail -> RecoveryError raised."""
        ctx = RecoveryContext(
            provider_list=["openai/gpt-4", "anthropic/claude"],
            current_provider_index=0,
        )
        with pytest.raises(RecoveryError) as excinfo:
            await provider_fallback(
                ctx,
                stage_name="generate",
                error_metadata={"last_error": "All providers failed"},
            )
        assert "All" in str(excinfo.value)
        assert "providers exhausted" in str(excinfo.value)
        assert excinfo.value.event is not None
        assert excinfo.value.event.outcome == "exhausted"

    @pytest.mark.asyncio
    async def test_privacy_tier_blocks_cloud_fallback(self) -> None:
        """Strict privacy tier skips cloud providers -> exhausted error."""
        ctx = RecoveryContext(
            provider_list=["ollama/llama3.1", "openai/gpt-4"],
            current_provider_index=0,
            user_privacy_tier=PRIVACY_TIER_STRICT,
        )
        with pytest.raises(RecoveryError) as excinfo:
            await provider_fallback(
                ctx,
                stage_name="generate",
                error_metadata={"last_error": "ollama failed"},
            )
        # Should exhaust because cloud fallback is blocked
        assert excinfo.value.event is not None
        assert excinfo.value.event.outcome == "exhausted"

    @pytest.mark.asyncio
    async def test_no_providers_configured(self) -> None:
        """Empty provider list -> error directing to setup wizard."""
        ctx = RecoveryContext(provider_list=[])
        with pytest.raises(RecoveryError) as excinfo:
            await provider_fallback(
                ctx,
                stage_name="generate",
                error_metadata={},
            )
        message = str(excinfo.value)
        assert "No providers" in message or "gateway setup" in message
        assert excinfo.value.event is not None

    @pytest.mark.asyncio
    async def test_recovery_event_recorded(self) -> None:
        """Event appended with correct outcome on exhaustion."""
        ctx = RecoveryContext(
            provider_list=["openai/gpt-4", "ollama/llama3.1"],
        )
        with pytest.raises(RecoveryError) as excinfo:
            await provider_fallback(
                ctx,
                stage_name="generate",
                error_metadata={"last_error": "openai/gpt-4 failed"},
            )
        assert excinfo.value.event is not None
        assert excinfo.value.event.outcome == "exhausted"

    @pytest.mark.asyncio
    async def test_standard_privacy_allows_cloud(self) -> None:
        """Standard privacy tier iterates cloud providers."""
        ctx = RecoveryContext(
            provider_list=["ollama/llama3.1", "openai/gpt-4"],
            user_privacy_tier=PRIVACY_TIER_STANDARD,
        )
        # Without attempt_fn, provider_fallback always exhausts
        with pytest.raises(RecoveryError) as excinfo:
            await provider_fallback(
                ctx,
                stage_name="generate",
                error_metadata={"last_error": "ollama failed"},
            )
        assert excinfo.value.event is not None
        assert excinfo.value.event.outcome == "exhausted"

    @pytest.mark.asyncio
    async def test_success_with_attempt_fn(self) -> None:
        """attempt_fn returning True triggers success event."""

        async def _try_provider(provider: str) -> bool:
            return provider == "ollama/llama3.1"

        ctx = RecoveryContext(
            provider_list=["openai/gpt-4", "ollama/llama3.1"],
            current_provider_index=0,
        )
        event = await provider_fallback(
            ctx,
            stage_name="generate",
            error_metadata={"last_error": "openai/gpt-4 failed"},
            attempt_fn=_try_provider,
        )
        assert event.outcome == "resolved"
        assert event.provider_name == "ollama/llama3.1"
        assert "succeeded" in event.message

    @pytest.mark.asyncio
    async def test_attempt_fn_exception_continues(self) -> None:
        """Exception in attempt_fn on first fallback skips to next."""
        call_order: list[str] = []

        async def _first_raises(provider: str) -> bool:
            call_order.append(provider)
            if "mixtral" in provider:
                return True
            raise ConnectionError("Connection refused")

        ctx = RecoveryContext(
            provider_list=["ollama/llama3.1", "openai/gpt-4", "ollama/mixtral"],
            current_provider_index=0,
            user_privacy_tier=PRIVACY_TIER_STANDARD,
        )
        event = await provider_fallback(
            ctx,
            stage_name="generate",
            error_metadata={"last_error": "ollama failed"},
            attempt_fn=_first_raises,
        )
        # First fallback (gpt-4) raised, second (mixtral) succeeded
        assert len(call_order) == 2
        assert "openai/gpt-4" in call_order
        assert "ollama/mixtral" in call_order
        assert event.outcome == "resolved"
        assert event.provider_name == "ollama/mixtral"

    @pytest.mark.asyncio
    async def test_second_episode_resets_cursor_after_exhaustion(self) -> None:
        """R3-3 Test A — second independent provider_fallback call on the same
        context must start the provider scan at index 0 again. Without the fix,
        the first call leaves ``current_provider_index`` at ``len(provider_list) - 1``,
        and the second call's loop becomes ``range(len, len)`` = empty, skipping
        every provider and raising immediately without reaching index 1.
        """
        call_order: list[str] = []

        async def _record(provider: str) -> bool:
            call_order.append(provider)
            return False  # every fallback fails

        ctx = RecoveryContext(
            provider_list=["ollama/llama3.1", "openai/gpt-4", "anthropic/claude"],
            current_provider_index=0,
            user_privacy_tier=PRIVACY_TIER_STANDARD,
        )
        # First episode — exhausts the provider list.
        with pytest.raises(RecoveryError):
            await provider_fallback(
                ctx,
                stage_name="generate",
                error_metadata={"last_error": "primary failed"},
                attempt_fn=_record,
            )
        # Without the fix the cursor is at index 2 (last provider tried); the
        # second episode below would not reach index 1.
        with pytest.raises(RecoveryError):
            await provider_fallback(
                ctx,
                stage_name="generate",
                error_metadata={"last_error": "primary failed again"},
                attempt_fn=_record,
            )
        # Second episode must re-visit index 1 (openai/gpt-4), proving the
        # cursor was reset to 0 at the top of the episode.
        assert call_order.count("openai/gpt-4") == 2, (
            f"expected openai/gpt-4 visited in both episodes, got {call_order}"
        )
        assert call_order.count("ollama/llama3.1") == 0

    @pytest.mark.asyncio
    async def test_second_episode_resets_cursor_after_successful_fallback(self) -> None:
        """R3-3 Test B — after a successful fallback to provider index 1, the
        second independent episode on the same context must retry index 1
        (proving the cursor was reset), not skip past it.
        """
        call_order: list[str] = []

        async def _succeed_at_index_1(provider: str) -> bool:
            call_order.append(provider)
            # Index 1 succeeds every time; everything else fails.
            return provider == "openai/gpt-4"

        ctx = RecoveryContext(
            provider_list=["ollama/llama3.1", "openai/gpt-4", "anthropic/claude"],
            current_provider_index=0,
            user_privacy_tier=PRIVACY_TIER_STANDARD,
        )
        # First episode — resolves at index 1.
        event = await provider_fallback(
            ctx,
            stage_name="generate",
            error_metadata={"last_error": "primary failed"},
            attempt_fn=_succeed_at_index_1,
        )
        assert event.outcome == "resolved"
        assert event.provider_name == "openai/gpt-4"
        # Second episode — must reset and try index 1 again. Without the fix
        # the cursor would still be 1 and the loop would skip straight to index 2.
        event2 = await provider_fallback(
            ctx,
            stage_name="generate",
            error_metadata={"last_error": "primary failed again"},
            attempt_fn=_succeed_at_index_1,
        )
        assert event2.outcome == "resolved"
        assert event2.provider_name == "openai/gpt-4"
        # Index 1 was visited in both episodes; index 2 was never visited
        # (without the fix, the second episode would skip index 1 and hit index 2).
        assert call_order.count("openai/gpt-4") == 2, (
            f"expected openai/gpt-4 visited in both episodes, got {call_order}"
        )
        assert "anthropic/claude" not in call_order, (
            f"second episode must not skip to index 2, got {call_order}"
        )

    @pytest.mark.asyncio
    async def test_inner_loop_iterates_forward_within_episode(self) -> None:
        """R3-3 Test C — regression guard. Within a single recovery episode the
        inner for-loop must still iterate forward through providers after a
        failure, preserving the intended cursor semantics.
        """
        call_order: list[str] = []

        async def _fail_first_succeed_second(provider: str) -> bool:
            call_order.append(provider)
            if provider == "openai/gpt-4":
                return False
            return provider == "anthropic/claude"

        ctx = RecoveryContext(
            provider_list=["ollama/llama3.1", "openai/gpt-4", "anthropic/claude"],
            current_provider_index=0,
            user_privacy_tier=PRIVACY_TIER_STANDARD,
        )
        event = await provider_fallback(
            ctx,
            stage_name="generate",
            error_metadata={"last_error": "primary failed"},
            attempt_fn=_fail_first_succeed_second,
        )
        # Inner loop must visit index 1 (fails), then index 2 (succeeds), and
        # not re-visit any provider.
        assert call_order == ["openai/gpt-4", "anthropic/claude"]
        assert event.outcome == "resolved"
        assert event.provider_name == "anthropic/claude"
