"""Unit tests for bilateral report formatting (terminal + JSON output)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

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


def make_clause(clause_id: str = "c1", title: str = "Test", text: str = "Test clause") -> Clause:
    return Clause(
        id=clause_id,
        title=title,
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
    confidence: float = 0.85,
) -> ClauseAssessment:
    return ClauseAssessment(
        clause_id=clause_id,
        clause_text="Test clause text",
        playbook_category="test-cat",
        position=position,
        confidence=confidence,
        citation="test excerpt",
        qa_verdict=QAVerdict.agree,
        extraction_model="test-model",
        qa_model="test-model",
    )


def make_alignment_pair(
    pair_id: str = "A0-B0",
    clause_a: Clause | None = None,
    clause_b: Clause | None = None,
) -> AlignmentPair:
    ca = clause_a or make_clause("a1", title="Confidentiality", text="Party A clause")
    cb = clause_b or make_clause("b1", title="Confidentiality", text="Party B clause")
    return AlignmentPair(
        pair_id=pair_id,
        clause_a=ca,
        clause_b=cb,
        method=MatchingMethod.exact,
        score=1.0,
    )


def make_paired_assessment(
    pair_id: str = "pair-001",
    divergence: DivergenceVerdict = DivergenceVerdict.aligned,
    confidence: float = 0.85,
    color: AssessmentColor | None = None,
) -> PairedAssessment:
    alignment = make_alignment_pair(pair_id=f"A0-B0-{pair_id}")
    ass_a = make_assessment("a1")
    ass_b = make_assessment("b1")
    return PairedAssessment(
        pair_id=pair_id,
        alignment=alignment,
        party_a_assessment=ass_a,
        party_b_assessment=ass_b,
        divergence=divergence,
        confidence=confidence,
        color=color,
    )


def make_report(
    assessments: list[PairedAssessment] | None = None,
    verbose: bool = False,
) -> ComparisonReport:
    if assessments is None:
        assessments = [
            make_paired_assessment(
                "pair-001", DivergenceVerdict.aligned, 0.92, AssessmentColor.green
            ),
            make_paired_assessment(
                "pair-002", DivergenceVerdict.divergent, 0.82, AssessmentColor.red
            ),
            make_paired_assessment(
                "pair-003", DivergenceVerdict.uncertain, 0.55, AssessmentColor.amber
            ),
        ]

    dm_a = DocMeta(
        filename="party_a.pdf",
        page_count=12,
        clause_count=28,
        pii_stripped=True,
        parsed_at=datetime.now(UTC),
    )
    dm_b = DocMeta(
        filename="party_b.pdf",
        page_count=15,
        clause_count=30,
        pii_stripped=True,
        parsed_at=datetime.now(UTC),
    )

    alignment_table = AlignmentTable(
        matched_pairs=[make_alignment_pair()],
        unmatched_a=[make_clause("a-u1", title="Indemnification")],
        unmatched_b=[
            make_clause("b-u1", title="Force Majeure"),
            make_clause("b-u2", title="Assignment"),
        ],
    )

    summary = ComparisonSummary(
        total_pairs=len(assessments),
        divergent_count=sum(1 for a in assessments if a.has_divergence),
        aligned_count=sum(1 for a in assessments if a.divergence == DivergenceVerdict.aligned),
        uncertain_count=sum(1 for a in assessments if a.divergence == DivergenceVerdict.uncertain),
        green_count=sum(1 for a in assessments if a.color == AssessmentColor.green),
        amber_count=sum(1 for a in assessments if a.color == AssessmentColor.amber),
        red_count=sum(1 for a in assessments if a.color == AssessmentColor.red),
        avg_alignment_quality=sum(a.alignment_quality for a in assessments)
        / max(len(assessments), 1),
        agreement_rate=sum(1 for a in assessments if not a.has_divergence)
        / max(len(assessments), 1),
    )

    return ComparisonReport(
        document_a=dm_a,
        document_b=dm_b,
        alignment_table=alignment_table,
        assessments=assessments,
        summary=summary,
        playbook_id="precheck-nda-v1",
        generated_at=datetime.now(UTC),
        confidence_threshold=0.7,
    )


# ---------------------------------------------------------------------------
# Terminal output tests
# ---------------------------------------------------------------------------


class TestFormatTerminal:
    """Tests for format_comparison_terminal()."""

    def test_output_is_string(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_terminal

        report = make_report()
        output = format_comparison_terminal(report)
        assert isinstance(output, str)
        assert len(output) > 100

    def test_contains_disclaimer(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_terminal

        report = make_report()
        output = format_comparison_terminal(report)
        assert "EXPERIMENTAL" in output
        assert "64%" in output

    def test_contains_document_info(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_terminal

        report = make_report()
        output = format_comparison_terminal(report)
        assert "party_a.pdf" in output
        assert "party_b.pdf" in output

    def test_contains_per_pair_table(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_terminal

        report = make_report()
        output = format_comparison_terminal(report)
        assert "pair-001" in output or "Green" in output
        assert "Red" in output
        assert "Amber" in output

    def test_contains_unmatched_section(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_terminal

        report = make_report()
        output = format_comparison_terminal(report)
        assert "Unmatched" in output

    def test_contains_summary(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_terminal

        report = make_report()
        output = format_comparison_terminal(report)
        assert "Summary" in output or "Agreement" in output
        assert "Green" in output
        assert "Amber" in output
        assert "Red" in output

    def test_color_badges_rendered(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_terminal

        report = make_report()
        output = format_comparison_terminal(report)
        # Green, Red, Amber should all appear as Rich-style markup or text
        assert "green" in output.lower() or "OK" in output
        assert "red" in output.lower() or "RED" in output
        assert "amber" in output.lower() or "AMBER" in output


class TestFormatTerminalVerbose:
    """Tests for verbose mode output."""

    def test_verbose_shows_rcbsf_dimensions(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_terminal

        # Create a report with RCBSF details
        assessments = [
            make_paired_assessment(
                "pair-001", DivergenceVerdict.divergent, 0.82, AssessmentColor.red
            ),
        ]
        assessments[0].primary_dimension = RCBSFDimension.evidence
        assessments[0].rcbsf_details = {RCBSFDimension.evidence: "Different evidentiary standard"}
        assessments[0].rationale = "Party A uses 'reasonable efforts', Party B uses 'best efforts'"
        assessments[0].citations = ["Party A: 'reasonable efforts'", "Party B: 'best efforts'"]
        report = make_report(assessments)
        output = format_comparison_terminal(report, verbose=True)
        assert "evidence" in output.lower()
        assert "reasonable" in output.lower()

    def test_verbose_shows_alignment_quality(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_terminal

        report = make_report()
        output = format_comparison_terminal(report, verbose=True)
        assert "alignment" in output.lower()


# ---------------------------------------------------------------------------
# JSON output tests
# ---------------------------------------------------------------------------


class TestFormatJson:
    """Tests for format_comparison_json()."""

    def test_output_is_valid_json(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_json

        report = make_report()
        output = format_comparison_json(report)
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_contains_schema_version(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_json

        report = make_report()
        data = json.loads(format_comparison_json(report))
        assert data["schema_version"] == "1.0.0"

    def test_contains_disclaimer(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_json

        report = make_report()
        data = json.loads(format_comparison_json(report))
        assert data["experimental"] is True
        assert "disclaimer" in data

    def test_contains_document_info(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_json

        report = make_report()
        data = json.loads(format_comparison_json(report))
        assert "document_a" in data
        assert "document_b" in data
        assert data["document_a"]["filename"] == "party_a.pdf"
        assert data["document_b"]["filename"] == "party_b.pdf"

    def test_contains_assessments(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_json

        report = make_report()
        data = json.loads(format_comparison_json(report))
        assert len(data["assessments"]) == 3

    def test_assessment_includes_alignment_quality(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_json

        report = make_report()
        data = json.loads(format_comparison_json(report))
        for ass in data["assessments"]:
            assert "alignment_quality" in ass

    def test_contains_summary(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_json

        report = make_report()
        data = json.loads(format_comparison_json(report))
        assert "summary" in data
        assert "agreement_rate" in data["summary"]
        assert "green_count" in data["summary"]

    def test_empty_assessments(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_json

        report = make_report([])
        data = json.loads(format_comparison_json(report))
        assert data["assessments"] == []
        assert data["summary"]["total_pairs"] == 0


class TestFormatTerminalEmpty:
    """Tests for empty comparison output."""

    def test_empty_assessments_returns_valid_output(self) -> None:
        from openreview_cli.bilateral.report import format_comparison_terminal

        report = make_report([])
        output = format_comparison_terminal(report)
        assert isinstance(output, str)
        assert len(output) > 50


# ---------------------------------------------------------------------------
# Graceful None handling
# ---------------------------------------------------------------------------


class TestNoneFields:
    """Graceful handling of None fields in PairedAssessment."""

    def test_none_color_is_assigned_by_safety_net(self) -> None:
        from openreview_cli.bilateral.report import (
            format_comparison_json,
            format_comparison_terminal,
        )

        pa = make_paired_assessment("pair-001", DivergenceVerdict.aligned, 0.9, color=None)
        report = make_report([pa])
        term_out = format_comparison_terminal(report)
        assert isinstance(term_out, str)
        # Safety net in formatters assigns colors when None
        assert pa.color is not None  # mutated in place
        json_out = format_comparison_json(report)
        data = json.loads(json_out)
        # Color should be assigned (not None) by the safety net
        assert data["assessments"][0]["color"] in ("green", "amber", "red")


# ---------------------------------------------------------------------------
# compute_summary tests
# ---------------------------------------------------------------------------


class TestComputeSummary:
    """Tests for compute_summary()."""

    def test_counts_green_amber_red(self) -> None:
        from openreview_cli.bilateral.report import compute_summary

        assessments = [
            make_paired_assessment("p1", DivergenceVerdict.aligned, 0.9, AssessmentColor.green),
            make_paired_assessment("p2", DivergenceVerdict.divergent, 0.8, AssessmentColor.red),
            make_paired_assessment("p3", DivergenceVerdict.uncertain, 0.5, AssessmentColor.amber),
        ]
        summary = compute_summary(assessments)
        assert summary.green_count == 1
        assert summary.red_count == 1
        assert summary.amber_count == 1
        assert summary.total_pairs == 3

    def test_agreement_rate(self) -> None:
        from openreview_cli.bilateral.report import compute_summary

        assessments = [
            make_paired_assessment("p1", DivergenceVerdict.aligned, 0.9, AssessmentColor.green),
            make_paired_assessment("p2", DivergenceVerdict.divergent, 0.8, AssessmentColor.red),
        ]
        summary = compute_summary(assessments)
        assert summary.agreement_rate == 0.5

    def test_avg_alignment_quality(self) -> None:
        from openreview_cli.bilateral.report import compute_summary

        assessments = [
            make_paired_assessment("p1", DivergenceVerdict.aligned, 0.9, AssessmentColor.green),
            make_paired_assessment("p2", DivergenceVerdict.divergent, 0.8, AssessmentColor.red),
        ]
        assessments[0].alignment_quality = 1.0
        assessments[1].alignment_quality = 0.5
        summary = compute_summary(assessments)
        assert summary.avg_alignment_quality == 0.75

    def test_divergent_aligned_uncertain_counts(self) -> None:
        from openreview_cli.bilateral.report import compute_summary

        assessments = [
            make_paired_assessment("p1", DivergenceVerdict.aligned, 0.9, AssessmentColor.green),
            make_paired_assessment("p2", DivergenceVerdict.divergent, 0.8, AssessmentColor.red),
            make_paired_assessment("p3", DivergenceVerdict.uncertain, 0.5, AssessmentColor.amber),
        ]
        summary = compute_summary(assessments)
        assert summary.aligned_count == 1
        assert summary.divergent_count == 1
        assert summary.uncertain_count == 1

    def test_overall_color_worst_clause_wins(self) -> None:
        from openreview_cli.bilateral.report import compute_summary

        # Red wins over Amber
        assessments = [
            make_paired_assessment("p1", DivergenceVerdict.aligned, 0.9, AssessmentColor.green),
            make_paired_assessment("p2", DivergenceVerdict.divergent, 0.8, AssessmentColor.red),
            make_paired_assessment("p3", DivergenceVerdict.uncertain, 0.5, AssessmentColor.amber),
        ]
        summary = compute_summary(assessments)
        assert summary.overall_color == "red"

    def test_overall_color_amber_wins_no_red(self) -> None:
        from openreview_cli.bilateral.report import compute_summary

        assessments = [
            make_paired_assessment("p1", DivergenceVerdict.aligned, 0.9, AssessmentColor.green),
            make_paired_assessment("p2", DivergenceVerdict.uncertain, 0.5, AssessmentColor.amber),
        ]
        summary = compute_summary(assessments)
        assert summary.overall_color == "amber"

    def test_overall_color_green_when_all_green(self) -> None:
        from openreview_cli.bilateral.report import compute_summary

        assessments = [
            make_paired_assessment("p1", DivergenceVerdict.aligned, 0.9, AssessmentColor.green),
            make_paired_assessment("p2", DivergenceVerdict.aligned, 0.9, AssessmentColor.green),
        ]
        summary = compute_summary(assessments)
        assert summary.overall_color == "green"

    def test_color_not_set_defaults_to_no_color(self) -> None:
        from openreview_cli.bilateral.report import compute_summary

        assessments = [
            make_paired_assessment("p1", DivergenceVerdict.aligned, 0.9, color=None),
        ]
        summary = compute_summary(assessments)
        assert summary.green_count == 0
        assert summary.amber_count == 0
        assert summary.red_count == 0

    def test_empty_assessments(self) -> None:
        from openreview_cli.bilateral.report import compute_summary

        summary = compute_summary([])
        assert summary.total_pairs == 0
        assert summary.green_count == 0
        assert summary.agreement_rate == 0.0
