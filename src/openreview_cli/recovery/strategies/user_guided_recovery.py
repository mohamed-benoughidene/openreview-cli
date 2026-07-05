"""user_guided_recovery — actionable terminal error when all strategies
exhausted.

FR-05, SC-07: when all automated recovery strategies are exhausted, produce a
user-facing error message with at least 2 actionable suggestions. Never a
silent fallback.
"""

from __future__ import annotations

import logging
from typing import Any

from openreview_cli.recovery.models import (
    ErrorCategory,
    RecoveryContext,
    RecoveryEvent,
    RecoveryOutcome,
    suggestion_for,
)

logger = logging.getLogger(__name__)

STRATEGY_NAME = "user_guided_recovery"


async def user_guided_recovery(
    ctx: RecoveryContext,
    stage_name: str,
    error_metadata: dict[str, Any],
) -> RecoveryEvent:
    """Produce the final error message.

    Always terminal — never auto-recovers.

    Args:
        ctx: Recovery context with attempted strategies.
        stage_name: Name of the stage where recovery failed.
        error_metadata: Contains 'error_category', 'last_error', 'provider_name'.

    Returns:
        Always returns a RecoveryEvent with outcome 'unrecoverable'.
        Never raises (terminal strategy — no further escalation).
    """
    ctx.attempted_strategies.append(STRATEGY_NAME)

    category_raw = error_metadata.get(
        "error_category",
        ErrorCategory.unknown.value,
    )
    last_error = error_metadata.get("last_error", "Unknown error")
    provider_name = error_metadata.get("provider_name", "")

    # Build attempted strategies log
    attempted = ctx.attempted_strategies
    strategy_log = ", ".join(attempted) if attempted else "none"

    # Select suggestions based on error type using shared helper
    if isinstance(category_raw, ErrorCategory):
        cat_enum = category_raw
    else:
        try:
            cat_enum = ErrorCategory(category_raw)
        except ValueError:
            cat_enum = ErrorCategory.unknown
    suggestions = suggestion_for(cat_enum, provider_name, ctx.user_privacy_tier)

    message_lines = [
        f"Error: {last_error}",
        f"Location: Stage '{stage_name}'",
        f"Recovery strategies attempted: {strategy_log}",
        "",
        "Possible actions:",
    ]
    for i, suggestion in enumerate(suggestions, 1):
        message_lines.append(f"  {i}. {suggestion}")

    message = "\n".join(message_lines)

    event = RecoveryEvent(
        strategy_name=STRATEGY_NAME,
        stage_name=stage_name,
        provider_name=provider_name or None,
        outcome=RecoveryOutcome.UNRECOVERABLE,
        message=message,
    )
    ctx.events.append(event)

    logger.info(
        "User-guided recovery for stage '%s': %d suggestions generated",
        stage_name,
        len(suggestions),
    )

    return event
