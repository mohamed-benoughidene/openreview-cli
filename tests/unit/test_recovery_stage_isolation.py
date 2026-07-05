"""Unit tests for stage_isolation."""

import pytest

from openreview_cli.recovery.models import (
    RecoveryContext,
    RecoveryError,
)
from openreview_cli.recovery.strategies.stage_isolation import stage_isolation


class TestStageIsolation:
    @pytest.mark.asyncio
    async def test_non_critical_failure_continues(self) -> None:
        """Non-critical failure -> pipeline continues with partial data."""
        ctx = RecoveryContext(completed_stages=["parse"])
        event = await stage_isolation(
            ctx,
            stage_name="chunk",
            error_metadata={
                "critical": False,
                "error_message": "Chunking failed on page 5",
                "partial_output": {"chunks": ["c1", "c2", "c3"]},
            },
        )
        assert event.outcome == "resolved"
        assert "continues with partial data" in event.message
        assert "chunk" in ctx.failed_stages
        assert "chunk" in ctx.partial_data
        assert ctx.partial_data["chunk"]["chunks"] == ["c1", "c2", "c3"]

    @pytest.mark.asyncio
    async def test_critical_failure_halts(self) -> None:
        """Critical failure -> RecoveryError raised."""
        ctx = RecoveryContext(completed_stages=[])
        with pytest.raises(RecoveryError) as excinfo:
            await stage_isolation(
                ctx,
                stage_name="parse",
                error_metadata={
                    "critical": True,
                    "error_message": "PDF parsing failed: corrupt file",
                },
            )
        assert "critical" in str(excinfo.value).lower()
        assert "parse" in str(excinfo.value)
        assert excinfo.value.event is not None
        assert excinfo.value.event.outcome == "exhausted"

    @pytest.mark.asyncio
    async def test_partial_data_salvaged(self) -> None:
        """Partial output preserved before failure."""
        ctx = RecoveryContext(completed_stages=["parse"])
        partial = {"clauses": [{"id": 1}, {"id": 2}, {"id": 3}]}
        await stage_isolation(
            ctx,
            stage_name="extract",
            error_metadata={
                "critical": False,
                "error_message": "Partial extraction",
                "partial_output": partial,
            },
        )
        assert ctx.partial_data["extract"]["clauses"] == [{"id": 1}, {"id": 2}, {"id": 3}]

    @pytest.mark.asyncio
    async def test_recovery_event_recorded(self) -> None:
        """Event recorded with correct details for non-critical."""
        ctx = RecoveryContext()
        event = await stage_isolation(
            ctx,
            stage_name="chunk",
            error_metadata={
                "critical": False,
                "error_message": "Chunking failed",
            },
        )
        assert len(ctx.events) == 1
        assert ctx.events[0] is event
        assert ctx.events[0].outcome == "resolved"
        assert ctx.events[0].stage_name == "chunk"

    @pytest.mark.asyncio
    async def test_event_recorded_for_critical(self) -> None:
        """Event recorded before raising exception."""
        ctx = RecoveryContext()
        with pytest.raises(RecoveryError):
            await stage_isolation(
                ctx,
                stage_name="parse",
                error_metadata={
                    "critical": True,
                    "error_message": "Fatal error",
                },
            )
        assert len(ctx.events) == 1
        assert ctx.events[0].outcome == "exhausted"
