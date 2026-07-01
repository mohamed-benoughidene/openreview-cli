"""CLI integration tests for gateway commands.

Each test uses ``typer.testing.CliRunner`` to invoke individual gateway
subcommands and monkeypatch to mock the heavy backend operations (Gateway,
ModelRegistry, config file writes) so that no real API calls or file I/O
occur.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

if TYPE_CHECKING:
    import pytest

from openreview_cli.app import app
from openreview_cli.gateway.registry import ModelRegistry
from openreview_cli.gateway.router import VALID_SLOTS, Gateway

runner = CliRunner()


class TestGatewayCli:
    """Integration tests for ``openreview gateway <subcommand>``."""

    def test_gateway_help(self) -> None:
        """Verify ``--help`` lists every subcommand."""
        result = runner.invoke(app, ["gateway", "--help"])
        assert result.exit_code == 0
        for cmd in (
            "setup",
            "status",
            "providers",
            "models",
            "set",
            "refresh",
            "test",
            "costs",
        ):
            assert cmd in result.stdout, f"'{cmd}' not listed in gateway help"

    def test_gateway_status_empty_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Status reports all slots as not_configured when no models set."""
        # Avoid loading real config / contacting providers
        monkeypatch.setattr(Gateway, "__init__", lambda self: None)

        def _health_check(_self: Gateway) -> dict[str, dict[str, str]]:
            return {slot: {"status": "not_configured"} for slot in sorted(VALID_SLOTS)}

        monkeypatch.setattr(Gateway, "health_check", _health_check)

        result = runner.invoke(app, ["gateway", "status"])
        assert result.exit_code == 0
        assert "Gateway Status" in result.stdout
        assert "not_configured" in result.stdout
        for slot in sorted(VALID_SLOTS):
            assert slot in result.stdout

    def test_gateway_providers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Providers table lists every known provider with auth info."""
        monkeypatch.setattr(ModelRegistry, "load", lambda self: None)

        def _list_providers(
            _self: ModelRegistry,
        ) -> list[dict[str, str | bool | int]]:
            return [
                {"name": "ollama", "auth_required": False, "model_count": 3},
                {"name": "openai", "auth_required": True, "model_count": 5},
                {"name": "anthropic", "auth_required": True, "model_count": 2},
            ]

        monkeypatch.setattr(ModelRegistry, "list_providers", _list_providers)

        result = runner.invoke(app, ["gateway", "providers"])
        assert result.exit_code == 0
        assert "Supported Providers" in result.stdout
        for name in ("ollama", "openai", "anthropic"):
            assert name in result.stdout
        assert "none" in result.stdout  # ollama no auth
        assert "key required" in result.stdout  # openai / anthropic

    def test_gateway_models(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Known provider returns a table of models."""
        monkeypatch.setattr(ModelRegistry, "load", lambda self: None)

        def _list_models(
            _self: ModelRegistry, provider: str
        ) -> list[dict[str, str | bool | int | list[str]]]:
            if provider == "ollama":
                return [
                    {
                        "model_id": "llama3.2:3b",
                        "slots": ["reasoning", "extraction", "graph"],
                        "context": 8192,
                        "recommended": True,
                    },
                    {
                        "model_id": "nomic-embed-text",
                        "slots": ["embedding"],
                        "context": 2048,
                        "recommended": True,
                    },
                ]
            return []

        monkeypatch.setattr(ModelRegistry, "list_models", _list_models)

        result = runner.invoke(app, ["gateway", "models", "ollama"])
        assert result.exit_code == 0
        assert "Models for ollama" in result.stdout
        assert "llama3.2:3b" in result.stdout
        assert "nomic-embed-text" in result.stdout

    def test_gateway_models_invalid_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unknown provider prints a friendly message instead of a table."""
        monkeypatch.setattr(ModelRegistry, "load", lambda self: None)
        monkeypatch.setattr(ModelRegistry, "list_models", lambda self, p: [])

        result = runner.invoke(app, ["gateway", "models", "nonexistent"])
        assert result.exit_code == 0
        assert "No models found for provider 'nonexistent'." in result.stdout

    def test_gateway_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assign a model to a slot and confirm the success message."""
        monkeypatch.setattr(
            "openreview_cli.config.loader.set_config_value",
            lambda config_path, key, value: None,
        )

        result = runner.invoke(app, ["gateway", "set", "reasoning", "ollama/llama3.2:3b"])
        assert result.exit_code == 0
        assert "Set reasoning → ollama/llama3.2:3b" in result.stdout

    def test_gateway_invalid_slot(self) -> None:
        """Unknown slot causes an early exit with an error message.

        The slot-validity check runs *before* ``Gateway()`` is
        constructed, so no mocking is required.
        """
        result = runner.invoke(app, ["gateway", "test", "invalid_slot"])
        assert result.exit_code == 1
        assert "Invalid slot" in result.stdout
        # Valid slots should be listed in the error message
        for slot in sorted(VALID_SLOTS):
            assert slot in result.stdout
