"""Integration tests for help output, typo suggestion, and version flag.

T060 — ``--help`` output format and content
T062 — Typo suggestion for unknown commands
T064 — ``--version`` flag output
T066 — Shell completion auto-install during setup
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from openreview_cli import __version__
from openreview_cli.app import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up fresh XDG directories so _init() doesn't fail on missing config."""
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_dir))
    monkeypatch.setenv("XDG_DATA_HOME", str(data_dir))
    # Create minimal config so _init() can load it
    config_path = config_dir / "openreview" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("version: 1\ngateway:\n  models: {}\n  fallback:\n    retries: 2\n")
    return config_dir


# ---------------------------------------------------------------------------
# T060 — --help output
# ---------------------------------------------------------------------------


class TestHelpOutput:
    """Verify ``--help`` output contains usage, commands, grouped sections, and examples."""

    def test_root_help_has_usage_line(self) -> None:
        """openreview --help contains a usage line."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout

    def test_root_help_shows_all_commands(self) -> None:
        """openreview --help lists review, parse, setup, config, gateway, client."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for cmd in ["review", "parse", "setup", "config", "gateway", "client"]:
            assert cmd in result.stdout, f"Missing command '{cmd}' in help output"

    def test_root_help_has_examples_section(self) -> None:
        """openreview --help contains an examples section."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Example" in result.stdout or "example" in result.stdout.lower()

    def test_review_help_shows_options(self) -> None:
        """openreview review --help lists --mode and other options."""
        result = runner.invoke(app, ["review", "--help"])
        assert result.exit_code == 0
        assert "--mode" in result.stdout
        assert "--jurisdiction" in result.stdout

    def test_config_help_shows_subcommands(self) -> None:
        """openreview config --help shows nested subcommands."""
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        for sub in ["show", "get", "set", "unset", "path"]:
            assert sub in result.stdout, f"Missing subcommand '{sub}' in config --help"


# ---------------------------------------------------------------------------
# T062 — Typo suggestion
# ---------------------------------------------------------------------------


class TestTypoSuggestion:
    """Verify Typer's built-in suggest_commands for unknown commands."""

    def test_unknown_command_suggests_review(self) -> None:
        """openreview reviw prints suggestion for 'review'."""
        result = runner.invoke(app, ["reviw"])
        assert result.exit_code == 2
        output = result.stdout + result.stderr
        assert "reviw" in output
        assert "review" in output

    def test_unknown_config_variant_suggests_config(self) -> None:
        """openreview configura suggests 'config'."""
        result = runner.invoke(app, ["configura"])
        assert result.exit_code == 2
        output = result.stdout + result.stderr
        assert "config" in output


# ---------------------------------------------------------------------------
# T064 -- --version flag
# ---------------------------------------------------------------------------


class TestVersionFlag:
    """Verify ``--version`` prints the correct version string."""

    def test_version_prints_version_string(self, temp_config_dir: Path) -> None:
        """openreview --version prints 'openreview X.Y.Z'."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        output = result.stdout + result.stderr
        assert f"openreview {__version__}" in output

    def test_version_has_no_extra_stdout(self) -> None:
        """openreview --version prints only the version line on stdout."""
        with patch("openreview_cli.app._init") as mock_init:
            result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        lines = [line for line in result.stdout.split("\n") if line.strip()]
        assert len(lines) == 1, f"Expected 1 line, got {len(lines)}: {lines}"
        assert lines[0] == f"openreview {__version__}"


# ---------------------------------------------------------------------------
# T066 — Shell completion auto-install during setup
# ---------------------------------------------------------------------------


class TestCompletionInstall:
    """Verify setup wizard offers and handles shell completion install."""

    def test_setup_offers_completion_after_gateway(self, temp_config_dir: Path) -> None:
        """After gateway setup, completion install prompt is shown to the user."""
        questionary_mock = MagicMock()
        questionary_mock.unsafe_ask.return_value = False  # user declines

        with (
            patch("openreview_cli.app.gateway_setup") as mock_gw,
            patch("questionary.confirm", return_value=questionary_mock),
            patch("subprocess.run") as mock_subprocess,
        ):
            result = runner.invoke(app, ["setup"])

        assert result.exit_code == 0
        # Confirm was shown to the user
        questionary_mock.unsafe_ask.assert_called_once()
        # Since user declined, subprocess should NOT have been called
        mock_subprocess.assert_not_called()

    def test_setup_completion_failure_is_non_blocking(self, temp_config_dir: Path) -> None:
        """Completion install failure shows warning but does not block setup."""
        questionary_mock = MagicMock()
        questionary_mock.unsafe_ask.return_value = True  # user confirms

        with (
            patch("openreview_cli.app.gateway_setup") as mock_gw,
            patch("questionary.confirm", return_value=questionary_mock),
            patch("subprocess.run", side_effect=Exception("fail")),
        ):
            result = runner.invoke(app, ["setup"])

        # Setup should still succeed despite completion failure
        assert result.exit_code == 0
