"""Unit tests for gateway JSON-stdin applier (T013-T015)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from openreview_cli.gateway.apply import apply_config


class TestApplyConfig:
    """Tests for apply_config()."""

    def test_valid_json_applied_atomically(self, tmp_path: Path) -> None:
        """T013: valid JSON config writes config.yml + auth.json."""
        config_path = tmp_path / "config.yml"
        auth_path = tmp_path / "auth.json"

        json_str = json.dumps(
            {
                "version": 2,
                "providers": {
                    "openai": {
                        "name": "openai",
                        "env_key": "OPENAI_API_KEY",
                    },
                    "voyage": {
                        "name": "voyage",
                        "env_key": "VOYAGE_API_KEY",
                        "api_key_source": "file",
                        "api_key": "vo-secret-key",
                    },
                },
                "slots": {
                    "reasoning": {
                        "provider": "openai",
                        "model": "gpt-4o",
                    },
                    "embedding": {
                        "provider": "voyage",
                        "model": "voyage-3",
                    },
                },
            }
        )

        result = apply_config(json_str, config_path, auth_path)

        assert result["status"] == "ok"
        assert "openai" in result["providers"]
        assert "voyage" in result["providers"]
        assert "reasoning" in result["slots"]
        assert "embedding" in result["slots"]

        # config.yml written and contains expected data
        assert config_path.exists()
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        assert cfg["version"] == 2
        assert "openai" in cfg["providers"]
        assert "voyage" in cfg["providers"]
        assert cfg["providers"]["openai"]["name"] == "openai"
        assert cfg["slots"]["reasoning"]["model"] == "gpt-4o"

        # auth.json written only for file-sourced providers with api_key
        assert auth_path.exists()
        auth_data = json.loads(auth_path.read_text())
        assert auth_data["voyage"] == "vo-secret-key"
        # openai uses default api_key_source=file but no api_key in JSON → not in auth.json
        assert "openai" not in auth_data

    def test_invalid_json_missing_providers(self, tmp_path: Path) -> None:
        """T014: missing required field raises error naming the field."""
        config_path = tmp_path / "config.yml"
        auth_path = tmp_path / "auth.json"

        # version defaults to 2, providers is required with no default
        json_str = json.dumps(
            {
                "version": 2,
                "slots": {
                    "reasoning": {
                        "provider": "openai",
                        "model": "gpt-4o",
                    }
                },
            }
        )

        with pytest.raises(ValueError) as excinfo:
            apply_config(json_str, config_path, auth_path)

        error_msg = str(excinfo.value)
        # Error must name the failed field
        assert "providers" in error_msg

        # Verify NO partial write
        assert not config_path.exists()
        assert not auth_path.exists()

    def test_empty_input_returns_usage(self, tmp_path: Path) -> None:
        """T015: empty/whitespace input returns usage error."""
        config_path = tmp_path / "config.yml"
        auth_path = tmp_path / "auth.json"

        with pytest.raises(ValueError) as excinfo:
            apply_config("", config_path, auth_path)

        error_msg = str(excinfo.value)
        assert "No config provided" in error_msg
        assert "--help" in error_msg

        # Verify no files written
        assert not config_path.exists()
        assert not auth_path.exists()

    def test_whitespace_input_returns_usage(self, tmp_path: Path) -> None:
        """T015 variant: whitespace-only input is also rejected."""
        config_path = tmp_path / "config.yml"
        auth_path = tmp_path / "auth.json"

        with pytest.raises(ValueError) as excinfo:
            apply_config("   \n  \t  ", config_path, auth_path)

        error_msg = str(excinfo.value)
        assert "No config provided" in error_msg
        assert "--help" in error_msg


class TestApplyConfigDryRun:
    """Tests for apply_config_with_dry_run()."""

    def test_dry_run_valid_json(self) -> None:
        """Dry-run with valid JSON returns expected summary, no files written."""
        from openreview_cli.gateway.apply import apply_config_with_dry_run

        json_str = json.dumps(
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

        result = apply_config_with_dry_run(json_str)
        assert result["status"] == "ok"
        assert result["dry_run"] is True
        assert "openai" in result["providers"]
        assert "reasoning" in result["slots"]

    def test_dry_run_invalid_json(self) -> None:
        """Dry-run with invalid JSON raises error."""
        from openreview_cli.gateway.apply import apply_config_with_dry_run

        json_str = json.dumps(
            {
                "version": 2,
                "providers": {},
                "slots": {"bad_slot": {"provider": "openai", "model": "gpt-4o"}},
            }
        )

        with pytest.raises(ValueError) as excinfo:
            apply_config_with_dry_run(json_str)

        assert "bad_slot" in str(excinfo.value) or "invalid slot" in str(excinfo.value).lower()
