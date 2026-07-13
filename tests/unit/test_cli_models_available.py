"""Unit tests for ``openreview models available`` command.

T020-T022: TDD phase — test first, implement later.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

# ── Test data ─────────────────────────────────────────────────────────────────

# Minimal models.json for tests
MODELS_JSON = {
    "providers": {
        "openrouter": {
            "name": "OpenRouter",
            "env_key": "OPENROUTER_API_KEY",
            "auth_required": True,
            "models": {
                "openai/gpt-4o": {
                    "slots": ["reasoning", "extraction", "graph"],
                    "context": 128000,
                    "recommended": True,
                    "status": "active",
                },
                "anthropic/claude-sonnet-latest": {
                    "slots": ["reasoning", "extraction", "graph"],
                    "context": 200000,
                    "recommended": False,
                    "status": "active",
                },
            },
        },
        "voyage": {
            "name": "Voyage",
            "env_key": "VOYAGE_API_KEY",
            "auth_required": True,
            "models": {
                "voyage-3": {
                    "slots": ["embedding"],
                    "dimensions": 1024,
                    "recommended": True,
                    "status": "active",
                },
                "rerank-2": {
                    "slots": ["reranking"],
                    "context": 8192,
                    "recommended": True,
                    "status": "active",
                },
            },
        },
    },
}


class TestModelsAvailable:
    """Test suite for ``openreview models available`` command."""

    @pytest.fixture(autouse=True)
    def _setup_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Create temp config dir with auth.json and models.json."""
        config_dir = tmp_path / ".config" / "openreview"
        config_dir.mkdir(parents=True)

        # Override config paths via env var
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))
        monkeypatch.setenv("XDG_LOG_HOME", str(tmp_path / ".cache"))

        # Write models.json (simulate _GATEWAY_REGISTRY_PATH)
        models_path = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "openreview_cli"
            / "gateway"
            / "models.json"
        )
        # Use our minimal set for deterministic tests
        self._models_path = tmp_path / "models.json"
        self._models_path.write_text(json.dumps(MODELS_JSON))

        # Monkey-patch _GATEWAY_REGISTRY_PATH via the module where it's used
        import openreview_cli.app as app_module

        monkeypatch.setattr(app_module, "_GATEWAY_REGISTRY_PATH", self._models_path)

    # ── T020: configured providers return models ────────────────────────

    def test_available_with_configured_providers(self, tmp_path: Path) -> None:
        """Models appear for configured providers."""
        auth_path = tmp_path / ".config" / "openreview" / "auth.json"
        auth_path.write_text(json.dumps({"openrouter": "sk-or-fake", "voyage": "vo-fake"}))

        result = runner.invoke(app, ["models", "available"])
        assert result.exit_code == 0, f"stdout={result.stdout} stderr={result.stderr}"
        # Use --format json for deterministic assertions
        result2 = runner.invoke(app, ["models", "available", "--format", "json"])
        assert result2.exit_code == 0
        data = json.loads(result2.stdout)
        assert data["total"] == 4
        model_ids = {m["short_name"] for m in data["models"]}
        assert "openai/gpt-4o" in model_ids
        assert "anthropic/claude-sonnet-latest" in model_ids
        assert "voyage-3" in model_ids
        assert "rerank-2" in model_ids
        assert set(data["providers_found"]) == {"openrouter", "voyage"}

    # ── T021: no providers configured → empty list + message ─────────────

    def test_available_no_providers(self) -> None:
        """No providers configured shows info message."""
        # No auth.json created → no providers
        result = runner.invoke(app, ["models", "available"])
        assert result.exit_code == 0
        assert "No API keys configured" in result.stderr

    # ── T022: --provider filter ─────────────────────────────────────────

    def test_available_provider_filter(self, tmp_path: Path) -> None:
        """--provider openrouter returns only openrouter models."""
        auth_path = tmp_path / ".config" / "openreview" / "auth.json"
        auth_path.write_text(json.dumps({"openrouter": "sk-or-fake", "voyage": "vo-fake"}))

        result = runner.invoke(
            app, ["models", "available", "--provider", "openrouter", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["total"] == 2
        for m in data["models"]:
            assert m["provider"] == "openrouter"
        model_ids = {m["short_name"] for m in data["models"]}
        assert "openai/gpt-4o" in model_ids
        assert "anthropic/claude-sonnet-latest" in model_ids
        # Voyage models should NOT appear
        assert "voyage-3" not in model_ids
        assert "rerank-2" not in model_ids
