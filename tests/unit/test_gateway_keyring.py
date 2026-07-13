"""Tests for keyring_store module (Phase 8, T048-T050).

T048: Test keyring_store with mocked keyring
T049: Test auth.json fallback path
T050: Test last-4-chars display + no full key in output
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _patch_keyring_store(monkeypatch: pytest.MonkeyPatch, auth_dir: Path) -> None:
    """Patch keyring_store to use test config dir and reset caches."""
    monkeypatch.setattr(
        "openreview_cli.gateway.keyring_store.get_config_dir",
        lambda: auth_dir,
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
def auth_dir(tmp_path: Path) -> Path:
    d = tmp_path / "config"
    d.mkdir()
    return d


@pytest.fixture
def auth_path(auth_dir: Path) -> Path:
    return auth_dir / "auth.json"


@pytest.fixture
def empty_auth(auth_path: Path) -> Path:
    auth_path.write_text("{}")
    return auth_path


# ── T048: Test keyring_store with mocked keyring ──────────────────────────────


class TestT048KeyringAvailable:
    """T048: Keyring available — keyring library is used."""

    def test_get_key_calls_keyring(
        self, monkeypatch: pytest.MonkeyPatch, auth_dir: Path, empty_auth: Path
    ) -> None:
        """get_key calls keyring.get_password and returns the value."""
        _patch_keyring_store(monkeypatch, auth_dir)
        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store._is_keyring_available",
            lambda: True,
        )

        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = "sk-test-1234"
        monkeypatch.setattr("openreview_cli.gateway.keyring_store._KEYRING_MODULE", mock_keyring)

        auth_data = {"openai": "kr:1234"}
        empty_auth.write_text(json.dumps(auth_data))

        from openreview_cli.gateway.keyring_store import get_key

        result = get_key("openai")
        assert result == "sk-test-1234"
        mock_keyring.get_password.assert_called_once_with("openreview", "openai")

    def test_set_key_calls_keyring(
        self, monkeypatch: pytest.MonkeyPatch, auth_dir: Path, empty_auth: Path
    ) -> None:
        """set_key calls keyring.set_password."""
        _patch_keyring_store(monkeypatch, auth_dir)
        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store._is_keyring_available",
            lambda: True,
        )

        mock_keyring = MagicMock()
        monkeypatch.setattr("openreview_cli.gateway.keyring_store._KEYRING_MODULE", mock_keyring)

        from openreview_cli.gateway.keyring_store import set_key

        set_key("openai", "sk-test-1234")
        mock_keyring.set_password.assert_called_once_with("openreview", "openai", "sk-test-1234")

        auth = json.loads(empty_auth.read_text())
        assert auth["openai"] == "kr:1234"

    def test_delete_key_calls_keyring(
        self, monkeypatch: pytest.MonkeyPatch, auth_dir: Path, empty_auth: Path
    ) -> None:
        """delete_key calls keyring.delete_password."""
        _patch_keyring_store(monkeypatch, auth_dir)
        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store._is_keyring_available",
            lambda: True,
        )

        mock_keyring = MagicMock()
        monkeypatch.setattr("openreview_cli.gateway.keyring_store._KEYRING_MODULE", mock_keyring)

        auth_data = {"openai": "kr:1234"}
        empty_auth.write_text(json.dumps(auth_data))

        from openreview_cli.gateway.keyring_store import delete_key

        delete_key("openai")
        mock_keyring.delete_password.assert_called_once_with("openreview", "openai")

        auth = json.loads(empty_auth.read_text())
        assert "openai" not in auth

    def test_get_key_keyring_not_installed(
        self, monkeypatch: pytest.MonkeyPatch, auth_dir: Path, empty_auth: Path
    ) -> None:
        """When keyring raises ImportError, get_key returns None (no error)."""
        _patch_keyring_store(monkeypatch, auth_dir)
        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store._is_keyring_available",
            lambda: False,
        )

        auth_data = {"openai": "kr:1234"}
        empty_auth.write_text(json.dumps(auth_data))

        from openreview_cli.gateway.keyring_store import get_key

        result = get_key("openai")
        assert result is None

    def test_list_providers(
        self, monkeypatch: pytest.MonkeyPatch, auth_dir: Path, empty_auth: Path
    ) -> None:
        """list_providers reads auth.json, returns list of provider dicts."""
        _patch_keyring_store(monkeypatch, auth_dir)

        auth_data = {
            "openai": "kr:1234",
            "anthropic": "sk-ant-5678",
        }
        empty_auth.write_text(json.dumps(auth_data))

        from openreview_cli.gateway.keyring_store import list_providers

        providers = list_providers()
        assert len(providers) == 2

        openai_entry = next(p for p in providers if p["provider"] == "openai")
        anthropic_entry = next(p for p in providers if p["provider"] == "anthropic")

        assert openai_entry["last_4"] == "1234"
        assert openai_entry["source"] == "keyring"
        assert anthropic_entry["last_4"] == "5678"
        assert anthropic_entry["source"] == "file"


# ── T049: Test auth.json fallback path ─────────────────────────────────────


class TestT049FileFallback:
    """T049: Keyring unavailable — file fallback."""

    def test_set_key_falls_back_to_file(
        self, monkeypatch: pytest.MonkeyPatch, auth_dir: Path, empty_auth: Path
    ) -> None:
        """set_key writes to auth.json with full key when keyring unavailable."""
        _patch_keyring_store(monkeypatch, auth_dir)
        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store._is_keyring_available",
            lambda: False,
        )

        from openreview_cli.gateway.keyring_store import set_key

        set_key("openai", "sk-test-1234")

        auth = json.loads(empty_auth.read_text())
        assert auth["openai"] == "sk-test-1234"

    def test_get_key_from_file(
        self, monkeypatch: pytest.MonkeyPatch, auth_dir: Path, empty_auth: Path
    ) -> None:
        """get_key reads from auth.json when keyring unavailable."""
        _patch_keyring_store(monkeypatch, auth_dir)
        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store._is_keyring_available",
            lambda: False,
        )

        auth_data = {"openai": "sk-test-1234"}
        empty_auth.write_text(json.dumps(auth_data))

        from openreview_cli.gateway.keyring_store import get_key

        result = get_key("openai")
        assert result == "sk-test-1234"

    def test_delete_key_removes_from_file(
        self, monkeypatch: pytest.MonkeyPatch, auth_dir: Path, empty_auth: Path
    ) -> None:
        """delete_key removes provider from auth.json."""
        _patch_keyring_store(monkeypatch, auth_dir)
        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store._is_keyring_available",
            lambda: False,
        )

        auth_data = {"openai": "sk-test-1234"}
        empty_auth.write_text(json.dumps(auth_data))

        from openreview_cli.gateway.keyring_store import delete_key

        delete_key("openai")

        auth = json.loads(empty_auth.read_text())
        assert "openai" not in auth


# ── T050: Test last-4-chars display ───────────────────────────────────────


class TestT050Last4Chars:
    """T050: Last-4-chars display and full key in internal use."""

    def test_list_providers_shows_last_4(
        self, monkeypatch: pytest.MonkeyPatch, auth_dir: Path, empty_auth: Path
    ) -> None:
        """list_providers returns entries with last_4 field, never full key."""
        _patch_keyring_store(monkeypatch, auth_dir)

        auth_data = {"openai": "sk-test-1234"}
        empty_auth.write_text(json.dumps(auth_data))

        from openreview_cli.gateway.keyring_store import list_providers

        providers = list_providers()
        assert len(providers) == 1
        entry = providers[0]
        assert entry["last_4"] == "1234"
        assert "sk-test" not in entry["last_4"]

    def test_get_key_returns_full_key(
        self, monkeypatch: pytest.MonkeyPatch, auth_dir: Path, empty_auth: Path
    ) -> None:
        """get_key returns the full key (internal use, not for display)."""
        _patch_keyring_store(monkeypatch, auth_dir)
        monkeypatch.setattr(
            "openreview_cli.gateway.keyring_store._is_keyring_available",
            lambda: False,
        )

        auth_data = {"openai": "sk-test-1234"}
        empty_auth.write_text(json.dumps(auth_data))

        from openreview_cli.gateway.keyring_store import get_key

        result = get_key("openai")
        assert result == "sk-test-1234"

    def test_list_providers_keyring_source(
        self, monkeypatch: pytest.MonkeyPatch, auth_dir: Path, empty_auth: Path
    ) -> None:
        """list_providers shows keyring as source for kr: prefixed entries."""
        _patch_keyring_store(monkeypatch, auth_dir)

        auth_data = {"openai": "kr:abcd"}
        empty_auth.write_text(json.dumps(auth_data))

        from openreview_cli.gateway.keyring_store import list_providers

        providers = list_providers()
        assert len(providers) == 1
        entry = providers[0]
        assert entry["source"] == "keyring"
        assert entry["last_4"] == "abcd"
