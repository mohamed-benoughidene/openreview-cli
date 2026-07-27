"""CLI integration tests for gateway commands.

Each test uses ``typer.testing.CliRunner`` to invoke individual gateway
subcommands and monkeypatch to mock the heavy backend operations (Gateway,
ModelRegistry, config file writes) so that no real API calls or file I/O
occur.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.gateway import registry as _reg_mod
from openreview_cli.gateway.router import Gateway
from openreview_cli.slots import VALID_SLOTS

runner = CliRunner()


def _provider_stub(name: str, auth_required: bool, model_count: int) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        auth_required=auth_required,
        models=dict.fromkeys(range(model_count)),
    )


def _model_stub(slots: list[str], context: int, recommended: bool = False) -> SimpleNamespace:
    return SimpleNamespace(slots=slots, context=context, recommended=recommended)


class TestGatewayCli:
    """Integration tests for ``openreview gateway <subcommand>``."""

    @pytest.mark.integration
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

    @pytest.mark.integration
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

    @pytest.mark.integration
    def test_gateway_providers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Providers table lists every known provider with auth info."""
        monkeypatch.setattr(
            _reg_mod,
            "load_registry",
            lambda: {
                "ollama": _provider_stub("ollama", auth_required=False, model_count=3),
                "openai": _provider_stub("openai", auth_required=True, model_count=5),
                "anthropic": _provider_stub("anthropic", auth_required=True, model_count=2),
            },
        )

        result = runner.invoke(app, ["gateway", "providers"])
        assert result.exit_code == 0
        assert "Supported Providers" in result.stdout
        for name in ("ollama", "openai", "anthropic"):
            assert name in result.stdout
        assert "none" in result.stdout  # ollama no auth
        assert "key required" in result.stdout  # openai / anthropic

    @pytest.mark.integration
    def test_gateway_models(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Known provider returns a table of models."""
        monkeypatch.setattr(
            _reg_mod,
            "load_registry",
            lambda: {
                "ollama": SimpleNamespace(
                    name="ollama",
                    auth_required=False,
                    models={
                        "llama3.2:3b": _model_stub(
                            ["reasoning", "extraction", "graph"], 8192, recommended=True
                        ),
                        "nomic-embed-text": _model_stub(["embedding"], 2048, recommended=True),
                    },
                ),
            },
        )

        result = runner.invoke(app, ["gateway", "models", "ollama"])
        assert result.exit_code == 0
        assert "Models for ollama" in result.stdout
        assert "llama3.2:3b" in result.stdout
        assert "nomic-embed-text" in result.stdout

    @pytest.mark.integration
    def test_gateway_models_invalid_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unknown provider prints a friendly message instead of a table."""
        monkeypatch.setattr(
            _reg_mod,
            "load_registry",
            lambda: {
                "nonexistent": SimpleNamespace(name="nonexistent", models={}),
            },
        )

        result = runner.invoke(app, ["gateway", "models", "nonexistent"])
        assert result.exit_code == 0
        assert "No models found for provider 'nonexistent'." in result.stdout

    @pytest.mark.integration
    def test_gateway_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assign a model to a slot and confirm the success message."""
        monkeypatch.setattr(
            "openreview_cli.config.loader.set_config_value",
            lambda config_path, key, value: None,
        )

        result = runner.invoke(app, ["gateway", "set", "reasoning", "ollama/llama3.2:3b"])
        assert result.exit_code == 0
        assert "Set reasoning → ollama/llama3.2:3b" in result.stdout

    @pytest.mark.integration
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
