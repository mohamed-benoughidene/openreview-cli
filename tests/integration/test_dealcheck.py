"""Integration tests for dealcheck CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


class TestDealCheckCli:
    """DealCheck CLI integration tests (mock-free)."""

    @pytest.mark.integration
    def test_dealcheck_help(self) -> None:
        result = runner.invoke(app, ["dealcheck", "--help"])
        assert result.exit_code == 0
        assert "DealCheck" in result.stdout or "vendor" in result.stdout.lower()

    @pytest.mark.integration
    def test_dealcheck_no_args_shows_error(self) -> None:
        result = runner.invoke(app, ["dealcheck"])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_dealcheck_file_not_found(self) -> None:
        result = runner.invoke(app, ["dealcheck", str(FIXTURES / "nonexistent.pdf")])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_dealcheck_accepts_format_flag(self) -> None:
        result = runner.invoke(app, ["dealcheck", "--help"])
        assert "text" in result.stdout or "json" in result.stdout
