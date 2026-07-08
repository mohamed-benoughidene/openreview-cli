"""Integration tests for subcheck CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


class TestSubCheckCli:
    """SubCheck CLI integration tests (mock-free)."""

    @pytest.mark.integration
    def test_subcheck_help(self) -> None:
        result = runner.invoke(app, ["subcheck", "--help"])
        assert result.exit_code == 0
        assert "SubCheck" in result.stdout or "subcontractor" in result.stdout.lower()

    @pytest.mark.integration
    def test_subcheck_no_args_shows_error(self) -> None:
        result = runner.invoke(app, ["subcheck"])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_subcheck_file_not_found(self) -> None:
        result = runner.invoke(app, ["subcheck", str(FIXTURES / "nonexistent.pdf")])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_subcheck_accepts_format_flag(self) -> None:
        result = runner.invoke(app, ["subcheck", "--help"])
        assert "text" in result.stdout or "json" in result.stdout
