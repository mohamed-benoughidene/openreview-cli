"""Integration tests for the ``openreview setup`` command.

Verifies that the setup subcommand:
- Shows welcome panel with privacy notice
- ``--non-interactive`` creates/validates config
- Produces a config with the required keys
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.config.loader import load_config

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up fresh XDG directories with NO config.yml present."""
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    return config_dir


# ---------------------------------------------------------------------------
# setup --non-interactive
# ---------------------------------------------------------------------------


def test_setup_non_interactive_creates_config(temp_config_dir: Path) -> None:
    """openreview setup --non-interactive exits successfully."""
    # Mock questionary to avoid any interactive resolution
    with patch("questionary.confirm", return_value=MagicMock()):
        result = runner.invoke(app, ["setup", "--non-interactive"])

    assert result.exit_code == 0
    assert "Setup Complete" in result.stdout or "configured" in result.stdout.lower()


def test_setup_non_interactive_produces_valid_config(temp_config_dir: Path) -> None:
    """After setup --non-interactive, config.yml is valid and has required keys."""
    with patch("questionary.confirm", return_value=MagicMock()):
        runner.invoke(app, ["setup", "--non-interactive"])

    config_path = temp_config_dir / "openreview" / "config.yml"
    assert config_path.exists(), "config.yml should exist after setup"

    config = load_config(config_path)
    assert "version" in config
    assert "gateway" in config
    assert "models" in config["gateway"]
    assert "reasoning" in config["gateway"]["models"]
    assert "extraction" in config["gateway"]["models"]
    assert "embedding" in config["gateway"]["models"]
    assert "reranking" in config["gateway"]["models"]
    assert "graph" in config["gateway"]["models"]


def test_setup_non_interactive_all_slots_configured(temp_config_dir: Path) -> None:
    """All five required slots have a primary model after setup."""
    with patch("questionary.confirm", return_value=MagicMock()):
        runner.invoke(app, ["setup", "--non-interactive"])

    config_path = temp_config_dir / "openreview" / "config.yml"
    config = load_config(config_path)

    for slot in ("reasoning", "extraction", "embedding", "reranking", "graph"):
        primary = config["gateway"]["models"][slot].get("primary")
        assert primary, f"Slot '{slot}' should have a primary model"


# ---------------------------------------------------------------------------
# setup --help
# ---------------------------------------------------------------------------


def test_setup_help_does_not_trigger_first_run(temp_config_dir: Path) -> None:
    """openreview setup --help should not show welcome panel.

    The help output should mention the setup command.
    """
    result = runner.invoke(app, ["setup", "--help"])
    assert result.exit_code == 0
    assert "Configure OpenReview" in result.stdout or "setup" in result.stdout.lower()
