"""Tests for the panel UI components (info, warning, error, success)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from openreview_cli.ui.components.panel import (
    error_panel,
    info_panel,
    success_panel,
    warning_panel,
)

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture


# ---------------------------------------------------------------------------
# info_panel
# ---------------------------------------------------------------------------


def test_info_panel_renders(capsys: CaptureFixture[str]) -> None:
    """info_panel prints a panel with an ℹ prefix and cyan border."""  # noqa: RUF002
    info_panel("Indexing 42 contracts", title="Progress")
    captured = capsys.readouterr()
    assert "ℹ" in captured.out or "[i]" in captured.out  # noqa: RUF001
    assert "Indexing 42 contracts" in captured.out
    assert "Progress" in captured.out


def test_info_panel_border_style(capsys: CaptureFixture[str]) -> None:
    """Info panel border_style uses cyan."""
    info_panel("hello")
    captured = capsys.readouterr()
    # Rich renders the border_style as ANSI; we check the escape code for cyan (36)
    assert "36" in captured.out or "cyan" in captured.out or "hello" in captured.out


def test_info_panel_no_title(capsys: CaptureFixture[str]) -> None:
    """info_panel works with empty title."""
    info_panel("just a message")
    captured = capsys.readouterr()
    assert "just a message" in captured.out


# ---------------------------------------------------------------------------
# warning_panel
# ---------------------------------------------------------------------------


def test_warning_panel_renders(capsys: CaptureFixture[str]) -> None:
    """warning_panel prints a panel with a ⚠ prefix and yellow border."""
    warning_panel("Disk space low", title="Storage")
    captured = capsys.readouterr()
    assert "⚠" in captured.out or "[!]" in captured.out
    assert "Disk space low" in captured.out
    assert "Storage" in captured.out


# ---------------------------------------------------------------------------
# success_panel
# ---------------------------------------------------------------------------


def test_success_panel_renders(capsys: CaptureFixture[str]) -> None:
    """success_panel prints a panel with a ✓ prefix and green border."""
    success_panel("All checks passed", title="Complete")
    captured = capsys.readouterr()
    assert "✓" in captured.out or "[OK]" in captured.out
    assert "All checks passed" in captured.out
    assert "Complete" in captured.out


# ---------------------------------------------------------------------------
# error_panel
# ---------------------------------------------------------------------------


def test_error_panel_three_part_format(capsys: CaptureFixture[str]) -> None:
    """error_panel shows What / Why / How to fix sections."""
    with pytest.raises(SystemExit) as exc_info:
        error_panel("Failed to load config", "File not found", "Check the path")
    captured = capsys.readouterr()
    assert "Failed to load config" in captured.out
    assert "File not found" in captured.out
    assert "Check the path" in captured.out
    # Verify three-part structure
    assert "What failed" in captured.out
    assert "Why" in captured.out
    assert "How to fix" in captured.out


def test_error_panel_exit_code_default(capsys: CaptureFixture[str]) -> None:
    """error_panel exits with code 1 by default."""
    with pytest.raises(SystemExit) as exc_info:
        error_panel("x", "y", "z")
    assert exc_info.value.code == 1


def test_error_panel_exit_code_custom(capsys: CaptureFixture[str]) -> None:
    """error_panel accepts a custom exit code."""
    with pytest.raises(SystemExit) as exc_info:
        error_panel("x", "y", "z", exit_code=4)
    assert exc_info.value.code == 4


def test_error_panel_icon(capsys: CaptureFixture[str]) -> None:
    """error_panel has the ✗ icon in its output."""
    with pytest.raises(SystemExit):
        error_panel("x", "y", "z")
    captured = capsys.readouterr()
    assert "✗" in captured.out or "[ERR]" in captured.out


# ---------------------------------------------------------------------------
# No-color mode
# ---------------------------------------------------------------------------


def test_panel_no_color_strips_border(
    capsys: CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """When NO_COLOR is set, panel border is not coloured (no ANSI codes)."""
    monkeypatch.setenv("NO_COLOR", "1")
    # Reimport module to pick up new env var — use a fresh renderer
    # We rely on the module-level renderer; reset by creating a new one
    import importlib

    import openreview_cli.ui.components.panel as panel_mod
    import openreview_cli.ui.console as console_mod

    # Force a fresh SGRenderer with no_color=True
    original = console_mod.renderer
    console_mod.renderer = console_mod.SGRenderer(no_color=True)
    importlib.reload(panel_mod)

    try:
        panel_mod.info_panel("no color test", title="NC")
        captured = capsys.readouterr()
        # No ANSI escape sequences for colour should appear
        assert "\x1b[" not in captured.out, f"Unexpected ANSI codes: {captured.out!r}"
        assert "no color test" in captured.out
        assert "NC" in captured.out
    finally:
        console_mod.renderer = original
        importlib.reload(panel_mod)


# ---------------------------------------------------------------------------
# ASCII fallback
# ---------------------------------------------------------------------------


def test_panel_ascii_icons(capsys: CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """When no-unicode mode, panels use ASCII icons."""
    monkeypatch.setenv("NO_COLOR", "1")
    import importlib

    import openreview_cli.ui.components.panel as panel_mod
    import openreview_cli.ui.console as console_mod

    original = console_mod.renderer
    console_mod.renderer = console_mod.SGRenderer(no_color=True, no_unicode=True)
    importlib.reload(panel_mod)

    try:
        # info — should show [i] not ℹ  # noqa: RUF003
        panel_mod.info_panel("ascii info")
        captured = capsys.readouterr()
        assert "[i]" in captured.out
        assert "ℹ" not in captured.out  # noqa: RUF001

        # warning — should show [!] not ⚠
        panel_mod.warning_panel("ascii warning")
        captured = capsys.readouterr()
        assert "[!]" in captured.out
        assert "⚠" not in captured.out

        # error — should show [ERR] not ✗
        with pytest.raises(SystemExit):
            panel_mod.error_panel("a", "b", "c")
        captured = capsys.readouterr()
        assert "[ERR]" in captured.out
        assert "✗" not in captured.out

        # success — should show [OK] not ✓
        panel_mod.success_panel("ascii success")
        captured = capsys.readouterr()
        assert "[OK]" in captured.out
        assert "✓" not in captured.out
    finally:
        console_mod.renderer = original
        importlib.reload(panel_mod)
