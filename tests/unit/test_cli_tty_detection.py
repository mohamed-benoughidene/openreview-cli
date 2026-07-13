"""Unit tests for TTY detection per FR-030.

T035: Verify that commands detect non-TTY context and behave correctly:
  - Non-TTY with no stdin → exit 1, usage message
  - Non-TTY with piped data → process normally
  - TTY context → work as expected

TDD phase: some tests may FAIL until TTY detection is fully wired (T038).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()


class TestGatewaySetupTtyDetection:
    """``openreview gateway setup`` TTY detection."""

    @pytest.fixture(autouse=True)
    def _setup_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_dir = tmp_path / ".config" / "openreview"
        config_dir.mkdir(parents=True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))
        monkeypatch.setenv("XDG_LOG_HOME", str(tmp_path / ".cache"))

    def test_non_tty_no_stdin_exits_1(self) -> None:
        """Non-TTY with no stdin → exit 1 with usage message."""
        result = runner.invoke(app, ["gateway", "setup"])
        assert result.exit_code == 1, f"expected 1 got {result.exit_code}: {result.stderr}"
        assert "No config provided" in result.stdout or "No config provided" in (
            result.stderr or ""
        )

    def test_non_tty_with_stdin_processes(self, tmp_path: Path) -> None:
        """Non-TTY with piped JSON → processes normally."""
        valid_json = json.dumps(
            {
                "version": 2,
                "providers": {
                    "openai": {
                        "name": "openai",
                        "api_key_source": "env",
                        "env_key": "OPENAI_API_KEY",
                    },
                },
                "slots": {
                    "reasoning": {"provider": "openai", "model": "gpt-4o"},
                },
            }
        )
        result = runner.invoke(app, ["gateway", "setup"], input=valid_json)
        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "complete" in result.stdout.lower()

    def test_gateway_setup_dry_run_json_format(self) -> None:
        """--dry-run with --format json produces valid JSON."""
        valid_json = json.dumps(
            {
                "version": 2,
                "providers": {
                    "openai": {
                        "name": "openai",
                        "api_key_source": "env",
                        "env_key": "OPENAI_API_KEY",
                    },
                },
                "slots": {
                    "reasoning": {"provider": "openai", "model": "gpt-4o"},
                },
            }
        )
        result = runner.invoke(
            app, ["gateway", "setup", "--dry-run", "--format", "json"], input=valid_json
        )
        assert result.exit_code == 0, f"stderr: {result.stderr}"
        import json as _json

        data = _json.loads(result.stdout)
        assert data["status"] == "validated"
        assert data["dry_run"] is True


class TestNonInteractiveCommands:
    """Other commands should work without TTY."""

    @pytest.fixture(autouse=True)
    def _setup_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_dir = tmp_path / ".config" / "openreview"
        config_dir.mkdir(parents=True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))
        monkeypatch.setenv("XDG_LOG_HOME", str(tmp_path / ".cache"))

    def test_gateway_status_non_tty(self) -> None:
        """gateway status works without TTY."""
        result = runner.invoke(app, ["gateway", "status"])
        assert result.exit_code in (0, 2), f"unexpected exit {result.exit_code}: {result.stderr}"

    def test_models_available_non_tty(self) -> None:
        """models available works without TTY."""
        result = runner.invoke(app, ["models", "available"])
        assert result.exit_code == 0, f"stderr: {result.stderr}"
