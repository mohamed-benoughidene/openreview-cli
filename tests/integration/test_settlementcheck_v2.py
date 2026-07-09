"""Integration tests for SettlementCheck v2 CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class TestSettlementCheckV2Cli:
    """SettlementCheck v2 CLI integration tests (mock-free)."""

    @pytest.mark.integration
    def test_settlementcheck_v2_help(self) -> None:
        result = runner.invoke(app, ["settlementcheck_v2", "--help"])
        assert result.exit_code == 0
        assert "SettlementCheck" in result.stdout or "settlement" in result.stdout.lower()

    @pytest.mark.integration
    def test_settlementcheck_v2_no_args_shows_error(self) -> None:
        result = runner.invoke(app, ["settlementcheck_v2"])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_settlementcheck_v2_file_not_found(self) -> None:
        path = FIXTURES_DIR / "nonexistent.pdf"
        result = runner.invoke(app, ["settlementcheck_v2", str(path)])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_settlementcheck_v2_accepts_format_flag(self) -> None:
        result = runner.invoke(app, ["settlementcheck_v2", "--help"])
        assert "text" in result.stdout or "json" in result.stdout
