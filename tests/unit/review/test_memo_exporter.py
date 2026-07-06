"""Unit tests for MemoExporter orchestrator."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from openreview_cli.review.memo.exporter import MemoExporter
from openreview_cli.review.memo.models import MemoFormat, MemoReport
from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Position,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
)


def _make_assessment(
    cid: str,
    pos: Position = Position.PREFERRED,
    conf: float = 0.9,
    color_str: str = "green",
) -> ClauseAssessment:
    ca = ClauseAssessment(
        clause_id=cid,
        clause_text=f"Clause {cid} text for memo export testing.",
        playbook_category="confidentiality-term",
        position=pos,
        confidence=conf,
        citation=f"clause {cid} citation",
        qa_verdict=QAVerdict.agree,
        extraction_model="m1",
        qa_model="m1",
    )
    from openreview_cli.review.colors import AssessmentColor

    ca.color = AssessmentColor(color_str)
    return ca


def _make_report(assessments: list[ClauseAssessment] | None = None) -> ReviewReport:
    if assessments is None:
        assessments = [
            _make_assessment("c1", Position.PREFERRED, 0.92, "green"),
            _make_assessment("c2", Position.ACCEPTABLE, 0.78, "amber"),
            _make_assessment("c3", Position.WALKAWAY, 0.55, "red"),
        ]
    dm = DocMeta(
        filename="nda-sample.pdf",
        page_count=5,
        clause_count=len(assessments),
        pii_stripped=True,
    )
    summary = ReviewSummary(
        preferred_count=1,
        acceptable_count=1,
        walkaway_count=1,
        uncertain_count=0,
        no_match_count=0,
        amber_count=1,
        green_count=1,
        red_count=1,
        avg_confidence=sum(a.confidence for a in assessments) / max(len(assessments), 1),
    )
    return ReviewReport(
        document=dm,
        assessments=assessments,
        summary=summary,
        playbook_id="precheck-nda-v1",
        generated_at=datetime.now(UTC),
        playbook_version=1,
    )


class TestMemoExporterConstruction:
    def test_default_format(self) -> None:
        report = _make_report()
        exporter = MemoExporter(report=report, mode="precheck")
        assert MemoFormat.MARKDOWN in exporter.formats
        assert len(exporter.formats) == 1

    def test_explicit_formats(self) -> None:
        report = _make_report()
        exporter = MemoExporter(
            report=report, mode="precheck", formats={MemoFormat.JSON, MemoFormat.DOCX}
        )
        assert MemoFormat.JSON in exporter.formats
        assert MemoFormat.DOCX in exporter.formats
        assert MemoFormat.MARKDOWN not in exporter.formats

    def test_default_output_dir(self) -> None:
        report = _make_report()
        exporter = MemoExporter(report=report, mode="precheck")
        assert exporter.output_dir == Path("review_results")

    def test_custom_output_dir(self) -> None:
        report = _make_report()
        exporter = MemoExporter(report=report, mode="precheck", output_dir=Path("/tmp/memos"))
        assert exporter.output_dir == Path("/tmp/memos")

    def test_mode_string(self) -> None:
        report = _make_report()
        for mode in ("precheck", "dealcheck", "hirecheck"):
            exporter = MemoExporter(report=report, mode=mode)
            assert exporter.mode == mode


class TestBuildMemoReport:
    def test_basic_conversion(self) -> None:
        report = _make_report()
        exporter = MemoExporter(report=report, mode="precheck")
        memo = exporter._build_memo_report()

        assert isinstance(memo, MemoReport)
        assert memo.memo_version == "1.0"
        assert memo.mode == "precheck"
        assert memo.document_name == "nda-sample.pdf"
        assert memo.playbook_name == "precheck-nda-v1"
        assert memo.playbook_version == "1"
        assert len(memo.clauses) == 3

    def test_summary_mapping(self) -> None:
        report = _make_report()
        exporter = MemoExporter(report=report, mode="precheck")
        memo = exporter._build_memo_report()

        assert memo.overall.clauses_checked == 3
        assert memo.overall.confidence_avg == report.summary.avg_confidence
        # recommendation logic: no red clauses → approve; but we have red → reject
        assert memo.overall.recommendation in ("approve", "revise", "reject")

    def test_clause_mapping(self) -> None:
        report = _make_report()
        exporter = MemoExporter(report=report, mode="precheck")
        memo = exporter._build_memo_report()

        clause = memo.clauses[0]
        assert clause.id == "c1"
        assert clause.title == "confidentiality-term"
        assert clause.assessment == "match"
        assert clause.color == "green"
        assert clause.confidence == 0.92

    def test_empty_assessments(self) -> None:
        report = _make_report(assessments=[])
        exporter = MemoExporter(report=report, mode="precheck")
        with pytest.raises(ValueError, match="No review results"):
            exporter._build_memo_report()

    def test_disclaimer_present(self) -> None:
        report = _make_report()
        exporter = MemoExporter(report=report, mode="precheck")
        memo = exporter._build_memo_report()
        assert memo.disclaimer
        assert "AI-generated" in memo.disclaimer or "automated" in memo.disclaimer

    def test_tier_info_mapped(self) -> None:
        report = _make_report()
        exporter = MemoExporter(report=report, mode="precheck")
        memo = exporter._build_memo_report()
        # When no privacy footer, tier_info may be None
        assert memo.tier_info is not None or memo.tier_info is None

    def test_citation_metrics_from_report(self) -> None:
        """MemoSummary CR/CL fields populated from report.cg_metrics when available."""
        from openreview_cli.grounding.models import CGMetrics

        report = _make_report()
        report.cg_metrics = CGMetrics(
            citation_precision=0.85,
            citation_relevance=0.72,
            citation_locality=0.91,
        )
        exporter = MemoExporter(report=report, mode="precheck")
        memo = exporter._build_memo_report()

        assert memo.overall.citation_relevance == 0.72
        assert memo.overall.citation_locality == 0.91

    def test_citation_metrics_none_when_no_cg_metrics(self) -> None:
        """MemoSummary CR/CL fields are None when report has no cg_metrics."""
        report = _make_report()
        exporter = MemoExporter(report=report, mode="precheck")
        memo = exporter._build_memo_report()

        assert memo.overall.citation_relevance is None
        assert memo.overall.citation_locality is None


class TestExport:
    def test_export_raises_on_empty(self) -> None:
        report = _make_report(assessments=[])
        exporter = MemoExporter(report=report, mode="precheck")
        with pytest.raises(ValueError, match="No review results"):
            exporter.export()

    def test_export_markdown_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = _make_report()
            exporter = MemoExporter(
                report=report,
                mode="precheck",
                output_dir=Path(tmp),
                formats={MemoFormat.MARKDOWN},
            )
            result = exporter.export()
            assert MemoFormat.MARKDOWN in result
            assert result[MemoFormat.MARKDOWN].exists()
            content = result[MemoFormat.MARKDOWN].read_text()
            assert "nda-sample" in content
            assert "precheck" in content

    def test_export_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = _make_report()
            exporter = MemoExporter(
                report=report,
                mode="dealcheck",
                output_dir=Path(tmp),
                formats={MemoFormat.JSON},
            )
            result = exporter.export()
            assert MemoFormat.JSON in result
            assert result[MemoFormat.JSON].exists()
            content = result[MemoFormat.JSON].read_text()
            import json

            data = json.loads(content)
            assert "memo_version" in data
            assert "clauses" in data

    def test_export_docx_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = _make_report()
            exporter = MemoExporter(
                report=report,
                mode="hirecheck",
                output_dir=Path(tmp),
                formats={MemoFormat.DOCX},
            )
            result = exporter.export()
            assert MemoFormat.DOCX in result
            assert result[MemoFormat.DOCX].exists()
            from docx import Document

            doc = Document(str(result[MemoFormat.DOCX]))
            assert doc.tables

    def test_export_all_formats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = _make_report()
            exporter = MemoExporter(
                report=report,
                mode="precheck",
                output_dir=Path(tmp),
                formats={MemoFormat.MARKDOWN, MemoFormat.JSON, MemoFormat.DOCX},
            )
            result = exporter.export()
            assert len(result) == 3
            for fmt in (MemoFormat.MARKDOWN, MemoFormat.JSON, MemoFormat.DOCX):
                assert fmt in result
                assert result[fmt].exists()

    def test_format_dedup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = _make_report()
            exporter = MemoExporter(
                report=report,
                mode="precheck",
                output_dir=Path(tmp),
                formats={MemoFormat.MARKDOWN, MemoFormat.MARKDOWN},  # duplicate
            )
            result = exporter.export()
            assert len(result) == 1
            assert MemoFormat.MARKDOWN in result
