"""Integration tests for the pipeline framework — end-to-end scenarios.

These tests use monkeypatching and mock adapters to simulate real pipeline
execution without loading heavy NLP models (Presidio, etc.).  All tests are
fast, running purely in-memory with synthetic data.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, cast

import pytest

from openreview_cli.pipeline import (
    CriticalStageError,
    Pipeline,
    ProgressEvent,
    Stage,
    StageError,
    StageResult,
)
from openreview_cli.pipeline.runner import PipelineReport
from tests.conftest import ErrorStage, MockStage

# ---------------------------------------------------------------------------
# IT-T-001: 5-stage mock pipeline — happy path
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_five_stage_mock_pipeline() -> None:
    """Instantiate 5 mock stages, run pipeline, verify all results."""
    stages: list[Any] = [
        MockStage("parse", return_value={"document": "doc", "clauses": ["c1"]}),
        MockStage("strip", return_value={"stripped_clauses": ["c1"]}),
        MockStage("chunk", return_value={"chunks": ["chunk1", "chunk2"]}),
        MockStage("retrieve", return_value={"retrieved": ["r1"]}),
        MockStage("generate", return_value={"generated": "review text"}),
    ]
    pipeline = Pipeline(stages=stages)
    report = asyncio.run(pipeline.run({"document_path": "/fake/path.pdf"}))

    assert isinstance(report, PipelineReport)
    assert len(report.stage_results) == 5
    for i, s in enumerate(stages):
        assert s.call_count == 1, f"{s.name} not called exactly once"
        assert report.stage_results[i].stage_name == s.name

    keys_seen: set[str] = set()
    for sr in report.stage_results:
        keys_seen.update(sr.output_keys)
    assert "document" in keys_seen
    assert "clauses" in keys_seen
    assert "stripped_clauses" in keys_seen
    assert "chunks" in keys_seen
    assert "retrieved" in keys_seen
    assert "generated" in keys_seen

    assert report.total_duration_s >= 0
    assert report.cancelled is False
    assert isinstance(report.per_stage_memory_mb, dict)
    assert len(report.per_stage_memory_mb) == 5

    for sr in report.stage_results:
        assert isinstance(sr, StageResult)
        assert sr.duration_s >= 0
        assert sr.error is None
        assert sr.skipped is False


# ---------------------------------------------------------------------------
# IT-T-002: Mixed error handling — critical + non-critical
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_mixed_error_handling() -> None:
    """Pipeline with mix of critical/non-critical/healthy stages."""
    stages: list[Any] = [
        MockStage("s1", return_value={"key1": "val1"}),
        ErrorStage("s2_noncritical", critical=False, error_cls=StageError),
        MockStage("s3", return_value={"key3": "val3"}),
        ErrorStage("s4_noncritical", critical=False, error_cls=StageError),
        MockStage("s5", return_value={"key5": "val5"}),
    ]
    pipeline = Pipeline(stages=stages)
    report = asyncio.run(pipeline.run({}))

    assert len(report.stage_results) == 5
    assert report.stage_results[0].error is None
    assert report.stage_results[1].error == "s2_noncritical failed"
    assert report.stage_results[2].error is None
    assert stages[2].call_count == 1
    assert report.stage_results[3].error == "s4_noncritical failed"
    assert report.stage_results[4].error is None
    assert stages[4].call_count == 1
    assert report.cancelled is False


@pytest.mark.integration
def test_mixed_error_with_critical_halts() -> None:
    """Critical stage failure halts pipeline immediately, capturing partial report."""
    stages: list[Any] = [
        MockStage("s1", return_value={"key1": "val1"}),
        ErrorStage("s2_noncritical", critical=False, error_cls=StageError),
        MockStage("s3", return_value={"key3": "val3"}),
        ErrorStage("s4_critical", critical=True, error_cls=CriticalStageError),
        MockStage("s5", return_value={"key5": "val5"}),
    ]
    pipeline = Pipeline(stages=stages)

    with pytest.raises(CriticalStageError) as exc_info:
        asyncio.run(pipeline.run({}))

    assert stages[0].call_count == 1
    assert stages[1].call_count == 1
    assert stages[2].call_count == 1
    assert stages[3].call_count == 1
    assert stages[4].call_count == 0

    report = cast("PipelineReport", exc_info.value.pipeline_report)
    assert report is not None
    assert len(report.stage_results) == 4
    assert report.stage_results[3].error is not None
    assert "s4_critical failed" in str(report.stage_results[3].error)


# ---------------------------------------------------------------------------
# IT-T-003: Cancellation mid-pipeline
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_cancellation_mid_pipeline() -> None:
    """Trigger cancellation during a slow stage and verify partial report."""
    token = asyncio.Event()

    class SlowCancellableStage(Stage):
        def __init__(self, name: str, sleep: float = 10) -> None:
            self.name = name
            self._sleep = sleep
            self.started = asyncio.Event()
            self.completed = False

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            self.started.set()
            await asyncio.sleep(self._sleep)
            self.completed = True
            return {self.name: "done"}

    stages: list[Any] = [
        MockStage("fast1", return_value={"a": 1}),
        SlowCancellableStage("slow", sleep=0.5),
        MockStage("fast2", return_value={"b": 2}),
    ]
    pipeline = Pipeline(stages=stages, cancellation_token=token)

    async def run_and_cancel() -> PipelineReport:
        run_task = asyncio.create_task(pipeline.run({}))
        await stages[1].started.wait()
        token.set()
        return await run_task

    report = asyncio.run(run_and_cancel())

    assert report.cancelled is True
    assert len(report.stage_results) == 2
    assert report.stage_results[0].stage_name == "fast1"
    assert report.stage_results[0].error is None
    assert report.stage_results[1].stage_name == "slow"
    assert report.stage_results[1].error is None
    assert stages[2].call_count == 0


# ---------------------------------------------------------------------------
# IT-T-004: Custom 2-stage pipeline with real adapter classes
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_custom_two_stage_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    """Compose ParseStage + ChunkStage with monkeypatched internals."""
    from openreview_cli.pipeline.adapters import ChunkStage, ParseStage

    def fake_parse_document(_path: str) -> tuple[Any, list[Any]]:
        return (
            {"name": "test_doc.pdf", "pages": 1},
            [{"id": 0, "text": "This is clause one."}, {"id": 1, "text": "This is clause two."}],
        )

    import openreview_cli.parsing.stream

    monkeypatch.setattr(openreview_cli.parsing.stream, "parse_document", fake_parse_document)

    def fake_stream_chunks(_clauses: list[Any], _config: Any = None) -> list[dict[str, Any]]:
        return [{"text": "chunked clause", "index": 0}]

    import openreview_cli.chunking

    monkeypatch.setattr(openreview_cli.chunking, "stream_chunks", fake_stream_chunks)

    stages = [ParseStage(), ChunkStage()]
    pipeline = Pipeline(stages=stages)
    report = asyncio.run(pipeline.run({"document_path": "/fake/test.pdf"}))

    assert len(report.stage_results) == 2
    assert report.stage_results[0].stage_name == "parse"
    assert report.stage_results[0].error is None
    assert report.stage_results[1].stage_name == "chunk"
    assert report.stage_results[1].error is None
    assert report.cancelled is False

    parse_keys = set(report.stage_results[0].output_keys)
    assert "document" in parse_keys
    assert "clauses" in parse_keys

    chunk_keys = set(report.stage_results[1].output_keys)
    assert "chunks" in chunk_keys


# ---------------------------------------------------------------------------
# IT-T-005: 50-page document throughput (fast mock)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_fifty_page_throughput() -> None:
    """Simulate pipeline on a 50-page document using fast mock stages."""
    mock_clauses = [{"id": i, "text": f"Clause {i} content."} for i in range(50)]
    mock_chunks = [{"text": f"Chunk {i}", "index": i} for i in range(10)]
    mock_retrieved = [{"text": f"Result {i}", "score": 0.9 - i * 0.05} for i in range(5)]

    stages = [
        MockStage("parse", return_value={"document": {"pages": 50}, "clauses": list(mock_clauses)}),
        MockStage("strip", return_value={"stripped_clauses": list(mock_clauses)}),
        MockStage("chunk", return_value={"chunks": list(mock_chunks)}),
        MockStage("retrieve", return_value={"retrieved": list(mock_retrieved)}),
        MockStage("generate", return_value={"generated": "50-page document review complete."}),
    ]
    pipeline = Pipeline(stages=stages)

    start = time.monotonic()
    report = asyncio.run(pipeline.run({"document_path": "/fake/50p.pdf"}))
    elapsed = time.monotonic() - start

    assert elapsed < 30.0, f"Pipeline took {elapsed:.2f}s (expected < 30s)"
    assert len(report.stage_results) == 5
    assert report.cancelled is False
    assert report.total_duration_s < 30.0
    assert "generated" in {k for sr in report.stage_results for k in sr.output_keys}


# ---------------------------------------------------------------------------
# IT-T-006: KeyboardInterrupt graceful shutdown
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_keyboard_interrupt_graceful() -> None:
    """Simulate Ctrl+C during stage execution."""
    token = asyncio.Event()

    class InterruptStage(Stage):
        def __init__(self, name: str) -> None:
            self.name = name
            self.call_count = 0

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            self.call_count += 1
            raise KeyboardInterrupt()

    stages: list[Any] = [
        MockStage("fast1", return_value={"a": 1}),
        InterruptStage("interrupted"),
        MockStage("fast2", return_value={"b": 2}),
    ]

    pipeline = Pipeline(stages=stages, cancellation_token=token)

    with pytest.raises(KeyboardInterrupt):
        asyncio.run(pipeline.run({}))

    assert stages[0].call_count == 1
    assert stages[1].call_count == 1
    assert stages[2].call_count == 0


# ---------------------------------------------------------------------------
# Additional E2E scenarios
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_custom_stage_ordering() -> None:
    """Custom stage ordering: reverse order of the standard 5 stages."""
    stages = [
        MockStage("generate", return_value={"generated": "gen"}),
        MockStage("retrieve", return_value={"retrieved": ["r1"]}),
        MockStage("chunk", return_value={"chunks": ["c1"]}),
        MockStage("strip", return_value={"stripped_clauses": ["s1"]}),
        MockStage("parse", return_value={"document": "doc", "clauses": ["p1"]}),
    ]
    pipeline = Pipeline(stages=stages)
    report = asyncio.run(pipeline.run({}))

    assert len(report.stage_results) == 5
    stage_names = [sr.stage_name for sr in report.stage_results]
    assert stage_names == ["generate", "retrieve", "chunk", "strip", "parse"]
    assert report.cancelled is False


@pytest.mark.integration
def test_single_stage_pipeline() -> None:
    """Pipeline with a single stage executes successfully."""
    stage = MockStage("singleton", return_value={"result": 42})
    pipeline = Pipeline(stages=[stage])
    report = asyncio.run(pipeline.run({}))

    assert len(report.stage_results) == 1
    assert report.stage_results[0].stage_name == "singleton"
    assert report.stage_results[0].error is None
    assert report.stage_results[0].output_keys == ["result"]
    assert stage.call_count == 1


@pytest.mark.integration
def test_pipeline_stage_result_memory_breakdown() -> None:
    """Verify PipelineReport has stage_results, per_stage_memory_mb, total_duration."""
    stages = [
        MockStage("a", return_value={"a": 1}, sleep=0.01),
        MockStage("b", return_value={"b": 2}, sleep=0.01),
    ]
    pipeline = Pipeline(stages=stages)
    report = asyncio.run(pipeline.run({}))

    assert len(report.stage_results) == 2
    sum_stage = sum(sr.duration_s for sr in report.stage_results)
    assert report.total_duration_s >= sum_stage
    assert isinstance(report.per_stage_memory_mb, dict)
    assert "a" in report.per_stage_memory_mb
    assert "b" in report.per_stage_memory_mb
    for sr in report.stage_results:
        if sr.memory_mb is not None:
            assert sr.memory_mb >= 0


@pytest.mark.integration
def test_error_isolation_non_critical_continues() -> None:
    """Non-critical stage failure allows pipeline to continue."""
    s1 = MockStage("s1", return_value={"shared": "data"})
    s2 = ErrorStage("s2", critical=False, error_cls=StageError)
    s3 = MockStage("s3", return_value={"more": "output"})

    pipeline = Pipeline(stages=[s1, s2, s3])
    report = asyncio.run(pipeline.run({}))

    assert len(report.stage_results) == 3
    assert report.stage_results[0].error is None
    assert report.stage_results[1].error == "s2 failed"
    assert report.stage_results[2].error is None
    assert s3.call_count == 1

    assert "shared" in report.stage_results[0].output_keys
    assert "more" in report.stage_results[2].output_keys


@pytest.mark.integration
def test_progress_callback_end_to_end() -> None:
    """Progress callback is invoked for each stage transition in an E2E run."""
    events: list[ProgressEvent] = []

    def capture(event: ProgressEvent) -> None:
        events.append(event)

    stages = [
        MockStage("alpha", return_value={"x": 1}),
        MockStage("beta", return_value={"y": 2}),
    ]
    pipeline = Pipeline(stages=stages, progress_callback=capture)
    asyncio.run(pipeline.run({}))

    assert len(events) == 4
    assert events[0].status == "running"
    assert events[0].stage_name == "alpha"
    assert events[1].status == "completed"
    assert events[1].stage_name == "alpha"
    assert events[2].status == "running"
    assert events[2].stage_name == "beta"
    assert events[3].status == "completed"
    assert events[3].stage_name == "beta"
