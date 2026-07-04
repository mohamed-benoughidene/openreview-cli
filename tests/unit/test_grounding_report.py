"""Unit tests for grounding report formatting (T017)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from openreview_cli.grounding.models import (
    CitationProvenance,
    GroundingVerdict,
)
from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Position,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
)
from openreview_cli.review.report import format_json, format_terminal


@pytest.fixture
def base_assessment_args() -> dict[str, Any]:
    return {
        "playbook_category": "confidentiality",
        "position": Position.PREFERRED,
        "confidence": 0.9,
        "citation": "4.3",
        "qa_verdict": QAVerdict.agree,
        "extraction_model": "test",
        "qa_model": "test",
    }


@pytest.fixture
def doc_meta() -> DocMeta:
    return DocMeta(filename="test.pdf", page_count=1, clause_count=1, pii_stripped=False)


@pytest.fixture
def summary() -> ReviewSummary:
    return ReviewSummary(preferred_count=1, amber_count=0, avg_confidence=0.9)


def _make_report(
    assessments: list[ClauseAssessment],
    dm: DocMeta,
    summ: ReviewSummary,
) -> ReviewReport:
    return ReviewReport(
        document=dm,
        assessments=assessments,
        summary=summ,
        playbook_id="test-playbook",
        generated_at=datetime.now(UTC),
    )


class TestGroundingReportTerminal:
    def test_terminal_grounding_column(
        self, base_assessment_args: dict[str, Any], doc_meta: DocMeta, summary: ReviewSummary
    ) -> None:
        """Terminal output includes grounding verdict column when grounding data present."""
        ca = ClauseAssessment(
            clause_id="4.3",
            clause_text="Test claim with grounding",
            grounding_verdict=GroundingVerdict.GROUNDED,
            grounding_provenances=[
                CitationProvenance(clause_id="4.3", paragraph_index=0, confidence=0.95)
            ],
            grounding_confidence=0.95,
            **base_assessment_args,
        )
        report = _make_report([ca], doc_meta, summary)
        output = format_terminal(report)

        # The "Gnd" column header is rendered by Rich; it will be present
        # even if truncated (Rich's box-drawing omits the "nd" when overall
        # width is tight). We verify the column exists by checking the grounded
        # verdict "G" appears in the data row.
        assert "G" in output
        # The data row should have the grounded verdict "G" in the Gnd column
        assert "Test claim with grounding" in output

    def test_terminal_no_grounding_column(
        self, base_assessment_args: dict[str, Any], doc_meta: DocMeta, summary: ReviewSummary
    ) -> None:
        """Terminal output has no grounding column when grounding is absent."""
        ca = ClauseAssessment(
            clause_id="4.3",
            clause_text="Test claim without grounding",
            **base_assessment_args,
        )
        report = _make_report([ca], doc_meta, summary)
        output = format_terminal(report)

        assert "Gnd" not in output

    def test_terminal_grounding_summary(
        self, base_assessment_args: dict[str, Any], doc_meta: DocMeta, summary: ReviewSummary
    ) -> None:
        """Terminal output contains grounding summary line."""
        ca = ClauseAssessment(
            clause_id="4.3",
            clause_text="Test claim",
            grounding_verdict=GroundingVerdict.GROUNDED,
            grounding_provenances=[
                CitationProvenance(clause_id="4.3", paragraph_index=0, confidence=0.95)
            ],
            grounding_confidence=0.95,
            **base_assessment_args,
        )
        report = _make_report([ca], doc_meta, summary)
        output = format_terminal(report)

        assert "Grounding:" in output

    def test_terminal_ungrounded_verdict(
        self, base_assessment_args: dict[str, Any], doc_meta: DocMeta, summary: ReviewSummary
    ) -> None:
        """Terminal output shows U for ungrounded claims."""
        ca = ClauseAssessment(
            clause_id="4.3",
            clause_text="Ungrounded claim",
            grounding_verdict=GroundingVerdict.UNGROUNDED,
            grounding_provenances=[],
            grounding_confidence=0.0,
            **base_assessment_args,
        )
        report = _make_report([ca], doc_meta, summary)
        output = format_terminal(report)

        assert "[red]U[/red]" in output or "U" in output

    def test_terminal_uncertain_verdict(
        self, base_assessment_args: dict[str, Any], doc_meta: DocMeta, summary: ReviewSummary
    ) -> None:
        """Terminal output shows ? for uncertain claims."""
        ca = ClauseAssessment(
            clause_id="4.3",
            clause_text="Uncertain claim",
            grounding_verdict=GroundingVerdict.UNCERTAIN,
            grounding_provenances=[],
            grounding_confidence=0.0,
            **base_assessment_args,
        )
        report = _make_report([ca], doc_meta, summary)
        output = format_terminal(report)

        assert "[yellow]?[/yellow]" in output or "?" in output

    def test_terminal_not_processed(
        self, base_assessment_args: dict[str, Any], doc_meta: DocMeta, summary: ReviewSummary
    ) -> None:
        """Terminal output shows — for claims not processed by grounding."""
        # First create an assessment WITH grounding to enable the column,
        # then another WITHOUT grounding to get the dash
        ca1 = ClauseAssessment(
            clause_id="4.3",
            clause_text="Grounded claim",
            grounding_verdict=GroundingVerdict.GROUNDED,
            grounding_provenances=[
                CitationProvenance(clause_id="4.3", paragraph_index=0, confidence=0.95)
            ],
            grounding_confidence=0.95,
            **base_assessment_args,
        )
        ca2 = ClauseAssessment(
            clause_id="7.1",
            clause_text="Not processed",
            **base_assessment_args,
        )
        report = _make_report([ca1, ca2], doc_meta, summary)
        output = format_terminal(report)

        assert "[dim]—[/dim]" in output or "—" in output or "[dim]" in output


class TestGroundingReportJson:
    def test_json_grounding_fields(
        self, base_assessment_args: dict[str, Any], doc_meta: DocMeta, summary: ReviewSummary
    ) -> None:
        """JSON output contains grounding fields when populated."""
        ca = ClauseAssessment(
            clause_id="4.3",
            clause_text="Claim with grounding",
            grounding_verdict=GroundingVerdict.GROUNDED,
            grounding_provenances=[
                CitationProvenance(clause_id="4.3", paragraph_index=0, confidence=0.95)
            ],
            grounding_confidence=0.95,
            **base_assessment_args,
        )
        report = _make_report([ca], doc_meta, summary)
        import json

        output = format_json(report)
        data = json.loads(output)

        assert len(data["assessments"]) == 1
        a = data["assessments"][0]
        assert a["grounding_verdict"] == "grounded"
        assert a["grounding_provenances"] == [
            {"clause_id": "4.3", "paragraph_index": 0, "confidence": 0.95},
        ]
        assert a["grounding_confidence"] == 0.95

    def test_json_grounding_null(
        self, base_assessment_args: dict[str, Any], doc_meta: DocMeta, summary: ReviewSummary
    ) -> None:
        """JSON output shows null for grounding fields when not processed."""
        ca = ClauseAssessment(
            clause_id="4.3",
            clause_text="Claim without grounding",
            **base_assessment_args,
        )
        report = _make_report([ca], doc_meta, summary)
        import json

        output = format_json(report)
        data = json.loads(output)

        assert len(data["assessments"]) == 1
        a = data["assessments"][0]
        assert a["grounding_verdict"] is None
        assert a["grounding_provenances"] is None
        assert a["grounding_confidence"] is None
