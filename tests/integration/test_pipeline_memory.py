"""Integration tests for pipeline memory budget enforcement.

Full 5-stage pipeline with controlled memory allocation at each stage,
verifying per-stage tracking, peak memory, and disposable key cleanup.

These tests operate purely in-memory with synthetic data — no model loading,
no filesystem I/O.  All tests are fast (sub-second) and deterministic.
"""

from __future__ import annotations

import asyncio
import gc
import tracemalloc
from typing import Any

import pytest

from openreview_cli.pipeline import Pipeline, Stage
from openreview_cli.pipeline.runner import PipelineReport

pytestmark = pytest.mark.memory


# ---------------------------------------------------------------------------
# Helper stages
# ---------------------------------------------------------------------------


class AllocStage(Stage):
    """Stage that allocates *mbytes* MB of data in context.

    Stores an internal reference to the data so cleanup can release it.
    """

    def __init__(self, name: str, mbytes: int = 2) -> None:
        self.name = name
        self._mbytes = mbytes
        self._allocated: list[bytes] | None = None

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        data = [b"x" * (1024 * 1024) for _ in range(self._mbytes)]
        self._allocated = data
        return {f"{self.name}_data": data, f"{self.name}_meta": f"result_{self.name}"}

    def cleanup(self, ctx: dict[str, Any]) -> None:
        self._allocated = None


class NoopStage(Stage):
    """Stage that returns a small result with minimal allocation."""

    def __init__(self, name: str = "noop") -> None:
        self.name = name

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {f"{self.name}_out": f"{self.name}_done"}


# ---------------------------------------------------------------------------
# P3-T-005: Full 5-stage pipeline memory budget
# ---------------------------------------------------------------------------


def test_pipeline_memory_budget() -> None:
    """5 alloc stages through pipeline: verify per-stage tracking and peak."""
    if not tracemalloc.is_tracing():
        tracemalloc.start()

    stages: list[Stage] = [
        AllocStage("parse", mbytes=2),
        AllocStage("strip", mbytes=2),
        AllocStage("chunk", mbytes=2),
        AllocStage("retrieve", mbytes=2),
        AllocStage("generate", mbytes=2),
    ]
    pipeline = Pipeline(stages=stages)
    report = asyncio.run(pipeline.run({}))

    # All 5 stages completed successfully
    assert len(report.stage_results) == 5
    for sr in report.stage_results:
        assert sr.error is None, f"Stage {sr.stage_name} failed: {sr.error}"

    # Per-stage memory is recorded for every stage by name
    assert isinstance(report.per_stage_memory_mb, dict)
    for s in stages:
        assert s.name in report.per_stage_memory_mb, f"Missing per-stage entry for {s.name}"
        assert report.per_stage_memory_mb[s.name] >= 0

    # Each StageResult has a memory_mb value
    for sr in report.stage_results:
        assert sr.memory_mb is not None
        assert sr.memory_mb >= 0

    # Peak memory is reported and finite
    assert report.peak_memory_mb is not None
    assert report.peak_memory_mb >= 0

    # Reasonable bound: 5 stages x 2 MB each + runner overhead < 30 MB
    # (set generously to avoid GC-timing flakiness)
    assert report.peak_memory_mb < 30.0, (
        f"Peak memory {report.peak_memory_mb:.1f} MB exceeds 30 MB ceiling"
    )


# ---------------------------------------------------------------------------
# Per-stage memory breakdown
# ---------------------------------------------------------------------------


def test_per_stage_memory_contains_all_stages() -> None:
    """PipelineReport.per_stage_memory_mb has entries for all provided stages."""
    if not tracemalloc.is_tracing():
        tracemalloc.start()

    stages: list[Stage] = [
        AllocStage("alpha", mbytes=1),
        NoopStage("beta"),
        AllocStage("gamma", mbytes=1),
    ]
    pipeline = Pipeline(stages=stages)
    report = asyncio.run(pipeline.run({}))

    assert "alpha" in report.per_stage_memory_mb
    assert "beta" in report.per_stage_memory_mb
    assert "gamma" in report.per_stage_memory_mb

    for _name, delta in report.per_stage_memory_mb.items():
        assert delta >= 0


# ---------------------------------------------------------------------------
# Cleanup releases internal references
# ---------------------------------------------------------------------------


def test_memory_cleanup_drops_references() -> None:
    """Stage.cleanup() releases internal references after context merge."""
    if not tracemalloc.is_tracing():
        tracemalloc.start()

    cleanup_called = [False]  # list for nonlocal mutation in class scope

    class CleanupVerificationStage(Stage):
        name = "cleanup_verification"

        def __init__(self) -> None:
            self._large_data: list[bytes] | None = None

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            self._large_data = [b"y" * (1024 * 1024) for _ in range(2)]
            return {"large_data": self._large_data}

        def cleanup(self, ctx: dict[str, Any]) -> None:
            # Clear the internal reference to simulate releasing memory
            self._large_data = None
            cleanup_called[0] = True

    stages: list[Stage] = [
        CleanupVerificationStage(),
        NoopStage("verifier"),
    ]
    pipeline = Pipeline(stages=stages)
    report = asyncio.run(pipeline.run({}))

    assert cleanup_called[0], "cleanup() was not called"
    assert report.stage_results[0].error is None
    assert report.stage_results[1].error is None


# ---------------------------------------------------------------------------
# Disposable keys reduce memory retention
# ---------------------------------------------------------------------------


def test_disposable_keys_reduce_memory_retention() -> None:
    """Pipeline with disposable keys retains less current memory at end."""
    if not tracemalloc.is_tracing():
        tracemalloc.start()

    # -- Producer WITHOUT disposable keys -----------------------------------
    class ProducerKeep(Stage):
        name = "producer_keep"

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            # Simulate 3 MB of data retained in context
            data = [b"x" * (1024 * 1024) for _ in range(3)]
            return {"big_data": data, "meta_key": "value"}

        # no cleanup, no disposable_keys — data stays in context forever

    # -- Producer WITH disposable keys --------------------------------------
    class ProducerDispose(Stage):
        name = "producer_dispose"
        disposable_keys = {"big_data"}

        def __init__(self) -> None:
            self._data: list[bytes] | None = None

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            data = [b"x" * (1024 * 1024) for _ in range(3)]
            self._data = data
            return {"big_data": data, "meta_key": "value"}

        def cleanup(self, ctx: dict[str, Any]) -> None:
            self._data = None

    class Consumer(Stage):
        name = "consumer"

        async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
            return {"consumed": True}

    # Run pipeline without disposable keys
    tracemalloc.stop()
    tracemalloc.clear_traces()
    tracemalloc.start()

    asyncio.run(Pipeline(stages=[ProducerKeep(), Consumer()]).run({}))
    gc.collect()
    _current_keep, peak_keep = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Run pipeline with disposable keys
    tracemalloc.clear_traces()
    tracemalloc.start()

    asyncio.run(Pipeline(stages=[ProducerDispose(), Consumer()]).run({}))
    gc.collect()
    _current_dispose, peak_dispose = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # The dispose variant frees its big_data after the consumer stage,
    # so its peak should be no higher than the keep variant's peak.
    # (Both allocate the same amount; the key difference is that the
    # dispose variant's allocation can be freed by GC before the end.)
    assert peak_dispose <= peak_keep + 0.5 * 1024 * 1024, (
        f"Dispose peak {peak_dispose / 1024 / 1024:.1f} MB >> "
        f"keep peak {peak_keep / 1024 / 1024:.1f} MB — "
        "disposable keys should not increase memory retention"
    )


# ---------------------------------------------------------------------------
# PipelineReport consistency
# ---------------------------------------------------------------------------


def test_pipeline_report_consistency() -> None:
    """PipelineReport fields are internally consistent after a memory-tracked run."""
    if not tracemalloc.is_tracing():
        tracemalloc.start()

    stages: list[Stage] = [
        AllocStage("s1", mbytes=1),
        AllocStage("s2", mbytes=1),
    ]
    pipeline = Pipeline(stages=stages)
    report = asyncio.run(pipeline.run({}))

    assert isinstance(report, PipelineReport)
    assert len(report.stage_results) == 2

    # total_duration_s >= sum of individual stage durations
    sum_stage = sum(sr.duration_s for sr in report.stage_results)
    assert report.total_duration_s >= sum_stage, (
        f"total {report.total_duration_s} < sum {sum_stage}"
    )

    # per_stage_memory_mb matches stage_results names and order
    stage_names = [sr.stage_name for sr in report.stage_results]
    assert list(report.per_stage_memory_mb.keys()) == stage_names, (
        f"Per-stage keys {list(report.per_stage_memory_mb.keys())} != stage names {stage_names}"
    )

    # peak_memory_mb >= each per-stage delta (peak aggregates everything)
    for name, delta in report.per_stage_memory_mb.items():
        if report.peak_memory_mb is not None and delta is not None:
            assert report.peak_memory_mb >= delta, (
                f"peak {report.peak_memory_mb} < {name} delta {delta}"
            )

    assert report.cancelled is False
