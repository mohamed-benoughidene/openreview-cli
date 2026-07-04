"""Unit tests for bilateral comparison data models.

Covers enum values, dataclass construction, defaults, computed properties,
validation, and worst-clause-wins logic.
"""

from datetime import UTC, datetime

import pytest

from openreview_cli.bilateral.models import (
    AlignmentPair,
    AlignmentTable,
    ComparisonReport,
    ComparisonSummary,
    DivergenceVerdict,
    MatchingMethod,
    PairedAssessment,
    RCBSFDimension,
)
from openreview_cli.parsing.models import Clause
from openreview_cli.review.colors import AssessmentColor
from openreview_cli.review.models import ClauseAssessment, DocMeta, Position, QAVerdict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_clause(clause_id: str = "c1", text: str = "Confidentiality clause text") -> Clause:
    """Create a minimal Clause for testing."""
    return Clause(
        id=clause_id,
        title="Confidentiality",
        text=text,
        level=1,
        parent_id=None,
        source_page=1,
        source_paragraph=None,
        source_span=(0, len(text)),
    )


def make_assessment(
    clause_id: str = "c1",
    position: Position = Position.ACCEPTABLE,
    confidence: float = 0.9,
) -> ClauseAssessment:
    """Create a minimal ClauseAssessment for testing."""
    return ClauseAssessment(
        clause_id=clause_id,
        clause_text="Some clause text",
        playbook_category="confidentiality-term",
        position=position,
        confidence=confidence,
        citation="text excerpt",
        qa_verdict=QAVerdict.agree,
        extraction_model="test-model",
        qa_model="test-model",
    )


def make_doc_meta(filename: str = "doc_a.pdf") -> DocMeta:
    """Create a minimal DocMeta for testing."""
    return DocMeta(
        filename=filename,
        page_count=10,
        clause_count=5,
        pii_stripped=True,
        parsed_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# RCBSFDimension
# ---------------------------------------------------------------------------


class TestRCBSFDimension:
    def test_all_values_present(self) -> None:
        expected = {"category", "location", "evidence", "issue", "suggestion", "no_divergence"}
        actual = {v.value for v in RCBSFDimension}
        assert actual == expected

    def test_no_divergence_not_counted_as_divergence(self) -> None:
        assert RCBSFDimension.no_divergence.value == "no_divergence"
        # no_divergence should not be treated as a divergence dimension
        divergence_dims = {
            RCBSFDimension.category,
            RCBSFDimension.location,
            RCBSFDimension.evidence,
            RCBSFDimension.issue,
            RCBSFDimension.suggestion,
        }
        assert RCBSFDimension.no_divergence not in divergence_dims


# ---------------------------------------------------------------------------
# MatchingMethod
# ---------------------------------------------------------------------------


class TestMatchingMethod:
    def test_all_values_present(self) -> None:
        expected = {"exact", "fuzzy", "positional"}
        actual = {v.value for v in MatchingMethod}
        assert actual == expected


# ---------------------------------------------------------------------------
# DivergenceVerdict
# ---------------------------------------------------------------------------


class TestDivergenceVerdict:
    def test_all_values_present(self) -> None:
        expected = {"divergent", "aligned", "uncertain"}
        actual = {v.value for v in DivergenceVerdict}
        assert actual == expected


# ---------------------------------------------------------------------------
# AlignmentPair
# ---------------------------------------------------------------------------


class TestAlignmentPair:
    def test_construction_with_valid_data(self) -> None:
        c_a = make_clause("a1", "Party A text")
        c_b = make_clause("b1", "Party B text")
        pair = AlignmentPair(
            pair_id="A0-B0",
            clause_a=c_a,
            clause_b=c_b,
            method=MatchingMethod.exact,
            score=1.0,
        )
        assert pair.pair_id == "A0-B0"
        assert pair.clause_a == c_a
        assert pair.clause_b == c_b
        assert pair.method == MatchingMethod.exact
        assert pair.score == 1.0

    def test_score_out_of_range_raises(self) -> None:
        c_a = make_clause("a1")
        c_b = make_clause("b1")
        with pytest.raises(ValueError, match="score"):
            AlignmentPair(
                pair_id="A0-B0",
                clause_a=c_a,
                clause_b=c_b,
                method=MatchingMethod.exact,
                score=1.5,
            )
        with pytest.raises(ValueError, match="score"):
            AlignmentPair(
                pair_id="A0-B0",
                clause_a=c_a,
                clause_b=c_b,
                method=MatchingMethod.exact,
                score=-0.1,
            )

    def test_zero_score_is_valid(self) -> None:
        c_a = make_clause()
        c_b = make_clause()
        pair = AlignmentPair(
            pair_id="A0-B0",
            clause_a=c_a,
            clause_b=c_b,
            method=MatchingMethod.positional,
            score=0.0,
        )
        assert pair.score == 0.0


# ---------------------------------------------------------------------------
# AlignmentTable
# ---------------------------------------------------------------------------


class TestAlignmentTable:
    def test_construction_with_valid_data(self) -> None:
        c_a = make_clause("a1")
        c_b = make_clause("b1")
        pair = AlignmentPair(
            pair_id="A0-B0",
            clause_a=c_a,
            clause_b=c_b,
            method=MatchingMethod.exact,
            score=1.0,
        )
        table = AlignmentTable(
            matched_pairs=[pair],
            unmatched_a=[],
            unmatched_b=[],
        )
        assert table.matched_count == 1
        assert table.alignment_method == "heading-cascade"

    def test_alignment_rate_all_matched(self) -> None:
        c_a1, c_b1 = make_clause("a1"), make_clause("b1")
        c_a2, c_b2 = make_clause("a2"), make_clause("b2")
        p1 = AlignmentPair("A0-B0", c_a1, c_b1, MatchingMethod.exact, 1.0)
        p2 = AlignmentPair("A1-B1", c_a2, c_b2, MatchingMethod.exact, 1.0)
        table = AlignmentTable(matched_pairs=[p1, p2], unmatched_a=[], unmatched_b=[])
        assert table.alignment_rate == 1.0

    def test_alignment_rate_with_unmatched(self) -> None:
        c_a1, c_b1 = make_clause("a1"), make_clause("b1")
        c_a2 = make_clause("a2")
        p1 = AlignmentPair("A0-B0", c_a1, c_b1, MatchingMethod.exact, 1.0)
        table = AlignmentTable(matched_pairs=[p1], unmatched_a=[c_a2], unmatched_b=[])
        # 2 matched + 1 unmatched_a = 3 total, 2/3 ≈ 0.666...
        assert table.alignment_rate == pytest.approx(2 / 3)

    def test_alignment_rate_empty(self) -> None:
        table = AlignmentTable(matched_pairs=[], unmatched_a=[], unmatched_b=[])
        assert table.alignment_rate == 0.0

    def test_alignment_rate_partial(self) -> None:
        c_a1, c_b1 = make_clause("a1"), make_clause("b1")
        c_a2, c_b2 = make_clause("a2"), make_clause("b2")
        c_a3 = make_clause("a3")
        c_b3 = make_clause("b3")
        p1 = AlignmentPair("A0-B0", c_a1, c_b1, MatchingMethod.exact, 1.0)
        p2 = AlignmentPair("A1-B1", c_a2, c_b2, MatchingMethod.exact, 1.0)
        table = AlignmentTable(
            matched_pairs=[p1, p2],
            unmatched_a=[c_a3],
            unmatched_b=[c_b3],
        )
        # 4 matched + 1 unma + 1 unb = 6 total, 4/6 ≈ 0.666...
        assert table.alignment_rate == pytest.approx(4 / 6)

    def test_default_alignment_method(self) -> None:
        table = AlignmentTable(matched_pairs=[], unmatched_a=[], unmatched_b=[])
        assert table.alignment_method == "heading-cascade"

    def test_custom_alignment_method(self) -> None:
        table = AlignmentTable(
            matched_pairs=[],
            unmatched_a=[],
            unmatched_b=[],
            alignment_method="embedding",
        )
        assert table.alignment_method == "embedding"


# ---------------------------------------------------------------------------
# PairedAssessment
# ---------------------------------------------------------------------------


class TestPairedAssessment:
    def test_construction_with_valid_data(self) -> None:
        c_a = make_clause("a1")
        c_b = make_clause("b1")
        pair = AlignmentPair("A0-B0", c_a, c_b, MatchingMethod.exact, 1.0)
        ass = PairedAssessment(
            pair_id="pair-001",
            alignment=pair,
            party_a_assessment=make_assessment("a1"),
            party_b_assessment=make_assessment("b1"),
            divergence=DivergenceVerdict.aligned,
        )
        assert ass.pair_id == "pair-001"
        assert ass.divergence == DivergenceVerdict.aligned
        assert ass.alignment_quality == 1.0  # default
        assert ass.color is None  # default
        assert ass.error is None  # default
        assert ass.rcbsf_details == {}  # default
        assert ass.primary_dimension is None  # default

    def test_with_divergence_detected(self) -> None:
        c_a = make_clause("a1")
        c_b = make_clause("b1")
        pair = AlignmentPair("A0-B0", c_a, c_b, MatchingMethod.exact, 1.0)
        ass = PairedAssessment(
            pair_id="pair-001",
            alignment=pair,
            party_a_assessment=make_assessment("a1"),
            party_b_assessment=make_assessment("b1"),
            divergence=DivergenceVerdict.divergent,
            primary_dimension=RCBSFDimension.evidence,
            rcbsf_details={RCBSFDimension.evidence: "Different evidentiary standards"},
        )
        assert ass.has_divergence is True
        assert ass.primary_dimension == RCBSFDimension.evidence
        assert ass.rcbsf_details[RCBSFDimension.evidence] == "Different evidentiary standards"

    def test_no_divergence(self) -> None:
        c_a = make_clause("a1")
        c_b = make_clause("b1")
        pair = AlignmentPair("A0-B0", c_a, c_b, MatchingMethod.exact, 1.0)
        ass = PairedAssessment(
            pair_id="pair-001",
            alignment=pair,
            party_a_assessment=make_assessment("a1"),
            party_b_assessment=make_assessment("b1"),
            divergence=DivergenceVerdict.aligned,
        )
        assert ass.has_divergence is False

    def test_alignment_quality_out_of_range_raises(self) -> None:
        c_a = make_clause()
        c_b = make_clause()
        pair = AlignmentPair("A0-B0", c_a, c_b, MatchingMethod.exact, 1.0)
        with pytest.raises(ValueError, match="alignment_quality"):
            PairedAssessment(
                pair_id="p1",
                alignment=pair,
                party_a_assessment=make_assessment(),
                party_b_assessment=make_assessment(),
                divergence=DivergenceVerdict.aligned,
                alignment_quality=1.5,
            )
        with pytest.raises(ValueError, match="alignment_quality"):
            PairedAssessment(
                pair_id="p1",
                alignment=pair,
                party_a_assessment=make_assessment(),
                party_b_assessment=make_assessment(),
                divergence=DivergenceVerdict.aligned,
                alignment_quality=-0.1,
            )

    def test_color_assignment(self) -> None:
        c_a = make_clause()
        c_b = make_clause()
        pair = AlignmentPair("A0-B0", c_a, c_b, MatchingMethod.exact, 1.0)
        ass = PairedAssessment(
            pair_id="p1",
            alignment=pair,
            party_a_assessment=make_assessment(),
            party_b_assessment=make_assessment(),
            divergence=DivergenceVerdict.divergent,
            color=AssessmentColor.red,
        )
        assert ass.color == AssessmentColor.red

    def test_error_field(self) -> None:
        c_a = make_clause()
        c_b = make_clause()
        pair = AlignmentPair("A0-B0", c_a, c_b, MatchingMethod.exact, 1.0)
        ass = PairedAssessment(
            pair_id="p1",
            alignment=pair,
            party_a_assessment=make_assessment(),
            party_b_assessment=make_assessment(),
            divergence=DivergenceVerdict.uncertain,
            error="Comparison agent failed",
        )
        assert ass.error == "Comparison agent failed"


# ---------------------------------------------------------------------------
# ComparisonSummary
# ---------------------------------------------------------------------------


class TestComparisonSummary:
    def test_defaults(self) -> None:
        s = ComparisonSummary()
        assert s.total_pairs == 0
        assert s.divergent_count == 0
        assert s.aligned_count == 0
        assert s.uncertain_count == 0
        assert s.green_count == 0
        assert s.amber_count == 0
        assert s.red_count == 0
        assert s.avg_alignment_quality == 0.0
        assert s.agreement_rate == 0.0
        assert s.overall_color == "green"

    def test_construction_with_values(self) -> None:
        s = ComparisonSummary(
            divergent_count=2,
            aligned_count=18,
            uncertain_count=0,
            green_count=16,
            amber_count=2,
            red_count=2,
            total_pairs=20,
            avg_alignment_quality=0.92,
            agreement_rate=0.8,
        )
        assert s.divergent_count == 2
        assert s.aligned_count == 18
        assert s.green_count == 16
        assert s.amber_count == 2
        assert s.red_count == 2
        assert s.total_pairs == 20
        assert s.agreement_rate == 0.8
        # overall_color is a computed property based on red_count > amber_count > green_count
        assert s.overall_color == "red"  # red_count=2 → overall=red

    def test_overall_color_worst_clause_wins_green(self) -> None:
        """All green → overall_color is green."""
        s = ComparisonSummary(
            green_count=10,
            amber_count=0,
            red_count=0,
            total_pairs=10,
        )
        assert s.overall_color == "green"

    def test_overall_color_worst_clause_wins_amber(self) -> None:
        """Any Amber (no Red) → overall_color is amber."""
        s = ComparisonSummary(
            green_count=8,
            amber_count=2,
            red_count=0,
            total_pairs=10,
        )
        assert s.overall_color == "amber"

    def test_overall_color_worst_clause_wins_red(self) -> None:
        """Any Red → overall_color is red (overrides Amber)."""
        s = ComparisonSummary(
            green_count=5,
            amber_count=3,
            red_count=2,
            total_pairs=10,
        )
        assert s.overall_color == "red"

    def test_overall_color_red_only(self) -> None:
        """All Red → overall_color is red."""
        s = ComparisonSummary(
            green_count=0,
            amber_count=0,
            red_count=5,
            total_pairs=5,
        )
        assert s.overall_color == "red"

    def test_overall_color_mixed_amber_red(self) -> None:
        """Red wins over Amber."""
        s = ComparisonSummary(
            green_count=0,
            amber_count=1,
            red_count=1,
            total_pairs=2,
        )
        assert s.overall_color == "red"


# ---------------------------------------------------------------------------
# ComparisonReport
# ---------------------------------------------------------------------------


class TestComparisonReport:
    def test_construction_with_valid_data(self) -> None:
        c_a = make_clause("a1")
        c_b = make_clause("b1")
        pair = AlignmentPair("A0-B0", c_a, c_b, MatchingMethod.exact, 1.0)
        table = AlignmentTable(matched_pairs=[pair], unmatched_a=[], unmatched_b=[])
        ass = PairedAssessment(
            pair_id="pair-001",
            alignment=pair,
            party_a_assessment=make_assessment("a1"),
            party_b_assessment=make_assessment("b1"),
            divergence=DivergenceVerdict.aligned,
        )
        summary = ComparisonSummary(
            total_pairs=1,
            aligned_count=1,
            green_count=1,
            agreement_rate=1.0,
        )
        now = datetime.now(UTC)
        report = ComparisonReport(
            document_a=make_doc_meta("doc_a.pdf"),
            document_b=make_doc_meta("doc_b.pdf"),
            alignment_table=table,
            assessments=[ass],
            summary=summary,
            playbook_id="precheck-nda-v1",
            generated_at=now,
        )
        assert report.experimental is True
        assert report.schema_version == "1.0.0"
        assert report.confidence_threshold == 0.7  # default
        assert report.playbook_id == "precheck-nda-v1"
        assert len(report.assessments) == 1

    def test_defaults(self) -> None:
        c_a = make_clause()
        c_b = make_clause()
        pair = AlignmentPair("A0-B0", c_a, c_b, MatchingMethod.exact, 1.0)
        table = AlignmentTable(matched_pairs=[pair], unmatched_a=[], unmatched_b=[])
        ass = PairedAssessment(
            pair_id="p1",
            alignment=pair,
            party_a_assessment=make_assessment(),
            party_b_assessment=make_assessment(),
            divergence=DivergenceVerdict.aligned,
        )
        summary = ComparisonSummary()
        now = datetime.now(UTC)
        report = ComparisonReport(
            document_a=make_doc_meta(),
            document_b=make_doc_meta(),
            alignment_table=table,
            assessments=[ass],
            summary=summary,
            playbook_id="test",
            generated_at=now,
        )
        assert report.experimental is True
        assert report.disclaimer == ""
        assert report.confidence_threshold == 0.7
        assert report.schema_version == "1.0.0"

    def test_custom_confidence_threshold(self) -> None:
        c_a = make_clause()
        c_b = make_clause()
        pair = AlignmentPair("A0-B0", c_a, c_b, MatchingMethod.exact, 1.0)
        table = AlignmentTable(matched_pairs=[pair], unmatched_a=[], unmatched_b=[])
        ass = PairedAssessment(
            pair_id="p1",
            alignment=pair,
            party_a_assessment=make_assessment(),
            party_b_assessment=make_assessment(),
            divergence=DivergenceVerdict.aligned,
        )
        summary = ComparisonSummary()
        report = ComparisonReport(
            document_a=make_doc_meta(),
            document_b=make_doc_meta(),
            alignment_table=table,
            assessments=[ass],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(UTC),
            confidence_threshold=0.85,
        )
        assert report.confidence_threshold == 0.85
