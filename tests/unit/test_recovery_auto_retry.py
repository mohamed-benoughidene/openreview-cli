"""Unit tests for auto_retry."""

from collections.abc import Awaitable, Callable

import pytest

from openreview_cli.recovery.models import RecoveryContext, RecoveryError
from openreview_cli.recovery.strategies.auto_retry import STRATEGY_NAME, auto_retry


def _succeed_from(target: int) -> Callable[[int], Awaitable[bool]]:
    """Return attempt_fn that returns True from *target* onward."""

    async def _fn(attempt: int) -> bool:
        return attempt >= target

    return _fn


class TestAutoRetry:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self) -> None:
        """Succeeds on attempt 1."""
        ctx = RecoveryContext()
        event = await auto_retry(
            ctx,
            stage_name="generate",
            error_metadata={"provider_name": "openai/gpt-4"},
            attempt_fn=_succeed_from(1),
            max_attempts=4,
            base_interval_s=0.001,
        )
        assert event.outcome == "resolved"
        assert event.attempt == 1
        assert STRATEGY_NAME in ctx.attempted_strategies
        assert ctx.retry_counts.get("openai/gpt-4") == 1

    @pytest.mark.asyncio
    async def test_succeeds_on_attempt_m(self) -> None:
        """Succeeds on attempt 2 (M < max_attempts)."""
        ctx = RecoveryContext()
        event = await auto_retry(
            ctx,
            stage_name="generate",
            error_metadata={"provider_name": "ollama/llama3.1"},
            attempt_fn=_succeed_from(2),
            max_attempts=4,
            base_interval_s=0.001,
        )
        assert event.outcome == "resolved"
        assert event.attempt == 2

    @pytest.mark.asyncio
    async def test_succeeds_on_attempt_3(self) -> None:
        """Succeeds on attempt 3."""
        ctx = RecoveryContext()
        event = await auto_retry(
            ctx,
            stage_name="generate",
            error_metadata={"provider_name": "anthropic/claude"},
            attempt_fn=_succeed_from(3),
            max_attempts=4,
            base_interval_s=0.001,
        )
        assert event.outcome == "resolved"
        assert event.attempt == 3

    @pytest.mark.asyncio
    async def test_exhausts_after_max_attempts(self) -> None:
        """All attempts fail -> RecoveryError raised."""
        ctx = RecoveryContext()
        with pytest.raises(RecoveryError) as excinfo:
            await auto_retry(
                ctx,
                stage_name="generate",
                error_metadata={"provider_name": "openai/gpt-4"},
                max_attempts=4,
                base_interval_s=0.001,
            )
        assert "AutoRetry exhausted after 4 attempts" in str(excinfo.value)
        assert excinfo.value.event is not None
        assert excinfo.value.event.outcome == "exhausted"
        assert excinfo.value.event.attempt == 4

    @pytest.mark.asyncio
    async def test_backoff_timing_within_twenty_percent(self) -> None:
        """Backoff formula: base * attempt^2 * (1 ± 0.2).

        Test with jitter=0.0 so we get exact values.
        """
        # attempt 1: 1.0 * 1 = 1.0
        # attempt 2: 1.0 * 4 = 4.0
        # attempt 3: 1.0 * 9 = 9.0
        from openreview_cli.recovery.strategies.auto_retry import _backoff_delay

        d1 = _backoff_delay(1, 1.0, 0.0)
        d2 = _backoff_delay(2, 1.0, 0.0)
        d3 = _backoff_delay(3, 1.0, 0.0)
        assert d1 == pytest.approx(1.0, rel=0.001)
        assert d2 == pytest.approx(4.0, rel=0.001)
        assert d3 == pytest.approx(9.0, rel=0.001)

    @pytest.mark.asyncio
    async def test_jitter_produces_variation(self) -> None:
        """With jitter=0.2, values should vary within ±20%."""
        from openreview_cli.recovery.strategies.auto_retry import _backoff_delay

        delays = [_backoff_delay(2, 1.0, 0.2) for _ in range(10)]
        # Without jitter: 4.0. With jitter: within [3.2, 4.8]
        assert all(3.2 <= d <= 4.8 for d in delays)
        # Ensure at least some variation
        assert len({round(d, 2) for d in delays}) > 1

    @pytest.mark.asyncio
    async def test_recovery_event_recorded(self) -> None:
        """Events appended to ctx.events."""
        ctx = RecoveryContext()
        await auto_retry(
            ctx,
            stage_name="generate",
            error_metadata={"provider_name": "openai/gpt-4"},
            attempt_fn=_succeed_from(2),
            max_attempts=2,
            base_interval_s=0.001,
        )
        # Should have 1 event (succeeded on attempt 2, attempt 1 was internal)
        assert len(ctx.events) == 1
        assert ctx.events[0].outcome == "resolved"
        assert ctx.events[0].attempt == 2

    @pytest.mark.asyncio
    async def test_attempt_fn_raises(self) -> None:
        """attempt_fn raising -> continues to next attempt."""
        ctx = RecoveryContext()

        async def always_raise(_attempt: int) -> bool:
            msg = "Provider unavailable"
            raise RuntimeError(msg)

        with pytest.raises(RecoveryError) as excinfo:
            await auto_retry(
                ctx,
                stage_name="generate",
                error_metadata={"provider_name": "openai/gpt-4"},
                attempt_fn=always_raise,
                max_attempts=3,
                base_interval_s=0.001,
            )
        assert excinfo.value.event is not None
        assert excinfo.value.event.outcome == "exhausted"
