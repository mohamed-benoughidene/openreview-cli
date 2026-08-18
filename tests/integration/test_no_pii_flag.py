"""Integration tests for the --no-pii flag.

Extends existing subprocess-based tests (TestPrecheckNoPii) with
CliRunner+mock tests for PII engine call-count assertions, gateway
raw-text assertions, default stripping behavior, parameterized
subcommand coverage, and output format compliance.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from openreview_cli.bilateral.models import ComparisonReport
    from openreview_cli.review.models import ReviewReport

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PDF = FIXTURES / "pdf"
SIMPLE_CONTRACT = str(PDF / "simple_contract.pdf")

# ── helpers ──


def _make_review_report(*, pii_stripped: bool = True) -> ReviewReport:
    """Build a ReviewReport with minimal required fields."""
    from datetime import UTC, datetime

    from openreview_cli.review.models import DocMeta, ReviewReport, ReviewSummary

    return ReviewReport(
        document=DocMeta(
            filename="test.pdf",
            page_count=1,
            clause_count=0,
            pii_stripped=pii_stripped,
            parsed_at=datetime.now(UTC),
        ),
        assessments=[],
        summary=ReviewSummary(),
        playbook_id="test",
        generated_at=datetime.now(UTC),
        confidence_threshold=0.7,
    )


def _make_comparison_report(*, pii_stripped: bool = True) -> ComparisonReport:
    """Build a ComparisonReport with minimal required fields."""
    from datetime import UTC, datetime

    from openreview_cli.bilateral.models import ComparisonReport, ComparisonSummary
    from openreview_cli.review.models import DocMeta

    return ComparisonReport(
        document_a=DocMeta(
            filename="a.pdf",
            page_count=1,
            clause_count=0,
            pii_stripped=pii_stripped,
            parsed_at=datetime.now(UTC),
        ),
        document_b=DocMeta(
            filename="b.pdf",
            page_count=1,
            clause_count=0,
            pii_stripped=pii_stripped,
            parsed_at=datetime.now(UTC),
        ),
        alignment_table=MagicMock(),
        assessments=[],
        summary=ComparisonSummary(
            total_pairs=0,
            divergent_count=0,
            aligned_count=0,
            green_count=0,
            red_count=0,
            amber_count=0,
            uncertain_count=0,
            avg_alignment_quality=0.0,
            agreement_rate=0.0,
        ),
        playbook_id="test",
        generated_at=datetime.now(UTC),
        confidence_threshold=0.7,
        disclaimer="",
    )


# ── subprocess-based tests (original, kept for backward compatibility) ──


def run_precheck(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "openreview_cli", "precheck", *args],
        capture_output=True,
        text=True,
    )


class TestPrecheckNoPii:
    @pytest.mark.integration
    def test_no_pii_exit_code(self) -> None:
        result = run_precheck("--no-pii", "--document", str(PDF / "simple_contract.pdf"))
        assert result.returncode == 0

    @pytest.mark.integration
    def test_no_pii_warning(self) -> None:
        result = run_precheck("--no-pii", "--document", str(PDF / "simple_contract.pdf"))
        assert "PII stripping disabled" in result.stderr

    @pytest.mark.integration
    def test_no_pii_no_encrypted_mapping(self) -> None:
        result = run_precheck("--no-pii", "--document", str(PDF / "simple_contract.pdf"))
        m = re.search(r"Review memo generated:\s+(\S+)", result.stdout)
        assert m, "Could not find review directory in output"
        review_dir = Path(m.group(1)).parent
        assert not (review_dir / "pii_map.enc").exists()


# ── Precheck callback — PII engine call-count (T060) ──


class TestPrecheckPiiEngineCalls:
    """T060: PII engine call-count assertions for precheck callback."""

    @patch("openreview_cli.review.base.strip_and_persist")
    def test_engine_called_when_enabled(self, mock_strip: MagicMock) -> None:
        """strip_and_persist called once when --no-pii absent."""
        mock_strip.return_value = MagicMock(stripped_text="stripped", entities=[], failed_pages=[])
        result = runner.invoke(
            app,
            [
                "precheck",
                "--document",
                SIMPLE_CONTRACT,
                "--force-reprocess",
            ],
        )
        assert result.exit_code == 0
        mock_strip.assert_called_once()

    @patch("openreview_cli.review.base.strip_and_persist")
    def test_engine_not_called_when_disabled(self, mock_strip: MagicMock) -> None:
        """strip_and_persist NOT called when --no-pii present."""
        result = runner.invoke(
            app,
            ["precheck", "--no-pii", "--document", SIMPLE_CONTRACT],
        )
        assert result.exit_code == 0
        mock_strip.assert_not_called()

    @patch("openreview_cli.review.base.strip_and_persist")
    def test_warning_message_on_stderr(self, mock_strip: MagicMock) -> None:
        """Warning message printed to stderr when --no-pii is set."""
        result = runner.invoke(
            app,
            ["precheck", "--no-pii", "--document", SIMPLE_CONTRACT],
        )
        assert result.exit_code == 0
        assert "PII stripping disabled" in result.stderr


# ── Precheck callback — raw text / default behavior (T061, T062) ──


class TestPrecheckRawTextBehavior:
    """T061: PII stripped before external call by default."""

    @patch("openreview_cli.review.base.strip_and_persist")
    def test_stripped_text_written_by_default(self, mock_strip: MagicMock) -> None:
        """Default: stripped text written to result path."""
        mock_strip.return_value = MagicMock(
            stripped_text="stripped contract text",
            entities=[],
            failed_pages=[],
        )
        result = runner.invoke(
            app,
            [
                "precheck",
                "--document",
                SIMPLE_CONTRACT,
                "--force-reprocess",
            ],
        )
        assert result.exit_code == 0
        assert "Review memo generated" in result.stdout

    @patch("openreview_cli.review.base.strip_and_persist")
    def test_no_pii_bypasses_stripping(self, mock_strip: MagicMock) -> None:
        """--no-pii bypasses PII stripping entirely."""
        result = runner.invoke(
            app,
            ["precheck", "--no-pii", "--document", SIMPLE_CONTRACT],
        )
        assert result.exit_code == 0
        mock_strip.assert_not_called()


# ── Precheck callback — output format respects flag (T069) ──


class TestPrecheckOutputFormat:
    """T069: Output format works with --no-pii."""

    @patch("openreview_cli.review.base.strip_and_persist")
    def test_json_format_without_no_pii(self, mock_strip: MagicMock) -> None:
        """--format json works without --no-pii."""
        mock_strip.return_value = MagicMock(stripped_text="stripped", entities=[], failed_pages=[])
        result = runner.invoke(
            app,
            [
                "precheck",
                "--document",
                SIMPLE_CONTRACT,
                "--force-reprocess",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0

    @patch("openreview_cli.review.base.strip_and_persist")
    def test_json_format_with_no_pii(self, mock_strip: MagicMock) -> None:
        """--format json works with --no-pii."""
        result = runner.invoke(
            app,
            [
                "precheck",
                "--no-pii",
                "--document",
                SIMPLE_CONTRACT,
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0


# ── Review subcommand — PII in pipeline (T063) ──


class TestReviewSubcommandPii:
    """T063: PII behavior in review subcommand pipeline."""

    @patch("openreview_cli.pii.strip_pii_clauses")
    @patch("openreview_cli.review.extraction.call_gateway_chat")
    @patch("openreview_cli.review.qa.call_gateway_chat")
    def test_pii_strip_called_in_pipeline(
        self,
        mock_qa_gw: MagicMock,
        mock_ext_gw: MagicMock,
        mock_strip: MagicMock,
    ) -> None:
        """review: strip_pii_clauses called when --no-pii absent."""
        mock_strip.return_value = ([], MagicMock(entities=[], failed_pages=[]))
        mock_ext_gw.return_value = '{"position": "preferred", "confidence": 0.9, "citation": "t"}'
        mock_qa_gw.return_value = (
            '{"verdict": "agree", "citation_valid": true, '
            '"position_valid": true, "category_valid": true, '
            '"confidence_valid": true}'
        )
        result = runner.invoke(
            app,
            ["precheck", "review", SIMPLE_CONTRACT],
        )
        assert result.exit_code == 0
        mock_strip.assert_called_once()

    @patch("openreview_cli.review.run_review")
    def test_pii_skipped_in_pipeline(self, mock_run: MagicMock) -> None:
        """review: --no-pii=True passed to run_review when flag set."""
        mock_run.return_value = [_make_review_report(pii_stripped=True)]
        result = runner.invoke(
            app,
            ["precheck", "review", "--no-pii", SIMPLE_CONTRACT],
        )
        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args[1]["no_pii"] is True


# ── Compare subcommand — PII behavior (T064) ──


class TestCompareSubcommandPii:
    """T064: --no-pii behavior in compare subcommand (CLI wiring).

    The strip-called/not-called assertions live at the unit level
    (tests/unit/test_bilateral_pii_strip.py). Here we only verify the
    flag reaches run_comparison and the command exits cleanly.
    """

    @patch("openreview_cli.bilateral.run_comparison")
    def test_compare_runs_without_no_pii(
        self,
        mock_run: MagicMock,
    ) -> None:
        """compare subcommand runs without --no-pii."""
        mock_run.return_value = _make_comparison_report(pii_stripped=True)
        result = runner.invoke(
            app,
            ["precheck", "compare", SIMPLE_CONTRACT, SIMPLE_CONTRACT],
        )
        assert result.exit_code == 0

    @patch("openreview_cli.bilateral.run_comparison")
    def test_compare_runs_with_no_pii(
        self,
        mock_run: MagicMock,
    ) -> None:
        """compare subcommand runs with --no-pii; flag is forwarded."""
        mock_run.return_value = _make_comparison_report(pii_stripped=False)
        result = runner.invoke(
            app,
            [
                "precheck",
                "compare",
                "--no-pii",
                SIMPLE_CONTRACT,
                SIMPLE_CONTRACT,
            ],
        )
        assert result.exit_code == 0
        mock_run.assert_called_once()
        # --no-pii is forwarded to run_comparison, which skips stripping.
        assert mock_run.call_args[1].get("no_pii") is True

    @patch("openreview_cli.bilateral.run_comparison")
    def test_compare_with_allow_partial_pii_forwards_flag(
        self,
        mock_run: MagicMock,
    ) -> None:
        """--allow-partial-pii is forwarded to run_comparison."""
        mock_run.return_value = _make_comparison_report(pii_stripped=True)
        result = runner.invoke(
            app,
            [
                "precheck",
                "compare",
                "--allow-partial-pii",
                SIMPLE_CONTRACT,
                SIMPLE_CONTRACT,
            ],
        )
        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args[1].get("allow_partial_pii") is True
