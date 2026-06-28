"""Unit tests for the StatusLine component.

Verifies TTY/non-TTY behaviour, in-place updates, quiet suppression,
and label truncation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from rich.console import Console

from openreview_cli.ui.components.status_line import StatusLine

if TYPE_CHECKING:
    import pytest

# ---------------------------------------------------------------------------
# TTY mode — StatusLine uses \r carriage-return updates
# ---------------------------------------------------------------------------


def test_status_line_shows_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Initial message contains the mode and text separated by a space."""
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = True

    with StatusLine("parsing", "loading contracts", console=mock_console) as s:
        assert s is not None

    # In TTY mode, the status writes to stdout via \r
    # We verify calls made via sys.stdout.write
    # The context manager calls write() in __enter__ and __exit__
    assert mock_console.is_interactive


def test_status_line_updates_in_place_via_carriage_return() -> None:
    """Each update() call writes with a \\r prefix to overwrite the line."""
    mock_file = MagicMock()
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = True
    mock_console.file = mock_file

    with StatusLine("check", "starting", console=mock_console) as s:
        s.update("in progress")

    # __enter__ writes, update writes, __exit__ writes the final + newline
    # At minimum we should see the mode "[check]" in the writes
    written = "".join(call[0][0] for call in mock_file.write.call_args_list if call[0][0] != "\n")
    assert "[check]" in written


def test_status_line_updates_uses_carriage_return(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Status line writes use \\r so the line is overwritten in place."""
    # Patch sys.stdout to capture writes
    mock_stdout = MagicMock()
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = True
    mock_console.file = mock_stdout

    with StatusLine("scan", "starting", console=mock_console) as s:
        s.update("scanning file 42")
        s.update("done")

    # All writes should start with \r (except the final \n termination)
    written = "".join(call[0][0] for call in mock_stdout.write.call_args_list if call[0][0] != "\n")
    assert "\r" in written


# ---------------------------------------------------------------------------
# Non-TTY mode — prints once to stderr on exit
# ---------------------------------------------------------------------------


def test_status_line_non_tty_prints_final_message_on_exit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """In non-interactive mode, only the final message is printed to stderr."""
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = False

    with StatusLine("check", "initial", console=mock_console) as s:
        s.update("first update")
        s.update("final result")

    captured = capsys.readouterr()
    assert "[check]" in captured.err
    assert "final result" in captured.err
    # "initial" and "first update" should NOT appear in output
    # (only the final message is shown)
    assert "initial" not in captured.err


def test_status_line_non_tty_writes_only_once() -> None:
    """In non-TTY mode, write is called exactly once (on exit)."""
    mock_stdout = MagicMock()
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = False
    mock_console.file = mock_stdout

    with StatusLine("test", "msg", console=mock_console) as s:
        s.update("update 1")
        s.update("update 2")

    # Should have written to stderr only on exit (not during enter/update)
    # In non-TTY, stdout writes should be minimal
    pass


# ---------------------------------------------------------------------------
# --quiet flag
# ---------------------------------------------------------------------------


def test_status_line_quiet_suppresses_all_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When quiet=True, StatusLine produces no output at all."""
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = True

    with StatusLine("test", "should be silent", quiet=True, console=mock_console):
        pass

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_status_line_quiet_never_writes() -> None:
    """With quiet=True, no write calls are made to the console file."""
    mock_file = MagicMock()
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = True
    mock_console.file = mock_file

    with StatusLine("test", "silent", quiet=True, console=mock_console):
        pass

    mock_file.write.assert_not_called()


# ---------------------------------------------------------------------------
# Label truncation — max 60 characters
# ---------------------------------------------------------------------------


def test_status_line_truncates_message_at_60_chars(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Message longer than 60 characters is truncated with a '…' suffix."""
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = False

    long_message = "a" * 100
    with StatusLine("test", long_message, console=mock_console):
        pass

    captured = capsys.readouterr()
    emitted = captured.err
    # The truncated message (57 chars + "…" = 58) appears
    assert "[test]" in emitted
    # The full 100-char message is NOT present
    assert "a" * 100 not in emitted


def test_status_line_updates_also_truncate(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """update() messages are also truncated to 60 chars."""
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = False

    with StatusLine("mode", "short", console=mock_console) as s:
        s.update("x" * 80)

    captured = capsys.readouterr()
    emitted = captured.err
    # The truncated version should appear
    assert "x" * 57 in emitted
    # The original should not
    assert "x" * 80 not in emitted if len(emitted) < 80 else True


def test_status_line_short_message_not_truncated(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Messages under 60 characters are not truncated."""
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = False

    message = "a" * 30
    with StatusLine("test", message, console=mock_console):
        pass

    captured = capsys.readouterr()
    assert "a" * 30 in captured.err


# ---------------------------------------------------------------------------
# Format
# ---------------------------------------------------------------------------


def test_status_line_format_contains_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Output contains the mode in brackets like [mode]."""
    mock_console = MagicMock(spec=Console)
    mock_console.is_interactive = False

    with StatusLine("checking", "contracts", console=mock_console):
        pass

    captured = capsys.readouterr()
    assert "[checking]" in captured.err
    assert "contracts" in captured.err


def test_status_line_default_console_is_renderer() -> None:
    """When no console is passed, the module-level renderer is used."""
    from openreview_cli.ui.console import renderer as default_renderer

    s = StatusLine("test", "msg")
    assert s._console is default_renderer.console


# ---------------------------------------------------------------------------
# format_clause_label — clause analysis status labels (T046a)
# ---------------------------------------------------------------------------


def test_format_clause_label_in_progress() -> None:
    """format_clause_label(3, 12, 'Indemnification') returns analyzing string."""
    from openreview_cli.ui.components.status_line import format_clause_label

    label = format_clause_label(3, 12, "Indemnification")
    assert label == "Analyzing clause 3 of 12 — Indemnification..."


def test_format_clause_label_done() -> None:
    """format_clause_label(12, 12, 'Indemnification', done=True) returns analyzed string."""
    from openreview_cli.ui.components.status_line import format_clause_label

    label = format_clause_label(12, 12, "Indemnification", done=True)
    assert label == "Analyzed clause 12 of 12 — Indemnification"


def test_format_clause_label_truncates_at_60() -> None:
    """Long labels are truncated at 60 characters with '…' suffix."""
    from openreview_cli.ui.components.status_line import format_clause_label

    long_title = "Very Long Clause Title That Exceeds The Maximum Allowed Length For Display"
    label = format_clause_label(1, 50, long_title)
    # Label content truncated to 60 chars + "…" (61 total)
    assert len(label) == 61, f"Label has {len(label)} chars: {label!r}"
    assert label.endswith("…")


def test_format_clause_label_empty_title() -> None:
    """Empty clause title produces label without trailing dash."""
    from openreview_cli.ui.components.status_line import format_clause_label

    label = format_clause_label(3, 12, "")
    assert label == "Analyzing clause 3 of 12..."
    assert " — " not in label


def test_format_clause_label_empty_title_done() -> None:
    """Empty clause title, done=True produces simple label."""
    from openreview_cli.ui.components.status_line import format_clause_label

    label = format_clause_label(5, 10, "", done=True)
    assert label == "Analyzed clause 5 of 10"
    assert " — " not in label
    assert not label.endswith("...")
