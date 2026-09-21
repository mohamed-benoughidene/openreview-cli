"""CLI integration tests for gateway commands.

Each test uses ``typer.testing.CliRunner`` to invoke individual gateway
subcommands and monkeypatch to mock the heavy backend operations (Gateway,
ModelRegistry, config file writes) so that no real API calls or file I/O
occur.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.gateway import registry as _reg_mod
from openreview_cli.gateway.models import ModelEntry, ProviderInfo
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


def _real_provider(
    name: str,
    models: dict[str, ModelEntry],
    auth_required: bool = True,
) -> ProviderInfo:
    return ProviderInfo(name=name, auth_required=auth_required, models=models)


def _discovered(model_id: str, parameter_size: str = "7B") -> dict[str, Any]:
    return {
        "model_id": model_id,
        "slots": ["reasoning", "extraction", "graph"],
        "ram": None,
        "recommended": False,
        "status": "available",
        "note": f"Ollama local — {parameter_size}",
    }


def _discover_two() -> list[dict[str, Any]]:
    return [_discovered("qwen2.5:7b"), _discovered("mistral:7b")]


def _discover_empty() -> list[dict[str, Any]]:
    return []


def _discover_forbidden() -> list[dict[str, Any]]:
    raise AssertionError("discover_ollama must not be called")


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
    def test_gateway_models_unknown_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A provider absent from the registry exits 1 with the error message."""
        monkeypatch.setattr(_reg_mod, "load_registry", dict)

        result = runner.invoke(app, ["gateway", "models", "ghost"])
        assert result.exit_code == 1
        assert "No provider 'ghost' found." in result.output

    @pytest.mark.integration
    def test_gateway_models_ollama_merges_discovered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Discovered Ollama models are merged alongside the bundled ones."""
        monkeypatch.setattr(
            _reg_mod,
            "load_registry",
            lambda: {
                "ollama": _real_provider(
                    "ollama",
                    {"llama3.2:3b": ModelEntry(slots=["reasoning"], context=8192)},
                    auth_required=False,
                )
            },
        )
        monkeypatch.setattr(_reg_mod, "discover_ollama", _discover_two)

        result = runner.invoke(app, ["gateway", "models", "ollama"])
        assert result.exit_code == 0
        for model_id in ("llama3.2:3b", "qwen2.5:7b", "mistral:7b"):
            assert model_id in result.stdout

    @pytest.mark.integration
    def test_gateway_models_ollama_json_includes_discovered(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The --json payload lists bundled and discovered models together."""
        monkeypatch.setattr(
            _reg_mod,
            "load_registry",
            lambda: {
                "ollama": _real_provider(
                    "ollama",
                    {"llama3.2:3b": ModelEntry(slots=["reasoning"], context=8192)},
                    auth_required=False,
                )
            },
        )
        monkeypatch.setattr(_reg_mod, "discover_ollama", _discover_two)

        result = runner.invoke(app, ["gateway", "models", "ollama", "--json"])
        assert result.exit_code == 0
        rows = {row["id"]: row for row in json.loads(result.stdout)["ollama"]}
        assert set(rows) == {"llama3.2:3b", "qwen2.5:7b", "mistral:7b"}
        assert rows["qwen2.5:7b"]["note"].startswith("Ollama local — ")
        assert rows["mistral:7b"]["note"].startswith("Ollama local — ")

    @pytest.mark.integration
    def test_gateway_models_non_ollama_never_discovers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Discovery is Ollama-only; another provider must not probe the server."""
        monkeypatch.setattr(
            _reg_mod,
            "load_registry",
            lambda: {
                "openai": _real_provider("openai", {"gpt-4o": ModelEntry(slots=["reasoning"])})
            },
        )
        monkeypatch.setattr(_reg_mod, "discover_ollama", _discover_forbidden)

        result = runner.invoke(app, ["gateway", "models", "openai"])
        assert result.exit_code == 0
        assert "gpt-4o" in result.stdout

    @pytest.mark.integration
    def test_gateway_models_ollama_unreachable_still_lists_bundled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unreachable Ollama server leaves the bundled models intact."""
        monkeypatch.setattr(
            _reg_mod,
            "load_registry",
            lambda: {
                "ollama": _real_provider(
                    "ollama",
                    {"llama3.2:3b": ModelEntry(slots=["reasoning"], context=8192)},
                    auth_required=False,
                )
            },
        )
        monkeypatch.setattr(_reg_mod, "discover_ollama", _discover_empty)

        result = runner.invoke(app, ["gateway", "models", "ollama"])
        assert result.exit_code == 0
        assert "llama3.2:3b" in result.stdout
        assert "Traceback" not in result.stdout

    @pytest.mark.integration
    def test_gateway_models_no_discover_skips_probe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """--no-discover opts out of querying the local Ollama server."""
        monkeypatch.setattr(
            _reg_mod,
            "load_registry",
            lambda: {
                "ollama": _real_provider(
                    "ollama",
                    {"llama3.2:3b": ModelEntry(slots=["reasoning"], context=8192)},
                    auth_required=False,
                )
            },
        )
        monkeypatch.setattr(_reg_mod, "discover_ollama", _discover_forbidden)

        result = runner.invoke(app, ["gateway", "models", "ollama", "--no-discover"])
        assert result.exit_code == 0
        assert "llama3.2:3b" in result.stdout

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
