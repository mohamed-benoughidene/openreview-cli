"""Unit tests for pipeline memory tracking, quota enforcement, disposable keys."""

from __future__ import annotations

import asyncio
import tracemalloc
from typing import Any

import pytest

from openreview_cli.pipeline.base import Stage, dispose_context_keys
from openreview_cli.pipeline.errors import MemoryBudgetError
from openreview_cli.pipeline.runner import Pipeline


class AllocStage(Stage):
    """Stage that allocates memory and returns the data in context."""

    name = "allocator"

    def __init__(self, megabyte_count: int = 2) -> None:
        self._megabyte_count = megabyte_count

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        data = [b"x" * 1024 * 1024 for _ in range(self._megabyte_count)]
        return {"large_data": data}


class NoopStage(Stage):
    """Stage that does nothing with minimal allocation."""

    name = "noop"

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {"small": "data"}


def test_memory_tracking_reports_nonzero() -> None:
    """Stage that allocates has nonzero memory_mb in StageResult."""
    if not tracemalloc.is_tracing():
        tracemalloc.start()

    stage = AllocStage(megabyte_count=2)
    pipeline = Pipeline(stages=[stage])
    report = asyncio.run(pipeline.run({}))

    assert report.stage_results[0].memory_mb is not None
    assert report.stage_results[0].memory_mb > 0


def test_quota_violation_raises_memory_budget_error() -> None:
    """Stage exceeding memory_quota_mb raises MemoryBudgetError."""
    if not tracemalloc.is_tracing():
        tracemalloc.start()

    stage = AllocStage(megabyte_count=2)
    pipeline = Pipeline(stages=[stage], memory_quota_mb=0.5)

    with pytest.raises(MemoryBudgetError) as exc_info:
        asyncio.run(pipeline.run({}))

    assert "allocator" in str(exc_info.value)


def test_no_memory_error_when_quota_is_none() -> None:
    """Pipeline completes normally when memory_quota_mb is None (default)."""
    if not tracemalloc.is_tracing():
        tracemalloc.start()

    stage = AllocStage(megabyte_count=2)
    pipeline = Pipeline(stages=[stage])
    report = asyncio.run(pipeline.run({}))

    assert report.stage_results[0].error is None


def test_per_stage_memory_breakdown() -> None:
    """PipelineReport.per_stage_memory_mb contains per-stage memory deltas."""
    if not tracemalloc.is_tracing():
        tracemalloc.start()

    s1 = NoopStage()
    s2 = AllocStage(megabyte_count=2)
    pipeline = Pipeline(stages=[s1, s2])
    report = asyncio.run(pipeline.run({}))

    assert isinstance(report.per_stage_memory_mb, dict)
    assert "noop" in report.per_stage_memory_mb
    assert "allocator" in report.per_stage_memory_mb
    assert report.per_stage_memory_mb["allocator"] >= report.per_stage_memory_mb.get("noop", 0)


# ---------------------------------------------------------------------------
# CV-T-006: dispose_context_keys helper
# ---------------------------------------------------------------------------


def test_dispose_context_keys_removes_keys() -> None:
    """dispose_context_keys removes specified keys from context."""
    ctx = {"a": 1, "b": 2, "c": 3}
    dispose_context_keys(ctx, {"a", "c"})
    assert ctx == {"b": 2}


def test_dispose_context_keys_ignores_missing() -> None:
    """Missing keys are silently ignored."""
    ctx = {"a": 1}
    dispose_context_keys(ctx, {"a", "nonexistent"})
    assert ctx == {}


# ---------------------------------------------------------------------------
# CV-T-006: disposable key lifecycle
# ---------------------------------------------------------------------------


def test_stage_disposable_keys_removed_after_next_stage() -> None:
    """Keys in disposable_keys are removed from context after the next stage."""

    class ProdStage(Stage):
        name = "producer"
        disposable_keys = {"produced"}

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            return {"produced": "value", "kept": "forever"}

    class ConsStage(Stage):
        name = "consumer"

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            # Consumer still sees the produced key
            assert ctx.get("produced") == "value"
            assert ctx.get("kept") == "forever"
            return {"consumed": True}

    class FinalStage(Stage):
        name = "final"

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            # Produced should be gone after consumer completed
            assert "produced" not in ctx, "disposable key still present"
            assert ctx.get("kept") == "forever", "non-disposable key removed"
            return {"done": True}

    pipeline = Pipeline(stages=[ProdStage(), ConsStage(), FinalStage()])
    asyncio.run(pipeline.run({}))
