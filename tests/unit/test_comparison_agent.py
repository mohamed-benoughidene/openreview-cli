"""Unit tests for ComparisonAgent — bilateral PAKTON architecture.

Test order per D-12 spec:
1. Two identical contracts → all equivalent (no false mismatches)
2. Two contracts differing in position → flags contradiction at right clause
3. No clause alignment possible → empty diff, no crash
"""

from openreview_cli.review.comparison_agent import (
    ComparisonAgent,
    ComparisonReport,
    DivergenceType,
)
from openreview_cli.review.models import ClauseAssessment, Position, QAVerdict


def _make_assessment(
    clause_id: str,
    category: str,
    position: Position = Position.PREFERRED,
    confidence: float = 0.9,
    citation: str = "§1.1 test clause",
) -> ClauseAssessment:
    """Helper to build a ClauseAssessment for testing."""
    return ClauseAssessment(
        clause_id=clause_id,
        clause_text=f"Text for {category}",
        playbook_category=category,
        position=position,
        confidence=confidence,
        citation=citation,
        qa_verdict=QAVerdict.agree,
        extraction_model="test",
        qa_model="test",
    )


class TestComparisonAgent:
    """Suite: ComparisonAgent comparison pipeline."""

    def test_identical_contracts_all_equivalent(self) -> None:
        """Test 1: Two identical clause sets → all equivalent, no false mismatches."""
        assessments_a = [
            _make_assessment("1", "confidentiality"),
            _make_assessment("2", "term"),
            _make_assessment("3", "governing_law"),
        ]
        assessments_b = [
            _make_assessment("1", "confidentiality"),
            _make_assessment("2", "term"),
            _make_assessment("3", "governing_law"),
        ]

        agent = ComparisonAgent()
        report = agent.compare(assessments_a, assessments_b)

        assert isinstance(report, ComparisonReport)
        assert report.summary is not None
        assert report.summary.total_pairs == 3
        assert report.summary.divergences == 0
        assert report.summary.green_count == 3
        assert report.summary.overall_color == "green"
        assert report.summary.agreement_rate == 1.0

        # Every assessment must be equivalent
        for pa in report.assessments:
            assert pa.divergence == DivergenceType.EQUIVALENT, (
                f"Expected equivalent for {pa.clause_heading}, got {pa.divergence}"
            )
            assert pa.color == "green"

    def test_differing_position_flags_contradiction(self) -> None:
        """Test 2: Contracts differing in governing_law position → 1 contradiction."""
        assessments_a = [
            _make_assessment("1", "confidentiality", Position.PREFERRED),
            _make_assessment("2", "term", Position.ACCEPTABLE),
            _make_assessment(
                "3",
                "governing_law",
                Position.PREFERRED,
            ),
        ]
        assessments_b = [
            _make_assessment("1", "confidentiality", Position.PREFERRED),
            _make_assessment("2", "term", Position.ACCEPTABLE),
            _make_assessment(
                "3",
                "governing_law",
                Position.WALKAWAY,
                citation="§5.0 different law",
            ),
        ]

        agent = ComparisonAgent()
        report = agent.compare(assessments_a, assessments_b)

        assert report.summary is not None
        assert report.summary.total_pairs == 3
        assert report.summary.divergences == 1
        assert "governing_law" in (
            a.clause_heading
            for a in report.assessments
            if a.divergence == DivergenceType.CONTRADICTION
        )

        # Find the governing_law pair
        gl = next(a for a in report.assessments if a.clause_heading == "governing_law")
        assert gl.divergence == DivergenceType.CONTRADICTION
        assert gl.confidence == 0.8
        assert gl.color == "red"
        assert len(gl.citations) == 2
        assert any("walkaway" in c for c in gl.citations)

    def test_no_alignment_possible_empty_diff(self) -> None:
        """Test 3: Completely different categories → no crash, empty diff."""
        assessments_a = [
            _make_assessment("1", "confidentiality"),
            _make_assessment("2", "indemnification"),
        ]
        assessments_b = [
            _make_assessment("3", "governing_law"),
            _make_assessment("4", "arbitration"),
        ]

        agent = ComparisonAgent()
        report = agent.compare(assessments_a, assessments_b)

        assert report.summary is not None
        # All pairs are additions (each side has clauses the other doesn't)
        assert report.summary.total_pairs == 4
        assert report.summary.divergences == 4
        assert report.summary.divergences_by_type.get("addition", 0) == 4
        # No crash is the main assertion
        assert isinstance(report.assessments, list)

    def test_empty_assessment_lists_returns_empty_report(self) -> None:
        """Edge case: both lists empty → empty report, no crash."""
        agent = ComparisonAgent()
        report = agent.compare([], [])
        assert report.summary is not None
        assert report.summary.total_pairs == 0
        assert report.summary.divergences == 0
        assert isinstance(report.assessments, list)
        assert len(report.assessments) == 0
