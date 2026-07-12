"""Tests for TUI dispatch logic in app.py.

T006: When openreview runs with no subcommand and a TTY is attached,
the TUI should launch. When no TTY, launcher handles friendly message.
--no-tui forces CLI mode (help output).
"""

import sys
from unittest.mock import patch

from typer.testing import CliRunner

import openreview_cli.app as app_module
from openreview_cli import __version__

runner = CliRunner()


def test_no_args_with_tty_launches_tui(monkeypatch):
    """Invoking with no args and a TTY should launch the TUI."""
    monkeypatch.setattr("openreview_cli.app._init", lambda debug: None)

    with patch("openreview_cli.tui.launcher.launch_tui") as mock_launch:
        result = runner.invoke(app_module.app, [])

    assert result.exit_code == 0
    assert mock_launch.called


def test_no_args_without_tty_prints_message(monkeypatch):
    """Invoking with no args and no TTY should print friendly message."""
    monkeypatch.setattr("openreview_cli.app._init", lambda debug: None)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

    # Do NOT mock launch_tui — let real launcher handle non-TTY path
    result = runner.invoke(app_module.app, [])

    assert result.exit_code == 0
    assert "interactive terminal" in result.output


def test_no_tui_flag_skips_tui(monkeypatch):
    """--no-tui should skip TUI and show help even with TTY."""
    monkeypatch.setattr("openreview_cli.app._init", lambda debug: None)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(app_module, "_NO_TUI", True)

    with patch("openreview_cli.tui.launcher.launch_tui") as mock_launch:
        result = runner.invoke(app_module.app, [])

    assert result.exit_code == 0
    assert not mock_launch.called
    assert "openreview" in result.stdout.lower()


def test_subcommand_unchanged():
    """Existing subcommands should still work normally."""
    result = runner.invoke(app_module.app, ["parse", "--help"])
    assert result.exit_code == 0
    assert "parse" in result.stdout.lower()


def test_version_unchanged():
    """--version should still work."""
    result = runner.invoke(app_module.app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_unchanged():
    """--help should still work."""
    result = runner.invoke(app_module.app, ["--help"])
    assert result.exit_code == 0
    assert "openreview" in result.stdout.lower()
