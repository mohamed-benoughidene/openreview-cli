"""Integration tests for privacycheck CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


class TestPrivacyCheckCli:
    """PrivacyCheck CLI integration tests (mock-free)."""

    @pytest.mark.integration
    def test_privacycheck_help(self) -> None:
        result = runner.invoke(app, ["privacycheck", "--help"])
        assert result.exit_code == 0
        assert "PrivacyCheck" in result.stdout or "data processing" in result.stdout.lower()

    @pytest.mark.integration
    def test_privacycheck_no_args_shows_error(self) -> None:
        result = runner.invoke(app, ["privacycheck"])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_privacycheck_file_not_found(self) -> None:
        result = runner.invoke(app, ["privacycheck", str(FIXTURES / "nonexistent.pdf")])
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_privacycheck_accepts_format_flag(self) -> None:
        result = runner.invoke(app, ["privacycheck", "--help"])
        assert "text" in result.stdout or "json" in result.stdout
