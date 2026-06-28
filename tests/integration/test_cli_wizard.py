"""Integration tests for the first-run wizard flow.

Tests verify that the CLI shows the welcome panel on first run, offers to
launch the setup wizard, and handles Ctrl-C gracefully.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _make_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """All tests in this file need a fake TTY so that
    ``renderer.is_interactive`` returns ``True``."""
    from openreview_cli.ui.console import renderer as _r

    p = PropertyMock(return_value=True)
    monkeypatch.setattr(type(_r), "is_interactive", p)


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


def _mock_q_confirm(return_value: bool) -> MagicMock:
    """Return a mock ``questionary.confirm`` whose ``unsafe_ask`` returns
    *return_value*."""
    mock_instance = MagicMock()
    mock_instance.unsafe_ask.return_value = return_value
    return mock_instance


# ---------------------------------------------------------------------------
# First-run welcome panel
# ---------------------------------------------------------------------------


def test_first_run_shows_welcome_panel(temp_config_dir: Path) -> None:
    """Running any command with no config shows the welcome panel."""
    # Mock questionary.confirm to return True (user accepts wizard)
    with (
        patch("questionary.confirm", return_value=_mock_q_confirm(True)),
        patch("openreview_cli.app.gateway_setup") as mock_setup,
    ):
        result = runner.invoke(app, ["config", "show"])

    assert "Welcome" in result.stdout
    assert "OpenReview" in result.stdout


def test_first_run_offers_setup_wizard(temp_config_dir: Path) -> None:
    """The welcome panel offers to run the setup wizard."""
    with (
        patch("questionary.confirm", return_value=_mock_q_confirm(True)),
        patch("openreview_cli.app.gateway_setup") as mock_setup,
    ):
        result = runner.invoke(app, ["config", "show"])
        # First verify the welcome panel was shown
        assert "Welcome" in result.stdout, "Welcome panel should be shown"
        # Then verify gateway_setup was called when user accepts
        mock_setup.assert_called_once()


def test_first_run_skip_setup_continues(temp_config_dir: Path) -> None:
    """Declining the wizard (No) skips setup and runs normally."""
    with (
        patch("questionary.confirm", return_value=_mock_q_confirm(False)),
        patch("openreview_cli.app.gateway_setup") as mock_setup,
    ):
        result = runner.invoke(app, ["config", "show"])
        mock_setup.assert_not_called()
        # The original command should still run
        assert "privacy" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Ctrl-C exits cleanly
# ---------------------------------------------------------------------------


def test_first_run_ctrlc_exits_cleanly(temp_config_dir: Path) -> None:
    """Pressing Ctrl-C on the setup prompt exits with code 1."""
    mock_instance = MagicMock()
    mock_instance.unsafe_ask.side_effect = KeyboardInterrupt
    with patch("questionary.confirm", return_value=mock_instance):
        result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 1
