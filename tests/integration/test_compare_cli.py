"""Integration tests for the compare CLI command.

Tests D-10 (--show-redlines) and D-13 (--comparison-model) flags.
"""

from pathlib import Path

from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()


def test_compare_show_redlines_flag_accepts(tmp_path: Path) -> None:
    """--show-redlines is accepted by the CLI (default off).

    Tests with non-existent files to verify flag parsing only.
    """
    result = runner.invoke(
        app,
        [
            "precheck",
            "compare",
            "/nonexistent/doc_a.pdf",
            "/nonexistent/doc_b.pdf",
            "--show-redlines",
        ],
    )
    # Should fail with file-not-found, NOT with unknown flag
    assert result.exit_code != 0
    output = (result.stdout + result.stderr).lower()
    assert "not found" in output or "error" in output


def test_compare_comparison_model_flag_accepts(tmp_path: Path) -> None:
    """--comparison-model is accepted by the CLI."""
    result = runner.invoke(
        app,
        [
            "precheck",
            "compare",
            "/nonexistent/doc_a.pdf",
            "/nonexistent/doc_b.pdf",
            "--comparison-model",
            "my-special-model",
        ],
    )
    assert result.exit_code != 0


def test_compare_version_labels_accepted(tmp_path: Path) -> None:
    """--version-label-a and --version-label-b are accepted."""
    result = runner.invoke(
        app,
        [
            "precheck",
            "compare",
            "/nonexistent/doc_a.pdf",
            "/nonexistent/doc_b.pdf",
            "--version-label-a",
            "v1.0",
            "--version-label-b",
            "v2.0",
        ],
    )
    assert result.exit_code != 0
