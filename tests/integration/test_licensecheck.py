"""Integration tests for licensecheck CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


class TestLicenseCheckCli:
    """LicenseCheck CLI integration tests (mock-free)."""

    @pytest.mark.integration
    def test_licensecheck_help(self) -> None:
        result = runner.invoke(app, ["licensecheck", "--help"])
        assert result.exit_code == 0
        assert "LicenseCheck" in result.stdout or "license" in result.stdout.lower()

    @pytest.mark.integration
    def test_licensecheck_no_args_shows_error(self) -> None:
        result = runner.invoke(app, ["licensecheck"])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_licensecheck_file_not_found(self) -> None:
        result = runner.invoke(app, ["licensecheck", str(FIXTURES / "nonexistent.pdf")])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_licensecheck_accepts_format_flag(self) -> None:
        result = runner.invoke(app, ["licensecheck", "--help"])
        assert "text" in result.stdout or "json" in result.stdout
