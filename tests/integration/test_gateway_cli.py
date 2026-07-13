"""CLI integration tests for gateway commands.

Each test uses ``typer.testing.CliRunner`` to invoke individual gateway
subcommands and monkeypatch to mock the heavy backend operations (Gateway,
ModelRegistry, config file writes) so that no real API calls or file I/O
occur.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.gateway.registry import ModelRegistry
from openreview_cli.gateway.router import VALID_SLOTS, Gateway

runner = CliRunner()


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

    @pytest.mark.integration
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

    @pytest.mark.integration
    def test_gateway_models_invalid_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unknown provider prints a friendly message instead of a table."""
        monkeypatch.setattr(ModelRegistry, "load", lambda self: None)
        monkeypatch.setattr(ModelRegistry, "list_models", lambda self, p: [])

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
        # Error messages go to stderr (FR-032)
        output = (result.stderr or "") + (result.stdout or "")
        assert "Invalid slot" in output
        # Valid slots should be listed in the error message
        for slot in sorted(VALID_SLOTS):
            assert slot in output


class TestGatewayCosts:
    """Integration tests for ``openreview gateway costs``."""

    @pytest.mark.integration
    def test_costs_json_roundtrip(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Insert cost record, query via CLI, verify record appears in JSON output."""
        from openreview_cli.storage.database import init_database, log_cost

        cost_db = tmp_path / "openreview.db"
        init_database(cost_db)
        log_cost(cost_db, None, "openai/gpt-4o", "openai", 100, 50, 5, slot="reasoning")

        monkeypatch.setattr("openreview_cli.app.get_data_dir", lambda: tmp_path)

        result = runner.invoke(app, ["gateway", "costs", "--format", "json"])
        assert result.exit_code == 0, result.stdout

        import json

        data = json.loads(result.stdout)
        assert len(data["records"]) == 1
        rec = data["records"][0]
        assert rec["model"] == "openai/gpt-4o"
        assert rec["provider"] == "openai"
        assert rec["prompt_tokens"] == 100
        assert rec["completion_tokens"] == 50
        assert rec["cost_cents"] == 5

    @pytest.mark.integration
    def test_costs_filter_by_session(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Insert 2 cost records for different sessions, filter by one."""
        from openreview_cli.storage.database import get_connection, init_database, log_cost

        cost_db = tmp_path / "openreview.db"
        init_database(cost_db)
        conn = get_connection(cost_db)
        conn.execute("INSERT INTO sessions (id) VALUES (?), (?)", ("s1", "s2"))
        conn.commit()
        conn.close()

        log_cost(cost_db, "s1", "model-a", "p1", 10, 5, 1, slot="slot-a")
        log_cost(cost_db, "s2", "model-b", "p2", 20, 10, 2, slot="slot-b")

        monkeypatch.setattr("openreview_cli.app.get_data_dir", lambda: tmp_path)

        result = runner.invoke(
            app,
            ["gateway", "costs", "--session", "s1", "--format", "json"],
        )
        assert result.exit_code == 0, result.stdout

        import json

        data = json.loads(result.stdout)
        assert data["record_count"] == 1
        assert data["records"][0]["model"] == "model-a"
        assert data["records"][0]["session_id"] == "s1"

    @pytest.mark.integration
    def test_costs_json_is_valid_json(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Insert a record, verify JSON output parses correctly."""
        from openreview_cli.storage.database import init_database, log_cost

        cost_db = tmp_path / "openreview.db"
        init_database(cost_db)
        log_cost(cost_db, None, "m1", "p1", 5, 5, 1, slot="s1")

        monkeypatch.setattr("openreview_cli.app.get_data_dir", lambda: tmp_path)

        result = runner.invoke(app, ["gateway", "costs", "--format", "json"])
        assert result.exit_code == 0, result.stdout

        import json

        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        assert "records" in data
        assert isinstance(data["records"], list)
        assert "total_cost_cents" in data
        assert "record_count" in data
        assert data["record_count"] == 1
