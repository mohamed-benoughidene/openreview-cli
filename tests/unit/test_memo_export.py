"""Unit tests for batch_export_reports — D-41 Batch Memo Export."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Position,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
)
from openreview_cli.review.report import batch_export_reports


def _make_assessment(cid: str, pos: Position, conf: float) -> ClauseAssessment:
    ca = ClauseAssessment(
        clause_id=cid,
        clause_text=f"Clause {cid} text.",
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


def _make_report(num: int) -> ReviewReport:
    assessment = _make_assessment("c1", Position.PREFERRED, 0.92)
    dm = DocMeta(
        filename=f"doc_{num}.pdf",
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
        generated_at=datetime.now(UTC),
        playbook_version=1,
    )


def _serialise(report: ReviewReport) -> str:
    return json.dumps(asdict(report), indent=2, default=str, ensure_ascii=False)


class TestBatchExportReports:
    def test_three_reports_md(self, tmp_path: Path) -> None:
        src = tmp_path / "reports"
        src.mkdir()
        out = tmp_path / "out"
        paths: list[Path] = []
        for i in range(3):
            p = src / f"report_{i}.json"
            p.write_text(_serialise(_make_report(i)), encoding="utf-8")
            paths.append(p)

        written = batch_export_reports(paths, "md", out)
        assert len(written) == 3
        for p in written:
            assert p.exists()
            assert p.suffix == ".md"

    def test_three_reports_json(self, tmp_path: Path) -> None:
        src = tmp_path / "reports"
        src.mkdir()
        out = tmp_path / "out"
        paths = []
        for i in range(3):
            p = src / f"report_{i}.json"
            p.write_text(_serialise(_make_report(i)), encoding="utf-8")
            paths.append(p)

        written = batch_export_reports(paths, "json", out)
        assert len(written) == 3
        for p in written:
            assert p.exists()
            assert p.suffix == ".json"

    def test_invalid_json_skipped(self, tmp_path: Path) -> None:
        src = tmp_path / "reports"
        src.mkdir()
        out = tmp_path / "out"

        valid = src / "valid.json"
        valid.write_text(_serialise(_make_report(1)), encoding="utf-8")

        invalid = src / "invalid.json"
        invalid.write_text("not json", encoding="utf-8")

        written = batch_export_reports([valid, invalid], "json", out)
        assert len(written) == 1

    def test_missing_file(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        missing = tmp_path / "nonexistent.json"
        written = batch_export_reports([missing], "md", out)
        assert len(written) == 0

    def test_output_dir_created(self, tmp_path: Path) -> None:
        src = tmp_path / "reports"
        src.mkdir()
        out = tmp_path / "does_not_exist_yet"

        p = src / "report.json"
        p.write_text(_serialise(_make_report(1)), encoding="utf-8")

        written = batch_export_reports([p], "md", out)
        assert len(written) == 1
        assert out.is_dir()

    def test_malformed_data_skipped(self, tmp_path: Path) -> None:
        src = tmp_path / "reports"
        src.mkdir()
        out = tmp_path / "out"

        p = src / "bad.json"
        p.write_text(json.dumps({"not": "a report"}), encoding="utf-8")

        written = batch_export_reports([p], "md", out)
        assert len(written) == 0

    def test_returns_all_written_paths(self, tmp_path: Path) -> None:
        src = tmp_path / "reports"
        src.mkdir()
        out = tmp_path / "out"

        reports = [_make_report(i) for i in range(2)]
        paths = []
        for r in reports:
            p = src / f"{r.document.filename}.json"
            p.write_text(_serialise(r), encoding="utf-8")
            paths.append(p)

        written = batch_export_reports(paths, "json", out)
        assert len(written) == 2
        for w in written:
            assert w.parent == out
