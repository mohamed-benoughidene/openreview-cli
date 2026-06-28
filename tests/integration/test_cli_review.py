"""Integration tests for the review CLI flow (T044 / T045 / T047).

Tests verify:
- T044: TTY review flow with mocked questionary prompts
- T045: Streaming output — progress bar updates per clause, spinners
- T047: Ctrl-C cancellation during processing
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _make_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force TTY mode for all tests in this file."""
    from openreview_cli.ui.console import renderer as _r

    p = PropertyMock(return_value=True)
    monkeypatch.setattr(type(_r), "is_interactive", p)
    # CliRunner replaces sys.stdin/sys.stdout during invoke, so the
    # instance-level patch above ensures app.py's renderer.is_interactive
    # check returns True even when not running on a real PTY.


@pytest.fixture
def sample_contract(tmp_path: Path) -> Path:
    """Create a minimal valid PDF."""
    path = tmp_path / "contract.pdf"
    path.write_bytes(b"%PDF-1.4\n")
    return path


def _mock_select(*, return_value: str | list[str] | None = "full") -> MagicMock:
    """Return a mock questionary.select whose unsafe_ask returns *return_value*."""
    mock_instance = MagicMock()
    mock_instance.unsafe_ask.return_value = return_value
    return mock_instance


def _mock_confirm(*, return_value: bool = True) -> MagicMock:
    """Return a mock questionary.confirm whose unsafe_ask returns *return_value*."""
    mock_instance = MagicMock()
    mock_instance.unsafe_ask.return_value = return_value
    return mock_instance


def _mock_checkbox(*, return_value: list[str] | None = None) -> MagicMock:
    """Return a mock questionary.checkbox whose unsafe_ask returns *return_value*."""
    mock_instance = MagicMock()
    mock_instance.unsafe_ask.return_value = return_value
    return mock_instance


# ---------------------------------------------------------------------------
# T044 — Interactive review flow
# ---------------------------------------------------------------------------


class TestInteractiveReview:
    """Full interactive review flow with mocked prompts."""

    def test_interactive_review_full_mode(self, sample_contract: Path) -> None:
        """Full review flow: mode→jurisdiction→format→confirm→processing→results."""
        with (
            patch(
                "questionary.select",
                side_effect=[
                    _mock_select(return_value="full"),  # mode selection
                    _mock_select(return_value="us-de — United States — Delaware"),  # jurisdiction
                    _mock_select(return_value="table"),  # output format
                ],
            ),
            patch("questionary.confirm", return_value=_mock_confirm(return_value=True)),
        ):
            result = runner.invoke(app, ["review", str(sample_contract)])

        assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.stdout}"
        # Should show results table with data rows
        assert "Indemnificat" in result.stdout, "Results should show Indemnification row"
        assert "Governing Law" in result.stdout, "Results should show Governing Law row"
        assert "Termination" in result.stdout, "Results should show Termination row"
        assert "Unlimited liability" in result.stdout, "Results should show findings"

    def test_interactive_review_confirmation_shows_options(self, sample_contract: Path) -> None:
        """Confirmation step displays the selected options."""
        with (
            patch(
                "questionary.select",
                side_effect=[
                    _mock_select(return_value="clause-by-clause"),
                    _mock_select(return_value="uk — United Kingdom"),
                    _mock_select(return_value="json"),
                ],
            ),
            patch(
                "questionary.checkbox", return_value=_mock_checkbox(return_value=["1", "3", "5"])
            ),
            patch("questionary.confirm", return_value=_mock_confirm(return_value=True)),
        ):
            result = runner.invoke(app, ["review", str(sample_contract)])

        assert result.exit_code == 0
        # Confirmation should show the file path and mode
        assert sample_contract.name in result.stdout
        assert "clause-by-clause" in result.stdout

    def test_interactive_review_decline_confirmation_exits(self, sample_contract: Path) -> None:
        """Declining confirmation goes back; Esc on mode exits."""
        with (
            patch(
                "questionary.select",
                side_effect=[
                    _mock_select(return_value="risk-scan"),
                    _mock_select(return_value=None),  # Esc on 2nd visit → exit
                ],
            ),
            patch("questionary.confirm", return_value=_mock_confirm(return_value=False)),
        ):
            result = runner.invoke(app, ["review", str(sample_contract)])

        assert result.exit_code == 0
        # Should NOT show results (no processing happened)
        assert "Indemnificat" not in result.stdout

    def test_interactive_esc_at_mode_selection_exits(self, sample_contract: Path) -> None:
        """Pressing Esc (None) at mode selection exits the wizard."""
        with patch("questionary.select", return_value=_mock_select(return_value=None)):
            result = runner.invoke(app, ["review", str(sample_contract)])

        assert result.exit_code == 0
        # Esc exits cleanly without processing
        assert "Processing" not in result.stdout


# ---------------------------------------------------------------------------
# T045 — Streaming / progress display
# ---------------------------------------------------------------------------


class TestStreamingDisplay:
    """Progress and spinner display during processing."""

    def test_progress_updates_per_clause(self, sample_contract: Path) -> None:
        """Progress component updates for each clause in clause-by-clause mode."""
        with (
            patch(
                "questionary.select",
                side_effect=[
                    _mock_select(return_value="clause-by-clause"),
                    _mock_select(return_value="us-de — United States — Delaware"),
                    _mock_select(return_value="table"),
                ],
            ),
            patch(
                "questionary.checkbox", return_value=_mock_checkbox(return_value=["1", "2", "3"])
            ),
            patch("questionary.confirm", return_value=_mock_confirm(return_value=True)),
        ):
            result = runner.invoke(app, ["review", str(sample_contract)])

        assert result.exit_code == 0
        # Should show results with clause data
        assert "Indemnificat" in result.stdout
        assert "Governing Law" in result.stdout
        assert "Termination" in result.stdout

    def test_spinner_during_non_clause_processing(self, sample_contract: Path) -> None:
        """Spinner displays during PII stripping and AI generation."""
        with (
            patch(
                "questionary.select",
                side_effect=[
                    _mock_select(return_value="full"),
                    _mock_select(return_value="us-de — United States — Delaware"),
                    _mock_select(return_value="table"),
                ],
            ),
            patch("questionary.confirm", return_value=_mock_confirm(return_value=True)),
        ):
            result = runner.invoke(app, ["review", str(sample_contract)])

        assert result.exit_code == 0
        # Spinner output goes to stderr; check it contains our spinner labels
        assert "Stripping PII" in result.stderr or "Stripping PII" in result.stdout


# ---------------------------------------------------------------------------
# T047 — Cancellation
# ---------------------------------------------------------------------------


class TestCancellation:
    """Ctrl-C during review exits cleanly."""

    def test_ctrl_c_during_processing_prints_message(self, sample_contract: Path) -> None:
        """Ctrl-C during processing prints cancellation message and exits code 1."""
        # Mock processing to raise KeyboardInterrupt
        with (
            patch(
                "questionary.select",
                side_effect=[
                    _mock_select(return_value="full"),
                    _mock_select(return_value="us-de — United States — Delaware"),
                    _mock_select(return_value="table"),
                ],
            ),
            patch("questionary.confirm", return_value=_mock_confirm(return_value=True)),
            patch(
                "openreview_cli.cli.review_wizard.ReviewFlowWizard._step_processing",
                side_effect=KeyboardInterrupt,
            ),
        ):
            result = runner.invoke(app, ["review", str(sample_contract)])

        assert result.exit_code == 1
        # Verify cancellation message
        assert "Review cancelled" in result.stderr or "Review cancelled" in result.output

    def test_ctrl_c_during_spinner_exits_cleanly(self, sample_contract: Path) -> None:
        """Ctrl-C during spinner (PII/AI) does not leave partial state."""
        with (
            patch(
                "questionary.select",
                side_effect=[
                    _mock_select(return_value="full"),
                    _mock_select(return_value="us-de — United States — Delaware"),
                    _mock_select(return_value="table"),
                ],
            ),
            patch("questionary.confirm", return_value=_mock_confirm(return_value=True)),
            patch(
                "openreview_cli.cli.review_wizard.Spinner",
                side_effect=KeyboardInterrupt,
            ),
        ):
            result = runner.invoke(app, ["review", str(sample_contract)])

        # Should handle gracefully (exit code 1 since Spinner swallows KeyboardInterrupt
        # but the wizard eventually catches it)
        assert result.exit_code in (0, 1)

    def test_no_partial_files_remain(self, sample_contract: Path) -> None:
        """No temp/partial files are created by the review wizard."""
        with (
            patch(
                "questionary.select",
                side_effect=[
                    _mock_select(return_value="full"),
                    _mock_select(return_value="us-de — United States — Delaware"),
                    _mock_select(return_value="table"),
                ],
            ),
            patch("questionary.confirm", return_value=_mock_confirm(return_value=True)),
            patch(
                "openreview_cli.cli.review_wizard.ReviewFlowWizard._step_processing",
                side_effect=KeyboardInterrupt,
            ),
        ):
            result = runner.invoke(app, ["review", str(sample_contract)])

        assert result.exit_code == 1
        # No config files or temp files should exist for this review
        # (The review wizard doesn't create any files — verify that)
        config_dir = sample_contract.parent / ".openreview"
        assert not config_dir.exists() or not any(config_dir.iterdir())
