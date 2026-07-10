"""Integration tests for bilateral PAKTON command wiring.

Tests that run_bilateral_comparison correctly:
- Wires ComparisonAgent between two PAKTON runs
- Returns ComparisonReport with assessments and summary
- Handles errors gracefully
"""

from unittest.mock import patch

import pytest

from openreview_cli.review.comparison_agent import ComparisonReport, DivergenceType
from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Position,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
)

# ── Helpers ──

FAKE_DOCMETA = DocMeta(
    filename="test.pdf",
    page_count=5,
    clause_count=3,
    pii_stripped=False,
)


def _make_assessment(
    clause_id: str,
    category: str,
    position: Position = Position.PREFERRED,
) -> ClauseAssessment:
    return ClauseAssessment(
        clause_id=clause_id,
        clause_text=f"Text for {category}",
        playbook_category=category,
        position=position,
        confidence=0.9,
        citation=f"§1.{clause_id}",
        qa_verdict=QAVerdict.agree,
        extraction_model="test",
        qa_model="test",
    )


def _fake_review(assessments: list[ClauseAssessment]) -> list[ReviewReport]:
    return [
        ReviewReport(
            document=FAKE_DOCMETA,
            assessments=assessments,
            summary=ReviewSummary(),
            playbook_id="test-nda-v1",
            generated_at=__import__("datetime").datetime.now(),
        )
    ]


# ── Tests ──


class TestBilateralCommand:
    @pytest.mark.integration
    def test_bilateral_wires_agent_correctly(self) -> None:
        """Mock two PAKTON runs → ComparisonAgent produces correct report."""
        identical_a = [
            _make_assessment("1", "confidentiality", Position.PREFERRED),
            _make_assessment("2", "term", Position.ACCEPTABLE),
        ]
        identical_b = [
            _make_assessment("1", "confidentiality", Position.PREFERRED),
            _make_assessment("2", "term", Position.ACCEPTABLE),
        ]

        with (
            patch(
                "openreview_cli.review.run_review",
                side_effect=[_fake_review(identical_a), _fake_review(identical_b)],
            ),
        ):
            from openreview_cli.review.base import run_bilateral_comparison

            # Act
            report = run_bilateral_comparison(
                doc_a_path="/fake/a.pdf",
                doc_b_path="/fake/b.pdf",
                no_pii=True,
            )

            # Assert
            assert isinstance(report, ComparisonReport)
            assert report.summary is not None
            assert report.summary.total_pairs == 2
            assert report.summary.divergences == 0
            assert report.summary.green_count == 2
            assert report.summary.overall_color == "green"
            assert report.experimental is True
            assert "EXPERIMENTAL" in report.disclaimer

    @pytest.mark.integration
    def test_bilateral_detects_contradiction(self) -> None:
        """Different positions across documents → contradiction flagged."""
        a_assessments = [
            _make_assessment("1", "confidentiality", Position.PREFERRED),
            _make_assessment("2", "term", Position.ACCEPTABLE),
        ]
        b_assessments = [
            _make_assessment("1", "confidentiality", Position.WALKAWAY),
            _make_assessment("2", "term", Position.ACCEPTABLE),
        ]

        with (
            patch(
                "openreview_cli.review.run_review",
                side_effect=[_fake_review(a_assessments), _fake_review(b_assessments)],
            ),
        ):
            from openreview_cli.review.base import run_bilateral_comparison

            report = run_bilateral_comparison(
                doc_a_path="/fake/a.pdf",
                doc_b_path="/fake/b.pdf",
                no_pii=True,
            )

            assert report.summary is not None
            assert report.summary.divergences == 1

            # confidentiality should be contradiction
            pa = next(a for a in report.assessments if a.clause_heading == "confidentiality")
            assert pa.divergence == DivergenceType.CONTRADICTION
            assert pa.color == "red"

    @pytest.mark.integration
    def test_bilateral_no_assessments_does_not_crash(self) -> None:
        """Both documents yield empty assessment lists → empty report."""
        with (
            patch(
                "openreview_cli.review.run_review",
                side_effect=[_fake_review([]), _fake_review([])],
            ),
        ):
            from openreview_cli.review.base import run_bilateral_comparison

            report = run_bilateral_comparison(
                doc_a_path="/fake/a.pdf",
                doc_b_path="/fake/b.pdf",
                no_pii=True,
            )

            assert report.summary is not None
            assert report.summary.total_pairs == 0
            assert report.summary.divergences == 0
            # No crash trumps all
