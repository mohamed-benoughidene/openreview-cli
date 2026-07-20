import json
import platform
from pathlib import Path

import pytest

from openreview_cli.config.auth import (
    ensure_auth,
    load_auth,
    save_key,
    save_provider_credentials,
)


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


def test_load_auth_preserves_legacy_string_and_new_dict(tmp_path: Path) -> None:
    """Regression: legacy single-string entry and new dict entry must both
    survive a load_auth round-trip in one auth.json."""
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(
        json.dumps({"openai": "sk-legacy", "bedrock": {"AWS_REGION_NAME": "us-east-1"}})
    )
    result = load_auth(auth_path)
    assert result["openai"] == "sk-legacy"
    assert result["bedrock"] == {"AWS_REGION_NAME": "us-east-1"}


def test_save_provider_credentials_writes_dict_and_preserves_legacy(
    tmp_path: Path,
) -> None:
    """save_provider_credentials writes dict-shaped auth for a provider while
    leaving a pre-existing legacy string entry untouched (coexistence)."""
    auth_path = tmp_path / "auth.json"
    save_key(auth_path, "openai", "sk-legacy")

    save_provider_credentials(
        auth_path, "bedrock", {"AWS_REGION_NAME": "us-east-1", "AWS_ACCESS_KEY_ID": "AKIA"}
    )

    data = json.loads(auth_path.read_text())
    assert data["openai"] == "sk-legacy"
    assert data["bedrock"] == {"AWS_REGION_NAME": "us-east-1", "AWS_ACCESS_KEY_ID": "AKIA"}


def test_save_provider_credentials_merges_into_existing_fields(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    save_provider_credentials(auth_path, "bedrock", {"AWS_REGION_NAME": "us-east-1"})
    save_provider_credentials(auth_path, "bedrock", {"AWS_ACCESS_KEY_ID": "AKIA"})

    data = json.loads(auth_path.read_text())
    assert data["bedrock"] == {
        "AWS_REGION_NAME": "us-east-1",
        "AWS_ACCESS_KEY_ID": "AKIA",
    }


def test_provider_add_writes_dict_shaped_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`gateway provider add --cred` writes dict-shaped auth.json and leaves a
    pre-existing legacy string entry unchanged."""
    from typer.testing import CliRunner

    from openreview_cli.app import app

    monkeypatch.setattr("openreview_cli.config.paths.get_config_dir", lambda: tmp_path)
    monkeypatch.setattr("openreview_cli.gateway.registry.add_custom_provider", lambda *a, **k: None)

    auth_path = tmp_path / "auth.json"
    auth_path.write_text(json.dumps({"openai": "sk-legacy"}))

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "gateway",
            "provider",
            "add",
            "bedrock",
            "--base-url",
            "https://bedrock.example",
            "--cred",
            "AWS_REGION_NAME=us-east-1",
            "--cred",
            "AWS_ACCESS_KEY_ID=AKIA",
        ],
    )
    assert result.exit_code == 0, result.output

    data = json.loads(auth_path.read_text())
    assert data["openai"] == "sk-legacy"
    assert data["bedrock"] == {
        "AWS_REGION_NAME": "us-east-1",
        "AWS_ACCESS_KEY_ID": "AKIA",
    }


def test_provider_add_rejects_malformed_cred(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from openreview_cli.app import app

    monkeypatch.setattr("openreview_cli.config.paths.get_config_dir", lambda: tmp_path)
    monkeypatch.setattr("openreview_cli.gateway.registry.add_custom_provider", lambda *a, **k: None)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "gateway",
            "provider",
            "add",
            "bedrock",
            "--base-url",
            "https://bedrock.example",
            "--cred",
            "NO_EQUALS_HERE",
        ],
    )
    assert result.exit_code == 2
