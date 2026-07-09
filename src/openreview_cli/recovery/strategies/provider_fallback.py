"""provider_fallback — routes to alternate provider when primary fails.

FR-02, SC-04: after retry exhaustion (or on permanent error), iterate the
configured provider list in order. Privacy tier guard prevents silent cloud
fallback (SC-04).

Also provides ``provider_fallback_dual`` (D-32) which calls all eligible
providers in parallel via ``asyncio.gather`` and returns the first success.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from openreview_cli.recovery.models import (
    PRIVACY_TIER_STRICT,
    ErrorCategory,
    RecoveryContext,
    RecoveryError,
    RecoveryEvent,
    RecoveryOutcome,
    is_cloud_provider,
    suggestion_for,
)

logger = logging.getLogger(__name__)

STRATEGY_NAME = "provider_fallback"


async def provider_fallback(
    ctx: RecoveryContext,
    stage_name: str,
    error_metadata: dict[str, Any],
    attempt_fn: Callable[[str], Awaitable[bool]] | None = None,
) -> RecoveryEvent:
    """Attempt fallback providers in order.

    Args:
        ctx: Recovery context with provider list and privacy tier.
        stage_name: Name of the stage making the provider call.
        error_metadata: Error metadata (may include 'last_error').

    Returns:
        RecoveryEvent with outcome 'resolved' on success.

    Raises:
        RecoveryError: When all providers exhausted or privacy
            tier blocks remaining providers.
    """
    ctx.attempted_strategies.append(STRATEGY_NAME)

    provider_list = ctx.provider_list
    start_index = ctx.current_provider_index

    if not provider_list:
        event = RecoveryEvent(
            strategy_name=STRATEGY_NAME,
            stage_name=stage_name,
            outcome=RecoveryOutcome.EXHAUSTED,
            message=(
                "No AI providers configured. Run `openreview gateway setup` to configure one."
            ),
        )
        ctx.events.append(event)
        raise RecoveryError("No providers configured", event=event)

    last_error = error_metadata.get("last_error", "Provider failed")

    for i in range(start_index + 1, len(provider_list)):
        provider = provider_list[i]
        ctx.current_provider_index = i

        # Privacy tier check (SC-04)
        if ctx.user_privacy_tier == PRIVACY_TIER_STRICT and is_cloud_provider(provider):
            logger.warning(
                "Privacy tier 'strict' blocks cloud fallback to '%s'",
                provider,
            )
            continue

        # Try this provider
        if attempt_fn is not None:
            try:
                success = await attempt_fn(provider)
            except Exception as exc:
                last_error = str(exc)
                continue
            if success:
                event = RecoveryEvent(
                    strategy_name=STRATEGY_NAME,
                    stage_name=stage_name,
                    provider_name=provider,
                    outcome=RecoveryOutcome.RESOLVED,
                    message=f"Fallback to provider '{provider}' succeeded",
                )
                ctx.events.append(event)
                return event

        last_error = f"Provider '{provider}' failed"

    # All providers exhausted
    event = RecoveryEvent(
        strategy_name=STRATEGY_NAME,
        stage_name=stage_name,
        outcome=RecoveryOutcome.EXHAUSTED,
        message=(
            f"All {len(provider_list)} configured providers exhausted. Last error: {last_error}"
        ),
    )
    ctx.events.append(event)

    # Build suggestions via shared model (avoids duplicate logic)
    last_provider = provider_list[-1]
    suggestions = suggestion_for(
        category=ErrorCategory.permanent,
        provider_name=last_provider,
        privacy_tier=ctx.user_privacy_tier,
    )
    suggestion_text = " ".join(suggestions)

    raise RecoveryError(
        f"All providers exhausted. {suggestion_text}",
        event=event,
    )


async def provider_fallback_dual(
    ctx: RecoveryContext,
    stage_name: str,
    error_metadata: dict[str, Any],
    attempt_fn: Callable[[str], Awaitable[bool]] | None = None,
) -> RecoveryEvent:
    """Call providers in parallel via ``asyncio.gather``, return first success.

    D-32: Dual-path execution.  All eligible providers (respecting the
    privacy tier) are called concurrently.  The first provider that returns
    ``True`` wins.  Falls through with ``EXHAUSTED`` when all fail.

    Args:
        ctx: Recovery context with provider list and privacy tier.
        stage_name: Name of the stage making the provider call.
        error_metadata: Error metadata (may include 'last_error').
        attempt_fn: Async callable that returns True on success.

    Returns:
        RecoveryEvent with outcome ``resolved`` on success.

    Raises:
        RecoveryError: When all providers exhausted or privacy
            tier blocks remaining providers.
    """
    ctx.attempted_strategies.append(STRATEGY_NAME)

    provider_list = ctx.provider_list

    if not provider_list:
        event = RecoveryEvent(
            strategy_name=STRATEGY_NAME,
            stage_name=stage_name,
            outcome=RecoveryOutcome.EXHAUSTED,
            message=(
                "No AI providers configured. Run `openreview gateway setup` to configure one."
            ),
        )
        ctx.events.append(event)
        raise RecoveryError("No providers configured", event=event)

    # Filter providers by privacy tier (SC-04)
    eligible: list[str] = []
    for provider in provider_list:
        if ctx.user_privacy_tier == PRIVACY_TIER_STRICT and is_cloud_provider(provider):
            logger.warning(
                "Privacy tier 'strict' blocks cloud fallback to '%s'",
                provider,
            )
            continue
        eligible.append(provider)

    if not eligible:
        event = RecoveryEvent(
            strategy_name=STRATEGY_NAME,
            stage_name=stage_name,
            outcome=RecoveryOutcome.EXHAUSTED,
            message="All providers blocked by privacy tier",
        )
        ctx.events.append(event)
        raise RecoveryError("All providers blocked by privacy tier", event=event)

    # Call all eligible providers in parallel
    last_error: str = error_metadata.get("last_error", "Provider failed")
    if attempt_fn is not None:
        results = await asyncio.gather(
            *[attempt_fn(p) for p in eligible],
            return_exceptions=True,
        )

        for provider, result in zip(eligible, results, strict=False):
            if isinstance(result, Exception):
                last_error = f"Provider '{provider}' raised: {result}"
                logger.debug("Provider '%s' raised: %s", provider, result)
                continue
            if result:
                event = RecoveryEvent(
                    strategy_name=STRATEGY_NAME,
                    stage_name=stage_name,
                    provider_name=provider,
                    outcome=RecoveryOutcome.RESOLVED,
                    message=f"Dual-path fallback to provider '{provider}' succeeded",
                )
                ctx.events.append(event)
                return event

    # All providers exhausted
    event = RecoveryEvent(
        strategy_name=STRATEGY_NAME,
        stage_name=stage_name,
        outcome=RecoveryOutcome.EXHAUSTED,
        message=(
            f"All {len(eligible)} providers exhausted via dual-path. Last error: {last_error}"
        ),
    )
    ctx.events.append(event)

    last_provider = eligible[-1] if eligible else provider_list[-1]
    suggestions = suggestion_for(
        category=ErrorCategory.permanent,
        provider_name=last_provider,
        privacy_tier=ctx.user_privacy_tier,
    )
    suggestion_text = " ".join(suggestions)

    raise RecoveryError(
        f"All providers exhausted via dual-path. {suggestion_text}",
        event=event,
    )
