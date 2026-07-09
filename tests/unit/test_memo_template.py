"""Unit tests for MemoTemplate — D-42 Custom Memo Templates via Jinja2."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent

import pytest

from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Position,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
)
from openreview_cli.review.templates import MemoTemplate


def _make_assessment(cid: str, pos: Position, conf: float) -> ClauseAssessment:
    ca = ClauseAssessment(
        clause_id=cid,
        clause_text=f"Clause {cid} text for testing.",
        playbook_category="confidentiality-term",
        position=pos,
        confidence=conf,
        citation=f"clause {cid} citation",
        qa_verdict=QAVerdict.agree,
        extraction_model="m1",
        qa_model="m1",
    )
    from openreview_cli.review.colors import AssessmentColor

    ca.color = AssessmentColor.green
    return ca


def _make_report() -> ReviewReport:
    assessment = _make_assessment("c1", Position.PREFERRED, 0.92)
    dm = DocMeta(
        filename="test_doc.pdf",
        page_count=5,
        clause_count=1,
        pii_stripped=False,
    )
    summary = ReviewSummary(
        preferred_count=1,
        acceptable_count=0,
        walkaway_count=0,
        uncertain_count=0,
        no_match_count=0,
        amber_count=0,
        green_count=1,
        red_count=0,
        avg_confidence=0.92,
        avg_effective_confidence=0.92,
    )
    return ReviewReport(
        document=dm,
        assessments=[assessment],
        summary=summary,
        playbook_id="test-nda-v1",
        generated_at=datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
        playbook_version=1,
    )


class TestMemoTemplateDefault:
    """Default template produces same output shape as render_markdown."""

    def test_default_renders_without_error(self) -> None:
        template = MemoTemplate()
        report = _make_report()
        result = template.render(report)
        assert isinstance(result, str)
        assert len(result) > 50

    def test_default_contains_key_fields(self) -> None:
        template = MemoTemplate()
        report = _make_report()
        result = template.render(report)
        assert "test_doc.pdf" in result
        assert "precheck" in result
        assert "c1" in result
        assert "APPROVE" in result

    def test_default_does_not_contain_raw_jinja(self) -> None:
        template = MemoTemplate()
        report = _make_report()
        result = template.render(report)
        assert "{{" not in result


class TestMemoTemplateCustom:
    """Custom file-based templates render correctly."""

    def test_custom_template_overrides_content(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom.md.j2"
        custom.write_text(
            dedent("""\
            # Custom Report
            Document: {{ report.document.filename }}
            Clauses: {{ report.assessments | length }}
            """)
        )
        template = MemoTemplate(custom)
        report = _make_report()
        result = template.render(report)
        assert "# Custom Report" in result
        assert "test_doc.pdf" in result

    def test_custom_template_with_jinja_features(self, tmp_path: Path) -> None:
        custom = tmp_path / "loop.md.j2"
        custom.write_text(
            dedent("""\
            {% for ca in report.assessments %}
            - {{ ca.clause_id }}: {{ ca.position }}
            {% endfor %}
            """)
        )
        template = MemoTemplate(custom)
        report = _make_report()
        result = template.render(report)
        assert "- c1: preferred" in result

    def test_custom_template_missing_file(self) -> None:
        missing = Path("/nonexistent/template.md.j2")
        with pytest.raises(FileNotFoundError, match=str(missing)):
            MemoTemplate(missing)


class TestMemoTemplateBackwardCompat:
    """Default template output matches render_markdown output shape."""

    def test_default_matches_render_markdown(self) -> None:
        """Default MemoTemplate render should match render_markdown byte-for-byte."""
        from openreview_cli.review.memo.formats import render_markdown
        from openreview_cli.review.templates import _build_memo

        report = _make_report()

        # Get reference output from render_markdown using the same memo builder
        memo = _build_memo(report)
        expected = render_markdown(memo)

        # Get output from default template (also uses _build_memo internally)
        template = MemoTemplate()
        result = template.render(report)

        # Compare — they should produce the same output
        assert result == expected, (
            f"Default MemoTemplate output does not match render_markdown output.\n"
            f"Expected:\n{expected}\n\nGot:\n{result}"
        )


class TestMemoTemplateWithBatchExport:
    """batch_export_reports with --template flag."""

    def test_batch_export_with_template(self, tmp_path: Path) -> None:
        """When template_path is provided, markdown output should use the template."""
        import json

        from openreview_cli.review.report import batch_export_reports

        # Create a report JSON
        src = tmp_path / "reports"
        src.mkdir()
        out = tmp_path / "out"

        report = _make_report()
        p = src / "report.json"
        p.write_text(
            json.dumps(dataclasses.asdict(report), indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )

        # Create a custom template
        custom_tpl = tmp_path / "custom.md.j2"
        custom_tpl.write_text("TEMPLATE: {{ report.document.filename }}")

        written = batch_export_reports([p], "md", out, template_path=custom_tpl)
        assert len(written) == 1
        content = written[0].read_text(encoding="utf-8")
        assert "TEMPLATE:" in content
        assert "test_doc.pdf" in content
