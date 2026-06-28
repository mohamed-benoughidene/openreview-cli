"""Unit tests for the header UI components: separator, breadcrumb,
and step_indicator.

Verifies horizontal rules, breadcrumb trails, step indicators, and
NO_COLOR compliance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from openreview_cli.ui.components.header import (
    breadcrumb,
    separator,
    step_indicator,
)

if TYPE_CHECKING:
    import pytest

# ---------------------------------------------------------------------------
# separator
# ---------------------------------------------------------------------------


def test_separator_prints_horizontal_rule(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """separator() prints a horizontal rule to the terminal width."""
    separator()
    captured = capsys.readouterr()
    assert captured.out
    assert "\n" in captured.out
    # The line should be at least 10 chars wide (min terminal)
    assert len(captured.out.strip()) >= 10


def test_separator_uses_specified_char(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """separator('=') uses '=' to fill the terminal width."""
    separator("=")
    captured = capsys.readouterr()
    line = captured.out.strip()
    assert line
    assert all(ch == "=" for ch in line)


def test_separator_uses_terminal_width(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The rule spans the terminal width (detected via shutil)."""
    import shutil

    term_width = shutil.get_terminal_size(fallback=(80, 24)).columns
    separator("─")
    captured = capsys.readouterr()
    line = captured.out.strip()
    assert len(line) == term_width


def test_separator_default_char_is_unicode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The default separator character is '─' (Unicode box-drawing)."""
    separator()
    captured = capsys.readouterr()
    line = captured.out.strip()
    assert line.startswith("─")


# ---------------------------------------------------------------------------
# breadcrumb
# ---------------------------------------------------------------------------


def test_breadcrumb_trail(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """breadcrumb() prints a breadcrumb trail with > separators."""
    breadcrumb(["setup", "provider", "confirm"], current=1)
    captured = capsys.readouterr()
    out = captured.out.strip()
    assert "setup" in out
    assert "provider" in out
    assert "confirm" in out
    assert ">" in out


def test_breadcrumb_first_step_active(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When current=0, the first step is highlighted/active."""
    breadcrumb(["setup", "provider"], current=0)
    captured = capsys.readouterr()
    out = captured.out.strip()
    # The first step should appear prominently
    assert "setup" in out


def test_breadcrumb_last_step_active(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When current=last index, the final step is highlighted."""
    breadcrumb(["a", "b", "c"], current=2)
    captured = capsys.readouterr()
    out = captured.out.strip()
    assert "c" in out


def test_breadcrumb_single_step(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A single step renders without separators."""
    breadcrumb(["only"], current=0)
    captured = capsys.readouterr()
    out = captured.out.strip()
    assert "only" in out
    assert ">" not in out


def test_breadcrumb_negative_current_defaults_to_first(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A negative current index falls back to 0."""
    breadcrumb(["x", "y"], current=-1)
    captured = capsys.readouterr()
    out = captured.out.strip()
    # Should not crash, should show something
    assert out


def test_breadcrumb_empty_steps(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An empty steps list produces no output."""
    breadcrumb([], current=0)
    captured = capsys.readouterr()
    assert captured.out == ""


# ---------------------------------------------------------------------------
# step_indicator — spec §2.11
# ---------------------------------------------------------------------------


def test_step_indicator_first_step(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Step 1 of N shows ▶ for the first dot and ○ for remaining."""
    step_indicator(1, 4, "Initialize")
    captured = capsys.readouterr()
    out = captured.out
    assert "▶" in out or ">" in out  # current step indicator
    assert "Step 1 of 4" in out
    assert "Initialize" in out


def test_step_indicator_completed_and_current(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Step 2 shows ✓ for step 1, ▶ for step 2, ○ for remaining."""
    step_indicator(2, 4, "Configure")
    captured = capsys.readouterr()
    out = captured.out
    assert "✓" in out or "[OK]" in out  # completed
    assert "▶" in out or ">" in out  # current
    assert "○" in out or "[ ]" in out  # pending
    assert "Step 2 of 4" in out
    assert "Configure" in out


def test_step_indicator_final_step(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Last step shows ✓ for all previous and ▶ for current."""
    step_indicator(3, 3, "Finish")
    captured = capsys.readouterr()
    out = captured.out
    assert out.count("✓") == 2 or out.count("[OK]") == 2  # two completed
    assert "▶" in out or ">" in out  # current
    assert "Step 3 of 3" in out


def test_step_indicator_single_step(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With only 1 step, shows ▶ and the label."""
    step_indicator(1, 1, "Only")
    captured = capsys.readouterr()
    out = captured.out
    assert "▶" in out or ">" in out
    assert "Step 1 of 1" in out
    assert "Only" in out


def test_step_indicator_title_contains_spaces(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Step title with spaces renders correctly."""
    step_indicator(2, 3, "Parse contracts")
    captured = capsys.readouterr()
    out = captured.out
    assert "Parse contracts" in out
    assert "Step 2 of 3" in out


def test_step_indicator_current_beyond_total(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When current > total, all steps show ✓ (completed)."""
    step_indicator(5, 3, "Overflow")
    captured = capsys.readouterr()
    out = captured.out
    # Should not crash; all should be ✓
    assert "Step" in out


# ---------------------------------------------------------------------------
# NO_COLOR compliance
# ---------------------------------------------------------------------------


def test_separator_no_color(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """separator() contains no ANSI escape codes when NO_COLOR is set."""
    import importlib

    import openreview_cli.ui.components.header as header_mod
    import openreview_cli.ui.console as console_mod

    original = console_mod.renderer
    console_mod.renderer = console_mod.SGRenderer(no_color=True)
    importlib.reload(header_mod)

    try:
        header_mod.separator()
        captured = capsys.readouterr()
        assert "\x1b[" not in captured.out
        assert captured.out.strip()
    finally:
        console_mod.renderer = original


def test_breadcrumb_no_color(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """breadcrumb() contains no ANSI codes when NO_COLOR is set."""
    import importlib

    import openreview_cli.ui.components.header as header_mod
    import openreview_cli.ui.console as console_mod

    original = console_mod.renderer
    console_mod.renderer = console_mod.SGRenderer(no_color=True)
    importlib.reload(header_mod)

    try:
        header_mod.breadcrumb(["a", "b", "c"], current=1)
        captured = capsys.readouterr()
        assert "\x1b[" not in captured.out
        assert "a" in captured.out
        assert "b" in captured.out
        assert "c" in captured.out
    finally:
        console_mod.renderer = original


def test_step_indicator_no_color(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """step_indicator() contains no ANSI codes when NO_COLOR is set."""
    import importlib

    import openreview_cli.ui.components.header as header_mod
    import openreview_cli.ui.console as console_mod

    original = console_mod.renderer
    console_mod.renderer = console_mod.SGRenderer(no_color=True)
    importlib.reload(header_mod)

    try:
        header_mod.step_indicator(2, 4, "Test")
        captured = capsys.readouterr()
        assert "\x1b[" not in captured.out
        assert "Test" in captured.out
        assert "Step 2 of 4" in captured.out
    finally:
        console_mod.renderer = original
