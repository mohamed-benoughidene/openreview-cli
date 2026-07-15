"""Unit tests for Pipeline runner — ordering, error isolation, cancellation,
progress events, and report accuracy."""

from __future__ import annotations

import asyncio
import logging
import time
import weakref
from typing import Any, cast

import pytest

from openreview_cli.pipeline.base import Stage
from openreview_cli.pipeline.errors import CriticalStageError, StageError
from openreview_cli.pipeline.progress import ProgressEvent
from openreview_cli.pipeline.runner import Pipeline, PipelineReport
from tests.conftest import ErrorStage, MockStage, SlowStage, TrackingStage

# ---------------------------------------------------------------------------
# P1-T-001: 5-stage ordering
# ---------------------------------------------------------------------------


def test_five_stage_pipeline_ordering() -> None:
    """Runner calls each stage's run() exactly once, in order."""
    stages = [
        MockStage("parse"),
        MockStage("strip"),
        MockStage("chunk"),
        MockStage("retrieve"),
        MockStage("generate"),
    ]
    pipeline = Pipeline(stages=stages)
    report = asyncio.run(pipeline.run({"document_path": "/fake/path.pdf"}))

    assert len(report.stage_results) == 5
    for i, stage in enumerate(stages):
        assert stage.call_count == 1, f"{stage.name} was not called exactly once"
        assert report.stage_results[i].stage_name == stage.name


# ---------------------------------------------------------------------------
# P1-T-002: Context merge
# ---------------------------------------------------------------------------


def test_context_accumulates_across_stages() -> None:
    """Stage results are merged into shared context via ctx.update()."""
    s1 = TrackingStage("parse", return_value={"document": "doc", "clauses": ["c1"]})
    s2 = TrackingStage("strip", return_value={"stripped_clauses": ["c1"]})
    s3 = TrackingStage("chunk", return_value={"chunks": ["chunk1"]})

    pipeline = Pipeline(stages=[s1, s2, s3])
    asyncio.run(pipeline.run({"initial": "value"}))

    # Stage 1 receives only initial context
    assert s1.received_ctx is not None
    assert s1.received_ctx.get("initial") == "value"
    assert "document" not in s1.received_ctx

    # Stage 2 sees stage 1's output
    assert s2.received_ctx is not None
    assert s2.received_ctx.get("document") == "doc"
    assert s2.received_ctx.get("clauses") == ["c1"]

    # Stage 3 sees both stage 1 and 2's output
    assert s3.received_ctx is not None
    assert s3.received_ctx.get("document") == "doc"
    assert s3.received_ctx.get("stripped_clauses") == ["c1"]
    assert "chunks" not in s3.received_ctx


# ---------------------------------------------------------------------------
# P1-T-003: Non-critical error continues
# ---------------------------------------------------------------------------


def test_non_critical_error_continues() -> None:
    """Non-critical stage failure is captured, subsequent stages execute."""
    s1 = MockStage("s1", return_value={"key1": "val1"})
    s2 = ErrorStage("s2", critical=False, error_cls=StageError)
    s3 = MockStage("s3", return_value={"key3": "val3"})

    pipeline = Pipeline(stages=[s1, s2, s3])
    report = asyncio.run(pipeline.run({}))

    assert len(report.stage_results) == 3
    assert report.stage_results[0].error is None
    assert report.stage_results[1].error == "s2 failed"
    assert report.stage_results[2].error is None

    assert s1.call_count == 1
    assert s2.call_count == 1
    assert s3.call_count == 1


# ---------------------------------------------------------------------------
# P1-T-004: Critical error halts
# ---------------------------------------------------------------------------


def test_critical_error_halts() -> None:
    """Critical stage error raises CriticalStageError, remaining stages NOT called."""
    s1 = MockStage("s1", return_value={"key1": "val1"})
    s2 = ErrorStage("s2", critical=True, error_cls=CriticalStageError)
    s3 = MockStage("s3", return_value={"key3": "val3"})

    pipeline = Pipeline(stages=[s1, s2, s3])

    with pytest.raises(CriticalStageError) as exc_info:
        asyncio.run(pipeline.run({}))

    assert s1.call_count == 1
    assert s2.call_count == 1
    assert s3.call_count == 0

    report = cast("PipelineReport", exc_info.value.pipeline_report)
    assert report is not None
    assert len(report.stage_results) == 2
    assert report.stage_results[0].error is None
    assert report.stage_results[1].error is not None
    assert "s2 failed" in str(report.stage_results[1].error)


# ---------------------------------------------------------------------------
# P1-T-005: Empty pipeline
# ---------------------------------------------------------------------------


def test_empty_pipeline() -> None:
    """Empty stage list returns empty PipelineReport immediately."""
    pipeline = Pipeline(stages=[])
    report = asyncio.run(pipeline.run({"something": "exists"}))

    assert isinstance(report, PipelineReport)
    assert report.stage_results == []
    assert report.total_duration_s >= 0
    assert report.cancelled is False


# ---------------------------------------------------------------------------
# P1-T-006: No-op stage (returns None)
# ---------------------------------------------------------------------------


def test_stage_returns_none() -> None:
    """Stage returning None is treated as successful no-op."""

    class NoneStage(Stage):
        name = "none_stage"

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any] | None:
            return None

    stage = NoneStage()
    pipeline = Pipeline(stages=[stage])
    report = asyncio.run(pipeline.run({}))

    assert len(report.stage_results) == 1
    assert report.stage_results[0].error is None
    assert report.stage_results[0].output_keys == []


# ---------------------------------------------------------------------------
# P1-T-007: Async execution
# ---------------------------------------------------------------------------


def test_async_stage_execution() -> None:
    """Stage with async def run() is awaited by runner."""

    class AsyncStage(Stage):
        name = "async_stage"
        ran = False

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            self.ran = True
            return {"result": "async_ok"}

    stage = AsyncStage()
    pipeline = Pipeline(stages=[stage])
    asyncio.run(pipeline.run({}))

    assert stage.ran is True


# ---------------------------------------------------------------------------
# P1-T-008: Progress callback
# ---------------------------------------------------------------------------


def test_progress_callback_invoked() -> None:
    """progress_callback is invoked for each stage with correct ProgressEvent."""
    events: list[ProgressEvent] = []

    def capture(event: ProgressEvent) -> None:
        events.append(event)

    stages = [
        MockStage("first"),
        MockStage("second"),
        MockStage("third"),
    ]
    pipeline = Pipeline(stages=stages, progress_callback=capture)
    asyncio.run(pipeline.run({}))

    assert len(events) == 6  # 3 stages x 2 events each (running + completed)

    assert events[0].status == "running"
    assert events[0].stage_name == "first"
    assert events[1].status == "completed"
    assert events[1].stage_name == "first"
    assert events[1].duration_s is not None


# ---------------------------------------------------------------------------
# P1-T-009: Cancellation
# ---------------------------------------------------------------------------


def test_cancellation_returns_partial_report() -> None:
    """Setting cancellation_token returns partial PipelineReport with cancelled=True."""
    token = asyncio.Event()
    slow = SlowStage("slow", sleep=0.5)
    after = MockStage("after")

    pipeline = Pipeline(stages=[slow, after], cancellation_token=token)

    async def run_and_cancel() -> PipelineReport:
        run_task = asyncio.create_task(pipeline.run({}))
        await slow.started.wait()
        token.set()
        return await run_task

    report = asyncio.run(run_and_cancel())

    assert report.cancelled is True
    assert len(report.stage_results) == 1
    assert report.stage_results[0].stage_name == "slow"
    assert slow.completed is True
    assert after.call_count == 0


# ---------------------------------------------------------------------------
# P1-T-010: PipelineReport accuracy
# ---------------------------------------------------------------------------


def test_pipeline_report_accuracy() -> None:
    """PipelineReport contains correct stage_results, total_duration, cancelled flag."""
    stages = [
        MockStage("a", sleep=0.02),
        MockStage("b", sleep=0.03),
        MockStage("c", sleep=0.01),
    ]
    pipeline = Pipeline(stages=stages)
    report = asyncio.run(pipeline.run({}))

    assert len(report.stage_results) == 3
    assert report.stage_results[0].stage_name == "a"
    sum_stage = sum(r.duration_s for r in report.stage_results)
    assert report.total_duration_s >= sum_stage
    assert report.cancelled is False
    for r in report.stage_results:
        assert r.duration_s > 0


# ---------------------------------------------------------------------------
# P1-T-011: Zero-byte input
# ---------------------------------------------------------------------------


def test_empty_input_produces_empty_result() -> None:
    """Stage receiving empty input completes with empty result set."""

    class EmptyInputStage(Stage):
        name = "empty_input"

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            clauses = ctx.get("clauses", [])
            return {"clauses": clauses, "processed": len(clauses)}

    stage = EmptyInputStage()
    pipeline = Pipeline(stages=[stage])
    report = asyncio.run(pipeline.run({"clauses": []}))

    assert len(report.stage_results) == 1
    assert report.stage_results[0].error is None
    assert report.stage_results[0].output_keys == ["clauses", "processed"]


# ---------------------------------------------------------------------------
# P1-T-013: Stage concurrency (internal only, runner not involved)
# ---------------------------------------------------------------------------


def test_stage_internal_concurrency() -> None:
    """Stage with internal parallelism (via asyncio.gather) works in the pipeline."""

    class ConcurrentStage(Stage):
        name = "concurrent"

        async def _work(self, item: int) -> dict[str, int]:
            await asyncio.sleep(0.03)
            return {"item": item}

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            tasks = [self._work(i) for i in range(4)]
            results = await asyncio.gather(*tasks)
            return {"results": results}

    stage = ConcurrentStage()
    pipeline = Pipeline(stages=[stage])

    start = time.monotonic()
    asyncio.run(pipeline.run({}))
    elapsed = time.monotonic() - start

    assert elapsed < 0.1, f"Concurrent stage took {elapsed:.3f}s (expected < 0.1s)"


# ---------------------------------------------------------------------------
# CV-T-003 / CV-T-007: cleanup invoked after merge
# ---------------------------------------------------------------------------


def test_cleanup_invoked_after_merge() -> None:
    """cleanup() is called after stage result is merged into context."""

    class CleanupTracker(Stage):
        name = "tracker"
        cleanup_called = False

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            return {"key": "value"}

        def cleanup(self, ctx: dict[str, Any]) -> None:
            self.cleanup_called = True
            # Verify merge already happened — the key from run is in context
            assert ctx.get("key") == "value", "cleanup called before merge"

    stage = CleanupTracker()
    pipeline = Pipeline(stages=[stage])
    asyncio.run(pipeline.run({}))

    assert stage.cleanup_called is True


# ---------------------------------------------------------------------------
# CV-T-004 / CV-T-008: cleanup drops stage-local references
# ---------------------------------------------------------------------------


def test_cleanup_drops_references() -> None:
    """cleanup() releases stage-local references tracked via weakref."""

    class _Payload:
        """Custom class so weakref works (plain dict is not weakref-able)."""

    class RefStage(Stage):
        name = "ref_holder"

        def __init__(self) -> None:
            self.data: _Payload | None = _Payload()

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            return {"result": "ok"}

        def cleanup(self, ctx: dict[str, Any]) -> None:
            self.data = None

    stage = RefStage()
    ref = weakref.ref(stage.data)
    assert ref() is not None  # alive before pipeline

    pipeline = Pipeline(stages=[stage])
    asyncio.run(pipeline.run({}))

    assert stage.data is None  # released by cleanup
    # weakref should be dead (or soon to be) — trigger GC
    import gc

    gc.collect()
    assert ref() is None, "Stage reference not released after cleanup"


# ---------------------------------------------------------------------------
# CV-T-012: memory warning on exceed
# ---------------------------------------------------------------------------


def test_memory_warning_on_exceed(caplog: pytest.LogCaptureFixture) -> None:
    """WARNING emitted when a stage exceeds max_memory_mb."""
    import tracemalloc

    if not tracemalloc.is_tracing():
        tracemalloc.start()

    class BigStage(Stage):
        name = "big"

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            _data = [b"x" * 1024 * 256 for _ in range(20)]
            return {"big": _data}

    caplog.set_level(logging.WARNING)
    stage = BigStage()
    pipeline = Pipeline(stages=[stage], max_memory_mb=0.1)
    asyncio.run(pipeline.run({}))

    # Check a warning was logged about the stage exceeding the budget
    assert any(
        "exceeded memory budget" in rec.message and "big" in rec.message for rec in caplog.records
    )
