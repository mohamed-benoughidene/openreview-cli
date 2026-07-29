"""Unit tests for D-31: Persistent recovery state serialization and coordinator persistence."""

from pathlib import Path

import pytest

from openreview_cli.recovery.coordinator import RecoveryCoordinator
from openreview_cli.recovery.models import (
    PRIVACY_TIER_STRICT,
    RecoveryContext,
    RecoveryEvent,
    RecoveryOutcome,
)


class TestRecoveryContextSerialization:
    """RecoveryContext.to_dict() and from_dict() — JSON round-trip."""

    def test_to_dict_all_fields(self) -> None:
        ctx = RecoveryContext(
            provider_list=["openai/gpt-4"],
            attempted_strategies=["auto_retry"],
            current_provider_index=1,
            retry_counts={"generate": 2},
            failed_stages=["chunk"],
            completed_stages=["parse"],
            partial_data={"key": "value"},
            events=[
                RecoveryEvent(
                    strategy_name="auto_retry",
                    stage_name="generate",
                    provider_name="openai/gpt-4",
                    attempt=1,
                    outcome=RecoveryOutcome.RESOLVED,
                    message="ok",
                    timestamp=1000.0,
                )
            ],
        )
        d = ctx.to_dict()
        assert d["provider_list"] == ["openai/gpt-4"]
        assert d["attempted_strategies"] == ["auto_retry"]
        assert d["current_provider_index"] == 1
        assert d["retry_counts"]["generate"] == 2
        assert d["failed_stages"] == ["chunk"]
        assert d["completed_stages"] == ["parse"]
        assert d["partial_data"]["key"] == "value"
        assert d["events"][0]["strategy_name"] == "auto_retry"
        assert d["events"][0]["outcome"] == "resolved"
        assert d["events"][0]["timestamp"] == 1000.0
        assert d["user_privacy_tier"] == PRIVACY_TIER_STRICT

    def test_from_dict_round_trip(self) -> None:
        ctx = RecoveryContext(
            provider_list=["openai/gpt-4"],
            attempted_strategies=["auto_retry"],
            events=[
                RecoveryEvent(
                    strategy_name="auto_retry",
                    stage_name="generate",
                    outcome=RecoveryOutcome.RESOLVED,
                )
            ],
        )
        d = ctx.to_dict()
        restored = RecoveryContext.from_dict(d)
        assert restored.provider_list == ctx.provider_list
        assert restored.attempted_strategies == ctx.attempted_strategies
        assert restored.current_provider_index == ctx.current_provider_index
        assert len(restored.events) == len(ctx.events)
        assert restored.events[0].strategy_name == ctx.events[0].strategy_name
        assert restored.events[0].outcome == ctx.events[0].outcome
        assert restored.user_privacy_tier == ctx.user_privacy_tier

    def test_to_dict_from_dict_empty(self) -> None:
        ctx = RecoveryContext()
        d = ctx.to_dict()
        restored = RecoveryContext.from_dict(d)
        assert restored.provider_list == []
        assert restored.events == []
        assert restored.degradation_action_index == 0

    def test_from_dict_defaults(self) -> None:
        restored = RecoveryContext.from_dict({})
        assert isinstance(restored, RecoveryContext)
        assert restored.provider_list == []
        assert restored.current_provider_index == 0
        assert restored.events == []
        assert restored.memory_threshold_bytes == 83_886_080

    def test_json_serializable(self) -> None:
        """to_dict() output must survive json.dumps/json.loads round-trip."""
        import json

        ctx = RecoveryContext(
            provider_list=["ollama/llama3.1"],
            events=[
                RecoveryEvent(
                    strategy_name="provider_fallback",
                    stage_name="generate",
                    outcome=RecoveryOutcome.ESCALATED,
                )
            ],
        )
        serialized = json.dumps(ctx.to_dict())
        deserialized = json.loads(serialized)
        restored = RecoveryContext.from_dict(deserialized)
        assert restored.provider_list == ["ollama/llama3.1"]
        assert restored.events[0].outcome == RecoveryOutcome.ESCALATED

    def test_from_dict_respects_timestamp(self) -> None:
        ctx = RecoveryContext(
            events=[
                RecoveryEvent(
                    strategy_name="auto_retry",
                    stage_name="generate",
                    timestamp=9999.0,
                )
            ],
        )
        d = ctx.to_dict()
        restored = RecoveryContext.from_dict(d)
        assert restored.events[0].timestamp == 9999.0


class TestRecoveryCoordinatorPersistence:
    """RecoveryCoordinator with db_path auto-saves context."""

    @pytest.mark.asyncio
    async def test_auto_save_after_pre_stage(self, tmp_path: Path) -> None:
        coordinator = RecoveryCoordinator(db_path=str(tmp_path / "recovery.db"))
        ctx = coordinator.create_context(provider_list=["openai/gpt-4"])
        await coordinator.evaluate_pre_stage("parse", critical=False, memory_bytes=0, ctx=ctx)
        loaded = coordinator.resume_context(coordinator._pipeline_id)
        assert loaded is not None

    @pytest.mark.asyncio
    async def test_auto_save_after_stage_failure(self, tmp_path: Path) -> None:
        coordinator = RecoveryCoordinator(db_path=str(tmp_path / "recovery.db"))
        ctx = RecoveryContext()
        await coordinator.handle_stage_failure(
            "chunk", "Chunking failed", {"partial": "data"}, ctx, critical=False
        )
        loaded = coordinator.resume_context(coordinator._pipeline_id)
        assert loaded is not None
        assert "stage_isolation" in loaded.attempted_strategies

    @pytest.mark.asyncio
    async def test_auto_save_after_gateway_failure(self, tmp_path: Path) -> None:
        coordinator = RecoveryCoordinator(db_path=str(tmp_path / "recovery.db"))
        ctx = RecoveryContext(provider_list=["openai/gpt-4", "ollama/llama3.1"])
        await coordinator.handle_gateway_failure(
            "openai/gpt-4",
            {"http_status": 503, "error_type": "retryable"},
            ctx,
            stage_name="generate",
        )
        loaded = coordinator.resume_context(coordinator._pipeline_id)
        assert loaded is not None
        assert len(loaded.events) > 0

    @pytest.mark.asyncio
    async def test_build_report_deletes_on_success(self, tmp_path: Path) -> None:
        from openreview_cli.storage.recovery import load_recovery_state

        coordinator = RecoveryCoordinator(db_path=str(tmp_path / "recovery.db"))
        ctx = RecoveryContext()
        await coordinator.handle_stage_failure(
            "chunk", "Chunking failed", {"partial": "data"}, ctx, critical=False
        )
        report = coordinator.build_report(ctx)
        # Should be deleted since it's not unrecoverable
        assert report.final_status != "unrecoverable"
        saved = load_recovery_state(tmp_path / "recovery.db", coordinator._pipeline_id)
        assert saved is None

    @pytest.mark.asyncio
    async def test_build_report_keeps_on_unrecoverable(self, tmp_path: Path) -> None:
        from openreview_cli.storage.recovery import load_recovery_state

        coordinator = RecoveryCoordinator(db_path=str(tmp_path / "recovery.db"))
        ctx = RecoveryContext()
        ctx.events.append(
            RecoveryEvent(
                strategy_name="user_guided_recovery",
                stage_name="parse",
                outcome=RecoveryOutcome.UNRECOVERABLE,
                message="All strategies exhausted",
            )
        )
        report = coordinator.build_report(ctx)
        assert report.final_status == "unrecoverable"
        saved = load_recovery_state(tmp_path / "recovery.db", coordinator._pipeline_id)
        # Should still exist since final_status is unrecoverable
        assert saved is not None

    def test_resume_context_no_db_path(self) -> None:
        coordinator = RecoveryCoordinator()
        result = coordinator.resume_context("test-pipeline")
        assert result is None

    @pytest.mark.asyncio
    async def test_resume_context_restores_external_state(self, tmp_path: Path) -> None:
        from openreview_cli.storage.recovery import save_recovery_state

        db_path = tmp_path / "recovery.db"
        coordinator = RecoveryCoordinator(db_path=str(db_path))
        original = RecoveryContext(
            provider_list=["openai/gpt-4"],
            attempted_strategies=["auto_retry"],
            failed_stages=["chunk"],
        )
        save_recovery_state(db_path, "external-pipeline", "parse", original)
        loaded = coordinator.resume_context("external-pipeline")
        assert loaded is not None
        assert loaded.provider_list == ["openai/gpt-4"]
        assert loaded.attempted_strategies == ["auto_retry"]
        assert loaded.failed_stages == ["chunk"]
