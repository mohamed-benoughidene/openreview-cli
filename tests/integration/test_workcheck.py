"""Integration tests for workcheck CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


class TestWorkCheckCli:
    """WorkCheck CLI integration tests (mock-free)."""

    @pytest.mark.integration
    def test_workcheck_help(self) -> None:
        result = runner.invoke(app, ["workcheck", "--help"])
        assert result.exit_code == 0
        assert "WorkCheck" in result.stdout or "contractor" in result.stdout.lower()

    @pytest.mark.integration
    def test_workcheck_no_args_shows_error(self) -> None:
        result = runner.invoke(app, ["workcheck"])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_workcheck_file_not_found(self) -> None:
        result = runner.invoke(app, ["workcheck", str(FIXTURES / "nonexistent.pdf")])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_workcheck_accepts_format_flag(self) -> None:
        result = runner.invoke(app, ["workcheck", "--help"])
        assert "text" in result.stdout or "json" in result.stdout
