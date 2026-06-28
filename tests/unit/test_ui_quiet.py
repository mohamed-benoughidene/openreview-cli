"""Tests for --quiet mode suppression of non-error output.

T071 — Silent mode flag suppresses spinner, progress, and success
messages.  Errors still reach stdout/stderr.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from rich.console import Console

from openreview_cli.ui.components.progress import Progress
from openreview_cli.ui.components.spinner import Spinner

if TYPE_CHECKING:
    import pytest


def _mock_console() -> MagicMock:
    """Create a MagicMock that behaves like a non-interactive Console."""
    c = MagicMock(spec=Console)
    c.is_interactive = False
    return c


# ---------------------------------------------------------------------------
# Spinner quiet mode
# ---------------------------------------------------------------------------


def test_spinner_quiet_suppresses_output() -> None:
    """Spinner with quiet=True produces no output."""
    console = _mock_console()
    with Spinner("test", quiet=True, console=console):
        pass
    console.print.assert_not_called()


def test_spinner_quiet_does_not_start_rich_status(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Spinner with quiet=True does not create a Rich Status."""
    console = _mock_console()
    with Spinner("no output expected", quiet=True, console=console):
        pass
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_spinner_quiet_update_does_nothing() -> None:
    """Spinner.update() is a no-op when quiet."""
    console = _mock_console()
    with Spinner("start", quiet=True, console=console) as s:
        s.update("changed")
    # Status should not have been created
    assert s._status is None


# ---------------------------------------------------------------------------
# Progress quiet mode
# ---------------------------------------------------------------------------


def test_progress_quiet_suppresses_output() -> None:
    """Progress with quiet=True produces no output."""
    console = _mock_console()
    with Progress(10, "test", quiet=True, console=console) as p:
        p.advance(5)
        p.update("halfway")
    console.print.assert_not_called()


def test_progress_quiet_advance_does_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Progress.advance() is a no-op when quiet."""
    console = _mock_console()
    with Progress(10, "test", quiet=True, console=console) as p:
        p.advance(5)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_progress_quiet_cancel_does_not_print(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Progress.cancel() does not print when quiet."""
    console = _mock_console()
    with Progress(5, "test", quiet=True, console=console) as p:
        p.cancel()
    captured = capsys.readouterr()
    assert captured.err == ""


def test_progress_quiet_update_does_nothing() -> None:
    """Progress.update() is a no-op when quiet."""
    console = _mock_console()
    with Progress(10, "test", quiet=True, console=console) as p:
        p.update("silent update")
    console.print.assert_not_called()
