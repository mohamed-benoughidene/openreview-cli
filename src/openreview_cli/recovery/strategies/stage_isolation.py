"""stage_isolation — captures non-critical stage failures and continues.

FR-04, SC-06: when a non-critical pipeline stage fails, capture the error,
salvage partial output, and continue execution. Critical stage failures halt
the pipeline with a clear error.
"""

from __future__ import annotations

import logging
from typing import Any

from openreview_cli.recovery.models import (
    RecoveryContext,
    RecoveryError,
    RecoveryEvent,
    RecoveryOutcome,
)

logger = logging.getLogger(__name__)

STRATEGY_NAME = "stage_isolation"


async def stage_isolation(
    ctx: RecoveryContext,
    stage_name: str,
    error_metadata: dict[str, Any],
) -> RecoveryEvent:
    """Handle a stage failure based on criticality.

    Non-critical failures: mark stage as failed, salvage partial data, continue.
    Critical failures: halt pipeline with clear error.

    Args:
        ctx: Recovery context (mutated to record failure state).
        stage_name: Name of the failing stage.
        error_metadata: Must include 'critical' (bool) and may include
            'partial_output' (dict) and 'error_message' (str).

    Returns:
        RecoveryEvent with outcome 'resolved' (pipeline can continue with
        partial data) or 'exhausted' (for critical — must halt).

    Raises:
        RecoveryError: When the stage is critical — pipeline must halt.
    """
    ctx.attempted_strategies.append(STRATEGY_NAME)

    is_critical = error_metadata.get("critical", False)
    error_message = error_metadata.get("error_message", "Stage failed")
    partial_output = error_metadata.get("partial_output", {})

    # Record the failure
    ctx.failed_stages.append(stage_name)

    if is_critical:
        # Critical failure — halt pipeline
        event = RecoveryEvent(
            strategy_name=STRATEGY_NAME,
            stage_name=stage_name,
            outcome=RecoveryOutcome.EXHAUSTED,
            message=(f"Critical stage '{stage_name}' failed: {error_message}. Pipeline halted."),
        )
        ctx.events.append(event)
        raise RecoveryError(
            f"Critical stage '{stage_name}' failed: {error_message}",
            event=event,
        )

    # Non-critical — salvage partial data and continue
    if partial_output:
        for key, value in partial_output.items():
            ctx.partial_data.setdefault(stage_name, {})[key] = value

    event = RecoveryEvent(
        strategy_name=STRATEGY_NAME,
        stage_name=stage_name,
        outcome=RecoveryOutcome.RESOLVED,
        message=(
            f"Stage '{stage_name}' failed (non-critical): {error_message}. "
            f"Pipeline continues with partial data."
        ),
    )
    ctx.events.append(event)

    logger.info(
        "Stage '%s' failed non-critically — isolated, continuing with partial data",
        stage_name,
    )

    return event
