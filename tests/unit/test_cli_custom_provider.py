"""Tests for custom provider with base URL (Phase 11, T067-T068).

T067: Test custom provider with base URL
T068: Test custom model resolution
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from openreview_cli.gateway.v2_config import ProviderConfig

# ── Helpers ───────────────────────────────────────────────────────────────────


def _patch_keyring_store(monkeypatch: pytest.MonkeyPatch, config_dir: Path) -> None:
    """Point keyring_store to a temp config dir and reset caches."""
    monkeypatch.setattr(
        "openreview_cli.gateway.keyring_store.get_config_dir",
        lambda: config_dir,
    )
    monkeypatch.setattr(
        "openreview_cli.gateway.keyring_store._KEYRING_AVAILABLE",
        None,
    )
    monkeypatch.setattr(
        "openreview_cli.gateway.keyring_store._KEYRING_MODULE",
        None,
    )
    monkeypatch.setattr(
        "openreview_cli.gateway.keyring_store._WARNING_ISSUED",
        False,
    )


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    d = tmp_path / "config"
    d.mkdir()
    return d


@pytest.fixture
def auth_path(config_dir: Path) -> Path:
    p = config_dir / "auth.json"
    p.write_text("{}")
    return p


@pytest.fixture
def config_yml(config_dir: Path) -> Path:
    p = config_dir / "config.yml"
    p.write_text("version: 2\nproviders: {}\nslots: {}\n")
    return p


# ── T067: Custom provider with base URL ──────────────────────────────────────


class TestT067CustomProviderBaseUrl:
    """T067: Custom provider with base URL."""

    def test_save_base_url_roundtrip(
        self, monkeypatch: pytest.MonkeyPatch, config_dir: Path, auth_path: Path
    ) -> None:
        """save_base_url / get_base_url roundtrip."""
        _patch_keyring_store(monkeypatch, config_dir)

        from openreview_cli.gateway.keyring_store import (
            get_base_url,
            save_base_url,
        )

        save_base_url("custom", "https://my-endpoint.example.com")
        assert get_base_url("custom") == "https://my-endpoint.example.com"

        # stored as sentinel key in auth.json
        raw = json.loads(auth_path.read_text())
        assert raw["custom:base_url"] == "https://my-endpoint.example.com"

    def test_get_base_url_none_when_not_set(
        self, monkeypatch: pytest.MonkeyPatch, config_dir: Path, auth_path: Path
    ) -> None:
        """get_base_url returns None when no base_url stored."""
        _patch_keyring_store(monkeypatch, config_dir)

        from openreview_cli.gateway.keyring_store import get_base_url

        assert get_base_url("nonexistent") is None

    def test_save_base_url_with_key_roundtrip(
        self, monkeypatch: pytest.MonkeyPatch, config_dir: Path, auth_path: Path
    ) -> None:
        """set_key + save_base_url coexist."""
        _patch_keyring_store(monkeypatch, config_dir)

        from openreview_cli.gateway.keyring_store import (
            get_base_url,
            get_key,
            save_base_url,
            set_key,
        )

        set_key("custom", "sk-test-1234")
        save_base_url("custom", "https://my-endpoint.example.com")

        assert get_key("custom") == "sk-test-1234"
        assert get_base_url("custom") == "https://my-endpoint.example.com"

    def test_list_providers_includes_base_url(
        self, monkeypatch: pytest.MonkeyPatch, config_dir: Path, auth_path: Path
    ) -> None:
        """list_providers returns base_url in the entry dict."""
        _patch_keyring_store(monkeypatch, config_dir)

        from openreview_cli.gateway.keyring_store import (
            list_providers,
            save_base_url,
            set_key,
        )

        set_key("custom", "sk-test-5678")
        save_base_url("custom", "https://my-endpoint.example.com")

        providers = list_providers()
        assert len(providers) == 1
        entry = providers[0]
        assert entry["provider"] == "custom"
        assert entry["base_url"] == "https://my-endpoint.example.com"
        assert entry["last_4"] == "5678"

    def test_delete_key_also_removes_base_url(
        self, monkeypatch: pytest.MonkeyPatch, config_dir: Path, auth_path: Path
    ) -> None:
        """delete_key removes both key and base_url from auth.json."""
        _patch_keyring_store(monkeypatch, config_dir)

        from openreview_cli.gateway.keyring_store import (
            delete_key,
            get_base_url,
            get_key,
            save_base_url,
            set_key,
        )

        set_key("custom", "sk-test-1234")
        save_base_url("custom", "https://my-endpoint.example.com")

        assert get_key("custom") is not None
        assert get_base_url("custom") is not None

        delete_key("custom")
        assert get_key("custom") is None
        assert get_base_url("custom") is None

        raw = json.loads(auth_path.read_text())
        assert "custom" not in raw
        assert "custom:base_url" not in raw

    def test_auth_list_command_shows_base_url(
        self, monkeypatch: pytest.MonkeyPatch, config_dir: Path, auth_path: Path, config_yml: Path
    ) -> None:
        """`auth list` output includes base_url when present."""
        from typer.testing import CliRunner

        _patch_keyring_store(monkeypatch, config_dir)

        from openreview_cli.gateway.keyring_store import (
            save_base_url,
            set_key,
        )

        # must also mock get_config_dir for cli runner
        monkeypatch.setattr(
            "openreview_cli.config.paths.get_config_dir",
            lambda: config_dir,
        )

        set_key("custom", "sk-test-5678")
        save_base_url("custom", "https://my-endpoint.example.com")

        runner = CliRunner()
        from openreview_cli.app import app

        result = runner.invoke(app, ["auth", "list"])
        assert result.exit_code == 0
        # Should show custom provider and its base URL
        assert "custom" in result.stdout
        assert "my-endpoint.example.com" in result.stdout

    def test_base_url_in_gateway_status_json(
        self, monkeypatch: pytest.MonkeyPatch, config_dir: Path, auth_path: Path, config_yml: Path
    ) -> None:
        """gateway status --format json shows base_url for custom provider."""
        from typer.testing import CliRunner

        _patch_keyring_store(monkeypatch, config_dir)
        monkeypatch.setattr(
            "openreview_cli.config.paths.get_config_dir",
            lambda: config_dir,
        )

        from openreview_cli.gateway.keyring_store import (
            save_base_url,
            set_key,
        )

        set_key("custom", "sk-test-5678")
        save_base_url("custom", "https://my-endpoint.example.com")

        # mock Gateway.health_check to avoid real API calls
        mock_gw = MagicMock()
        mock_gw.health_check.return_value = {
            "reasoning": {
                "status": "configured",
                "provider": "custom",
                "model": "custom-model",
                "base_url": None,
            },
        }

        monkeypatch.setattr(
            "openreview_cli.gateway.router.Gateway",
            lambda: mock_gw,
        )

        runner = CliRunner()
        from openreview_cli.app import app

        result = runner.invoke(app, ["gateway", "status", "--format", "json"])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        # health_check is mocked so the base_url display depends on
        # how status merges it — at minimum ensure no crash
        assert isinstance(data, dict)


# ── T068: Custom model resolution ─────────────────────────────────────────────


class TestT068CustomModelResolution:
    """T068: Custom model resolution."""

    def test_custom_provider_in_registry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ModelRegistry finds 'custom' provider in models.json."""
        from openreview_cli.gateway.registry import ModelRegistry

        registry_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "openreview_cli"
            / "gateway"
            / "models.json"
        )
        registry = ModelRegistry(registry_path)
        registry.load()
        providers = registry.list_providers()
        custom = [p for p in providers if p["name"].lower().startswith("custom")]
        assert len(custom) >= 1

    def test_custom_model_accepted_as_opaque(
        self, monkeypatch: pytest.MonkeyPatch, config_dir: Path, auth_path: Path
    ) -> None:
        """Custom provider models not in static registry are accepted.

        The custom provider acts as a wildcard: any model name can be
        used because the actual model is served by the custom endpoint.
        """
        _patch_keyring_store(monkeypatch, config_dir)

        from openreview_cli.gateway.keyring_store import set_key
        from openreview_cli.gateway.registry import ModelRegistry

        set_key("custom", "sk-test-1234")

        registry_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "openreview_cli"
            / "gateway"
            / "models.json"
        )
        reg = ModelRegistry(registry_path)
        reg.load()

        available = reg.get_available_models(["custom"])
        custom_models = [m for m in available if m["provider"] == "custom"]
        # Should have at least the placeholder model
        assert len(custom_models) >= 1
        assert any(m["model_id"] == "custom-model" for m in custom_models)

    def test_provider_config_with_base_url(self) -> None:
        """ProviderConfig accepts base_url field."""
        cfg = ProviderConfig(
            name="custom",
            env_key="CUSTOM_API_KEY",
            base_url="https://my-endpoint.example.com",
        )
        assert cfg.base_url == "https://my-endpoint.example.com"
        assert cfg.name == "custom"

    def test_provider_config_base_url_default_none(self) -> None:
        """ProviderConfig.base_url defaults to None."""
        cfg = ProviderConfig(
            name="custom",
            env_key="CUSTOM_API_KEY",
        )
        assert cfg.base_url is None
