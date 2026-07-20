"""Tests for `gateway providers/models/provider add` CLI convergence (Phase 9 US7)."""

from __future__ import annotations

import json
from typing import Any

from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.gateway.errors import ProviderNameCollisionError
from openreview_cli.gateway.models import Capability, ModelEntry, ProviderInfo

runner = CliRunner()


def _make_provider(
    name: str,
    source: str = "bundled",
    env_key: str = "FOO_API_KEY",
    caps: Capability | None = None,
    models: dict[str, ModelEntry] | None = None,
    base_url: str | None = "http://x",
    is_local: bool = False,
) -> ProviderInfo:
    return ProviderInfo(
        name=name,
        env_key=env_key,
        auth_required=True,
        base_url=base_url,
        is_local=is_local,
        source=source,
        capabilities=caps or Capability(),
        models=models or {},
    )


def test_providers_json_parseable(monkeypatch: Any) -> None:
    reg = {
        "openai": _make_provider("openai", source="bundled"),
        "myfoo": _make_provider("myfoo", source="custom", env_key="MYFOO_API_KEY", is_local=True),
    }
    monkeypatch.setattr("openreview_cli.gateway.registry.load_registry", lambda: reg)

    result = runner.invoke(app, ["gateway", "providers", "--json"])
    assert result.exit_code == 0, result.output

    data = json.loads(result.stdout)
    assert "providers" in data
    assert len(data["providers"]) == 2

    for p in data["providers"]:
        for key in ("name", "base_url", "api_key_env", "capabilities", "is_local", "source"):
            assert key in p, f"missing {key}"
    custom = next(p for p in data["providers"] if p["name"] == "myfoo")
    assert custom["source"] == "custom"


def test_models_json_parseable(monkeypatch: Any) -> None:
    models = {"gpt-4o": ModelEntry(slots=["reasoning"], context=128000, recommended=True)}
    reg = {"openai": _make_provider("openai", models=models)}
    monkeypatch.setattr("openreview_cli.gateway.registry.load_registry", lambda: reg)

    result = runner.invoke(app, ["gateway", "models", "--json", "openai"])
    assert result.exit_code == 0, result.output

    data = json.loads(result.stdout)
    assert "openai" in data
    assert isinstance(data["openai"], list)
    assert len(data["openai"]) == 1
    assert data["openai"][0]["id"] == "gpt-4o"


def test_providers_json_equals_tui_list(monkeypatch: Any) -> None:
    reg = {
        "openai": _make_provider("openai", source="bundled"),
        "myfoo": _make_provider("myfoo", source="custom", env_key="MYFOO_API_KEY"),
    }
    monkeypatch.setattr("openreview_cli.gateway.registry.load_registry", lambda: reg)

    result = runner.invoke(app, ["gateway", "providers", "--json"])
    assert result.exit_code == 0, result.output
    cli_names = {p["name"] for p in json.loads(result.stdout)["providers"]}

    from openreview_cli.tui.domain.gateway import _get_registry

    tui_names = set(_get_registry().keys())

    assert cli_names == tui_names


def test_provider_add_valid(monkeypatch: Any) -> None:
    recorded: dict[str, Any] = {}

    def _stub(
        name: str, base_url: str, capabilities: Any = None, api_key_env: str | None = None
    ) -> ProviderInfo:
        recorded.update(
            name=name, base_url=base_url, capabilities=capabilities, api_key_env=api_key_env
        )
        return _make_provider(
            name, source="custom", env_key=api_key_env or f"{name.upper()}_API_KEY"
        )

    monkeypatch.setattr("openreview_cli.gateway.registry.add_custom_provider", _stub)

    result = runner.invoke(
        app,
        ["gateway", "provider", "add", "myfoo", "--base-url", "http://x", "--env-key", "MYFOO_KEY"],
    )
    assert result.exit_code == 0, result.output
    assert recorded["name"] == "myfoo"
    assert recorded["base_url"] == "http://x"
    assert recorded["api_key_env"] == "MYFOO_KEY"


def test_provider_add_collision_rejected(monkeypatch: Any) -> None:
    def _raise(
        name: str, base_url: str, capabilities: Any = None, api_key_env: str | None = None
    ) -> None:
        raise ProviderNameCollisionError("myfoo", "exists")

    monkeypatch.setattr("openreview_cli.gateway.registry.add_custom_provider", _raise)

    result = runner.invoke(
        app,
        ["gateway", "provider", "add", "myfoo", "--base-url", "http://x", "--env-key", "MYFOO_KEY"],
    )
    assert result.exit_code != 0
    assert "Error" in result.output


def test_provider_add_derives_env_when_omitted(monkeypatch: Any) -> None:
    recorded: dict[str, Any] = {}

    def _stub(
        name: str, base_url: str, capabilities: Any = None, api_key_env: str | None = None
    ) -> ProviderInfo:
        recorded.update(api_key_env=api_key_env)
        return _make_provider(
            name, source="custom", env_key=api_key_env or f"{name.upper()}_API_KEY"
        )

    monkeypatch.setattr("openreview_cli.gateway.registry.add_custom_provider", _stub)

    result = runner.invoke(app, ["gateway", "provider", "add", "myfoo", "--base-url", "http://x"])
    assert result.exit_code == 0, result.output
    assert recorded["api_key_env"] == "MYFOO_API_KEY"


def test_provider_add_rejects_empty_cred(tmp_path: Any, monkeypatch: Any) -> None:
    """T038 — FR-5: `--cred KEY=` (empty value) must be rejected, not stored."""
    monkeypatch.setattr("openreview_cli.config.paths.get_config_dir", lambda: tmp_path)

    def _stub(
        name: str, base_url: str, capabilities: Any = None, api_key_env: str | None = None
    ) -> Any:
        return _make_provider(
            name, source="custom", env_key=api_key_env or f"{name.upper()}_API_KEY"
        )

    monkeypatch.setattr("openreview_cli.gateway.registry.add_custom_provider", _stub)

    result = runner.invoke(
        app,
        [
            "gateway",
            "provider",
            "add",
            "myfoo",
            "--base-url",
            "http://x",
            "--cred",
            "AWS_REGION_NAME=",
        ],
    )
    assert result.exit_code != 0, result.output
    assert "empty" in result.output.lower(), result.output

    auth_path = tmp_path / "auth.json"
    if auth_path.exists():
        data = json.loads(auth_path.read_text())
        for prov in data.values():
            if isinstance(prov, dict):
                assert all(v != "" for v in prov.values()), f"empty cred stored: {data}"
