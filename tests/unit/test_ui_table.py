"""Tests for the SGTable component (table, json, plain output)."""

from __future__ import annotations

import json
import shutil
from typing import TYPE_CHECKING

from openreview_cli.types import OutputFormat
from openreview_cli.ui.components.table import SGTable

if TYPE_CHECKING:
    import pytest
    from _pytest.capture import CaptureFixture


# ---------------------------------------------------------------------------
# Default — Rich Table
# ---------------------------------------------------------------------------


def test_table_renders_rich(capsys: CaptureFixture[str]) -> None:
    """By default SGTable renders a Rich Table (box-drawing chars)."""
    table = SGTable(
        title="Test Table",
        columns=[("Name", "bold", 20), ("Value", "green", 10)],
        rows=[("Alice", "42"), ("Bob", "17")],
    )
    table.render()
    captured = capsys.readouterr()
    # Rich tables use box-drawing characters like ─ │
    assert "─" in captured.out or "━" in captured.out
    assert "Alice" in captured.out
    assert "Bob" in captured.out
    assert "42" in captured.out
    assert "17" in captured.out
    assert "Test Table" in captured.out
    assert "Name" in captured.out
    assert "Value" in captured.out


def test_table_header_style(capsys: CaptureFixture[str]) -> None:
    """Column headers render with header_style."""
    table = SGTable(
        title="H",
        columns=[("Col A", "bold underline", 20)],
        rows=[("data",)],
    )
    table.render()
    captured = capsys.readouterr()
    assert "Col A" in captured.out
    assert "data" in captured.out


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


def test_table_json_output(capsys: CaptureFixture[str]) -> None:
    """With output_format=JSON, SGTable prints JSON to stdout."""
    table = SGTable(
        title="JSON Test",
        columns=[("Name", "", 20), ("Count", "", 5)],
        rows=[("x", "1"), ("y", "2")],
        output_format=OutputFormat.JSON,
    )
    table.render()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0] == {"Name": "x", "Count": "1"}
    assert data[1] == {"Name": "y", "Count": "2"}


def test_table_json_empty(capsys: CaptureFixture[str]) -> None:
    """Empty table in JSON mode prints an empty list."""
    table = SGTable(
        title="Empty",
        columns=[("K", "", 10)],
        rows=[],
        output_format=OutputFormat.JSON,
    )
    table.render()
    captured = capsys.readouterr()
    assert json.loads(captured.out) == []


# ---------------------------------------------------------------------------
# Plain output
# ---------------------------------------------------------------------------


def test_table_plain_output(capsys: CaptureFixture[str]) -> None:
    """With output_format=PLAIN, SGTable prints fixed-width columns
    without borders or colour."""
    table = SGTable(
        title="Plain Table",
        columns=[("Name", "", 10), ("Value", "", 8)],
        rows=[("Alice", "42"), ("Bob", "99")],
        output_format=OutputFormat.PLAIN,
    )
    table.render()
    captured = capsys.readouterr()
    # No box drawing
    assert "─" not in captured.out
    assert "━" not in captured.out
    assert "│" not in captured.out
    # Headers should appear
    assert "Name" in captured.out
    assert "Value" in captured.out
    # Data should appear, aligned
    assert "Alice" in captured.out
    assert "42" in captured.out
    assert "Bob" in captured.out
    assert "99" in captured.out


def test_table_plain_no_color(capsys: CaptureFixture[str]) -> None:
    """Plain mode strips ANSI colour codes."""
    table = SGTable(
        title="NC",
        columns=[("X", "bold red", 10)],
        rows=[("val",)],
        output_format=OutputFormat.PLAIN,
    )
    table.render()
    captured = capsys.readouterr()
    # No ANSI escapes in plain mode
    assert "\x1b[" not in captured.out


# ---------------------------------------------------------------------------
# Empty table — "No data"
# ---------------------------------------------------------------------------


def test_table_empty_rich(capsys: CaptureFixture[str]) -> None:
    """Empty Rich table shows a 'No data' message."""
    table = SGTable(
        title="Empty",
        columns=[("A", "", 10)],
        rows=[],
    )
    table.render()
    captured = capsys.readouterr()
    assert "No data" in captured.out or "no data" in captured.out.lower()


def test_table_empty_json(capsys: CaptureFixture[str]) -> None:
    """Empty JSON table shows an empty list."""
    table = SGTable(
        title="Empty",
        columns=[("A", "", 10)],
        rows=[],
        output_format=OutputFormat.JSON,
    )
    table.render()
    captured = capsys.readouterr()
    assert json.loads(captured.out) == []


def test_table_empty_plain(capsys: CaptureFixture[str]) -> None:
    """Empty plain table shows a 'No data' message."""
    table = SGTable(
        title="Empty",
        columns=[("A", "", 10)],
        rows=[],
        output_format=OutputFormat.PLAIN,
    )
    table.render()
    captured = capsys.readouterr()
    assert "No data" in captured.out or "no data" in captured.out.lower()


# ---------------------------------------------------------------------------
# T068 — Narrow terminal (<60 cols)
# ---------------------------------------------------------------------------


def test_table_rich_narrow_terminal_no_crash(
    capsys: CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rich table does not crash when terminal width is <60 columns."""
    import os

    monkeypatch.setattr(
        shutil,
        "get_terminal_size",
        lambda fallback=(80, 24): os.terminal_size((50, 24)),
    )
    table = SGTable(
        title="Narrow",
        columns=[("Long Column Name", "bold", 30), ("Value", "green", 20)],
        rows=[("Alice has a very long name here", "42"), ("Bob", "A very long value indeed")],
    )
    # Must not raise
    table.render()
    captured = capsys.readouterr()
    assert "Alice" in captured.out or "Long Column" in captured.out


def test_table_plain_narrow_terminal_no_crash(
    capsys: CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Plain-mode table does not crash when terminal width is <60 columns."""
    import os

    monkeypatch.setattr(
        shutil,
        "get_terminal_size",
        lambda fallback=(80, 24): os.terminal_size((50, 24)),
    )
    table = SGTable(
        title="Narrow",
        columns=[("A", "", 40), ("B", "", 40)],
        rows=[("x", "y")],
        output_format=OutputFormat.PLAIN,
    )
    # Must not raise
    table.render()
    captured = capsys.readouterr()
    assert "x" in captured.out
    assert "y" in captured.out


def test_table_narrow_produces_some_output(
    capsys: CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Narrow terminal output is not empty."""
    import os

    monkeypatch.setattr(
        shutil,
        "get_terminal_size",
        lambda fallback=(80, 24): os.terminal_size((50, 24)),
    )
    table = SGTable(
        title="Test",
        columns=[("Col", "bold", 30)],
        rows=[("data",)],
    )
    table.render()
    captured = capsys.readouterr()
    assert captured.out.strip(), "Expected non-empty output on narrow terminal"
