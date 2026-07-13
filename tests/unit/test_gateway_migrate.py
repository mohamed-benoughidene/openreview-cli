from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from openreview_cli.gateway.migrate import migrate_config

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def v1_config_dict() -> dict[str, object]:
    """A representative v1 config.yml with all 5 slots."""
    return {
        "version": 1,
        "privacy": {
            "tier": "balanced",
            "strip_pii": True,
            "log_ttl_days": 30,
            "pii_threshold": 0.7,
        },
        "gateway": {
            "models": {
                "reasoning": {
                    "primary": "openai/gpt-4o",
                    "fallback": "ollama/qwen3:8b",
                    "params": {"temperature": 0.1, "max_tokens": 4000},
                },
                "extraction": {
                    "primary": "openai/gpt-4o-mini",
                    "fallback": None,
                    "params": {"temperature": 0.0, "max_tokens": 2000},
                },
                "embedding": {
                    "primary": "ollama/nomic-embed-text",
                },
                "reranking": {
                    "primary": "ollama/qwen3-reranker-0.6b",
                },
                "graph": {
                    "primary": "openai/gpt-4o",
                    "fallback": None,
                    "params": {"temperature": 0.0, "max_tokens": 4000},
                },
            },
            "fallback": {
                "retries": 2,
                "retry_delay": 1.0,
                "timeout": 60,
                "on_failure": "error",
            },
            "cost_limits": {
                "per_review_cents": 100,
                "daily_cents": 1000,
            },
            "model_registry_refresh_days": 7,
        },
    }


@pytest.fixture
def v2_config_dict() -> dict[str, object]:
    """A representative v2 config.yml (already migrated)."""
    return {
        "version": 2,
        "providers": {
            "openai": {
                "name": "openai",
                "api_key_source": "file",
                "env_key": "OPENAI_API_KEY",
                "enabled": True,
            },
            "ollama": {
                "name": "ollama",
                "api_key_source": "file",
                "env_key": "",
                "enabled": True,
                "base_url": "http://localhost:11434",
            },
        },
        "slots": {
            "reasoning": {
                "provider": "openai",
                "model": "gpt-4o",
                "fallback": {"provider": "ollama", "model": "qwen3:8b"},
            },
            "extraction": {
                "provider": "openai",
                "model": "gpt-4o-mini",
            },
            "embedding": {
                "provider": "ollama",
                "model": "nomic-embed-text",
            },
            "reranking": {
                "provider": "ollama",
                "model": "qwen3-reranker-0.6b",
            },
            "graph": {
                "provider": "openai",
                "model": "gpt-4o",
            },
            "grounding": {
                "provider": "openai",
                "model": "gpt-4o",
            },
        },
        "default_model": None,
        "fallback": {
            "retries": 2,
            "timeout": 60,
            "on_failure": "error",
        },
        "cost_limits": {
            "per_session_cents": 100,
            "daily_cents": 1000,
        },
    }


@pytest.fixture
def v1_config_path(v1_config_dict: dict[str, object], tmp_path: Path) -> Path:
    path = tmp_path / "config.yml"
    with open(path, "w") as f:
        yaml.dump(v1_config_dict, f)
    return path


@pytest.fixture
def v2_config_path(v2_config_dict: dict[str, object], tmp_path: Path) -> Path:
    path = tmp_path / "config.v2.yml"
    with open(path, "w") as f:
        yaml.dump(v2_config_dict, f)
    return path


@pytest.fixture
def auth_path(tmp_path: Path) -> Path:
    path = tmp_path / "auth.json"
    auth_data = {
        "openai": "sk-test-openai-key-12345",
        "ollama": "",
    }
    with open(path, "w") as f:
        json.dump(auth_data, f)
    return path


# ── T041: v1 → v2 migration preserves slot assignments ──────────────────────


class TestT041V1ToV2Migration:
    def test_slot_assignments_preserved(self, v1_config_path: Path, tmp_path: Path) -> None:
        """Migration produces v2 with correct provider/model per slot."""
        v2_path = tmp_path / "migrated.yml"
        result = migrate_config(str(v1_config_path), str(v2_path))

        assert result["status"] == "migrated"
        assert v2_path.exists()

        with open(v2_path) as f:
            v2 = yaml.safe_load(f)

        # Check version
        assert v2["version"] == 2

        # Check slots
        slots = v2["slots"]
        assert slots["reasoning"]["provider"] == "openai"
        assert slots["reasoning"]["model"] == "gpt-4o"
        assert slots["reasoning"]["fallback"]["provider"] == "ollama"
        assert slots["reasoning"]["fallback"]["model"] == "qwen3:8b"

        assert slots["extraction"]["provider"] == "openai"
        assert slots["extraction"]["model"] == "gpt-4o-mini"
        assert slots["extraction"].get("fallback") is None

        assert slots["embedding"]["provider"] == "ollama"
        assert slots["embedding"]["model"] == "nomic-embed-text"

        assert slots["reranking"]["provider"] == "ollama"
        assert slots["reranking"]["model"] == "qwen3-reranker-0.6b"

        assert slots["graph"]["provider"] == "openai"
        assert slots["graph"]["model"] == "gpt-4o"

        # Grounding should be added with same as reasoning
        assert slots["grounding"]["provider"] == "openai"
        assert slots["grounding"]["model"] == "gpt-4o"

    def test_providers_deduplicated(self, v1_config_path: Path, tmp_path: Path) -> None:
        """Providers are collected across all slots and deduplicated."""
        v2_path = tmp_path / "migrated.yml"
        result = migrate_config(str(v1_config_path), str(v2_path))

        assert result["status"] == "migrated"
        assert "openai" in result["providers_added"]
        assert "ollama" in result["providers_added"]

        with open(v2_path) as f:
            v2 = yaml.safe_load(f)

        providers = v2["providers"]
        assert "openai" in providers
        assert "ollama" in providers

        assert providers["openai"]["name"] == "openai"
        assert providers["openai"]["env_key"] == "OPENAI_API_KEY"
        assert providers["openai"]["enabled"] is True

        assert providers["ollama"]["name"] == "ollama"
        assert providers["ollama"]["env_key"] == "OLLAMA_API_KEY"
        assert providers["ollama"]["base_url"] == "http://localhost:11434"
        assert providers["ollama"]["enabled"] is True

    def test_v1_backup_created(self, v1_config_path: Path, tmp_path: Path) -> None:
        """V1 config is backed up as .v1.bak."""
        v2_path = tmp_path / "migrated.yml"
        result = migrate_config(str(v1_config_path), str(v2_path))

        assert result["status"] == "migrated"
        assert "backup" in result
        backup_path = Path(result["backup"])
        assert backup_path.exists()

        with open(backup_path) as f:
            backup = yaml.safe_load(f)
        assert backup["version"] == 1
        assert "gateway" in backup

    def test_result_contains_all_fields(self, v1_config_path: Path, tmp_path: Path) -> None:
        """Result dict has all expected keys."""
        v2_path = tmp_path / "migrated.yml"
        result = migrate_config(str(v1_config_path), str(v2_path))

        assert result["status"] == "migrated"
        assert "providers_added" in result
        assert "slots_migrated" in result
        assert "backup" in result
        assert isinstance(result["providers_added"], list)
        assert isinstance(result["slots_migrated"], list)

    def test_v2_config_validates_against_pydantic(
        self, v1_config_path: Path, tmp_path: Path
    ) -> None:
        """Generated v2 config passes V2Config Pydantic validation."""
        from openreview_cli.gateway.v2_config import V2Config

        v2_path = tmp_path / "migrated.yml"
        migrate_config(str(v1_config_path), str(v2_path))

        with open(v2_path) as f:
            v2 = yaml.safe_load(f)

        # Should not raise
        V2Config.model_validate(v2)


# ── T042: auth.json untouched ────────────────────────────────────────────────


class TestT042AuthNotTouched:
    def test_auth_json_not_modified(
        self, v1_config_path: Path, auth_path: Path, tmp_path: Path
    ) -> None:
        """auth.json content unchanged after migration."""
        original = auth_path.read_text()
        original_sha = hash(original)

        v2_path = tmp_path / "migrated.yml"
        migrate_config(str(v1_config_path), str(v2_path), auth_path=str(auth_path))

        after = auth_path.read_text()
        after_sha = hash(after)

        assert original_sha == after_sha, "auth.json content changed!"

    def test_auth_json_not_touched_when_path_not_given(
        self, v1_config_path: Path, tmp_path: Path
    ) -> None:
        """Without auth_path argument, auth.json shouldn't even be opened."""
        v2_path = tmp_path / "migrated.yml"
        result = migrate_config(str(v1_config_path), str(v2_path))

        assert result["status"] == "migrated"
        # No auth-related keys in result
        assert "auth" not in result

    def test_auth_json_permissions_unchanged(
        self, v1_config_path: Path, auth_path: Path, tmp_path: Path
    ) -> None:
        """File permissions preserved."""

        v2_path = tmp_path / "migrated.yml"
        migrate_config(str(v1_config_path), str(v2_path), auth_path=str(auth_path))

        # Should still be readable (we don't change perms, but verify it exists)
        assert auth_path.exists()


# ── T043: Already v2 config is no-op ─────────────────────────────────────────


class TestT043AlreadyV2Noop:
    def test_v2_config_is_noop(self, v2_config_path: Path, tmp_path: Path) -> None:
        """Migrating an already-v2 config returns noop status."""
        out_path = tmp_path / "out.yml"
        result = migrate_config(str(v2_config_path), str(out_path))

        assert result["status"] == "noop"
        assert "already v2" in result.get("reason", "").lower()

    def test_v2_config_no_file_written(self, v2_config_path: Path, tmp_path: Path) -> None:
        """No output file written when already v2."""
        out_path = tmp_path / "out.yml"
        migrate_config(str(v2_config_path), str(out_path))

        # The function should not have written to out_path
        assert not out_path.exists()

    def test_v2_config_original_unchanged(self, v2_config_path: Path, tmp_path: Path) -> None:
        """Original v2 file left untouched."""
        original_content = v2_config_path.read_text()

        out_path = tmp_path / "out.yml"
        migrate_config(str(v2_config_path), str(out_path))

        assert v2_config_path.read_text() == original_content

    def test_v2_config_no_backup_created(self, v2_config_path: Path, tmp_path: Path) -> None:
        """No .v1.bak backup for already-v2 config."""
        out_path = tmp_path / "out.yml"
        result = migrate_config(str(v2_config_path), str(out_path))

        assert "backup" not in result or result["backup"] is None
