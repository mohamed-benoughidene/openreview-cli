"""Unit tests for the Progress component.

Verifies TTY/non-TTY behaviour, description updates, ``cancel()``,
``--quiet`` suppression, and auto-cleanup on context exit.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from rich.console import Console
from rich.progress import Progress as RichProgress

from openreview_cli.ui.components.progress import Progress

if TYPE_CHECKING:
    import pytest

# ---------------------------------------------------------------------------
# TTY mode — Rich progress bar
# ---------------------------------------------------------------------------


def test_progress_shows_determinate_progress() -> None:
    """Interactive mode creates a Rich progress bar; advance/update work."""
    mock_rich_progress = MagicMock(spec=RichProgress)
    mock_task_id = MagicMock()
    mock_rich_progress.add_task.return_value = mock_task_id

    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = True

    with (
        patch(
            "openreview_cli.ui.components.progress.RichProgress",
            return_value=mock_rich_progress,
        ),
        Progress(100, "Processing", console=mock_console) as p,
    ):
        p.advance(5)
        p.update("Still going")

    mock_rich_progress.start.assert_called_once()
    mock_rich_progress.add_task.assert_called_once_with("Processing", total=100)
    mock_rich_progress.advance.assert_called_once_with(mock_task_id, advance=5)
    mock_rich_progress.update.assert_called_once_with(mock_task_id, description="Still going")
    mock_rich_progress.stop.assert_called_once()


# ---------------------------------------------------------------------------
# Non-TTY mode
# ---------------------------------------------------------------------------


def test_progress_non_tty_fallback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Non-interactive mode prints ``[current/total] description`` lines."""
    console = Console(file=io.StringIO())
    with Progress(10, "Working", console=console) as p:
        p.advance(3)

    captured = capsys.readouterr()
    # __enter__ prints [0/10] Working, advance prints [3/10] Working
    assert "[3/10] Working" in captured.err


# ---------------------------------------------------------------------------
# --quiet flag
# ---------------------------------------------------------------------------


def test_progress_quiet_suppresses_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When quiet=True, Progress produces no output at all."""
    console = Console(file=io.StringIO())
    with Progress(10, "Quiet", quiet=True, console=console) as p:
        p.advance(3)
        p.update("Still quiet")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


# ---------------------------------------------------------------------------
# cancel()
# ---------------------------------------------------------------------------


def test_progress_cancel_method(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """cancel() prints 'Cancelled' and stops the Rich progress bar."""
    mock_rich_progress = MagicMock(spec=RichProgress)
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = True

    with (
        patch(
            "openreview_cli.ui.components.progress.RichProgress",
            return_value=mock_rich_progress,
        ),
        Progress(100, "Task", console=mock_console) as p,
    ):
        p.cancel()

    captured = capsys.readouterr()
    assert "Cancelled" in captured.err
    mock_rich_progress.stop.assert_called_once()


# ---------------------------------------------------------------------------
# Context-manager cleanup
# ---------------------------------------------------------------------------


def test_progress_completion_cleans_up() -> None:
    """Rich progress is stopped when the context exits."""
    mock_rich_progress = MagicMock(spec=RichProgress)
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = True

    with (
        patch(
            "openreview_cli.ui.components.progress.RichProgress",
            return_value=mock_rich_progress,
        ),
        Progress(5, "Done", console=mock_console),
    ):
        pass

    mock_rich_progress.stop.assert_called_once()
