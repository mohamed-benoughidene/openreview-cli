"""Integration tests for the ``openreview config`` subcommands.

Verifies real file I/O on a temporary config directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from typer.testing import CliRunner

if TYPE_CHECKING:
    import pytest

from openreview_cli.app import app
from openreview_cli.config.loader import load_config

runner = CliRunner()


def _setup_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    from openreview_cli.config.paths import get_config_dir

    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.yml"


class TestConfigSet:
    """openreview config set …"""

    def test_set_writes_to_config_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config_file = _setup_config(monkeypatch, tmp_path)
        config_file.write_text(
            "version: 1\ngateway:\n  models:\n    reasoning:\n      primary: ollama/qwen3:8b\n"
        )

        result = runner.invoke(
            app, ["config", "set", "gateway.models.reasoning.primary", "ollama/llama3"]
        )

        assert result.exit_code == 0
        reloaded = load_config(config_file)
        assert reloaded["gateway"]["models"]["reasoning"]["primary"] == "ollama/llama3"


class TestConfigGet:
    """openreview config get …"""

    def test_get_reads_back_value(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        config_file = _setup_config(monkeypatch, tmp_path)
        config_file.write_text("version: 1\nprivacy:\n  tier: maximum\n")

        result = runner.invoke(app, ["config", "get", "privacy.tier"])

        assert result.exit_code == 0
        assert result.stdout.strip() == "maximum"


class TestConfigShow:
    """openreview config show …"""

    def test_show_json_output(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        config_file = _setup_config(monkeypatch, tmp_path)
        config_file.write_text("version: 1\nprivacy:\n  tier: performance\n")

        result = runner.invoke(app, ["config", "show", "--output", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["privacy"]["tier"] == "performance"

    def test_show_table_output_default(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config_file = _setup_config(monkeypatch, tmp_path)
        config_file.write_text("version: 1\nprivacy:\n  tier: balanced\n")

        result = runner.invoke(app, ["config", "show"])

        assert result.exit_code == 0
        assert "balanced" in result.stdout
        assert "privacy" in result.stdout.lower()


class TestConfigSetUnknownKey:
    """openreview config set <unknown> …"""

    def test_unknown_key_exits_with_code_2(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config_file = _setup_config(monkeypatch, tmp_path)
        config_file.write_text("version: 1\nprivacy:\n  tier: balanced\n")

        result = runner.invoke(app, ["config", "set", "unknown.key", "value"])

        assert result.exit_code == 2
        assert "Unknown config key" in result.stdout


class TestConfigUnset:
    """openreview config unset …"""

    def test_unset_resets_to_default(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        config_file = _setup_config(monkeypatch, tmp_path)
        config_file.write_text("version: 1\nprivacy:\n  tier: maximum\n")

        result = runner.invoke(app, ["config", "unset", "privacy.tier"])

        assert result.exit_code == 0
        reloaded = load_config(config_file)
        assert reloaded["privacy"]["tier"] == "balanced"


class TestConfigPath:
    """openreview config path …"""

    def test_path_returns_directory(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _setup_config(monkeypatch, tmp_path)

        result = runner.invoke(app, ["config", "path"])

        assert result.exit_code == 0
        assert "openreview" in result.stdout.lower()


class TestCorruptedConfig:
    """Corrupted config file handling."""

    def test_corrupted_yaml_shows_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config_file = _setup_config(monkeypatch, tmp_path)
        config_file.write_text("{invalid: yaml: [broken")

        result = runner.invoke(app, ["config", "show"])

        assert result.exit_code == 3
        assert "setup" in result.stdout.lower()
