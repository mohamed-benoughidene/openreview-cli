import json
import platform
from pathlib import Path

import pytest

from openreview_cli.config.auth import ensure_auth, load_auth


def test_auth_json_created_with_empty_object(tmp_path: Path) -> None:
    auth_path = ensure_auth(tmp_path)
    assert auth_path.exists()
    data = json.loads(auth_path.read_text())
    assert data == {}


def test_auth_json_permissions_on_unix(tmp_path: Path) -> None:
    if platform.system() == "Windows":
        pytest.skip("Unix-only permission test")
    auth_path = ensure_auth(tmp_path)
    mode = auth_path.stat().st_mode & 0o777
    assert mode == 0o600


def test_auth_json_warns_on_insecure_permissions(tmp_path: Path) -> None:
    if platform.system() == "Windows":
        pytest.skip("Unix-only permission test")
    auth_path = tmp_path / "auth.json"
    auth_path.write_text("{}")
    auth_path.chmod(0o644)
    ensure_auth(tmp_path)
    mode = auth_path.stat().st_mode & 0o777
    assert mode == 0o600


def test_load_auth_returns_empty_for_missing(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    auth_path.write_text("{}")
    result = load_auth(auth_path)
    assert result == {}


def test_provider_key_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-override")
    auth_path = tmp_path / "auth.json"
    auth_path.write_text('{"openai": "sk-file-value"}')
    result = load_auth(auth_path)
    assert result["openai"] == "sk-test-override"
