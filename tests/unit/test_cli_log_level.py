"""Unit/integration tests for CLI log-level resolution (P1/C2).

The CLI must be quiet by default: a normal command should not print the
``[INFO] config loaded`` / ``[INFO] auth configured`` /
``[INFO] database initialized`` startup diagnostics to stderr. Those lines
are only expected with ``-v/--verbose`` (INFO) or ``--debug`` (DEBUG).
"""

from __future__ import annotations

import logging

from typer.testing import CliRunner

from openreview_cli.app import _log_level, app

_STARTUP_INFO_LINES = ("config loaded", "auth configured", "database initialized")


def test_log_level_default_is_warning() -> None:
    assert _log_level(debug=False, verbose=False) == logging.WARNING


def test_log_level_defaults_are_warning() -> None:
    """The helper itself defaults to quiet when called with no arguments."""
    assert _log_level() == logging.WARNING


def test_log_level_verbose_is_info() -> None:
    assert _log_level(debug=False, verbose=True) == logging.INFO


def test_log_level_debug_is_debug() -> None:
    assert _log_level(debug=True, verbose=False) == logging.DEBUG


def test_log_level_debug_wins_over_verbose() -> None:
    assert _log_level(debug=True, verbose=True) == logging.DEBUG


def test_cli_emits_no_info_lines_by_default() -> None:
    """A normal command must not print INFO startup lines to stderr."""
    result = CliRunner().invoke(app, ["gateway", "costs"])
    assert result.exit_code == 0, result.output
    for line in _STARTUP_INFO_LINES:
        assert line not in result.stderr, result.stderr


def test_cli_verbose_flag_enables_info_lines() -> None:
    """The root -v/--verbose flag re-enables the INFO startup diagnostics."""
    result = CliRunner().invoke(app, ["--verbose", "gateway", "costs"])
    assert result.exit_code == 0, result.output
    assert "config loaded" in result.stderr, result.stderr
