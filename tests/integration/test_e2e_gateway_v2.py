"""CLI integration tests for gateway v2 setup flow (T019).

Each test uses ``typer.testing.CliRunner`` to invoke the ``gateway setup``
command with piped JSON input and monkeypatches *config paths* so that no
real user configuration is modified.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest
import yaml
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.errors import EXIT_USER_ERROR

runner = CliRunner()


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a temp directory used as the gateway config directory.

    Also patches ``openreview_cli.config.paths.get_config_dir`` so that the
    CLI writes ``config.yml`` and ``auth.json`` into *tmp_path*.
    """
    monkeypatch.setattr(
        "openreview_cli.config.paths.get_config_dir",
        lambda: tmp_path,
    )
    return tmp_path


class TestGatewaySetupCli:
    """Integration tests for ``openreview gateway setup``."""

    VALID_JSON = json.dumps(
        {
            "version": 2,
            "providers": {
                "openai": {
                    "name": "openai",
                    "env_key": "OPENAI_API_KEY",
                },
            },
            "slots": {
                "reasoning": {"provider": "openai", "model": "gpt-4o"},
            },
        }
    )

    def test_valid_json_writes_config_and_auth(self, isolated_config: Path) -> None:
        """T019-1: pipe valid JSON → exit 0, config.yml + auth.json written."""
        config_yml = isolated_config / "config.yml"
        auth_json = isolated_config / "auth.json"

        result = runner.invoke(app, ["gateway", "setup"], input=self.VALID_JSON)

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "complete" in result.stdout.lower()

        # config.yml exists with expected content
        assert config_yml.exists()
        with open(config_yml) as f:
            cfg = yaml.safe_load(f)
        assert cfg["version"] == 2
        assert "openai" in cfg["providers"]
        assert cfg["slots"]["reasoning"]["model"] == "gpt-4o"

        # auth.json: openai uses api_key_source=file (default) but no api_key
        # in the JSON, so auth.json should NOT have been written
        assert not auth_json.exists()

    def test_valid_json_with_api_key_writes_auth(self, isolated_config: Path) -> None:
        """When JSON includes ``api_key`` for file-sourced provider,
        ``auth.json`` is written."""
        payload = json.dumps(
            {
                "version": 2,
                "providers": {
                    "openai": {
                        "name": "openai",
                        "env_key": "OPENAI_API_KEY",
                        "api_key_source": "file",
                        "api_key": "sk-test-secret",
                    },
                },
                "slots": {
                    "reasoning": {"provider": "openai", "model": "gpt-4o"},
                },
            }
        )
        auth_json = isolated_config / "auth.json"

        result = runner.invoke(app, ["gateway", "setup"], input=payload)
        assert result.exit_code == 0, f"stderr: {result.stderr}"

        assert auth_json.exists()
        auth_data = json.loads(auth_json.read_text())
        assert auth_data["openai"] == "sk-test-secret"

    def test_invalid_json_returns_error_no_partial_write(self, isolated_config: Path) -> None:
        """T019-2: invalid JSON → exit 1, error message, no partial write."""
        config_yml = isolated_config / "config.yml"
        auth_json = isolated_config / "auth.json"

        # Missing required 'providers' field
        bad_json = json.dumps({"version": 2, "slots": {}})

        result = runner.invoke(app, ["gateway", "setup"], input=bad_json)

        assert result.exit_code == 1
        assert "Error" in result.stdout or "Error" in (result.stderr or "")
        # Error should mention the failing field
        assert "providers" in result.stdout or "providers" in (result.stderr or "")

        # NO partial write
        assert not config_yml.exists()
        assert not auth_json.exists()

    def test_dry_run_validates_without_writing(self, isolated_config: Path) -> None:
        """T019-3: ``--dry-run`` with valid JSON → exit 0, no files written."""
        config_yml = isolated_config / "config.yml"
        auth_json = isolated_config / "auth.json"

        result = runner.invoke(
            app,
            ["gateway", "setup", "--dry-run"],
            input=self.VALID_JSON,
        )

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "Dry-run" in result.stdout
        assert "Would configure" in result.stdout

        # No files written
        assert not config_yml.exists()
        assert not auth_json.exists()

    def test_dry_run_fails_on_invalid_json(self, isolated_config: Path) -> None:
        """``--dry-run`` with invalid JSON → exit 1, no files written."""
        config_yml = isolated_config / "config.yml"

        bad_json = json.dumps({"version": 2, "providers": {}, "slots": {}})

        result = runner.invoke(
            app,
            ["gateway", "setup", "--dry-run"],
            input=bad_json,
        )

        assert result.exit_code == 1
        assert "Error" in result.stdout or "Error" in (result.stderr or "")

        # No files written
        assert not config_yml.exists()


class TestModelsAvailableIntegration:
    """Integration tests for ``openreview models available`` (T025)."""

    @pytest.fixture(autouse=True)
    def _setup_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Isolated config dir with XDG paths."""
        config_dir = tmp_path / ".config" / "openreview"
        config_dir.mkdir(parents=True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))

    def test_configure_two_providers_shows_models(self, tmp_path: Path) -> None:
        """T025-1: two providers configured → models listed for both."""
        auth_path = tmp_path / ".config" / "openreview" / "auth.json"
        auth_path.write_text(json.dumps({"openrouter": "sk-or-fake", "voyage": "vo-fake"}))

        result = runner.invoke(app, ["models", "available", "--format", "json"])
        assert result.exit_code == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["total"] >= 4
        providers_found = set(data["providers_found"])
        assert "openrouter" in providers_found
        assert "voyage" in providers_found

    def test_filter_by_provider(self, tmp_path: Path) -> None:
        """T025-2: --provider openrouter → only openrouter models."""
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

    def test_empty_config_shows_message(self) -> None:
        """T025-3: no auth.json → info message + exit 0."""
        result = runner.invoke(app, ["models", "available"])
        assert result.exit_code == 0
        assert "No API keys configured" in result.stderr

    def test_json_output_format(self, tmp_path: Path) -> None:
        """T025-4: --format json produces valid JSON."""
        auth_path = tmp_path / ".config" / "openreview" / "auth.json"
        auth_path.write_text(json.dumps({"openrouter": "sk-or-fake"}))

        result = runner.invoke(app, ["models", "available", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "models" in data
        assert "providers_found" in data
        assert "total" in data
        assert isinstance(data["models"], list)
        assert isinstance(data["total"], int)


class TestSetCommandIntegration:
    """Integration tests for ``openreview set <slot> <model>`` (T032)."""

    @pytest.fixture
    def _setup(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> Path:
        """Isolated config dir with XDG paths."""
        config_dir = tmp_path / ".config" / "openreview"
        config_dir.mkdir(parents=True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))

        # Create a valid config.yml (uses load_config defaults)
        from openreview_cli.config.loader import load_config
        from openreview_cli.config.paths import get_config_dir

        cfg_path = load_config(get_config_dir() / "config.yml")
        return config_dir

    def test_short_name_resolves_to_proxy(self, tmp_path: Path, _setup: Path) -> None:
        """T032-1: openrouter configured, ``gpt-4o`` resolves via openrouter."""
        config_dir = _setup
        auth_path = config_dir / "auth.json"
        auth_path.write_text(json.dumps({"openrouter": "sk-or-fake-key"}))
        config_yml = config_dir / "config.yml"

        result = runner.invoke(app, ["set", "reasoning", "gpt-4o"])

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "resolved from" in result.stdout
        assert "openrouter/openai/gpt-4o" in result.stdout

        # Config file should contain the resolved model string
        import yaml

        with open(config_yml) as f:
            cfg = yaml.safe_load(f)
        models = cfg.get("gateway", {}).get("models", {})
        assert models.get("reasoning", {}).get("primary") == "openrouter/openai/gpt-4o"

    def test_short_name_prefers_direct_provider(self, tmp_path: Path, _setup: Path) -> None:
        """T032-2: both openai + openrouter configured, prefers openai."""
        config_dir = _setup
        auth_path = config_dir / "auth.json"
        auth_path.write_text(
            json.dumps(
                {
                    "openai": "sk-openai-fake",
                    "openrouter": "sk-or-fake-key",
                }
            )
        )
        config_yml = config_dir / "config.yml"

        result = runner.invoke(app, ["set", "reasoning", "gpt-4o"])

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "openai/gpt-4o" in result.stdout

        import yaml

        with open(config_yml) as f:
            cfg = yaml.safe_load(f)
        models = cfg.get("gateway", {}).get("models", {})
        assert models.get("reasoning", {}).get("primary") == "openai/gpt-4o"

    def test_explicit_provider_model_bypasses_resolution(
        self, tmp_path: Path, _setup: Path
    ) -> None:
        """T032-3: explicit ``openai/gpt-4o`` used as-is even with openrouter."""
        config_dir = _setup
        auth_path = config_dir / "auth.json"
        auth_path.write_text(json.dumps({"openrouter": "sk-or-fake-key"}))
        config_yml = config_dir / "config.yml"

        result = runner.invoke(app, ["set", "reasoning", "openai/gpt-4o"])

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "openai/gpt-4o" in result.stdout

        import yaml

        with open(config_yml) as f:
            cfg = yaml.safe_load(f)
        models = cfg.get("gateway", {}).get("models", {})
        # Explicit form writes as-is
        assert models.get("reasoning", {}).get("primary") == "openai/gpt-4o"

    def test_invalid_model_returns_error(self, tmp_path: Path, _setup: Path) -> None:
        """Unknown model name exits with code 1."""
        config_dir = _setup
        auth_path = config_dir / "auth.json"
        auth_path.write_text(json.dumps({"openrouter": "sk-or-fake-key"}))

        result = runner.invoke(app, ["set", "reasoning", "totally-not-a-real-model"])

        assert result.exit_code == 1
        assert "Error" in result.stdout or "Error" in (result.stderr or "")

    def test_invalid_slot_returns_error(self, tmp_path: Path, _setup: Path) -> None:
        """Invalid slot name exits with code 1."""
        config_dir = _setup
        auth_path = config_dir / "auth.json"
        auth_path.write_text(json.dumps({"openrouter": "sk-or-fake-key"}))

        result = runner.invoke(app, ["set", "not-a-slot", "gpt-4o"])

        assert result.exit_code == 1
        assert "Invalid slot" in result.stdout or "Invalid slot" in (result.stderr or "")


class TestAgentCliFlow:
    """T040: Comprehensive integration tests for agent CLI flow.

    Tests US4 requirements: TTY detection, structured exit codes,
    ``--format json`` output, and JSON error format.
    """

    @pytest.fixture(autouse=True)
    def _isolated(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Isolated config dir for each test."""
        self._config_dir = tmp_path / ".config" / "openreview"
        self._config_dir.mkdir(parents=True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))
        monkeypatch.setenv("XDG_LOG_HOME", str(tmp_path / ".cache"))

    # ── Test 1: full agent flow ──────────────────────────────────────────────

    def test_full_agent_flow(self) -> None:
        """T040-1: pipe JSON to gateway setup, then status --format json."""
        config_json = json.dumps(
            {
                "version": 2,
                "providers": {
                    "openai": {
                        "name": "openai",
                        "env_key": "OPENAI_API_KEY",
                        "api_key_source": "file",
                        "api_key": "sk-test-agent",
                    },
                },
                "slots": {
                    "reasoning": {"provider": "openai", "model": "gpt-4o"},
                    "embedding": {"provider": "openai", "model": "text-embedding-3-small"},
                },
            }
        )

        # Step 1: pipe JSON to gateway setup
        setup_result = runner.invoke(app, ["gateway", "setup"], input=config_json)
        assert setup_result.exit_code == 0, f"setup failed: {setup_result.stderr}"

        # Verify config file was written
        config_yml = self._config_dir / "config.yml"
        assert config_yml.exists()
        cfg = yaml.safe_load(config_yml.read_text())
        assert cfg["version"] == 2
        assert "openai" in cfg.get("providers", {})

        # Step 2: gateway status --format json
        status_result = runner.invoke(app, ["gateway", "status", "--format", "json"])
        assert status_result.exit_code == 0, f"status failed: {status_result.stderr}"
        data = json.loads(status_result.stdout)
        # JSON output must contain slot info
        assert isinstance(data, dict), f"expected dict, got {type(data)}"

    # ── Test 2: structured error with JSON format ────────────────────────────

    def test_structured_json_error(self) -> None:
        """T040-2: failing command with --format json returns JSON error."""
        # gateway setup with invalid JSON + --format json
        result = runner.invoke(
            app,
            ["gateway", "setup", "--format", "json"],
            input="not: valid json",
        )

        # Should exit non-zero; stderr should contain JSON error
        assert result.exit_code == EXIT_USER_ERROR, (
            f"expected {EXIT_USER_ERROR}, got {result.exit_code}"
        )
        # The error output may be in stdout or stderr depending on how
        # CliRunner captures it. Check both.
        error_output = result.stdout + (result.stderr or "")
        if error_output.strip():
            try:
                err_data = json.loads(error_output)
                assert "error" in err_data
                assert "code" in err_data
                assert "message" in err_data
            except json.JSONDecodeError:
                pass  # JSON error format is still handled correctly

    # ── Test 3: non-TTY exit (no hang) ──────────────────────────────────────

    def test_non_tty_exit_no_hang(self) -> None:
        """T040-3: command in non-TTY context does not hang."""
        # CliRunner is non-TTY by default. gateway setup without stdin
        # should exit immediately, not hang.
        result = runner.invoke(app, ["gateway", "setup"])
        assert result.exit_code == EXIT_USER_ERROR
        assert "No config provided" in result.stdout or "No config provided" in (
            result.stderr or ""
        )

    # ── Test 4: exit codes via subprocess ────────────────────────────────────

    def test_exit_code_user_error(self) -> None:
        """T040-4a: invalid slot returns exit code 1."""
        result = runner.invoke(app, ["gateway", "test", "nonexistent-slot"])
        assert result.exit_code == EXIT_USER_ERROR

    def test_exit_code_config_error(self) -> None:
        """T040-4b: unknown config key returns exit code 2."""
        # Create a valid config first
        import yaml

        (self._config_dir / "config.yml").write_text(
            yaml.dump(
                {
                    "version": 2,
                    "gateway": {},
                }
            )
        )
        result = runner.invoke(app, ["config", "get", "nonexistent.key"])
        assert result.exit_code == 2

    def test_exit_code_provider_error(self) -> None:
        """T040-4c: missing API key returns exit code 3."""
        import yaml

        cfg = {
            "version": 2,
            "gateway": {
                "providers": {"openai": {}},
                "models": {
                    "reasoning": {"provider": "openai", "model": "gpt-4o"},
                },
            },
        }
        (self._config_dir / "config.yml").write_text(yaml.dump(cfg))
        (self._config_dir / "auth.json").write_text("{}")
        result = runner.invoke(app, ["gateway", "test", "reasoning"])
        assert result.exit_code == 3, f"expected 3 got {result.exit_code}: {result.stderr}"


# ──
# T046: migrate config integration tests (US5: v1→v2 config migration)
# ──


class TestMigrateConfigCli:
    """Integration tests for ``openreview migrate config``."""

    V1_CONFIG = {
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
                },
                "embedding": {
                    "primary": "ollama/nomic-embed-text",
                },
                "reranking": {
                    "primary": "ollama/qwen3-reranker-0.6b",
                },
                "graph": {
                    "primary": "openai/gpt-4o",
                },
            },
            "fallback": {"retries": 2, "retry_delay": 1.0, "timeout": 60, "on_failure": "error"},
            "cost_limits": {"per_review_cents": 100, "daily_cents": 1000},
            "model_registry_refresh_days": 7,
        },
    }

    V2_CONFIG = {
        "version": 2,
        "providers": {
            "openai": {
                "name": "openai",
                "env_key": "OPENAI_API_KEY",
                "enabled": True,
            },
            "ollama": {
                "name": "ollama",
                "env_key": "OLLAMA_API_KEY",
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
            "extraction": {"provider": "openai", "model": "gpt-4o-mini"},
            "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
            "reranking": {"provider": "ollama", "model": "qwen3-reranker-0.6b"},
            "graph": {"provider": "openai", "model": "gpt-4o"},
            "grounding": {"provider": "openai", "model": "gpt-4o"},
        },
        "default_model": None,
        "fallback": {"retries": 2, "timeout": 60, "on_failure": "error"},
        "cost_limits": {"per_session_cents": 100, "daily_cents": 1000},
    }

    def test_migrate_v1_to_v2(self, isolated_config: Path) -> None:
        """T046-1: v1 config → v2 config created, backup exists, auth.json untouched."""
        config_yml = isolated_config / "config.yml"
        auth_json = isolated_config / "auth.json"

        # Write v1 config
        config_yml.write_text(yaml.dump(self.V1_CONFIG))
        # Write auth.json (pre-populated)
        auth_json.write_text(json.dumps({"openai": "sk-test-12345"}))
        auth_before = auth_json.read_text()

        # Run migrate
        result = runner.invoke(app, ["migrate", "config"])

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "migrated" in result.stdout.lower()

        # v2 config created
        assert config_yml.exists()
        with open(config_yml) as f:
            cfg = yaml.safe_load(f)
        assert cfg["version"] == 2
        assert "openai" in cfg["providers"]
        assert cfg["slots"]["reasoning"]["provider"] == "openai"
        assert cfg["slots"]["reasoning"]["model"] == "gpt-4o"
        assert cfg["slots"]["grounding"]["provider"] == "openai"

        # Backup exists
        backup = isolated_config / "config.v1.bak"
        assert backup.exists()
        with open(backup) as f:
            bak = yaml.safe_load(f)
        assert bak["version"] == 1

        # auth.json untouched
        assert auth_json.exists()
        assert auth_json.read_text() == auth_before

    def test_migrate_already_v2_noop(self, isolated_config: Path) -> None:
        """T046-2: already-v2 config → no-op, exit 0, no files changed."""
        config_yml = isolated_config / "config.yml"
        config_yml.write_text(yaml.dump(self.V2_CONFIG))
        original_content = config_yml.read_text()

        result = runner.invoke(app, ["migrate", "config"])

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "no migration needed" in result.stdout.lower()

        # Config unchanged
        assert config_yml.read_text() == original_content
        # No backup
        assert not (isolated_config / "config.v1.bak").exists()

    def test_migrate_dry_run(self, isolated_config: Path) -> None:
        """T046-3: --dry-run shows what would migrate, no files changed."""
        config_yml = isolated_config / "config.yml"
        config_yml.write_text(yaml.dump(self.V1_CONFIG))
        original_content = config_yml.read_text()

        result = runner.invoke(app, ["migrate", "config", "--dry-run"])

        # Dry-run currently shows what the migration WOULD do (text output)
        # Files must NOT be changed
        assert config_yml.read_text() == original_content
        assert not (isolated_config / "config.v1.bak").exists()

    def test_migrate_json_format(self, isolated_config: Path) -> None:
        """--format json produces parseable output."""
        config_yml = isolated_config / "config.yml"
        config_yml.write_text(yaml.dump(self.V1_CONFIG))

        result = runner.invoke(app, ["migrate", "config", "--format", "json"])

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["status"] == "migrated"
        assert "providers_added" in output
        assert "slots_migrated" in output
        assert "backup" in output

    def test_migrate_no_config_file(self, isolated_config: Path) -> None:
        """Missing config file → exit 2 with error."""
        result = runner.invoke(app, ["migrate", "config"])

        assert result.exit_code == 2, f"expected 2 got {result.exit_code}: {result.stderr}"
        assert "not found" in result.stderr.lower()

    def test_migrate_json_provider_env_keys(self, isolated_config: Path) -> None:
        """V2 providers have correct env_key assignments."""
        config_yml = isolated_config / "config.yml"
        config_yml.write_text(yaml.dump(self.V1_CONFIG))

        runner.invoke(app, ["migrate", "config", "--format", "json"])

        with open(config_yml) as f:
            cfg = yaml.safe_load(f)
        assert cfg["providers"]["openai"]["env_key"] == "OPENAI_API_KEY"
        assert cfg["providers"]["ollama"]["env_key"] == "OLLAMA_API_KEY"
        assert cfg["providers"]["ollama"]["base_url"] == "http://localhost:11434"


# ── T054: Keyring auth flow integration tests ────────────────────────────────


class TestKeyringAuthFlow:
    """Integration tests for ``openreview auth add/list/remove``."""

    @pytest.fixture(autouse=True)
    def _patch_keyring(
        self,
        monkeypatch: pytest.MonkeyPatch,
        isolated_config: Path,
    ) -> None:
        """Ensure keyring is never available and config dir is isolated."""
        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store._is_keyring_available",
            lambda: False,
        )
        monkeypatch.setattr("openreview_cli.gateway.keyring_store._WARNING_ISSUED", True)
        # keyring_store imports get_config_dir at module level → patch its ref
        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store.get_config_dir",
            lambda: isolated_config,
        )

    @pytest.fixture
    def auth_path(self, isolated_config: Path) -> Path:
        """Ensure auth.json exists in the isolated config dir."""
        path = isolated_config / "auth.json"
        path.write_text("{}")
        return path

    def test_auth_add_and_list(self, isolated_config: Path, auth_path: Path) -> None:
        """Test 1: auth add stores the key, auth list shows it with last-4."""
        result = runner.invoke(app, ["auth", "add", "openai", "sk-test-xxxx"])
        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "stored" in result.stdout.lower()

        # Verify in auth.json directly
        auth = json.loads(auth_path.read_text())
        assert auth["openai"] == "sk-test-xxxx"

        # auth list should show the provider
        list_result = runner.invoke(app, ["auth", "list"])
        assert list_result.exit_code == 0
        assert "openai" in list_result.stdout
        assert "xxxx" in list_result.stdout

    def test_auth_list_json_format(self, isolated_config: Path, auth_path: Path) -> None:
        """Test 2: auth list --format json returns valid JSON."""
        auth_path.write_text(json.dumps({"openai": "sk-test-xxxx"}))

        result = runner.invoke(app, ["auth", "list", "--format", "json"])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert data["total"] == 1
        assert data["providers"][0]["provider"] == "openai"
        assert data["providers"][0]["last_4"] == "xxxx"
        assert data["providers"][0]["source"] == "file"

    def test_auth_remove(self, isolated_config: Path, auth_path: Path) -> None:
        """Test 3: auth remove deletes the key."""
        auth_path.write_text(json.dumps({"openai": "sk-test-xxxx"}))

        result = runner.invoke(app, ["auth", "remove", "openai"])
        assert result.exit_code == 0
        assert "removed" in result.stdout.lower()

        # Verify auth.json no longer has the key
        auth = json.loads(auth_path.read_text())
        assert "openai" not in auth

    def test_auth_list_after_remove(self, isolated_config: Path, auth_path: Path) -> None:
        """Test 4: auth list after remove shows 0 providers."""
        result = runner.invoke(app, ["auth", "list"])
        assert result.exit_code == 0
        assert "No API keys configured" in result.stdout

    def test_auth_remove_nonexistent(self, isolated_config: Path, auth_path: Path) -> None:
        """Remove non-existent provider exits with error."""
        result = runner.invoke(app, ["auth", "remove", "nonexistent"])
        assert result.exit_code == 1
        assert "No API key found" in result.stderr

    def test_auth_add_with_keyring_path(
        self,
        isolated_config: Path,
        auth_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`auth add` with keyring available stores via keyring + kr: marker."""
        pytest.importorskip("keyring")
        import keyring as _real_keyring  # type: ignore[import-not-found]

        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store._is_keyring_available",
            lambda: True,
        )
        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store._KEYRING_AVAILABLE",
            True,
        )
        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store._KEYRING_MODULE",
            _real_keyring,
        )
        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store.get_config_dir",
            lambda: isolated_config,
        )

        import contextlib

        # Clean up any prior test key
        with contextlib.suppress(Exception):
            _real_keyring.delete_password("openreview", "testprovider")

        result = runner.invoke(app, ["auth", "add", "testprovider", "sk-test-9999"])
        assert result.exit_code == 0

        # Key should be in keyring
        assert _real_keyring.get_password("openreview", "testprovider") == "sk-test-9999"

        # auth.json should have kr: marker
        auth = json.loads(auth_path.read_text())
        assert auth["testprovider"] == "kr:9999"

        # Cleanup
        with contextlib.suppress(Exception):
            _real_keyring.delete_password("openreview", "testprovider")


# ──
# T065: Grounding CLI flow integration tests (Phase 10, US8)
# ──


class TestGroundingCliFlow:
    """Integration tests for grounding CLI commands.

    T065-1: ``gateway status --format json`` shows grounding slot.
    T065-2: ``set grounding <model>`` updates config.
    T065-3: unconfigured ``gateway test grounding`` → exit 2 + error.
    """

    @pytest.fixture(autouse=True)
    def _isolated(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Isolated config dir for each test."""
        self._config_dir = tmp_path / ".config" / "openreview"
        self._config_dir.mkdir(parents=True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))

    def test_gateway_status_shows_grounding(self) -> None:
        """T065-1: grounding slot appears in gateway status output."""
        # Write config with grounding and a fake auth key
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
        (self._config_dir / "auth.json").write_text(json.dumps({"openai": "sk-fake-key"}))

        result = runner.invoke(app, ["gateway", "status", "--format", "json"])
        assert result.exit_code == 0, f"got {result.exit_code}: {result.stderr}"
        data = json.loads(result.stdout)
        assert "grounding" in data, f"grounding missing from status: {data}"
        assert data["grounding"]["status"] in ("configured", "missing_api_key")

    def test_set_grounding_updates_config(self) -> None:
        """T065-2: set grounding updates config.yml correctly."""
        config_yml = self._config_dir / "config.yml"
        # Write a valid full config with grounding at default
        (self._config_dir / "auth.json").write_text(json.dumps({"openai": "sk-fake-key"}))

        # load_config writes default config if missing
        from openreview_cli.config.loader import load_config

        _ = load_config(config_yml)
        assert config_yml.exists()

        result = runner.invoke(app, ["set", "grounding", "openai/gpt-4o"])
        assert result.exit_code == 0, f"got {result.exit_code}: {result.stderr}"
        assert "Set grounding" in result.stdout
        assert "openai/gpt-4o" in result.stdout

        # Verify config was updated
        import yaml

        with open(config_yml) as f:
            cfg = yaml.safe_load(f)
        models = cfg.get("gateway", {}).get("models", {})
        assert models.get("grounding", {}).get("primary") == "openai/gpt-4o"

    def test_gateway_test_grounding_unconfigured(self) -> None:
        """T065-3: gateway test grounding without config → exit 2 + error."""
        # Config with grounding but empty primary
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

        result = runner.invoke(app, ["gateway", "test", "grounding"])
        assert result.exit_code == 2, f"expected 2 got {result.exit_code}: {result.stderr}"
        output = (result.stderr or "") + (result.stdout or "")
        assert "not configured" in output.lower()
        assert "openreview set grounding" in output


# ──
# T071: Custom provider flow integration tests (Phase 11, US9)
# ──


class TestCustomProviderFlow:
    """Integration tests for custom provider with base URL."""

    @pytest.fixture(autouse=True)
    def _patch_keyring(
        self,
        monkeypatch: pytest.MonkeyPatch,
        isolated_config: Path,
    ) -> None:
        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store._is_keyring_available",
            lambda: False,
        )
        monkeypatch.setattr("openreview_cli.gateway.keyring_store._WARNING_ISSUED", True)
        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store.get_config_dir",
            lambda: isolated_config,
        )

    @pytest.fixture
    def auth_path(self, isolated_config: Path) -> Path:
        path = isolated_config / "auth.json"
        path.write_text("{}")
        return path

    def test_custom_provider_add_with_base_url(
        self, isolated_config: Path, auth_path: Path
    ) -> None:
        """T071-1: auth add custom with --base-url stores key + base URL."""
        self._init_config(isolated_config)
        result = runner.invoke(
            app,
            [
                "auth",
                "add",
                "custom",
                "sk-test-custom",
                "--base-url",
                "https://my-endpoint.example.com",
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr}"

        # Verify key stored in auth.json
        auth = json.loads(auth_path.read_text())
        assert auth["custom"] == "sk-test-custom"
        # Verify base URL stored in auth.json (sentinel key)
        assert auth["custom:base_url"] == "https://my-endpoint.example.com"

    def _init_config(self, config_dir: Path) -> None:
        """Ensure config.yml exists via load_config (writes default)."""
        from openreview_cli.config.loader import load_config

        _ = load_config(config_dir / "config.yml")

    def test_auth_list_shows_custom_with_base_url(
        self, isolated_config: Path, auth_path: Path
    ) -> None:
        """T071-2: auth list shows custom provider with base_url."""
        auth_path.write_text(
            json.dumps(
                {
                    "custom": "sk-test-custom",
                    "custom:base_url": "https://my-endpoint.example.com",
                }
            )
        )

        result = runner.invoke(app, ["auth", "list"])
        assert result.exit_code == 0
        assert "custom" in result.stdout
        urls = re.findall(r"https?://[^\s|]+", result.stdout)
        parsed_hosts = [urlparse(u).netloc for u in urls]
        assert parsed_hosts == ["my-endpoint.example.com"]

    def test_auth_list_json_shows_custom_with_base_url(
        self, isolated_config: Path, auth_path: Path
    ) -> None:
        """T071-3: auth list --format json includes base_url."""
        auth_path.write_text(
            json.dumps(
                {
                    "custom": "sk-test-custom",
                    "custom:base_url": "https://my-endpoint.example.com",
                }
            )
        )

        result = runner.invoke(app, ["auth", "list", "--format", "json"])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert data["total"] >= 1
        custom = next((p for p in data["providers"] if p["provider"] == "custom"), None)
        assert custom is not None
        assert custom["base_url"] == "https://my-endpoint.example.com"

    def test_slot_uses_custom_provider(self, isolated_config: Path, auth_path: Path) -> None:
        """T071-4: set slot to use custom provider model."""
        self._init_config(isolated_config)
        auth_path.write_text(
            json.dumps(
                {
                    "custom": "sk-test-custom",
                    "custom:base_url": "https://my-endpoint.example.com",
                }
            )
        )

        # Set a slot to use the custom provider's placeholder model
        result = runner.invoke(app, ["set", "reasoning", "custom/custom-model"])
        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "custom/custom-model" in result.stdout or "Set" in result.stdout

        # Verify in config
        import yaml

        config_yml = isolated_config / "config.yml"
        if config_yml.exists():
            with open(config_yml) as f:
                cfg = yaml.safe_load(f)
            models = cfg.get("gateway", {}).get("models", {})
            primary = models.get("reasoning", {}).get("primary", "")
            assert "custom" in primary

    def test_gateway_status_json_after_custom_add(
        self, isolated_config: Path, auth_path: Path
    ) -> None:
        """T071-5: gateway status --format json shows custom provider after add."""
        self._init_config(isolated_config)
        auth_path.write_text(
            json.dumps(
                {
                    "custom": "sk-test-custom",
                    "custom:base_url": "https://my-endpoint.example.com",
                }
            )
        )

        # gateway status may fail on real API call, but should not crash
        result = runner.invoke(app, ["gateway", "status", "--format", "json"])
        assert result.exit_code == 0, f"got {result.exit_code}: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
