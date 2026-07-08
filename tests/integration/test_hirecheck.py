"""Integration tests for hirecheck CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


class TestHireCheckCli:
    """HireCheck CLI integration tests (mock-free)."""

    @pytest.mark.integration
    def test_hirecheck_help(self) -> None:
        result = runner.invoke(app, ["hirecheck", "--help"])
        assert result.exit_code == 0
        assert "HireCheck" in result.stdout or "employment" in result.stdout.lower()

    @pytest.mark.integration
    def test_hirecheck_no_args_shows_error(self) -> None:
        result = runner.invoke(app, ["hirecheck"])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_hirecheck_file_not_found(self) -> None:
        result = runner.invoke(app, ["hirecheck", str(FIXTURES / "nonexistent.pdf")])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_hirecheck_accepts_format_flag(self) -> None:
        result = runner.invoke(app, ["hirecheck", "--help"])
        assert "text" in result.stdout or "json" in result.stdout
