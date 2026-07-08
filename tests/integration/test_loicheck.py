"""Integration tests for loicheck CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


class TestLOICheckCli:
    """LOICheck CLI integration tests (mock-free)."""

    @pytest.mark.integration
    def test_loicheck_help(self) -> None:
        result = runner.invoke(app, ["loicheck", "--help"])
        assert result.exit_code == 0
        assert "LOICheck" in result.stdout or "letter of intent" in result.stdout.lower()

    @pytest.mark.integration
    def test_loicheck_no_args_shows_error(self) -> None:
        result = runner.invoke(app, ["loicheck"])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_loicheck_file_not_found(self) -> None:
        result = runner.invoke(app, ["loicheck", str(FIXTURES / "nonexistent.pdf")])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_loicheck_accepts_format_flag(self) -> None:
        result = runner.invoke(app, ["loicheck", "--help"])
        assert "text" in result.stdout or "json" in result.stdout
