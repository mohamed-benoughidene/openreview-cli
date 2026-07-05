"""graceful_degradation — reduces resource usage under memory pressure.

FR-03, SC-03: before a stage runs, check if current memory exceeds the
threshold. If so, apply degradation actions in least-disruptive order
(reduce_batch_size → switch_to_lightweight_model → simplify_processing →
reduce_context_window). If degradation is insufficient, halt with memory error.
"""

from __future__ import annotations

import logging
from typing import Any

from openreview_cli.recovery.models import (
    DEGRADATION_ACTIONS,
    RecoveryContext,
    RecoveryError,
    RecoveryEvent,
    RecoveryOutcome,
)

logger = logging.getLogger(__name__)

STRATEGY_NAME = "graceful_degradation"


async def graceful_degradation(
    ctx: RecoveryContext,
    stage_name: str,
    error_metadata: dict[str, Any],
) -> RecoveryEvent:
    """Check memory pressure and apply degradation if needed.

    State (action_index, active flag) lives on RecoveryContext so it
    persists across calls within a run but resets between runs.

    Args:
        ctx: Recovery context (reads memory_threshold_bytes).
        stage_name: Name of the stage being checked.
        error_metadata: Must include 'current_memory_bytes' from tracemalloc.

    Returns:
        RecoveryEvent with outcome 'degraded' if degradation was applied,
        or 'resolved' if no degradation was needed.

    Raises:
        RecoveryError: If all degradation actions applied but memory
            still exceeds budget.
    """
    ctx.attempted_strategies.append(STRATEGY_NAME)

    current_bytes = error_metadata.get("current_memory_bytes", 0)
    threshold = ctx.memory_threshold_bytes
    budget = ctx.memory_budget_bytes

    # Degradation needed — caller evaluated memory pressure before calling
    if ctx.degradation_action_index >= len(DEGRADATION_ACTIONS):
        # All actions exhausted but still over budget
        event = RecoveryEvent(
            strategy_name=STRATEGY_NAME,
            stage_name=stage_name,
            outcome=RecoveryOutcome.EXHAUSTED,
            message=(
                f"Memory degradation insufficient: "
                f"{current_bytes / 1024 / 1024:.1f} MB > "
                f"{budget / 1024 / 1024:.1f} MB budget. "
                f"Stage '{stage_name}' cannot proceed."
            ),
        )
        ctx.events.append(event)
        raise RecoveryError(
            f"Degradation exhausted — memory {current_bytes / 1024 / 1024:.1f} MB "
            f"exceeds budget {budget / 1024 / 1024:.1f} MB",
            event=event,
        )

    action = DEGRADATION_ACTIONS[ctx.degradation_action_index]
    ctx.degradation_action_index += 1

    event = RecoveryEvent(
        strategy_name=STRATEGY_NAME,
        stage_name=stage_name,
        outcome=RecoveryOutcome.DEGRADED,
        message=f"Memory pressure detected — applying {action}",
    )
    ctx.events.append(event)

    logger.info(
        "Degradation '%s' applied to stage '%s' "
        "(memory: %.1f MB, threshold: %.1f MB, budget: %.1f MB)",
        action,
        stage_name,
        current_bytes / 1024 / 1024,
        threshold / 1024 / 1024,
        budget / 1024 / 1024,
    )

    return event
