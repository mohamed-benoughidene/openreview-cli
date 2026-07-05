"""auto_retry — retries transient provider failures with exponential backoff.

FR-01, SC-02: transient failures (503, 429, timeout) retried up to N attempts
with exponential backoff. Backoff formula: base * attempt^2 * (1 ± jitter).
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from openreview_cli.recovery.models import (
    RecoveryContext,
    RecoveryError,
    RecoveryEvent,
    RecoveryOutcome,
)

logger = logging.getLogger(__name__)

STRATEGY_NAME = "auto_retry"


async def auto_retry(
    ctx: RecoveryContext,
    stage_name: str,
    error_metadata: dict[str, Any],
    attempt_fn: Callable[[int], Awaitable[bool]] | None = None,
    max_attempts: int = 4,
    base_interval_s: float = 1.0,
    jitter: float = 0.2,
) -> RecoveryEvent:
    """Retry a provider call with exponential backoff.

    Args:
        ctx: Recovery context (mutated to record retry counts).
        stage_name: Name of the stage making the provider call.
        error_metadata: Must include 'provider_name'.
        attempt_fn: Async callable called on each attempt.
            Return True for success, False/raise for failure.
            Default None means all attempts fail.
        max_attempts: Maximum number of retry attempts.
        base_interval_s: Base backoff interval in seconds.
        jitter: Random jitter fraction (±).

    Returns:
        RecoveryEvent with outcome 'resolved' on first success,
        'exhausted' on final failure.

    Raises:
        RecoveryError: After max_attempts all fail.
    """
    provider_name = error_metadata.get("provider_name", "unknown")
    ctx.attempted_strategies.append(STRATEGY_NAME)

    last_error: str = ""

    for attempt in range(1, max_attempts + 1):
        delay = _backoff_delay(attempt, base_interval_s, jitter)
        ctx.retry_counts[provider_name] = attempt

        if attempt_fn is not None:
            try:
                success = await attempt_fn(attempt)
            except Exception as exc:
                last_error = str(exc)
                if attempt < max_attempts:
                    await asyncio.sleep(delay)
                continue
            if success:
                event = RecoveryEvent(
                    strategy_name=STRATEGY_NAME,
                    stage_name=stage_name,
                    provider_name=provider_name,
                    attempt=attempt,
                    outcome=RecoveryOutcome.RESOLVED,
                    message=f"Provider call succeeded on attempt {attempt}/{max_attempts}",
                )
                ctx.events.append(event)
                return event

        # Wait before next attempt (skip wait on last attempt — we're done)
        if attempt < max_attempts:
            logger.debug(
                "Retry %d/%d for provider '%s' in %d ms",
                attempt,
                max_attempts,
                provider_name,
                int(delay * 1000),
            )
            await asyncio.sleep(delay)

        last_error = error_metadata.get("last_error", "") or f"Attempt {attempt} failed"

    # All attempts exhausted
    event = RecoveryEvent(
        strategy_name=STRATEGY_NAME,
        stage_name=stage_name,
        provider_name=provider_name,
        attempt=max_attempts,
        outcome=RecoveryOutcome.EXHAUSTED,
        message=(
            f"All {max_attempts} retries exhausted for provider '{provider_name}': {last_error}"
        ),
    )
    ctx.events.append(event)
    raise RecoveryError(
        f"AutoRetry exhausted after {max_attempts} attempts",
        event=event,
    )


def _backoff_delay(attempt: int, base_interval_s: float, jitter: float) -> float:
    """Compute exponential backoff with jitter: base * attempt^2 * (1 ± jitter)."""
    base = base_interval_s * (attempt * attempt)
    jitter_factor = 1.0 + random.uniform(-jitter, jitter)
    return base * jitter_factor
