"""Unit tests for report formatting (terminal + JSON output)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Position,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
)
from openreview_cli.review.report import format_json, format_terminal


def _make_assessment(cid: str, pos: Position, conf: float, amber: bool = False) -> ClauseAssessment:
    ca = ClauseAssessment(
        clause_id=cid,
        clause_text=f"Clause {cid} text that is reasonably long enough to appear in reports.",
        playbook_category="confidentiality-term",
        position=pos,
        confidence=conf,
        citation=f"clause {cid} citation",
        qa_verdict=QAVerdict.agree,
        extraction_model="m1",
        qa_model="m1",
    )
    if amber:
        ca.is_amber = True
    return ca


def _make_report(assessments: list[ClauseAssessment] | None = None) -> ReviewReport:
    if assessments is None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.92),
            _make_assessment("c2", Position.ACCEPTABLE, 0.85),
            _make_assessment("c3", Position.WALKAWAY, 0.72, amber=True),
            _make_assessment("c4", Position.UNCERTAIN, 0.45, amber=True),
        ]
    dm = DocMeta(
        filename="nda.docx",
        page_count=12,
        clause_count=len(assessments),
        pii_stripped=True,
    )
    summary = ReviewSummary(
        preferred_count=sum(1 for a in assessments if a.position == Position.PREFERRED),
        acceptable_count=sum(1 for a in assessments if a.position == Position.ACCEPTABLE),
        walkaway_count=sum(1 for a in assessments if a.position == Position.WALKAWAY),
        uncertain_count=sum(1 for a in assessments if a.position == Position.UNCERTAIN),
        no_match_count=0,
        amber_count=sum(1 for a in assessments if a.is_amber),
        avg_confidence=sum(a.confidence for a in assessments) / max(len(assessments), 1),
    )
    return ReviewReport(
        document=dm,
        assessments=assessments,
        summary=summary,
        playbook_id="precheck-nda-v1",
        generated_at=datetime.now(UTC),
    )


class TestFormatTerminal:
    def test_output_is_string(self) -> None:
        report = _make_report()
        output = format_terminal(report)
        assert isinstance(output, str)
        assert len(output) > 100

    def test_contains_document_info(self) -> None:
        report = _make_report()
        output = format_terminal(report)
        assert "nda.docx" in output
        assert "12 pages" in output
        assert "precheck-nda-v1" in output

    def test_contains_summary(self) -> None:
        report = _make_report()
        output = format_terminal(report)
        assert "Preferred" in output
        assert "Acceptable" in output
        assert "Walkaway" in output
        assert "Uncertain" in output
        assert "Amber" in output

    def test_contains_assessment_positions(self) -> None:
        report = _make_report()
        output = format_terminal(report)
        assert "PREFERRED" in output.upper()
        assert "ACCEPTABLE" in output.upper()
        assert "WALKAWAY" in output.upper()
        assert "UNCERTAIN" in output.upper()

    def test_amber_highlighted(self) -> None:
        """Amber clauses should have a visual indicator."""
        report = _make_report()
        output = format_terminal(report)
        assert "⚠" in output or "amber" in output.lower() or "!" in output

    def test_empty_assessments(self) -> None:
        report = _make_report([])
        output = format_terminal(report)
        assert "0" in output  # summary shows zeros

    def test_summary_counts_match(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.9),
            _make_assessment("c2", Position.ACCEPTABLE, 0.8),
            _make_assessment("c3", Position.WALKAWAY, 0.7),
            _make_assessment("c4", Position.UNCERTAIN, 0.3),
        ]
        report = _make_report(assessments)
        output = format_terminal(report)
        assert "1" in output  # preferred count


class TestFormatJson:
    def test_output_is_valid_json(self) -> None:
        report = _make_report()
        output = format_json(report)
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_schema_version_present(self) -> None:
        report = _make_report()
        data = json.loads(format_json(report))
        assert data["schema_version"] == "1.1.0"

    def test_document_metadata_included(self) -> None:
        report = _make_report()
        data = json.loads(format_json(report))
        assert data["document"]["filename"] == "nda.docx"
        assert data["document"]["page_count"] == 12
        assert data["document"]["pii_stripped"] is True

    def test_assessments_array_included(self) -> None:
        report = _make_report()
        data = json.loads(format_json(report))
        assert len(data["assessments"]) == 4
        first = data["assessments"][0]
        assert "clause_id" in first
        assert "position" in first
        assert "confidence" in first
        assert "citation" in first
        assert "is_amber" in first

    def test_summary_counts_are_consistent(self) -> None:
        report = _make_report()
        data = json.loads(format_json(report))
        n_assessments = len(data["assessments"])
        total_from_summary = (
            data["summary"]["preferred_count"]
            + data["summary"]["acceptable_count"]
            + data["summary"]["walkaway_count"]
            + data["summary"]["uncertain_count"]
            + data["summary"]["no_match_count"]
        )
        assert total_from_summary == n_assessments

    def test_empty_assessments_json(self) -> None:
        report = _make_report([])
        data = json.loads(format_json(report))
        assert data["assessments"] == []
        assert data["summary"]["preferred_count"] == 0

    def test_batch_format(self) -> None:
        """Batch reports as a list of ReviewReports should produce a JSON array."""
        report1 = _make_report()
        report2 = _make_report()
        output = format_json([report1, report2])
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 2
