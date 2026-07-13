"""Unit tests for gateway test grounding command (Phase 10, T061-T062).

These tests follow TDD:
  - T061: configured slot → success
  - T062: unconfigured slot → clear error + exit 2

Before Phase 10 implementation (T063): both fail.
  - T061: no ``elif slot == "grounding"`` branch, so command exits silently
    with code 0 and no ``Response:`` output.
  - T062: same silent exit — no error raised, test assertion on exit code 2
    and "not configured" message fails.

After T063:
  - T061: ``elif slot == "grounding"`` calls ``gw.chat()`` → response printed.
  - T062: ``elif slot == "grounding"`` calls ``gw.chat()`` → ``_get_slot_config``
    raises ``SlotNotConfiguredError`` → caught by new handler → exit 2 + hint.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.errors import EXIT_CONFIG_ERROR
from openreview_cli.gateway.router import Gateway

runner = CliRunner()


class TestGatewayTestGroundingConfigured:
    """T061: gateway test grounding with configured slot."""

    @pytest.fixture(autouse=True)
    def _setup_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Isolated config dir with XDG paths."""
        self._config_dir = tmp_path / ".config" / "openreview"
        self._config_dir.mkdir(parents=True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))

    def test_grounding_configured_returns_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T061: grounding slot configured → test responds OK."""
        # Write a valid config with grounding
        (self._config_dir / "config.yml").write_text(
            yaml.dump(
                {
                    "version": 1,
                    "gateway": {
                        "models": {
                            "grounding": {"primary": "openai/gpt-4o"},
                        },
                    },
                }
            )
        )
        (self._config_dir / "auth.json").write_text("{}")

        # Mock Gateway internals so no real API call happens
        monkeypatch.setattr(Gateway, "__init__", lambda self: None)
        monkeypatch.setattr(
            Gateway,
            "chat",
            lambda self, slot, messages, **kwargs: "OK from grounding",
        )

        result = runner.invoke(app, ["gateway", "test", "grounding"])

        # BEFORE T063: exits 0 silently, assertion fails (no "Response:OK from grounding")
        # AFTER T063: exits 0, prints "Response: OK from grounding"
        assert result.exit_code == 0, f"got {result.exit_code}: {result.stderr}"
        assert "Response: OK from grounding" in result.stdout


class TestGatewayTestGroundingNotConfigured:
    """T062: gateway test grounding with unconfigured slot."""

    @pytest.fixture(autouse=True)
    def _setup_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Isolated config dir with XDG paths."""
        self._config_dir = tmp_path / ".config" / "openreview"
        self._config_dir.mkdir(parents=True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))

        # Config with grounding slot but empty primary = not configured
        (self._config_dir / "config.yml").write_text(
            yaml.dump(
                {
                    "version": 1,
                    "gateway": {
                        "models": {
                            "grounding": {"primary": ""},
                        },
                    },
                }
            )
        )
        (self._config_dir / "auth.json").write_text("{}")

    def test_grounding_not_configured_returns_clear_error(self) -> None:
        """T062: no grounding config → error message + exit 2."""
        # Do NOT mock Gateway — exercise the real path through
        # _get_slot_config which should raise SlotNotConfiguredError
        # when primary is empty.
        result = runner.invoke(app, ["gateway", "test", "grounding"])

        # BEFORE T063: exits 0 silently (no elif for grounding)
        # AFTER T063: catches SlotNotConfiguredError → exit 2 + hint
        assert result.exit_code == EXIT_CONFIG_ERROR, (
            f"expected {EXIT_CONFIG_ERROR}, got {result.exit_code}: {result.stderr}"
        )
        output = (result.stderr or "") + (result.stdout or "")
        assert "not configured" in output.lower()
        assert "openreview set grounding" in output
