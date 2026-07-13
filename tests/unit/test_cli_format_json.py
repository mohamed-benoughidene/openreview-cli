"""Unit tests for ``--format json`` on CLI commands.

T033: Verify that all gateway commands accept ``--format json`` and
produce valid machine-parseable JSON output.

TDD phase: these tests will FAIL until --format flags are added (T036).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()


class TestGatewayStatusFormatJson:
    """``openreview gateway status --format json`` produces valid JSON."""

    @pytest.fixture(autouse=True)
    def _setup_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Isolated config dir with a valid config.yml."""
        config_dir = tmp_path / ".config" / "openreview"
        config_dir.mkdir(parents=True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))
        monkeypatch.setenv("XDG_LOG_HOME", str(tmp_path / ".cache"))

        # Minimal config.yml
        import yaml

        cfg = {
            "version": 2,
            "gateway": {
                "providers": {"openai": {"api_key": "sk-test"}},
                "models": {
                    "reasoning": {"provider": "openai", "model": "gpt-4o"},
                },
            },
        }
        (config_dir / "config.yml").write_text(yaml.dump(cfg))
        (config_dir / "auth.json").write_text(json.dumps({"openai": "sk-test"}))

    def test_gateway_status_json(self) -> None:
        """gateway status --format json produces valid JSON."""
        result = runner.invoke(app, ["gateway", "status", "--format", "json"])
        assert result.exit_code == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        # Should have slots/providers keys
        assert isinstance(data, dict)


class TestGatewayCostsFormatJson:
    """``openreview gateway costs --format json`` produces valid JSON."""

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

    def test_gateway_costs_today_json(self) -> None:
        """gateway costs --today --format json produces valid JSON."""
        result = runner.invoke(app, ["gateway", "costs", "--today", "--format", "json"])
        # May exit 0 or 2 (no db), but should produce valid JSON on stdout
        assert result.exit_code == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, dict)


class TestModelsAvailableFormatJson:
    """``openreview models available --format json`` (already works)."""

    def test_models_available_json_empty(self) -> None:
        """No providers → valid JSON output."""
        result = runner.invoke(app, ["models", "available", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "models" in data
        assert "providers_found" in data
        assert "total" in data
