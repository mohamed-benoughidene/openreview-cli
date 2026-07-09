"""Integration tests for D-31: Persistent recovery state save/load across coordinator instances."""

from pathlib import Path

import pytest

from openreview_cli.recovery.coordinator import RecoveryCoordinator
from openreview_cli.recovery.models import (
    RecoveryContext,
    RecoveryEvent,
    RecoveryOutcome,
)
from openreview_cli.storage.database import load_recovery_state, save_recovery_state


class TestRecoveryPersistenceIntegration:
    """Save mid-pipeline, fresh coordinator, resume_context() — state matches."""

    @pytest.mark.asyncio
    async def test_save_mid_pipeline_resume_new_coordinator(self, tmp_path: Path) -> None:
        """Save state during pipeline, create fresh coordinator, resume, verify."""
        db_path = tmp_path / "recovery.db"

        # --- first coordinator: save mid-pipeline state ---
        c1 = RecoveryCoordinator(db_path=str(db_path))
        ctx = RecoveryContext(
            provider_list=["openai/gpt-4", "ollama/llama3.1"],
            attempted_strategies=["auto_retry"],
            current_provider_index=1,
            retry_counts={"generate": 2},
            failed_stages=["chunk"],
            completed_stages=["parse"],
            partial_data={"key": "value"},
            events=[
                RecoveryEvent(
                    strategy_name="provider_fallback",
                    stage_name="generate",
                    outcome=RecoveryOutcome.RESOLVED,
                )
            ],
        )
        # Simulate mid-pipeline save via coordinator's internal persist
        c1._persist_context("generate", ctx)
        pipeline_id = c1._pipeline_id

        # --- second coordinator: fresh instance, resume from DB ---
        c2 = RecoveryCoordinator(db_path=str(db_path))
        loaded = c2.resume_context(pipeline_id)
        assert loaded is not None

        # Verify full state matches
        assert loaded.provider_list == ["openai/gpt-4", "ollama/llama3.1"]
        assert loaded.attempted_strategies == ["auto_retry"]
        assert loaded.current_provider_index == 1
        assert loaded.retry_counts == {"generate": 2}
        assert loaded.failed_stages == ["chunk"]
        assert loaded.completed_stages == ["parse"]
        assert loaded.partial_data == {"key": "value"}
        assert len(loaded.events) == 1
        assert loaded.events[0].strategy_name == "provider_fallback"
        assert loaded.events[0].outcome == RecoveryOutcome.RESOLVED

    @pytest.mark.asyncio
    async def test_save_via_stage_failure_then_resume(self, tmp_path: Path) -> None:
        """Persist via handle_stage_failure, fresh coordinator resumes."""
        db_path = tmp_path / "recovery.db"
        c1 = RecoveryCoordinator(db_path=str(db_path))
        ctx = RecoveryContext(provider_list=["openai/gpt-4"])
        await c1.handle_stage_failure(
            "chunk", "Chunking failed", {"partial": "data"}, ctx, critical=False
        )
        pipeline_id = c1._pipeline_id

        c2 = RecoveryCoordinator(db_path=str(db_path))
        loaded = c2.resume_context(pipeline_id)
        assert loaded is not None
        # stage_isolation should have added event + attempted_strategies
        assert "stage_isolation" in loaded.attempted_strategies
        assert len(loaded.events) > 0

    def test_save_and_load_direct(self, tmp_path: Path) -> None:
        """Direct save/load via database functions — verifies round-trip."""
        db_path = tmp_path / "recovery.db"
        ctx = RecoveryContext(
            provider_list=["openai/gpt-4"],
            attempted_strategies=["auto_retry"],
        )
        save_recovery_state(db_path, "direct-pipeline", "test", ctx)
        loaded = load_recovery_state(db_path, "direct-pipeline")
        assert loaded is not None
        assert loaded.provider_list == ["openai/gpt-4"]
        assert loaded.attempted_strategies == ["auto_retry"]
