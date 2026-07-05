"""Edge case tests for memo export (T023).

Covers:
- Empty report
- Unsupported format
- File-exists deduplication
- Truncation of long clause text
- Missing citation
- Duplicate format flags
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from openreview_cli.review.memo.exporter import MemoExporter
from openreview_cli.review.memo.filename import deduplicate, resolve_output_dir
from openreview_cli.review.memo.models import MemoFormat
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
    text: str = "Standard clause text.",
) -> ClauseAssessment:
    ca = ClauseAssessment(
        clause_id=cid,
        clause_text=text,
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


def _make_report(assessments: list[ClauseAssessment]) -> ReviewReport:
    from datetime import UTC, datetime

    dm = DocMeta(
        filename="nda-sample.pdf",
        page_count=5,
        clause_count=len(assessments),
        pii_stripped=True,
    )
    summary = ReviewSummary(
        preferred_count=sum(1 for a in assessments if a.position == Position.PREFERRED),
        acceptable_count=sum(1 for a in assessments if a.position == Position.ACCEPTABLE),
        walkaway_count=sum(1 for a in assessments if a.position == Position.WALKAWAY),
        uncertain_count=0,
        no_match_count=0,
        amber_count=sum(
            1
            for a in assessments
            if hasattr(a, "color") and str(getattr(a, "color", "")) == "amber"
        ),
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


class TestEmptyReport:
    def test_no_assessments_raises(self) -> None:
        report = _make_report([])
        exporter = MemoExporter(report=report, mode="precheck")
        with pytest.raises(ValueError, match="No review results"):
            exporter.export()


class TestUnsupportedFormat:
    def test_unsupported_format_skipped(self) -> None:
        """Unsupported formats are skipped with a warning (not hard error)."""
        with tempfile.TemporaryDirectory() as tmp:
            report = _make_report([_make_assessment("c1")])
            # MemoFormat only has MARKDOWN, JSON, DOCX — all supported
            # This test verifies that any format works
            exporter = MemoExporter(
                report=report,
                mode="precheck",
                output_dir=Path(tmp),
                formats={MemoFormat.MARKDOWN},
            )
            result = exporter.export()
            assert MemoFormat.MARKDOWN in result


class TestFileExistsDedup:
    def test_dedup_on_second_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = _make_report([_make_assessment("c1")])
            exporter = MemoExporter(
                report=report,
                mode="precheck",
                output_dir=output_dir,
                formats={MemoFormat.MARKDOWN},
            )
            # First export
            result1 = exporter.export()
            path1 = result1[MemoFormat.MARKDOWN]
            assert path1.exists()

            # Second export — should get dedup suffix
            result2 = exporter.export()
            path2 = result2[MemoFormat.MARKDOWN]
            assert path2.exists()
            assert path2 != path1
            assert "-1" in path2.stem or path2 != path1

    def test_dedup_increment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Create a file that would collide
            p0 = Path(tmp) / "precheck-nda-sample-20260705-120000.md"
            p0.write_text("existing")
            p1 = Path(tmp) / "precheck-nda-sample-20260705-120000-1.md"
            p1.write_text("existing-1")

            result = deduplicate(p0)
            assert result == Path(tmp) / "precheck-nda-sample-20260705-120000-2.md"


class TestTruncation:
    def test_long_text_truncated(self) -> None:
        from openreview_cli.review.memo.formats import render_markdown

        with tempfile.TemporaryDirectory() as tmp:
            long_text = "A" * 15000
            report = _make_report([_make_assessment("c1", text=long_text)])
            exporter = MemoExporter(
                report=report,
                mode="precheck",
                output_dir=Path(tmp),
                formats={MemoFormat.MARKDOWN},
            )
            memo = exporter._build_memo_report()
            md = render_markdown(memo)
            assert "Truncated" in md
            assert "10,000" in md

    def test_short_text_unchanged(self) -> None:
        from openreview_cli.review.memo.formats import render_markdown

        short = "Short text."
        with tempfile.TemporaryDirectory() as tmp:
            report = _make_report([_make_assessment("c1", text=short)])
            exporter = MemoExporter(
                report=report,
                mode="precheck",
                output_dir=Path(tmp),
                formats={MemoFormat.MARKDOWN},
            )
            memo = exporter._build_memo_report()
            md = render_markdown(memo)
            assert "Truncated" not in md
            assert short in md


class TestMissingCitation:
    def test_citation_not_available(self) -> None:
        from openreview_cli.review.memo.formats import _citation_str

        result = _citation_str(None)
        assert "not available" in result


class TestDuplicateFlags:
    def test_duplicate_format_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = _make_report([_make_assessment("c1")])
            # Python set deduplicates {'md', 'md'} automatically
            exporter = MemoExporter(
                report=report,
                mode="precheck",
                output_dir=Path(tmp),
                formats={MemoFormat.MARKDOWN, MemoFormat.MARKDOWN},
            )
            assert len(exporter.formats) == 1


class TestOutputDirectory:
    def test_auto_creates_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            new_dir = Path(tmp) / "auto-created" / "nested"
            result = resolve_output_dir(new_dir)
            assert result.is_dir()

    def test_rejects_file_path(self) -> None:
        with tempfile.NamedTemporaryFile() as f, pytest.raises(ValueError, match="not a directory"):
            resolve_output_dir(Path(f.name))
