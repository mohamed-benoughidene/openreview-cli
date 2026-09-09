"""Unit tests for RecoveryCoordinator."""

import contextlib

import pytest

from openreview_cli.recovery.coordinator import RecoveryCoordinator
from openreview_cli.recovery.models import (
    PRIVACY_TIER_NONE,
    PRIVACY_TIER_STANDARD,
    PRIVACY_TIER_STRICT,
    RecoveryContext,
    RecoveryEvent,
    RecoveryOutcome,
)


def _http_status_for(exc: Exception) -> int | None:
    """Mirror of review/_gateway.py._http_status_for — invoked in tests so
    the seam's classification can be exercised without going through the
    gateway helper module (keeps these tests as pure coordinator tests).
    """
    # Lazy import to mirror review/_gateway.py behaviour.
    from openreview_cli.review._gateway import _http_status_for as _real

    return _real(exc)


@pytest.fixture
def coordinator() -> RecoveryCoordinator:
    return RecoveryCoordinator()


class TestRecoveryCoordinator:
    def test_create_context_injects_product_tier_translated_to_recovery_tier(self) -> None:
        """create_context must derive user_privacy_tier from the product tier."""
        coord = RecoveryCoordinator(user_privacy_tier="maximum")
        assert coord.create_context().user_privacy_tier == PRIVACY_TIER_STRICT

    def test_create_context_balanced_to_standard(self) -> None:
        coord = RecoveryCoordinator(user_privacy_tier="balanced")
        assert coord.create_context().user_privacy_tier == PRIVACY_TIER_STANDARD

    def test_create_context_performance_to_none(self) -> None:
        coord = RecoveryCoordinator(user_privacy_tier="performance")
        assert coord.create_context().user_privacy_tier == PRIVACY_TIER_NONE

    def test_create_context_default_is_strict(self) -> None:
        """No product tier supplied → recovery default (strict), never leaking a
        non-strict tier."""
        coord = RecoveryCoordinator()
        assert coord.create_context().user_privacy_tier == PRIVACY_TIER_STRICT

    @pytest.mark.asyncio
    async def test_strategy_selection_transient_to_provider_fallback(
        self, coordinator: RecoveryCoordinator
    ) -> None:
        """Transient error -> provider fallback (auto_retry removed from gateway path)."""
        ctx = RecoveryContext(provider_list=["openai/gpt-4"])
        result = await coordinator.handle_gateway_failure(
            "openai/gpt-4",
            {"http_status": 503, "error_type": "service_unavailable"},
            ctx,
            stage_name="generate",
        )
        # Should have events indicating provider_fallback was attempted
        assert len(ctx.events) > 0
        provider_fallback_events = [e for e in ctx.events if e.strategy_name == "provider_fallback"]
        assert len(provider_fallback_events) > 0
        # No auto_retry in gateway path
        auto_retry_events = [e for e in ctx.events if e.strategy_name == "auto_retry"]
        assert len(auto_retry_events) == 0

    @pytest.mark.asyncio
    async def test_strategy_selection_permanent_to_fallback(
        self, coordinator: RecoveryCoordinator
    ) -> None:
        """Permanent error -> provider fallback."""
        ctx = RecoveryContext(provider_list=["openai/gpt-4", "ollama/llama3.1"])
        result = await coordinator.handle_gateway_failure(
            "openai/gpt-4",
            {"http_status": 401, "error_type": "auth_error"},
            ctx,
            stage_name="generate",
        )
        # The result should be a signal or event
        provider_fallback_events = [e for e in ctx.events if e.strategy_name == "provider_fallback"]
        # With no simulate_fallback_success, it should exhaust
        assert len(provider_fallback_events) > 0

    @pytest.mark.asyncio
    async def test_event_accumulation(self, coordinator: RecoveryCoordinator) -> None:
        """Events accumulate properly after strategy execution."""
        ctx = RecoveryContext(provider_list=["openai/gpt-4"])
        with contextlib.suppress(Exception):
            await coordinator.handle_gateway_failure(
                "openai/gpt-4",
                {"http_status": 503},
                ctx,
                stage_name="generate",
            )

        assert len(ctx.events) > 0
        for event in ctx.events:
            assert isinstance(event, RecoveryEvent)
            assert event.stage_name == "generate"

    @pytest.mark.asyncio
    async def test_full_transient_flow(self, coordinator: RecoveryCoordinator) -> None:
        """Transient -> provider_fallback attempt (no auto_retry in gateway path)."""
        ctx = RecoveryContext(
            provider_list=["openai/gpt-4", "ollama/llama3.1"],
            current_provider_index=0,
        )
        result = await coordinator.handle_gateway_failure(
            "openai/gpt-4",
            {
                "http_status": 503,
                "error_type": "retryable",
            },
            ctx,
            stage_name="generate",
        )
        strategy_names = [e.strategy_name for e in ctx.events]
        assert "auto_retry" not in strategy_names
        assert "provider_fallback" in strategy_names

    @pytest.mark.asyncio
    async def test_handle_stage_failure_non_critical(
        self, coordinator: RecoveryCoordinator
    ) -> None:
        """Non-critical stage failure -> stage isolation (returns None)."""
        ctx = RecoveryContext()
        await coordinator.handle_stage_failure(
            "chunk",
            "Chunking failed",
            {"partial": "data"},
            ctx,
            critical=False,
        )
        assert "stage_isolation" in ctx.attempted_strategies

    @pytest.mark.asyncio
    async def test_handle_stage_failure_critical(self, coordinator: RecoveryCoordinator) -> None:
        """Critical stage failure -> halt (returns None)."""
        ctx = RecoveryContext()
        await coordinator.handle_stage_failure(
            "parse",
            "Parse failed",
            {},
            ctx,
            critical=True,
        )
        assert "stage_isolation" in ctx.attempted_strategies

    @pytest.mark.asyncio
    async def test_build_report(self, coordinator: RecoveryCoordinator) -> None:
        """build_report returns RecoveryReport with events."""
        ctx = RecoveryContext()
        ctx.events.append(
            RecoveryEvent(
                strategy_name="auto_retry",
                stage_name="generate",
                outcome=RecoveryOutcome.RESOLVED,
                message="Retry succeeded",
            )
        )
        # Simulate the coordinator owning the ctx
        report = coordinator.build_report(ctx)
        assert len(report.events) == 1
        assert report.final_status == "resolved"

    @pytest.mark.asyncio
    async def test_report_with_degradation(self, coordinator: RecoveryCoordinator) -> None:
        """Report includes degradation notices."""
        ctx = RecoveryContext()
        ctx.events.append(
            RecoveryEvent(
                strategy_name="graceful_degradation",
                stage_name="chunk",
                outcome=RecoveryOutcome.DEGRADED,
                message="Memory pressure — reduced batch size",
            )
        )
        report = coordinator.build_report(ctx)
        assert report.final_status == "degraded"
        assert len(report.degradation_notices) == 1


class TestR34ErrorTaxonomySeam:
    """R3-4 end-to-end seam tests for the gateway-error classification.

    These tests drive ``coordinator.handle_gateway_failure`` with realistic
    error metadata shaped like the production ``review/_gateway.py`` seam
    would produce for each gateway error type. They verify the actual
    recovery path: provider_fallback for transient, user_guided_recovery
    for terminal.
    """

    @pytest.mark.asyncio
    async def test_unclassified_provider_error_uses_provider_fallback(
        self, coordinator: RecoveryCoordinator
    ) -> None:
        """R3-4 Test B — unclassified single-provider failure must reach
        provider_fallback (transient path), not be classified as terminal."""
        from openreview_cli.gateway.errors import UnclassifiedProviderError

        exc = UnclassifiedProviderError("provider ollama raised RuntimeError('boom')")
        ctx = RecoveryContext(
            provider_list=["openai/gpt-4", "anthropic/claude"],
            current_provider_index=0,
            user_privacy_tier=PRIVACY_TIER_STANDARD,
        )
        with contextlib.suppress(Exception):
            await coordinator.handle_gateway_failure(
                "openai/gpt-4",
                {
                    "http_status": _http_status_for(exc),
                    "error_type": type(exc).__name__,
                    "last_error": str(exc),
                },
                ctx,
                stage_name="generate",
            )
        provider_fallback_events = [e for e in ctx.events if e.strategy_name == "provider_fallback"]
        assert len(provider_fallback_events) >= 1, (
            "UnclassifiedProviderError must route to provider_fallback "
            "(classified transient), not user_guided_recovery"
        )

    @pytest.mark.asyncio
    async def test_connection_error_uses_provider_fallback(
        self, coordinator: RecoveryCoordinator
    ) -> None:
        """R3-4 Test C — gateway ConnectionError must reach provider_fallback."""
        from openreview_cli.gateway.errors import ConnectionError as GatewayConnectionError

        exc = GatewayConnectionError("openai", "Connection refused")
        ctx = RecoveryContext(
            provider_list=["openai/gpt-4", "ollama/llama3.1"],
            current_provider_index=0,
            user_privacy_tier=PRIVACY_TIER_STANDARD,
        )
        with contextlib.suppress(Exception):
            await coordinator.handle_gateway_failure(
                "openai/gpt-4",
                {
                    "http_status": _http_status_for(exc),
                    "error_type": type(exc).__name__,
                    "last_error": str(exc),
                },
                ctx,
                stage_name="generate",
            )
        provider_fallback_events = [e for e in ctx.events if e.strategy_name == "provider_fallback"]
        assert len(provider_fallback_events) >= 1, (
            "gateway ConnectionError must route to provider_fallback, "
            "not user_guided_recovery (was mapped to None pre-fix)"
        )

    @pytest.mark.asyncio
    async def test_all_providers_failed_remains_terminal(
        self, coordinator: RecoveryCoordinator
    ) -> None:
        """R3-4 Test D — AllProvidersFailedError (genuine gateway-local
        exhaustion) must NOT reach provider_fallback; it routes to
        user_guided_recovery (terminal).
        """
        from openreview_cli.gateway.errors import AllProvidersFailedError

        exc = AllProvidersFailedError("All providers failed")
        ctx = RecoveryContext(
            provider_list=["openai/gpt-4", "anthropic/claude"],
            current_provider_index=0,
            user_privacy_tier=PRIVACY_TIER_STANDARD,
        )
        with contextlib.suppress(Exception):
            await coordinator.handle_gateway_failure(
                "openai/gpt-4",
                {
                    "http_status": _http_status_for(exc),
                    "error_type": type(exc).__name__,
                    "last_error": str(exc),
                },
                ctx,
                stage_name="generate",
            )
        provider_fallback_events = [e for e in ctx.events if e.strategy_name == "provider_fallback"]
        assert len(provider_fallback_events) == 0, (
            "AllProvidersFailedError must remain terminal (no provider_fallback)"
        )

    @pytest.mark.asyncio
    async def test_no_matching_provider_remains_terminal(
        self, coordinator: RecoveryCoordinator
    ) -> None:
        """NoMatchingProviderError must NOT reach provider_fallback."""
        from openreview_cli.gateway.errors import NoMatchingProviderError

        exc = NoMatchingProviderError("MAXIMUM tier requires a local provider")
        ctx = RecoveryContext(
            provider_list=["openai/gpt-4"],
            current_provider_index=0,
            user_privacy_tier=PRIVACY_TIER_STANDARD,
        )
        with contextlib.suppress(Exception):
            await coordinator.handle_gateway_failure(
                "openai/gpt-4",
                {
                    "http_status": _http_status_for(exc),
                    "error_type": type(exc).__name__,
                    "last_error": str(exc),
                },
                ctx,
                stage_name="generate",
            )
        provider_fallback_events = [e for e in ctx.events if e.strategy_name == "provider_fallback"]
        assert len(provider_fallback_events) == 0, (
            "NoMatchingProviderError must remain terminal (no provider_fallback)"
        )

    @pytest.mark.asyncio
    async def test_unclassified_error_with_empty_provider_list_terminates(
        self, coordinator: RecoveryCoordinator
    ) -> None:
        """R3-4 Test E — unclassified failure with no recovery-layer
        provider_list must terminate cleanly (no retry loop)."""
        from openreview_cli.gateway.errors import UnclassifiedProviderError

        exc = UnclassifiedProviderError("provider ollama raised RuntimeError('boom')")
        ctx = RecoveryContext(
            provider_list=[],
            current_provider_index=0,
            user_privacy_tier=PRIVACY_TIER_STANDARD,
        )
        # Should complete without infinite loop or unhandled exception.
        result = await coordinator.handle_gateway_failure(
            "openai/gpt-4",
            {
                "http_status": _http_status_for(exc),
                "error_type": type(exc).__name__,
                "last_error": str(exc),
            },
            ctx,
            stage_name="generate",
        )
        assert result is None, "no providers available → terminal (returns None)"
        provider_fallback_events = [e for e in ctx.events if e.strategy_name == "provider_fallback"]
        # provider_fallback was attempted (with empty list) — it raised and
        # the coordinator fell through to user_guided_recovery. This is one
        # bounded attempt, not a loop.
        assert len(provider_fallback_events) >= 1

    @pytest.mark.asyncio
    async def test_no_recovery_loop_with_unclassified_error(
        self, coordinator: RecoveryCoordinator
    ) -> None:
        """R3-4 Test F — the new transient classification must not create an
        infinite retry loop. The provider_fallback strategy must be invoked
        exactly once (handle_gateway_failure calls it once per failure
        episode and does not recurse); the function must terminate.
        """
        from openreview_cli.gateway.errors import UnclassifiedProviderError

        exc = UnclassifiedProviderError("provider raised RuntimeError")
        ctx = RecoveryContext(
            provider_list=["openai/gpt-4", "anthropic/claude"],
            current_provider_index=0,
            user_privacy_tier=PRIVACY_TIER_STANDARD,
        )
        with contextlib.suppress(Exception):
            await coordinator.handle_gateway_failure(
                "openai/gpt-4",
                {
                    "http_status": _http_status_for(exc),
                    "error_type": type(exc).__name__,
                    "last_error": str(exc),
                },
                ctx,
                stage_name="generate",
            )
        # Count distinct (by identity) provider_fallback invocations.
        # (provider_fallback appends its own EXHAUSTED event before raising;
        # the coordinator also appends exc.event on the RecoveryError catch —
        # this is a pre-existing pattern that does not indicate a loop.)
        provider_fallback_events = [e for e in ctx.events if e.strategy_name == "provider_fallback"]
        assert len(provider_fallback_events) >= 1, (
            "provider_fallback was never invoked — transient classification did not route"
        )
        # If the loop existed, we'd see >>2 events; the upper bound is the
        # existing pre-fix pattern (provider_fallback appends one event + the
        # coordinator appends exc.event again). 2 = exactly one invocation.
        assert len(provider_fallback_events) <= 2, (
            f"provider_fallback was invoked more than once "
            f"(possible recovery loop): {len(provider_fallback_events)} events"
        )
