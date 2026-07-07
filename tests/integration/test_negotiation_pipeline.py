"""Integration tests for the negotiation pipeline."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from openreview_cli.negotiation.models import (
    NegotiationReport,
    NegotiationSummary,
    PayoffMatrix,
    PayoffSource,
)
from openreview_cli.negotiation.payoffs import build_payoff_matrix
from openreview_cli.negotiation.recommend import build_recommendation
from openreview_cli.negotiation.report import format_json, format_terminal
from openreview_cli.negotiation.solvers import solve_level_k, solve_nash, solve_qre
from openreview_cli.review.extraction import match_category
from openreview_cli.review.models import Position
from openreview_cli.review.playbook import load_playbook


class TestNegotiationPipeline:
    """End-to-end test of the negotiation pipeline with mocked data."""

    @pytest.fixture
    def sample_assessment(self) -> object:
        """Create a sample assessment for testing."""

        class MockAssessment:
            clause_id = "confidentiality"
            clause_text = "Both parties agree to maintain confidentiality."
            playbook_category = "confidentiality"
            position = "preferred"
            confidence = 0.85
            citation = "§1"
            qa_verdict = "agree"
            extraction_model = "test"
            qa_model = "test"
            color = None
            amber_reasons = None
            effective_confidence = None

        return MockAssessment()

    def test_full_pipeline_qre(self, sample_assessment: object) -> None:
        """Full pipeline with QRE solver produces valid report."""
        matrix, _ = build_payoff_matrix(sample_assessment)
        assert matrix is not None

        A = matrix.user_payoffs
        B = matrix.counterparty_payoffs

        user_strat, cp_strat, eq_type = solve_qre(A, B, lam=1.0)

        strategy = build_recommendation(
            user_strategy=user_strat,
            counterparty_strategy=cp_strat,
            matrix=matrix,
            eq_type=eq_type,
            model="qre",
            model_params={"lambda": 1.0},
            confidence_threshold=0.7,
        )

        assert strategy.clause_id == "confidentiality"
        assert strategy.model == "qre"
        assert len(strategy.user_strategy) == 3
        assert abs(sum(strategy.user_strategy) - 1.0) < 1e-6
        assert "sign" not in strategy.suggested_counteroffer.lower()
        assert "reject" not in strategy.suggested_counteroffer.lower()

    def test_full_pipeline_nash(self, sample_assessment: object) -> None:
        """Full pipeline with Nash solver."""
        matrix, _ = build_payoff_matrix(sample_assessment)
        assert matrix is not None

        user_strat, cp_strat, eq_type, is_fb = solve_nash(
            matrix.user_payoffs, matrix.counterparty_payoffs
        )

        strategy = build_recommendation(
            user_strategy=user_strat,
            counterparty_strategy=cp_strat,
            matrix=matrix,
            eq_type=eq_type,
            model="nash",
            confidence_threshold=0.7,
            is_fallback=is_fb,
        )

        assert strategy.equilibrium_type in ("pure", "mixed", "multiple")
        assert "Consider" in strategy.suggested_counteroffer

    def test_full_pipeline_level_k(self, sample_assessment: object) -> None:
        """Full pipeline with Level-k solver."""
        matrix, _ = build_payoff_matrix(sample_assessment)
        assert matrix is not None

        user_strat, cp_strat, eq_type = solve_level_k(
            matrix.user_payoffs, matrix.counterparty_payoffs, k=2
        )

        strategy = build_recommendation(
            user_strategy=user_strat,
            counterparty_strategy=cp_strat,
            matrix=matrix,
            eq_type=eq_type,
            model="level_k",
            model_params={"k": 2.0},
            confidence_threshold=0.7,
        )

        assert strategy.model == "level_k"
        assert "Consider" in strategy.suggested_counteroffer

    def test_json_output_contract(self, sample_assessment: object) -> None:
        """JSON output matches expected schema."""
        matrix, _ = build_payoff_matrix(sample_assessment)
        assert matrix is not None

        user_strat, cp_strat, eq_type = solve_qre(
            matrix.user_payoffs, matrix.counterparty_payoffs, lam=1.0
        )
        strategy = build_recommendation(
            user_strategy=user_strat,
            counterparty_strategy=cp_strat,
            matrix=matrix,
            eq_type=eq_type,
            model="qre",
            model_params={"lambda": 1.0},
            confidence_threshold=0.7,
        )

        now = datetime.now(UTC)
        summary = NegotiationSummary(
            total_clauses=1,
            equilibrium_distribution={eq_type: 1},
            amber_count=1 if strategy.is_amber else 0,
            avg_confidence=strategy.confidence,
            impasse_count=0,
            deadlock_risk=False,
        )
        report = NegotiationReport(
            strategies=[strategy],
            payoff_matrices=[matrix],
            summary=summary,
            playbook_id="test-nda",
            generated_at=now,
            confidence_threshold=0.7,
            schema_version="0.1.0",
        )

        json_str = format_json(report)
        data = json.loads(json_str)

        assert "experimental" in data
        assert data["experimental"] is True
        assert "disclaimer" in data
        assert "advisory" in data["disclaimer"]
        assert "strategies" in data
        assert len(data["strategies"]) == 1
        assert "payoff_matrices" in data
        assert data["schema_version"] == "0.1.0"

    def test_terminal_output_format(self, sample_assessment: object) -> None:
        """Terminal output renders without errors."""
        matrix, _ = build_payoff_matrix(sample_assessment)
        assert matrix is not None

        user_strat, cp_strat, eq_type = solve_qre(
            matrix.user_payoffs, matrix.counterparty_payoffs, lam=1.0
        )
        strategy = build_recommendation(
            user_strategy=user_strat,
            counterparty_strategy=cp_strat,
            matrix=matrix,
            eq_type=eq_type,
            model="qre",
            model_params={"lambda": 1.0},
            confidence_threshold=0.7,
        )

        now = datetime.now(UTC)
        summary = NegotiationSummary(
            total_clauses=1,
            equilibrium_distribution={eq_type: 1},
            amber_count=0,
            avg_confidence=0.8,
            impasse_count=0,
            deadlock_risk=False,
        )
        report = NegotiationReport(
            strategies=[strategy],
            payoff_matrices=[matrix],
            summary=summary,
            playbook_id="test-nda",
            generated_at=now,
            confidence_threshold=0.7,
        )

        output = format_terminal(report)
        assert "EXPERIMENTAL" in output
        assert "advisory" in output
        assert strategy.clause_id in output

    def test_no_positions_found(self) -> None:
        """Empty report when no assessments."""
        now = datetime.now(UTC)
        report = NegotiationReport(
            strategies=[],
            payoff_matrices=[],
            summary=NegotiationSummary(),
            playbook_id="test",
            generated_at=now,
        )
        output = format_terminal(report)
        assert "No clauses" in output

    def test_cross_reference_alignment(self) -> None:
        """Cross-reference note populated when source is inferred_from_alignment."""
        matrix = PayoffMatrix(
            clause_id="test",
            actions=["preferred", "acceptable", "walkaway"],
            user_payoffs=[[0.9, 0.5, 0.1], [0.6, 0.4, 0.2], [0.2, 0.1, 0.0]],
            counterparty_payoffs=[[0.1, 0.5, 0.9], [0.2, 0.4, 0.6], [0.0, 0.1, 0.2]],
            symmetric=False,
            source=PayoffSource.INFERRED_FROM_ALIGNMENT,
            weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
        )
        strategy = build_recommendation(
            user_strategy=[0.6, 0.3, 0.1],
            counterparty_strategy=[0.2, 0.5, 0.3],
            matrix=matrix,
            eq_type="mixed",
            model="qre",
            model_params={"lambda": 1.0},
            confidence_threshold=0.7,
        )
        assert strategy.diverges_from_alignment
        assert "diverges" in strategy.cross_reference_note.lower()

    def test_impasse_scenario(self) -> None:
        """Clause at impasse produces deadlock warning."""
        matrix = PayoffMatrix(
            clause_id="test",
            actions=["preferred", "acceptable", "walkaway"],
            user_payoffs=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            counterparty_payoffs=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            symmetric=True,
            source=PayoffSource.KNOWN,
            weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
        )
        strategy = build_recommendation(
            user_strategy=[0.0, 0.0, 1.0],
            counterparty_strategy=[0.0, 0.0, 1.0],
            matrix=matrix,
            eq_type="pure",
            model="nash",
            confidence_threshold=0.7,
        )
        assert "impasse" in strategy.predicted_outcome.lower()
        assert strategy.is_amber


class TestWhatIfParameters:
    """Tests for what-if parameter variation (US3)."""

    @pytest.fixture
    def sample_assessment(self) -> object:
        class MockAssessment:
            clause_id = "test"
            clause_text = "Test clause"
            playbook_category = "confidentiality"
            position = "preferred"
            confidence = 0.8
            citation = "§1"
            qa_verdict = "agree"
            extraction_model = "test"
            qa_model = "test"
            color = None
            amber_reasons = None
            effective_confidence = None

        return MockAssessment()

    def test_different_weights_different_output(self, sample_assessment: object) -> None:
        """Different weights produce different payoff matrices."""
        matrix_balanced, _ = build_payoff_matrix(sample_assessment)
        matrix_risk, _ = build_payoff_matrix(
            sample_assessment, weights={"risk": 0.7, "financial": 0.15, "obligation": 0.15}
        )
        assert matrix_balanced is not None and matrix_risk is not None
        assert matrix_balanced.user_payoffs != matrix_risk.user_payoffs

    def test_different_rationality_different_output(self, sample_assessment: object) -> None:
        """Different λ values shift QRE output."""
        matrix, _ = build_payoff_matrix(sample_assessment)
        assert matrix is not None
        A, B = matrix.user_payoffs, matrix.counterparty_payoffs

        strat_low, _, _ = solve_qre(A, B, lam=0.1)
        strat_high, _, _ = solve_qre(A, B, lam=10.0)

        # Lower rationality → more uniform, higher → more decisive
        low_entropy = -sum(p * np.log(p + 1e-10) for p in strat_low)
        high_entropy = -sum(p * np.log(p + 1e-10) for p in strat_high)
        assert low_entropy >= high_entropy  # less rational = more uniform

    def test_different_k_different_output(self, sample_assessment: object) -> None:
        """Different k values shift Level-k output."""
        matrix, _ = build_payoff_matrix(sample_assessment)
        assert matrix is not None
        A, B = matrix.user_payoffs, matrix.counterparty_payoffs

        strat_k0, _, _ = solve_level_k(A, B, k=0)
        strat_k2, _, _ = solve_level_k(A, B, k=2)

        # k=0 is uniform, k=2 should be more decisive
        k0_entropy = -sum(p * np.log(p + 1e-10) for p in strat_k0)
        k2_entropy = -sum(p * np.log(p + 1e-10) for p in strat_k2)
        assert k0_entropy >= k2_entropy

    def test_deterministic_repeatability(self, sample_assessment: object) -> None:
        """Same params produce identical output."""
        matrix, _ = build_payoff_matrix(sample_assessment)
        assert matrix is not None
        A, B = matrix.user_payoffs, matrix.counterparty_payoffs

        strat_a, _, _ = solve_qre(A, B, lam=1.0)
        strat_b, _, _ = solve_qre(A, B, lam=1.0)

        np.testing.assert_array_almost_equal(strat_a, strat_b)


class TestPlaybookPositionExtraction:
    """Tests for playbook-based position extraction in negotiate CLI (T029)."""

    @pytest.fixture
    def fixtures_dir(self) -> Path:
        return Path(__file__).parent.parent / "fixtures" / "negotiation"

    def test_playbook_full_positions_match_category(self, fixtures_dir: Path) -> None:
        """Full playbook: match_category assigns category from heading."""
        pb_path = fixtures_dir / "full-playbook.yaml"
        if not pb_path.exists():
            pytest.skip("full-playbook.yaml fixture not found")

        playbook = load_playbook(pb_path)
        cat = match_category("Confidentiality", playbook)
        assert cat is not None
        assert cat.default_position in (Position.PREFERRED, Position.ACCEPTABLE, Position.WALKAWAY)
        assert cat.id == "confidentiality"

    def test_playbook_partial_no_match(self, fixtures_dir: Path) -> None:
        """Partial playbook: unmatched heading returns None."""
        pb_path = fixtures_dir / "partial-playbook.yaml"
        if not pb_path.exists():
            pytest.skip("partial-playbook.yaml fixture not found")

        playbook = load_playbook(pb_path)
        cat = match_category("NonExistentClause", playbook)
        assert cat is None

    def test_different_playbooks_different_positions(self, fixtures_dir: Path) -> None:
        """Different playbook fixtures produce different position mappings."""
        full_path = fixtures_dir / "full-playbook.yaml"
        partial_path = fixtures_dir / "partial-playbook.yaml"
        if not full_path.exists() or not partial_path.exists():
            pytest.skip("playbook fixtures not found")

        pb_full = load_playbook(full_path)
        pb_partial = load_playbook(partial_path)

        # Match same heading against both playbooks
        cat_full = match_category("Confidentiality", pb_full)
        cat_partial = match_category("Confidentiality", pb_partial)

        # Both playbooks have confidentiality category
        assert cat_full is not None
        assert cat_partial is not None
        # Position from full playbook should be defined
        assert cat_full.default_position in (
            Position.PREFERRED,
            Position.ACCEPTABLE,
            Position.WALKAWAY,
        )
        # Full playbook has more categories than partial
        assert len(pb_full.categories) > len(pb_partial.categories)
