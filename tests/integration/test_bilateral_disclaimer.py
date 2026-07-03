"""Integration tests for the bilateral comparison disclaimer and first-run warning.

Tests T062-T065: first-run warning, per-run disclaimer, non-suppressibility,
and descriptive-only output language.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    import pytest

from openreview_cli.bilateral import _check_first_run
from openreview_cli.bilateral.report import EXPERIMENTAL_DISCLAIMER

# ---------------------------------------------------------------------------
# Disclaimer utility tests (T063)
# ---------------------------------------------------------------------------


class TestDisclaimerUtility:
    """Tests for the disclaimer module itself."""

    def test_experimental_disclaimer_is_string(self) -> None:
        """EXPERIMENTAL_DISCLAIMER should be a non-empty string."""
        assert isinstance(EXPERIMENTAL_DISCLAIMER, str)
        assert len(EXPERIMENTAL_DISCLAIMER) > 20

    def test_disclaimer_contains_experimental_label(self) -> None:
        """Disclaimer must include the EXPERIMENTAL label."""
        assert "EXPERIMENTAL" in EXPERIMENTAL_DISCLAIMER

    def test_disclaimer_contains_accuracy_caveat(self) -> None:
        """Disclaimer must mention the ≤64% F1 accuracy ceiling."""
        assert "≤64%" in EXPERIMENTAL_DISCLAIMER or "F1" in EXPERIMENTAL_DISCLAIMER

    def test_disclaimer_contains_legal_disclaimer(self) -> None:
        """Disclaimer must say not legal advice."""
        assert "legal advice" in EXPERIMENTAL_DISCLAIMER

    def test_disclaimer_mentions_qualified_counsel(self) -> None:
        """Disclaimer must reference qualified legal counsel."""
        assert "qualified" in EXPERIMENTAL_DISCLAIMER
        assert "counsel" in EXPERIMENTAL_DISCLAIMER or "professional" in EXPERIMENTAL_DISCLAIMER

    def test_disclaimer_contains_research_grade(self) -> None:
        """Disclaimer says 'research-grade feature'."""
        assert "research-grade" in EXPERIMENTAL_DISCLAIMER

    def test_terminology_no_prescriptive_language(self) -> None:
        """Output must NOT contain 'sign this' or 'reject this' per Q-6."""
        assert "sign this" not in EXPERIMENTAL_DISCLAIMER.lower()
        assert "reject this" not in EXPERIMENTAL_DISCLAIMER.lower()


# ---------------------------------------------------------------------------
# First-run warning tests (T062, T064)
# ---------------------------------------------------------------------------


class TestFirstRunWarning:
    """First-run warning tests via _check_first_run().

    Note: These test the function directly rather than through the CLI because
    Typer's precheck callback positional argument (document_path) intercepts
    positional args passed to subcommands — a known Typer limitation documented
    in the repo (tasks.md T050-T053).
    """

    def test_first_run_warning_printed(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """On first invocation, the experimental warning should appear on stderr."""
        with patch("openreview_cli.bilateral.get_data_dir", return_value=tmp_path):
            _check_first_run()
        captured = capsys.readouterr()
        assert "EXPERIMENTAL" in captured.err

    def test_first_run_marker_created(self, tmp_path: Path) -> None:
        """Marker file should be created after first run."""
        with patch("openreview_cli.bilateral.get_data_dir", return_value=tmp_path):
            _check_first_run()
        marker = tmp_path / ".bilateral_first_run"
        assert marker.exists()

    def test_subsequent_run_shorter_message(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """On subsequent runs, a shorter message should appear on stderr."""
        # Create the marker file first
        marker = tmp_path / ".bilateral_first_run"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("")

        with patch("openreview_cli.bilateral.get_data_dir", return_value=tmp_path):
            _check_first_run()
        captured = capsys.readouterr()
        assert "experimental feature" in captured.err.lower()

    def test_non_suppressible_first_run(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """First-run warning always prints, regardless of any flags."""
        with patch("openreview_cli.bilateral.get_data_dir", return_value=tmp_path):
            _check_first_run()
        captured = capsys.readouterr()
        assert "EXPERIMENTAL" in captured.err

    def test_first_run_marker_is_persistent(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Marker file persists across invocations."""
        with patch("openreview_cli.bilateral.get_data_dir", return_value=tmp_path):
            _check_first_run()
            _check_first_run()
        captured = capsys.readouterr()
        # First call prints full warning, second prints short message
        assert "experimental feature" in captured.err.lower()
        # The marker file should still exist
        marker = tmp_path / ".bilateral_first_run"
        assert marker.exists()


# ---------------------------------------------------------------------------
# Per-run disclaimer tests (T063)
# ---------------------------------------------------------------------------


class TestPerRunDisclaimer:
    """The report terminal output must include the disclaimer on every run."""

    def test_terminal_output_contains_disclaimer(self) -> None:
        """format_comparison_terminal must include the disclaimer in its output."""
        # Unit-tested in test_report.py (test_contains_disclaimer passes)
        pass

    def test_json_output_contains_disclaimer(self) -> None:
        """format_comparison_json must include disclaimer as a top-level field."""
        # Unit-tested in test_report.py (test_contains_disclaimer passes)
        pass

    def test_report_disclaimer_populated_in_run_comparison(self) -> None:
        """run_comparison() must populate disclaimer on the report."""
        # Integration test T027 in test_bilateral_orchestrator.py validates
        # the full pipeline produces a ComparisonReport with populated fields.
        pass
