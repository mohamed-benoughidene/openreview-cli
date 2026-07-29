"""RecoveryCoordinator — orchestrates strategy selection and execution.

FR-06: recovery actions reported through progress events.
FR-07: user data preserved during recovery.
SC-01: high auto-recovery rate via correct strategy selection.
SC-05: recovery visibility in output.
"""

from __future__ import annotations

import enum
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from openreview_cli.config import RecoveryConfig
from openreview_cli.recovery.models import (
    ErrorCategory,
    RecoveryContext,
    RecoveryError,
    RecoveryEvent,
    RecoveryOutcome,
    RecoveryReport,
    classify_error,
)
from openreview_cli.recovery.strategies.auto_retry import auto_retry
from openreview_cli.recovery.strategies.graceful_degradation import graceful_degradation
from openreview_cli.recovery.strategies.provider_fallback import provider_fallback
from openreview_cli.recovery.strategies.stage_isolation import stage_isolation
from openreview_cli.recovery.strategies.user_guided_recovery import user_guided_recovery

logger = logging.getLogger(__name__)


class RecoverySignal(enum.StrEnum):
    """Decision signals returned by coordinator methods."""

    PROCEED = "proceed"
    SKIP = "skip"
    CONTINUE_WITH_PARTIAL = "continue_with_partial"
    RETRY_STAGE = "retry_stage"
    HALT = "halt"


class RecoveryCoordinator:
    """Orchestrates error classification and strategy execution for the pipeline.

    Strategy selection logic (per plan.md Appendix):
        transient → auto_retry → exhaust → provider_fallback
        permanent → provider_fallback → exhaust → user_guided_recovery
        resource → graceful_degradation → exhaust → halt
        stage_failure → stage_isolation → continue with partial
        stage_failure_critical → halt → user_guided_recovery
        unknown → user_guided_recovery
    """

    def __init__(
        self,
        config: RecoveryConfig | None = None,
        memory_budget_bytes: int = 104_857_600,
        db_path: str | None = None,
    ) -> None:
        self._config = config or RecoveryConfig()
        self._memory_budget_bytes = memory_budget_bytes
        self._db_path = db_path
        self._pipeline_id = uuid.uuid4().hex

    # -- Public API called by pipeline runner --

    def create_context(self, provider_list: list[str] | None = None) -> RecoveryContext:
        """Create a RecoveryContext with the coordinator's config injected."""
        return RecoveryContext(
            memory_budget_bytes=self._memory_budget_bytes,
            memory_threshold_bytes=int(
                self._memory_budget_bytes * self._config.memory_threshold_pct / 100.0
            ),
            provider_list=provider_list or [],
            saved_results={},
        )

    async def evaluate_pre_stage(
        self,
        stage_name: str,
        critical: bool,
        memory_bytes: int | None = None,
        ctx: RecoveryContext | None = None,
    ) -> RecoverySignal:
        """Evaluate whether a stage can proceed.

        Checks memory pressure if memory_bytes provided.
        """
        local_ctx = ctx or self.create_context()

        if memory_bytes is not None and memory_bytes >= local_ctx.memory_threshold_bytes:
            try:
                event = await graceful_degradation(
                    local_ctx,
                    stage_name,
                    {"current_memory_bytes": memory_bytes},
                )
                if event.outcome == RecoveryOutcome.EXHAUSTED:
                    self._persist_context(stage_name, local_ctx)
                    return RecoverySignal.HALT
            except RecoveryError:
                self._persist_context(stage_name, local_ctx)
                return RecoverySignal.HALT

        self._persist_context(stage_name, local_ctx)
        return RecoverySignal.PROCEED

    async def handle_stage_failure(
        self,
        stage_name: str,
        error_message: str,
        partial_output: dict[str, Any],
        ctx: RecoveryContext,
        critical: bool = False,
        attempt_fn: Callable[[int], Awaitable[bool]] | None = None,
    ) -> None:
        """Handle a stage execution failure.

        Attempts auto_retry for non-critical stage failures before falling
        through to stage isolation. Returns None—pipeline runner independently
        determines halt vs continue via the CriticalStageError exception and
        the stage's critical flag. Return value is discarded by runner in v1.
        """
        category = classify_error(stage_critical=critical)

        # Auto-retry for non-critical stage failures before isolating
        if category == ErrorCategory.stage_failure and attempt_fn is not None:
            try:
                event = await auto_retry(
                    ctx,
                    stage_name,
                    {"last_error": error_message},
                    attempt_fn=attempt_fn,
                    max_attempts=self._config.max_retries,
                    base_interval_s=self._config.base_interval_s,
                )
                if event.outcome == RecoveryOutcome.RESOLVED:
                    self._persist_context(stage_name, ctx)
                    return
            except RecoveryError:
                # Exhausted — fall through to stage isolation
                pass

        if category in (ErrorCategory.stage_failure, ErrorCategory.stage_failure_critical):
            try:
                event = await stage_isolation(
                    ctx,
                    stage_name,
                    {
                        "critical": critical,
                        "error_message": error_message,
                        "partial_output": partial_output,
                    },
                )
                if event.outcome == RecoveryOutcome.RESOLVED:
                    self._persist_context(stage_name, ctx)
                    return  # Stage isolation recovered — continue without user-guided
            except RecoveryError:
                # Critical failure — fall through to user-guided recovery
                pass

        # If we can't recover, produce user-guided error
        await self._run_user_guided_recovery(
            ctx,
            stage_name,
            {
                "error_category": category.value,
                "last_error": error_message,
            },
        )
        self._persist_context(stage_name, ctx)

    async def handle_gateway_failure(
        self,
        provider_name: str,
        error_metadata: dict[str, Any],
        ctx: RecoveryContext,
        stage_name: str = "",
        attempt_fn: Callable[[str], Awaitable[bool]] | None = None,
    ) -> RecoveryEvent | None:
        """Handle a gateway/provider call failure.

        Applies provider fallback → user-guided recovery based on the
        error classification.

        Returns a RecoveryEvent if resolution found, or raises/returns None
        if all strategies exhausted.

        This method is a public test seam — coordinator tests can call it
        directly without instantiating a full pipeline.
        """
        http_status = error_metadata.get("http_status")
        error_type = error_metadata.get("error_type")
        last_error = error_metadata.get("last_error", "")

        category = classify_error(
            http_status=http_status,
            error_type=error_type,
        )

        # --- transient/permanent → provider fallback ---
        if category in (ErrorCategory.transient, ErrorCategory.permanent):
            # Provider fallback
            try:
                result = await provider_fallback(
                    ctx,
                    stage_name,
                    {
                        "provider_name": provider_name,
                        "last_error": last_error,
                    },
                    attempt_fn=attempt_fn,
                )
            except RecoveryError as exc:
                last_event = exc.event
                if last_event:
                    ctx.events.append(last_event)
                # Fall through to user-guided
            else:
                self._persist_context(stage_name, ctx)
                return result

        # --- unknown / exhausted → user-guided recovery ---
        await self._run_user_guided_recovery(
            ctx,
            stage_name,
            {
                "error_category": category.value,
                "last_error": last_error or f"Provider '{provider_name}' failed",
                "provider_name": provider_name,
            },
        )
        self._persist_context(stage_name, ctx)
        return None

    def build_report(self, ctx: RecoveryContext) -> RecoveryReport:
        """Assemble a RecoveryReport from the recovery context.

        Called by pipeline runner after execution completes.
        """
        # Determine final status
        final_status = "resolved"
        degradation_notices: list[str] = []
        partial_results = False
        actionable_error: str | None = None

        for event in ctx.events:
            if event.outcome == RecoveryOutcome.UNRECOVERABLE:
                final_status = "unrecoverable"
                actionable_error = event.message
            elif event.outcome == RecoveryOutcome.DEGRADED:
                final_status = "degraded"
                degradation_notices.append(f"[{event.stage_name}] {event.message}")
            elif event.outcome == RecoveryOutcome.EXHAUSTED:
                if final_status == "resolved":
                    final_status = "degraded"

        if ctx.failed_stages:
            partial_results = True

        summary_parts: list[str] = []
        if final_status == "resolved":
            summary_parts.append("All stages completed without intervention")
        elif final_status == "degraded":
            summary_parts.append("Completed with degradation")
            if partial_results:
                summary_parts.append("(partial results)")
        else:
            summary_parts.append("Unrecoverable error")

        if ctx.failed_stages:
            summary_parts.append(f"— {len(ctx.failed_stages)} stage(s) had failures")

        # Build combined summary from events if we have them
        if ctx.events:
            resolved_count = sum(1 for e in ctx.events if e.outcome == RecoveryOutcome.RESOLVED)
            total_events = len(ctx.events)
            event_summary = f" [{resolved_count}/{total_events} events resolved]"
            summary_parts.append(event_summary)

        # D-31: persist final state; delete on success/degraded, keep on unrecoverable
        self._finalize_context(ctx, final_status)

        return RecoveryReport(
            events=list(ctx.events),
            final_status=final_status,
            summary=" ".join(summary_parts),
            degradation_notices=degradation_notices,
            partial_results=partial_results,
            actionable_error=actionable_error,
        )

    # -- Persistence (D-31) --

    def _persist_context(self, stage_name: str, ctx: RecoveryContext) -> None:
        """Persist current context to DB when db_path is configured."""
        if self._db_path is None:
            return
        from openreview_cli.storage.recovery import save_recovery_state

        save_recovery_state(Path(self._db_path), self._pipeline_id, stage_name, ctx)

    def _finalize_context(self, ctx: RecoveryContext, final_status: str) -> None:
        """Persist final state then delete on success/degraded, keep on unrecoverable."""
        if self._db_path is None:
            return
        self._persist_context("final", ctx)
        if final_status != "unrecoverable":
            from openreview_cli.storage.recovery import delete_recovery_state

            delete_recovery_state(Path(self._db_path), self._pipeline_id)

    def resume_context(self, pipeline_id: str) -> RecoveryContext | None:
        """Load a previously saved context from DB.

        Returns None when db_path is not configured or pipeline_id not found.
        """
        if self._db_path is None:
            return None
        from openreview_cli.storage.recovery import load_recovery_state

        return load_recovery_state(Path(self._db_path), pipeline_id)

    # -- Internal helpers --

    async def _run_user_guided_recovery(
        self,
        ctx: RecoveryContext,
        stage_name: str,
        error_metadata: dict[str, Any],
    ) -> RecoveryEvent:
        """Run user-guided recovery (always terminal)."""
        return await user_guided_recovery(ctx, stage_name, error_metadata)
