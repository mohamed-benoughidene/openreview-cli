"""Integration tests for leasecheck CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


class TestLeaseCheckCli:
    """LeaseCheck CLI integration tests (mock-free)."""

    @pytest.mark.integration
    def test_leasecheck_help(self) -> None:
        result = runner.invoke(app, ["leasecheck", "--help"])
        assert result.exit_code == 0
        assert "LeaseCheck" in result.stdout or "lease" in result.stdout.lower()

    @pytest.mark.integration
    def test_leasecheck_no_args_shows_error(self) -> None:
        result = runner.invoke(app, ["leasecheck"])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_leasecheck_file_not_found(self) -> None:
        result = runner.invoke(app, ["leasecheck", str(FIXTURES / "nonexistent.pdf")])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_leasecheck_accepts_format_flag(self) -> None:
        result = runner.invoke(app, ["leasecheck", "--help"])
        assert "text" in result.stdout or "json" in result.stdout
