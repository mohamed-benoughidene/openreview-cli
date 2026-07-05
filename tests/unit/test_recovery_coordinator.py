"""Unit tests for RecoveryCoordinator."""

import contextlib

import pytest

from openreview_cli.recovery.coordinator import RecoveryCoordinator
from openreview_cli.recovery.models import (
    RecoveryContext,
    RecoveryEvent,
    RecoveryOutcome,
)


@pytest.fixture
def coordinator() -> RecoveryCoordinator:
    return RecoveryCoordinator()


class TestRecoveryCoordinator:
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
