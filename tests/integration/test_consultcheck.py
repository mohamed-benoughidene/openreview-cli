"""Integration tests for consultcheck CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


class TestConsultCheckCli:
    """ConsultCheck CLI integration tests (mock-free)."""

    @pytest.mark.integration
    def test_consultcheck_help(self) -> None:
        result = runner.invoke(app, ["consultcheck", "--help"])
        assert result.exit_code == 0
        assert "ConsultCheck" in result.stdout or "consulting" in result.stdout.lower()

    @pytest.mark.integration
    def test_consultcheck_no_args_shows_error(self) -> None:
        result = runner.invoke(app, ["consultcheck"])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_consultcheck_file_not_found(self) -> None:
        result = runner.invoke(app, ["consultcheck", str(FIXTURES / "nonexistent.pdf")])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_consultcheck_accepts_format_flag(self) -> None:
        result = runner.invoke(app, ["consultcheck", "--help"])
        assert "text" in result.stdout or "json" in result.stdout
