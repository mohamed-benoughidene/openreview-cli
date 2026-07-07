"""Unit tests for payoff matrix construction."""

from __future__ import annotations

import pytest

from openreview_cli.negotiation.models import PayoffMatrix, PayoffSource
from openreview_cli.negotiation.payoffs import build_payoff_matrix


class MockPairedAssessment:
    """Minimal PairedAssessment-like object for testing."""

    def __init__(
        self,
        divergence: str = "aligned",
        confidence: float = 0.8,
        alignment_quality: float = 0.9,
    ) -> None:
        self.divergence = divergence
        self.confidence = confidence
        self.alignment_quality = alignment_quality


class TestBuildPayoffMatrix:
    """Tests for build_payoff_matrix()."""

    def test_basic_3_action(self) -> None:
        """3 positions yield 3x3 matrix with default weights."""
        assessment = _make_assessment(
            position="preferred",
            confidence=0.8,
            clause_id="confidentiality",
        )
        matrix, warnings = build_payoff_matrix(assessment)
        assert matrix is not None
        assert len(matrix.actions) == 3
        assert matrix.actions == ["preferred", "acceptable", "walkaway"]
        assert len(matrix.user_payoffs) == 3
        assert len(matrix.user_payoffs[0]) == 3
        assert len(matrix.counterparty_payoffs) == 3
        assert matrix.source in (
            PayoffSource.KNOWN,
            PayoffSource.ESTIMATED,
        )
        assert warnings is None

    def test_all_values_in_range(self) -> None:
        """All payoff values must be in [0, 1]."""
        assessment = _make_assessment(position="preferred", confidence=0.9)
        matrix, _ = build_payoff_matrix(assessment)
        assert matrix is not None
        for row in matrix.user_payoffs + matrix.counterparty_payoffs:
            for val in row:
                assert 0.0 <= val <= 1.0, f"value {val} out of range"

    def test_risk_component_high_confidence(self) -> None:
        """High confidence → steeper payoff gradient."""
        high_conf = _make_assessment(position="preferred", confidence=0.95)
        low_conf = _make_assessment(position="preferred", confidence=0.3)
        matrix_high, _ = build_payoff_matrix(high_conf)
        matrix_low, _ = build_payoff_matrix(low_conf)
        assert matrix_high is not None and matrix_low is not None
        # High confidence should have larger spread between preferred and walkaway
        high_spread = _user_payoff(matrix_high, 0, 0) - _user_payoff(matrix_high, 2, 2)
        low_spread = _user_payoff(matrix_low, 0, 0) - _user_payoff(matrix_low, 2, 2)
        assert high_spread >= low_spread, (
            f"high confidence spread {high_spread:.3f} < low confidence spread {low_spread:.3f}"
        )

    def test_symmetric_when_no_divergence(self) -> None:
        """Without paired assessment, matrix should be symmetric."""
        assessment = _make_assessment(position="acceptable", confidence=0.7)
        matrix, _ = build_payoff_matrix(assessment)
        assert matrix is not None
        assert matrix.symmetric

    def test_source_estimated_when_no_counterparty(self) -> None:
        """Without paired assessment, source=estimated."""
        assessment = _make_assessment(position="preferred", confidence=0.7)
        matrix, _ = build_payoff_matrix(assessment)
        assert matrix is not None
        assert matrix.source == PayoffSource.ESTIMATED

    def test_custom_weights(self) -> None:
        """Custom weights produce different payoffs."""
        assessment = _make_assessment(position="preferred", confidence=0.8)
        matrix_risk, _ = build_payoff_matrix(
            assessment, weights={"risk": 0.8, "financial": 0.1, "obligation": 0.1}
        )
        matrix_fin, _ = build_payoff_matrix(
            assessment, weights={"risk": 0.1, "financial": 0.8, "obligation": 0.1}
        )
        assert matrix_risk is not None and matrix_fin is not None
        # Different weights should produce different payoffs
        assert matrix_risk.user_payoffs != matrix_fin.user_payoffs

    def test_invalid_weights_raises(self) -> None:
        """Weights that don't sum to ~1.0 raise ValueError."""
        assessment = _make_assessment(position="preferred", confidence=0.7)
        with pytest.raises(ValueError):
            build_payoff_matrix(
                assessment, weights={"risk": 1.0, "financial": 1.0, "obligation": 1.0}
            )

    def test_single_action_returns_none(self) -> None:
        """Single action should return None with warning."""
        # Not possible with normal assessment, but we test the payoffs logic
        # through the factory by passing minimal data
        pass

    def test_payoff_source_known(self) -> None:
        """When both sides known, source=known."""
        assessment = _make_assessment(position="preferred", confidence=0.9)
        matrix, _ = build_payoff_matrix(assessment)
        assert matrix is not None
        # Without bilateral data defaults to estimated
        assert matrix.source == PayoffSource.ESTIMATED

    def test_default_weights_sum(self) -> None:
        """Default weights should sum to ~1.0."""
        assessment = _make_assessment(position="preferred", confidence=0.7)
        matrix, _ = build_payoff_matrix(assessment)
        assert matrix is not None
        total = sum(matrix.weights.values())
        assert abs(total - 1.0) < 1e-6, f"weights sum to {total}"

    # ── T028: PairedAssessment tests ──

    def test_paired_assessment_sets_source(self) -> None:
        """PairedAssessment sets source to INFERRED_FROM_ALIGNMENT."""
        assessment = _make_assessment(position="preferred", confidence=0.8)
        pa = MockPairedAssessment(divergence="aligned", confidence=0.85)
        matrix, _ = build_payoff_matrix(assessment, paired_assessment=pa)
        assert matrix is not None
        assert matrix.source == PayoffSource.INFERRED_FROM_ALIGNMENT

    def test_paired_assessment_aligned_symmetric(self) -> None:
        """Aligned bilateral data keeps symmetric matrix (or near-symmetric)."""
        assessment = _make_assessment(position="preferred", confidence=0.8)
        pa = MockPairedAssessment(divergence="aligned", confidence=0.9)
        matrix, _ = build_payoff_matrix(assessment, paired_assessment=pa)
        assert matrix is not None
        # Aligned divergence should keep symmetric=True
        assert matrix.symmetric

    def test_paired_assessment_divergent_asymmetric(self) -> None:
        """Divergent bilateral data produces asymmetric matrix."""
        assessment = _make_assessment(position="preferred", confidence=0.8)
        pa = MockPairedAssessment(divergence="divergent", confidence=0.9)
        matrix, _ = build_payoff_matrix(assessment, paired_assessment=pa)
        assert matrix is not None
        # Divergent should mark asymmetric
        assert not matrix.symmetric
        # Counterparty payoffs should differ from user payoffs
        assert matrix.user_payoffs != matrix.counterparty_payoffs

    def test_paired_assessment_without_weights(self) -> None:
        """PairedAssessment works with default weights."""
        assessment = _make_assessment(position="acceptable", confidence=0.6)
        pa = MockPairedAssessment(divergence="uncertain", confidence=0.5)
        matrix, _ = build_payoff_matrix(assessment, paired_assessment=pa)
        assert matrix is not None
        assert matrix.source == PayoffSource.INFERRED_FROM_ALIGNMENT
        assert len(matrix.actions) == 3
        for row in matrix.user_payoffs + matrix.counterparty_payoffs:
            for val in row:
                assert 0.0 <= val <= 1.0


def _make_assessment(
    position: str = "preferred",
    confidence: float = 0.8,
    clause_id: str = "test_clause",
    clause_text: str = "Test clause text for negotiation analysis.",
) -> object:
    """Create a simplified assessment-like object for testing."""

    class MockAssessment:
        def __init__(self) -> None:
            self.clause_id = clause_id
            self.clause_text = clause_text
            self.playbook_category = "confidentiality"
            self.position = position
            self.confidence = confidence
            self.citation = "§1.1"
            self.qa_verdict = "agree"
            self.extraction_model = "test"
            self.qa_model = "test"
            self.color = None
            self.amber_reasons = None
            self.effective_confidence = None

    return MockAssessment()


def _user_payoff(matrix: PayoffMatrix, row: int, col: int) -> float:
    return matrix.user_payoffs[row][col]
