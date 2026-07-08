"""Integration tests for settlementcheck CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


class TestSettlementCheckCli:
    """SettlementCheck CLI integration tests (mock-free)."""

    @pytest.mark.integration
    def test_settlementcheck_help(self) -> None:
        result = runner.invoke(app, ["settlementcheck", "--help"])
        assert result.exit_code == 0
        assert "SettlementCheck" in result.stdout or "settlement" in result.stdout.lower()

    @pytest.mark.integration
    def test_settlementcheck_no_args_shows_error(self) -> None:
        result = runner.invoke(app, ["settlementcheck"])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_settlementcheck_file_not_found(self) -> None:
        result = runner.invoke(app, ["settlementcheck", str(FIXTURES / "nonexistent.pdf")])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_settlementcheck_accepts_format_flag(self) -> None:
        result = runner.invoke(app, ["settlementcheck", "--help"])
        assert "text" in result.stdout or "json" in result.stdout
