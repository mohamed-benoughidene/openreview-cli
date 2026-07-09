"""Tests for provider_fallback_dual — parallel multi-provider strategy.

D-32: Multi-provider parallel/dual-path execution.
"""

from __future__ import annotations

import pytest

from openreview_cli.recovery.models import (
    PRIVACY_TIER_STRICT,
    RecoveryContext,
    RecoveryError,
    RecoveryOutcome,
)
from openreview_cli.recovery.strategies.provider_fallback import (
    provider_fallback_dual,
)


@pytest.fixture
def ctx() -> RecoveryContext:
    return RecoveryContext(
        provider_list=["provider_a", "provider_b", "provider_c"],
        current_provider_index=0,
        user_privacy_tier="normal",
    )


@pytest.mark.asyncio
async def test_dual_returns_first_success(ctx: RecoveryContext) -> None:
    """Dual-path returns first successful result, any provider order."""
    results: dict[str, bool] = {"provider_a": False, "provider_b": True, "provider_c": False}

    async def attempt_fn(provider: str) -> bool:
        return results.get(provider, False)

    event = await provider_fallback_dual(ctx, "test_stage", {}, attempt_fn)

    assert event.outcome == RecoveryOutcome.RESOLVED
    assert event.provider_name == "provider_b"


@pytest.mark.asyncio
async def test_dual_falls_back_when_all_fail(ctx: RecoveryContext) -> None:
    """Dual-path raises RecoveryError when all providers fail."""

    async def attempt_fn(provider: str) -> bool:
        return False

    with pytest.raises(RecoveryError) as exc_info:
        await provider_fallback_dual(ctx, "test_stage", {}, attempt_fn)

    assert exc_info.value.event is not None
    assert exc_info.value.event.outcome == RecoveryOutcome.EXHAUSTED


@pytest.mark.asyncio
async def test_dual_handles_empty_provider_list() -> None:
    """Dual-path raises RecoveryError with helpful message when no providers."""
    empty_ctx = RecoveryContext(
        provider_list=[],
        current_provider_index=0,
        user_privacy_tier="normal",
    )

    async def attempt_fn(provider: str) -> bool:
        return True

    with pytest.raises(RecoveryError) as exc_info:
        await provider_fallback_dual(empty_ctx, "test_stage", {}, attempt_fn)

    assert exc_info.value.event is not None
    assert exc_info.value.event.outcome == RecoveryOutcome.EXHAUSTED
    assert "No AI providers configured" in exc_info.value.event.message


@pytest.mark.asyncio
async def test_dual_blocks_cloud_in_strict_mode() -> None:
    """Dual-path blocks cloud providers when privacy tier is strict."""
    strict_ctx = RecoveryContext(
        provider_list=["ollama", "openai"],
        current_provider_index=0,
        user_privacy_tier=PRIVACY_TIER_STRICT,
    )

    async def attempt_fn(provider: str) -> bool:
        return True

    event = await provider_fallback_dual(strict_ctx, "test_stage", {}, attempt_fn)
    assert event.outcome == RecoveryOutcome.RESOLVED
    assert event.provider_name == "ollama"


@pytest.mark.asyncio
async def test_dual_handles_exception_in_provider(ctx: RecoveryContext) -> None:
    """Dual-path skips providers that raise exceptions, moves to next."""

    async def attempt_fn(provider: str) -> bool:
        if provider == "provider_a":
            msg = "Connection refused"
            raise ConnectionError(msg)
        return provider == "provider_b"

    event = await provider_fallback_dual(ctx, "test_stage", {}, attempt_fn)
    assert event.outcome == RecoveryOutcome.RESOLVED
    assert event.provider_name == "provider_b"


@pytest.mark.asyncio
async def test_dual_strategy_name_set(ctx: RecoveryContext) -> None:
    """Dual-path adds strategy name to ctx.attempted_strategies."""

    async def attempt_fn(provider: str) -> bool:
        return True

    await provider_fallback_dual(ctx, "test_stage", {}, attempt_fn)
    assert "provider_fallback" in ctx.attempted_strategies


@pytest.mark.asyncio
async def test_dual_appends_event_on_success(ctx: RecoveryContext) -> None:
    """Dual-path appends RecoveryEvent to ctx.events on success."""

    async def attempt_fn(provider: str) -> bool:
        return True

    event = await provider_fallback_dual(ctx, "test_stage", {}, attempt_fn)
    assert event in ctx.events
    assert len(ctx.events) == 1


@pytest.mark.asyncio
async def test_dual_appends_event_on_exhausted(ctx: RecoveryContext) -> None:
    """Dual-path appends RecoveryEvent on exhaustion before raising."""

    async def attempt_fn(provider: str) -> bool:
        return False

    with pytest.raises(RecoveryError):
        await provider_fallback_dual(ctx, "test_stage", {}, attempt_fn)

    assert any(e.outcome == RecoveryOutcome.EXHAUSTED for e in ctx.events)
