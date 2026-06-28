"""Unit tests for the Spinner component.

Verifies TTY/non-TTY behaviour, label updates, clean exit,
KeyboardInterrupt handling, and ``--quiet`` suppression.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from rich.console import Console
from rich.status import Status

from openreview_cli.ui.components.spinner import Spinner

if TYPE_CHECKING:
    import pytest

# ---------------------------------------------------------------------------
# TTY mode — Spinner creates / manages ``rich.status.Status``
# ---------------------------------------------------------------------------


def test_spinner_creates_rich_status_in_tty_mode() -> None:
    """In interactive mode, Spinner creates and starts a Status."""
    mock_status = MagicMock(spec=Status)
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = True

    with (
        patch("openreview_cli.ui.components.spinner.Status", return_value=mock_status),
        Spinner("working", console=mock_console) as s,
    ):
        assert s._status is mock_status

    mock_status.start.assert_called_once()
    mock_status.stop.assert_called_once()


def test_spinner_updates_label_during_operation() -> None:
    """Spinner.update() delegates to status.update()."""
    mock_status = MagicMock(spec=Status)
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = True

    with (
        patch("openreview_cli.ui.components.spinner.Status", return_value=mock_status),
        Spinner("initial", console=mock_console) as s,
    ):
        s.update("updated")

    mock_status.update.assert_called_once_with("updated")


def test_spinner_clears_on_exit() -> None:
    """Spinner stops the Status when the context exits."""
    mock_status = MagicMock(spec=Status)
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = True

    with (
        patch("openreview_cli.ui.components.spinner.Status", return_value=mock_status),
        Spinner("test", console=mock_console),
    ):
        pass

    mock_status.stop.assert_called_once()


# ---------------------------------------------------------------------------
# Non-TTY mode — plain text fallback
# ---------------------------------------------------------------------------


def test_spinner_prints_label_once_in_non_tty_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When the console is not interactive, Spinner prints ``label...``."""
    console = Console(file=io.StringIO())
    with Spinner("working", console=console):
        pass

    captured = capsys.readouterr()
    assert "working..." in captured.err


# ---------------------------------------------------------------------------
# --quiet flag
# ---------------------------------------------------------------------------


def test_spinner_quiet_suppresses_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When quiet=True, Spinner produces no output at all."""
    console = Console(file=io.StringIO())
    with Spinner("quiet test", quiet=True, console=console):
        pass

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


# ---------------------------------------------------------------------------
# KeyboardInterrupt handling
# ---------------------------------------------------------------------------


def test_spinner_ctrl_c_exits_cleanly() -> None:
    """KeyboardInterrupt inside spinner is caught and does not propagate."""
    mock_status = MagicMock(spec=Status)
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = True

    with (
        patch("openreview_cli.ui.components.spinner.Status", return_value=mock_status),
        Spinner("test", console=mock_console),
    ):
        raise KeyboardInterrupt()

    # Should have reached here — KeyboardInterrupt was suppressed.
    mock_status.stop.assert_called_once()
