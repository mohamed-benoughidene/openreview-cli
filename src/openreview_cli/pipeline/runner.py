"""Pipeline orchestrator -- runs stages sequentially, handles cancellation,
tracks progress, and manages memory monitoring."""

from __future__ import annotations

import logging
import time
import tracemalloc
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Sequence

from openreview_cli.pipeline.base import PipelineContext, Stage, StageResult, dispose_context_keys
from openreview_cli.pipeline.errors import (
    CriticalStageError,
    MemoryBudgetError,
    StageError,
)
from openreview_cli.pipeline.progress import (
    ProgressCallback,
    ProgressEvent,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineReport:
    """Final output of a pipeline run.

    Attributes:
        stage_results: Results for each stage in execution order.
        total_duration_s: Total wall-clock duration of the pipeline in seconds.
        cancelled: True if execution was interrupted via cancellation token.
        peak_memory_mb: Peak RSS memory measured during the run (None if not tracked).
        per_stage_memory_mb: Per-stage memory deltas keyed by stage name.
    """

    stage_results: list[StageResult] = field(default_factory=list)
    total_duration_s: float = 0.0
    cancelled: bool = False
    peak_memory_mb: float | None = None
    per_stage_memory_mb: dict[str, float] = field(default_factory=dict)


class _StageOutcome(NamedTuple):
    """Internal holder for a single stage's execution result."""

    sr: StageResult
    critical: bool


class Pipeline:
    """Orchestrates sequential stage execution with error isolation.

    Args:
        stages: Ordered sequence of stage objects.
        memory_quota_mb: Hard limit on per-stage memory delta (measured via
            tracemalloc).  If a stage exceeds this the pipeline raises
            ``MemoryBudgetError``.
        max_memory_mb: Warning threshold on per-stage memory delta.  When a
            stage exceeds this threshold a ``logging.WARNING`` message is
            emitted but execution continues.  This is the public-facing name
            for the warning threshold (``memory_quota_mb`` is the optional
            hard-limit implementation detail).
        cancellation_token: An ``asyncio.Event`` that, when set, signals the
            pipeline to cancel gracefully after the current stage completes.
        progress_callback: Called with a ``ProgressEvent`` on each stage transition.
    """

    def __init__(
        self,
        stages: Sequence[Stage],
        memory_quota_mb: float | None = None,
        max_memory_mb: float | None = None,
        cancellation_token: asyncio.Event | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self._stages = list(stages)
        self._memory_quota_mb = memory_quota_mb
        self._max_memory_mb = max_memory_mb
        self._cancellation_token = cancellation_token
        self._progress_callback = progress_callback
        self._tracemalloc_enabled = tracemalloc.is_tracing()
        self._per_stage_memory_mb: dict[str, float] = {}
        self._pending_disposable: set[str] = set()

    async def run(self, ctx: PipelineContext | None = None) -> PipelineReport:
        """Execute all stages sequentially.

        Args:
            ctx: Initial shared context. If None, starts with an empty dict.

        Returns:
            PipelineReport with per-stage results, total duration,
            cancellation flag, and peak memory.

        Raises:
            CriticalStageError: If a critical stage fails. The exception
                carries a ``pipeline_report`` attribute with the partial
                results collected up to the failing stage.
        """
        context: PipelineContext = {} if ctx is None else dict(ctx)
        context.setdefault("errors", [])
        context.setdefault("cancelled", False)

        start_time = time.monotonic()
        stage_results: list[StageResult] = []
        critical_failure = False
        critical_message: str | None = None

        for i, stage in enumerate(self._stages):
            if self._cancellation_token and self._cancellation_token.is_set():
                context["cancelled"] = True
                break

            result = await self._execute_single_stage(context, i, stage)
            stage_results.append(result.sr)

            # Dispose keys from the previous stage (CV-T-005)
            dispose_context_keys(context, self._pending_disposable)
            self._pending_disposable = set(stage.disposable_keys)

            if result.critical:
                critical_failure = True
                critical_message = result.sr.error
                break

        total_duration = time.monotonic() - start_time

        peak_mb: float | None = None
        if self._tracemalloc_enabled:
            _current, peak_bytes = tracemalloc.get_traced_memory()
            peak_mb = peak_bytes / (1024 * 1024)

        report = PipelineReport(
            stage_results=stage_results,
            total_duration_s=total_duration,
            cancelled=bool(context.get("cancelled")),
            peak_memory_mb=peak_mb,
            per_stage_memory_mb=dict(self._per_stage_memory_mb),
        )

        if critical_failure:
            raise CriticalStageError(
                critical_message or "Critical stage failed",
                pipeline_report=report,
            )

        return report

    async def _execute_single_stage(
        self,
        context: PipelineContext,
        index: int,
        stage: Stage,
    ) -> _StageOutcome:
        """Run one stage: pre-snapshot, execute, post-snapshot, merge.

        Returns a ``_StageOutcome`` with the recorded ``StageResult`` and a
        ``critical`` flag.
        """
        self._emit(
            ProgressEvent(
                stage_index=index,
                total_stages=len(self._stages),
                stage_name=stage.name,
                status="running",
            )
        )

        # CV-T-013: skip check before any execution
        if stage.should_skip(context):
            sr = StageResult(
                stage_name=stage.name,
                duration_s=0.0,
                skipped=True,
            )
            self._emit(
                ProgressEvent(
                    stage_index=index,
                    total_stages=len(self._stages),
                    stage_name=stage.name,
                    status="skipped",
                    duration_s=0.0,
                )
            )
            return _StageOutcome(sr=sr, critical=stage.critical)

        pre_snapshot = tracemalloc.take_snapshot() if self._tracemalloc_enabled else None
        stage_start = time.monotonic()
        error: str | None = None
        result: dict[str, Any] = {}
        critical = False

        try:
            raw = await stage.run(context)
            if raw is not None:
                result = raw
        except CriticalStageError as exc:
            error = str(exc)
            critical = True
        except StageError as exc:
            error = str(exc)
        except Exception as exc:
            error = f"Unexpected error: {exc}"

        stage_duration = time.monotonic() - stage_start

        post_snapshot = tracemalloc.take_snapshot() if self._tracemalloc_enabled else None
        memory_mb = _compute_memory_delta(pre_snapshot, post_snapshot)

        # max_memory_mb warning (CV-T-011) — emitted before quota check so
        # both can fire if applicable
        if (
            memory_mb is not None
            and self._max_memory_mb is not None
            and memory_mb > self._max_memory_mb
        ):
            logger.warning(
                "Stage '%s' exceeded memory budget: %.1f MB (limit: %s MB)",
                stage.name,
                memory_mb,
                self._max_memory_mb,
            )

        # Quota enforcement — raises before merging any result
        if (
            memory_mb is not None
            and self._memory_quota_mb is not None
            and memory_mb > self._memory_quota_mb
        ):
            raise MemoryBudgetError(
                f"Stage '{stage.name}' exceeded memory quota: "
                f"{memory_mb:.1f} MB (limit: {self._memory_quota_mb} MB)"
            )

        # Merge result into context
        output_keys = list(result.keys())
        context.update(result)

        # CV-T-002: cleanup after merge, before progress emission for next stage
        stage.cleanup(context)

        self._per_stage_memory_mb[stage.name] = memory_mb or 0.0

        sr = StageResult(
            stage_name=stage.name,
            duration_s=stage_duration,
            error=error,
            output_keys=output_keys,
            skipped=False,
            memory_mb=memory_mb,
        )

        if error is not None and not critical:
            context["errors"].append(sr)

        status: str = "failed" if error is not None else "completed"
        self._emit(
            ProgressEvent(
                stage_index=index,
                total_stages=len(self._stages),
                stage_name=stage.name,
                status=status,  # type: ignore[arg-type]
                duration_s=stage_duration,
            )
        )

        return _StageOutcome(sr=sr, critical=critical)

    def _emit(self, event: ProgressEvent) -> None:
        """Forward a progress event to the registered callback, if any."""
        if self._progress_callback is not None:
            self._progress_callback(event)


def _compute_memory_delta(
    pre: tracemalloc.Snapshot | None,
    post: tracemalloc.Snapshot | None,
) -> float | None:
    """Return the net memory delta in MB between two tracemalloc snapshots."""
    if pre is None or post is None:
        return None
    diff = post.compare_to(pre, "traceback")
    total = sum(stat.size_diff for stat in diff if stat.size_diff > 0)
    return total / (1024 * 1024)
