"""Integration tests for 'openreview export' CLI command — D-41 Batch Memo Export."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Position,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
)

runner = CliRunner()


def _sample_json_report(num: int) -> str:
    ca = ClauseAssessment(
        clause_id="c1",
        clause_text="Integration test clause.",
        playbook_category="confidentiality",
        position=Position.PREFERRED,
        confidence=0.9,
        citation="c1 citation",
        qa_verdict=QAVerdict.agree,
        extraction_model="m1",
        qa_model="m1",
    )
    from openreview_cli.review.colors import AssessmentColor

    ca.color = AssessmentColor.green

    report = ReviewReport(
        document=DocMeta(
            filename=f"integration_{num}.pdf",
            page_count=3,
            clause_count=1,
            pii_stripped=False,
        ),
        assessments=[ca],
        summary=ReviewSummary(
            preferred_count=1,
            avg_confidence=0.9,
            avg_effective_confidence=0.9,
            green_count=1,
        ),
        playbook_id="test-nda-v1",
        generated_at=datetime(2024, 1, 1, tzinfo=UTC),
        playbook_version=1,
    )
    return json.dumps(asdict(report), indent=2, default=str, ensure_ascii=False)


@pytest.fixture
def report_dir(tmp_path: Path) -> Path:
    d = tmp_path / "reports"
    d.mkdir()
    for i in range(2):
        p = d / f"report_{i}.json"
        p.write_text(_sample_json_report(i), encoding="utf-8")
    return d


class TestExportCliBatch:
    def test_batch_dir_md_default(self, report_dir: Path, tmp_path: Path) -> None:
        out = tmp_path / "out"
        result = runner.invoke(
            app,
            ["export", "--batch-dir", str(report_dir), "--output-dir", str(out)],
        )
        assert result.exit_code == 0
        assert "Exported" in result.stdout
        files = list(out.glob("*.md"))
        assert len(files) == 2

    def test_batch_dir_json_format(self, report_dir: Path, tmp_path: Path) -> None:
        out = tmp_path / "out"
        result = runner.invoke(
            app,
            [
                "export",
                "--batch-dir",
                str(report_dir),
                "--format",
                "json",
                "--output-dir",
                str(out),
            ],
        )
        assert result.exit_code == 0
        files = list(out.glob("*.json"))
        assert len(files) == 2

    def test_batch_dir_empty(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty_reports"
        empty.mkdir()
        out = tmp_path / "out"
        result = runner.invoke(
            app,
            ["export", "--batch-dir", str(empty), "--output-dir", str(out)],
        )
        assert result.exit_code == 1
        assert "No JSON report files found" in result.stderr

    def test_batch_dir_not_a_directory(self, tmp_path: Path) -> None:
        not_a_dir = tmp_path / "nope.txt"
        not_a_dir.write_text("x", encoding="utf-8")
        out = tmp_path / "out"
        result = runner.invoke(
            app,
            ["export", "--batch-dir", str(not_a_dir), "--output-dir", str(out)],
        )
        assert result.exit_code == 2
        assert "not a directory" in result.stderr

    def test_template_flag_overrides_content(self, report_dir: Path, tmp_path: Path) -> None:
        """--template flag causes markdown output to use custom Jinja2 template."""
        out = tmp_path / "out"
        custom_tpl = tmp_path / "custom.md.j2"
        custom_tpl.write_text("CUSTOM: {{ report.document.filename }}", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "export",
                "--batch-dir",
                str(report_dir),
                "--output-dir",
                str(out),
                "--template",
                str(custom_tpl),
            ],
        )
        # If --template not yet supported, expect exit code 2 (unknown option)
        assert result.exit_code == 0, (
            f"Expected exit code 0 but got {result.exit_code}: "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        files = sorted(out.glob("*.md"))
        assert len(files) == 2
        for f in files:
            content = f.read_text(encoding="utf-8")
            assert "CUSTOM:" in content
            assert "integration_" in content

    def test_template_flag_with_json_format_ignored(self, report_dir: Path, tmp_path: Path) -> None:
        """--template flag does NOT affect JSON/DOCX formats."""
        out = tmp_path / "out"
        custom_tpl = tmp_path / "custom.md.j2"
        custom_tpl.write_text("CUSTOM: {{ report.document.filename }}", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "export",
                "--batch-dir",
                str(report_dir),
                "--output-dir",
                str(out),
                "--template",
                str(custom_tpl),
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, (
            f"Expected exit code 0 but got {result.exit_code}: "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        files = list(out.glob("*.json"))
        assert len(files) == 2
        # JSON files should NOT contain the template content
        for f in files:
            content = f.read_text(encoding="utf-8")
            assert "CUSTOM:" not in content

    def test_batch_dir_memo_json(self, tmp_path: Path) -> None:
        from openreview_cli.review.memo.formats import render_json
        from openreview_cli.review.memo.models import MemoClause, MemoReport, MemoSummary

        d = tmp_path / "memo_reports"
        d.mkdir()
        out = tmp_path / "out"
        memo = MemoReport(
            memo_version="1.0",
            mode="precheck",
            document_name="saved_memo.pdf",
            playbook_name="precheck-nda-v1",
            playbook_version="1",
            review_date="2026-08-03T12:25:23+00:00",
            overall=MemoSummary(
                recommendation="revise",
                clauses_checked=1,
                matches=0,
                differences=1,
                confidence_avg=0.5,
            ),
            clauses=[
                MemoClause(
                    id="c1",
                    title="confidentiality",
                    playbook_requirement="walkaway",
                    contract_text="text",
                    assessment="difference",
                    color="red",
                    confidence=0.5,
                )
            ],
            disclaimer="test",
        )
        (d / "precheck-saved_memo.json").write_text(render_json(memo), encoding="utf-8")

        result = runner.invoke(
            app,
            ["export", "--batch-dir", str(d), "--format", "md", "--output-dir", str(out)],
        )
        assert result.exit_code == 0
        assert "Exported 1 memo" in result.stdout
        assert len(list(out.glob("*.md"))) == 1
