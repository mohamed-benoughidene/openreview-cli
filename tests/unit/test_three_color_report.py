"""Unit tests for three-color terminal and JSON report formatting."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from openreview_cli.review.colors import AssessmentColor, assign_colors
from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Position,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
)
from openreview_cli.review.report import format_json, format_terminal


def _make_assessment(
    cid: str,
    pos: Position,
    conf: float,
    amber: bool = False,
    error: str | None = None,
    qa_verdict: QAVerdict = QAVerdict.agree,
) -> ClauseAssessment:
    ca = ClauseAssessment(
        clause_id=cid,
        clause_text=f"Clause {cid} text that is reasonably long enough to appear in reports.",
        playbook_category="confidentiality-term",
        position=pos,
        confidence=conf,
        citation=f"clause {cid} citation",
        qa_verdict=qa_verdict,
        extraction_model="m1",
        qa_model="m1",
        error=error,
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
    green_count = sum(1 for a in assessments if a.color == AssessmentColor.green)
    red_count = sum(1 for a in assessments if a.color == AssessmentColor.red)
    valid_conf = [
        a.effective_confidence
        for a in assessments
        if a.effective_confidence is not None and a.playbook_category != "no-match"
    ]
    avg_effective_confidence = sum(valid_conf) / len(valid_conf) if valid_conf else 0.0
    summary = ReviewSummary(
        preferred_count=sum(1 for a in assessments if a.position == Position.PREFERRED),
        acceptable_count=sum(1 for a in assessments if a.position == Position.ACCEPTABLE),
        walkaway_count=sum(1 for a in assessments if a.position == Position.WALKAWAY),
        uncertain_count=sum(1 for a in assessments if a.position == Position.UNCERTAIN),
        no_match_count=0,
        green_count=green_count,
        red_count=red_count,
        amber_count=sum(1 for a in assessments if a.color == AssessmentColor.amber),
        avg_confidence=sum(a.confidence for a in assessments) / max(len(assessments), 1),
        avg_effective_confidence=avg_effective_confidence,
    )
    return ReviewReport(
        document=dm,
        assessments=assessments,
        summary=summary,
        playbook_id="precheck-nda-v1",
        generated_at=datetime.now(UTC),
    )


class TestFormatTerminalThreeColor:
    def test_green_assessment_shows_green_badge(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.92),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        output = format_terminal(report)
        assert "● OK" in output

    def test_amber_assessment_shows_amber_badge(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.45),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        output = format_terminal(report)
        assert "⚠" in output
        assert "AMBER" in output

    def test_red_assessment_shows_red_badge(self) -> None:
        assessments = [
            _make_assessment("c1", Position.WALKAWAY, 0.92),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        output = format_terminal(report)
        assert "● RED" in output

    def test_amber_reason_breakdown_shown(self) -> None:
        assessments = [
            _make_assessment(
                "c1",
                Position.PREFERRED,
                0.45,
                qa_verdict=QAVerdict.disagree,
            ),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        output = format_terminal(report)
        assert "low_confidence" in output or "Low confidence" in output
        assert (
            "Qa Disagreement" in output
            or "qa_disagreement" in output
            or "QA disagreement" in output
        )

    def test_multiple_amber_reasons_together(self) -> None:
        assessments = [
            _make_assessment(
                "c1",
                Position.PREFERRED,
                0.3,
                error="LLM error",
                qa_verdict=QAVerdict.disagree,
            ),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        output = format_terminal(report)
        assert "Error" in output
        assert "low_confidence" in output or "Low confidence" in output

    def test_green_assessment_no_amber_reasons_in_output(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.92),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        output = format_terminal(report)
        assert "● OK" in output

    def test_summary_shows_green_amber_red_counts(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.92),
            _make_assessment("c2", Position.ACCEPTABLE, 0.85),
            _make_assessment("c3", Position.WALKAWAY, 0.95),
            _make_assessment("c4", Position.PREFERRED, 0.45),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        output = format_terminal(report)
        assert "Green:" in output
        assert "Amber:" in output
        assert "Red:" in output

    def test_summary_shows_avg_effective_confidence(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.92),
            _make_assessment("c2", Position.ACCEPTABLE, 0.85),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        output = format_terminal(report)
        assert "Avg effective confidence" in output

    def test_summary_shows_confidence_threshold(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.92),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        output = format_terminal(report)
        assert "Confidence threshold: 0.7" in output or "Confidence threshold" in output

    def test_backward_compat_amber_flags_still_present(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.45),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        output = format_terminal(report)
        assert "Amber flags" in output

    def test_empty_assessments(self) -> None:
        report = _make_report([])
        output = format_terminal(report)
        assert "No clauses to assess" in output

    def test_no_grounding_no_grounding_triggers(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.92),
            _make_assessment("c2", Position.PREFERRED, 0.3),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        output = format_terminal(report)
        assert "grounding" not in output.lower()


class TestFormatJsonThreeColor:
    def test_assessment_has_color_field(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.92),
            _make_assessment("c2", Position.PREFERRED, 0.3),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        data = json.loads(format_json(report))
        assert data["assessments"][0]["color"] == "green"
        assert data["assessments"][1]["color"] == "amber"

    def test_assessment_has_amber_reasons_field(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.92),
            _make_assessment("c2", Position.PREFERRED, 0.3),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        data = json.loads(format_json(report))
        assert data["assessments"][0]["amber_reasons"] == []
        assert data["assessments"][1]["amber_reasons"] == ["low_confidence"]

    def test_assessment_has_effective_confidence_field(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.92),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        data = json.loads(format_json(report))
        assert data["assessments"][0]["effective_confidence"] == 0.92

    def test_report_has_confidence_threshold(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.92),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        data = json.loads(format_json(report))
        assert "confidence_threshold" in data
        assert data["confidence_threshold"] == 0.7

    def test_summary_has_green_red_avg_effective_counts(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.92),
            _make_assessment("c2", Position.ACCEPTABLE, 0.85),
            _make_assessment("c3", Position.WALKAWAY, 0.95),
            _make_assessment("c4", Position.PREFERRED, 0.45),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        data = json.loads(format_json(report))
        assert data["summary"]["green_count"] == 2
        assert data["summary"]["red_count"] == 1
        assert isinstance(data["summary"]["avg_effective_confidence"], float)

    def test_backward_compat_amber_count_present(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.3),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        data = json.loads(format_json(report))
        assert "amber_count" in data["summary"]

    def test_schema_version_1_1_0(self) -> None:
        report = _make_report()
        data = json.loads(format_json(report))
        assert data["schema_version"] == "1.1.0"

    def test_is_amber_consistent_with_color(self) -> None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.92),
            _make_assessment("c2", Position.PREFERRED, 0.3),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        data = json.loads(format_json(report))
        assert data["assessments"][0]["is_amber"] is False
        assert data["assessments"][0]["color"] == "green"
        assert data["assessments"][1]["is_amber"] is True
        assert data["assessments"][1]["color"] == "amber"

    def test_json_output_is_valid_json(self) -> None:
        report = _make_report()
        output = format_json(report)
        data = json.loads(output)
        assert isinstance(data, dict)
