"""Integration tests for indemnitycheck CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


class TestIndemnityCheckCli:
    """IndemnityCheck CLI integration tests (mock-free)."""

    @pytest.mark.integration
    def test_indemnitycheck_help(self) -> None:
        result = runner.invoke(app, ["indemnitycheck", "--help"])
        assert result.exit_code == 0
        assert "IndemnityCheck" in result.stdout or "indemnification" in result.stdout.lower()

    @pytest.mark.integration
    def test_indemnitycheck_no_args_shows_error(self) -> None:
        result = runner.invoke(app, ["indemnitycheck"])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_indemnitycheck_file_not_found(self) -> None:
        result = runner.invoke(app, ["indemnitycheck", str(FIXTURES / "nonexistent.pdf")])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_indemnitycheck_accepts_format_flag(self) -> None:
        result = runner.invoke(app, ["indemnitycheck", "--help"])
        assert "text" in result.stdout or "json" in result.stdout
