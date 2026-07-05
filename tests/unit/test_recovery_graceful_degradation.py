"""Unit tests for graceful_degradation."""

import pytest

from openreview_cli.recovery.models import (
    RecoveryContext,
    RecoveryError,
)
from openreview_cli.recovery.strategies.graceful_degradation import (
    graceful_degradation,
)


class TestGracefulDegradation:
    @pytest.mark.asyncio
    async def test_threshold_triggers_degradation(self) -> None:
        """Memory over threshold -> degradation applied."""
        ctx = RecoveryContext(memory_threshold_bytes=80_000_000)
        event = await graceful_degradation(
            ctx,
            stage_name="chunk",
            error_metadata={"current_memory_bytes": 90_000_000},
        )
        assert event.outcome == "degraded"
        assert "reduce_batch_size" in event.message
        assert "graceful_degradation" in ctx.attempted_strategies

    @pytest.mark.asyncio
    async def test_actions_applied_in_order(self) -> None:
        """Actions applied in least-disruptive order."""
        ctx = RecoveryContext(memory_threshold_bytes=80_000_000)

        # First call -> reduce_batch_size
        e1 = await graceful_degradation(ctx, "chunk", {"current_memory_bytes": 90_000_000})
        assert "reduce_batch_size" in e1.message

        assert ctx.degradation_action_index == 1

    @pytest.mark.asyncio
    async def test_exhaustion_when_degradation_insufficient(self) -> None:
        """All degradation actions exhausted but still over budget."""
        ctx = RecoveryContext(memory_threshold_bytes=80_000_000)

        # Exhaust all 4 actions by calling execute repeatedly
        actions = [
            "reduce_batch_size",
            "switch_to_lightweight_model",
            "simplify_processing",
            "reduce_context_window",
        ]
        for expected_action in actions:
            e = await graceful_degradation(
                ctx,
                stage_name="chunk",
                error_metadata={"current_memory_bytes": 90_000_000},
            )
            assert e.outcome == "degraded"
            assert expected_action in e.message

        # Next call should exhaust
        with pytest.raises(RecoveryError) as excinfo:
            await graceful_degradation(
                ctx,
                stage_name="chunk",
                error_metadata={"current_memory_bytes": 90_000_000},
            )
        assert "exhausted" in str(excinfo.value).lower()
        assert excinfo.value.event is not None
        assert excinfo.value.event.outcome == "exhausted"

    @pytest.mark.asyncio
    async def test_recovery_event_recorded(self) -> None:
        """Event recorded with correct details."""
        ctx = RecoveryContext(memory_threshold_bytes=80_000_000)
        event = await graceful_degradation(
            ctx,
            stage_name="chunk",
            error_metadata={"current_memory_bytes": 90_000_000},
        )
        assert len(ctx.events) == 1
        assert ctx.events[0] is event
        assert ctx.events[0].stage_name == "chunk"
        assert ctx.events[0].outcome == "degraded"
