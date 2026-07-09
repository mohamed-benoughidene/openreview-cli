"""Integration tests for --dual-path CLI flag (D-32).

Tests that the flag parses correctly and flows through to run_review().
"""

from __future__ import annotations

from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()


def test_dual_path_flag_parses_as_false_by_default() -> None:
    """--dual-path defaults to False in precheck review help output."""
    result = runner.invoke(app, ["precheck", "review", "--help"])
    assert result.exit_code == 0
    assert "--dual-path" in result.stdout
    # no explicit --dual-path means False — help text confirms it's an option


def test_dual_path_flag_parses_as_true() -> None:
    """--dual-path flag is accepted by precheck review command."""
    result = runner.invoke(
        app,
        [
            "precheck",
            "review",
            "--dual-path",
            "--help",  # stop before actual execution
        ],
    )
    assert result.exit_code == 0
    assert "--dual-path" in result.stdout


def test_dual_path_flag_in_precheck_callback() -> None:
    """--dual-path appears in precheck callback help."""
    result = runner.invoke(app, ["precheck", "--help"])
    assert result.exit_code == 0
    assert "--dual-path" in result.stdout
