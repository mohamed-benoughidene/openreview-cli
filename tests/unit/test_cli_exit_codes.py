"""Unit tests for structured exit codes per FR-031.

T034: Verify every error type returns the correct exit code:
  1 = user error (invalid input, missing args)
  2 = config error (missing/invalid config, schema violation)
  3 = provider error (API failure, auth failure, rate limit)

TDD phase: these tests will FAIL until exit codes are normalized (T037).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()


class TestExitCodeUserError:
    """Exit code 1 = user error."""

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

    def test_gateway_setup_no_stdin_exits_1(self) -> None:
        """gateway setup with no stdin → exit code 1."""
        result = runner.invoke(app, ["gateway", "setup"])
        assert result.exit_code == 1, f"expected 1 got {result.exit_code}: {result.stderr}"

    def test_invalid_slot_name_exits_1(self) -> None:
        """Invalid slot name → exit code 1."""
        result = runner.invoke(app, ["gateway", "test", "not-a-slot"])
        assert result.exit_code == 1, f"expected 1 got {result.exit_code}: {result.stderr}"

    def test_gateway_setup_invalid_json_exits_1(self) -> None:
        """Invalid JSON piped to gateway setup → exit code 1."""
        result = runner.invoke(app, ["gateway", "setup"], input="not: valid: json}")
        assert result.exit_code == 1, f"expected 1 got {result.exit_code}: {result.stderr}"


class TestExitCodeConfigError:
    """Exit code 2 = config error."""

    @pytest.fixture(autouse=True)
    def _setup_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._config_dir = tmp_path / ".config" / "openreview"
        self._config_dir.mkdir(parents=True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))
        monkeypatch.setenv("XDG_LOG_HOME", str(tmp_path / ".cache"))

    def test_config_get_unknown_key_exits_2(self) -> None:
        """config get with unknown key → exit code 2."""
        # Write a valid config first
        import yaml

        (self._config_dir / "config.yml").write_text(yaml.dump({"version": 2}))
        result = runner.invoke(app, ["config", "get", "nonexistent.key"])
        assert result.exit_code == 2, f"expected 2 got {result.exit_code}: {result.stderr}"


class TestExitCodeProviderError:
    """Exit code 3 = provider error."""

    @pytest.fixture(autouse=True)
    def _setup_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._config_dir = tmp_path / ".config" / "openreview"
        self._config_dir.mkdir(parents=True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))
        monkeypatch.setenv("XDG_LOG_HOME", str(tmp_path / ".cache"))
        # Valid config but no API keys → provider error when routing
        import yaml

        cfg = {
            "version": 2,
            "gateway": {
                "providers": {"openai": {}},
                "models": {
                    "reasoning": {"provider": "openai", "model": "gpt-4o"},
                },
            },
        }
        (self._config_dir / "config.yml").write_text(yaml.dump(cfg))
        (self._config_dir / "auth.json").write_text("{}")

    def test_no_api_key_exits_3(self) -> None:
        """Missing API key for provider → exit code 3."""
        result = runner.invoke(app, ["gateway", "test", "reasoning"])
        assert result.exit_code == 3, f"expected 3 got {result.exit_code}: {result.stderr}"
