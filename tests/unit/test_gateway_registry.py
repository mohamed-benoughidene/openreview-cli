from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

from openreview_cli.gateway.errors import EnvKeyCollisionError
from openreview_cli.gateway.registry import (
    ModelRegistry,
    _build_provider,
    add_custom_provider,
    load_registry,
)

MODELS_JSON = {
    "providers": {
        "openai": {
            "name": "OpenAI",
            "env_key": "OPENAI_API_KEY",
            "auth_required": True,
            "models": {
                "gpt-4o": {
                    "slots": ["reasoning", "extraction"],
                    "context": 128000,
                    "recommended": True,
                    "status": "active",
                },
                "gpt-4o-mini": {
                    "slots": ["reasoning"],
                    "context": 128000,
                    "recommended": False,
                    "status": "active",
                },
            },
        },
        "anthropic": {
            "name": "Anthropic",
            "env_key": "ANTHROPIC_API_KEY",
            "auth_required": True,
            "models": {
                "claude-3-opus": {
                    "slots": ["reasoning", "extraction"],
                    "context": 200000,
                    "recommended": True,
                    "status": "active",
                },
            },
        },
    },
}


class _MockResponse:
    def __init__(self, text: str) -> None:
        self.text = text
        self._parsed = json.loads(text)

    def json(self) -> Any:
        return self._parsed

    def raise_for_status(self) -> None:
        pass


def test_load_valid_json(tmp_path: Path) -> None:
    registry_path = tmp_path / "models.json"
    registry_path.write_text(json.dumps(MODELS_JSON))
    registry = ModelRegistry(registry_path)
    registry.load()
    assert "openai" in registry._providers
    assert "anthropic" in registry._providers
    assert len(registry._providers["openai"].models) == 2
    assert len(registry._providers["anthropic"].models) == 1
    assert registry._providers["openai"].name == "OpenAI"
    assert registry._providers["openai"].env_key == "OPENAI_API_KEY"
    assert registry._providers["openai"].auth_required is True


def test_load_non_existent_file(tmp_path: Path) -> None:
    registry_path = tmp_path / "nonexistent.json"
    registry = ModelRegistry(registry_path)
    registry.load()
    assert registry._providers == {}


def test_list_providers(tmp_path: Path) -> None:
    registry_path = tmp_path / "models.json"
    registry_path.write_text(json.dumps(MODELS_JSON))
    registry = ModelRegistry(registry_path)
    registry.load()
    providers = registry.list_providers()
    assert len(providers) == 2
    names = {p["name"] for p in providers}
    assert names == {"OpenAI", "Anthropic"}
    for p in providers:
        if p["name"] == "OpenAI":
            assert p["env_key"] == "OPENAI_API_KEY"
            assert p["auth_required"] is True
            assert p["model_count"] == 2
        elif p["name"] == "Anthropic":
            assert p["env_key"] == "ANTHROPIC_API_KEY"
            assert p["auth_required"] is True
            assert p["model_count"] == 1


def test_list_models_known_provider(tmp_path: Path) -> None:
    registry_path = tmp_path / "models.json"
    registry_path.write_text(json.dumps(MODELS_JSON))
    registry = ModelRegistry(registry_path)
    registry.load()
    models = registry.list_models("openai")
    assert len(models) == 2
    model_ids = {m["model_id"] for m in models}
    assert model_ids == {"gpt-4o", "gpt-4o-mini"}
    for m in models:
        if m["model_id"] == "gpt-4o":
            assert m["slots"] == ["reasoning", "extraction"]
            assert m["context"] == 128000
            assert m["recommended"] is True


def test_list_models_unknown_provider(tmp_path: Path) -> None:
    registry_path = tmp_path / "models.json"
    registry_path.write_text(json.dumps(MODELS_JSON))
    registry = ModelRegistry(registry_path)
    registry.load()
    models = registry.list_models("nonexistent")
    assert models == []


def test_refresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_path = tmp_path / "models.json"
    registry = ModelRegistry(registry_path)

    def mock_get(url: str, **kwargs: Any) -> _MockResponse:
        return _MockResponse(json.dumps(MODELS_JSON))

    monkeypatch.setattr(httpx, "get", mock_get)
    count = registry.refresh("https://example.com/models.json")
    assert count == 3
    assert registry_path.exists()
    assert json.loads(registry_path.read_text()) == MODELS_JSON
    assert len(registry.list_providers()) == 2


def test_discover_ollama(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_path = tmp_path / "models.json"
    registry = ModelRegistry(registry_path)
    ollama_data = {
        "models": [
            {
                "name": "llama3:latest",
                "details": {"parameter_size": "7B"},
            },
            {
                "name": "mistral:latest",
                "details": {"parameter_size": "7B"},
            },
        ]
    }

    def mock_get(url: str, **kwargs: Any) -> _MockResponse:
        return _MockResponse(json.dumps(ollama_data))

    monkeypatch.setattr(httpx, "get", mock_get)
    models = registry.discover_ollama("http://localhost:11434")
    assert len(models) == 2
    assert models[0]["model_id"] == "llama3:latest"
    assert models[0]["note"] == "Ollama local — 7B"
    assert models[1]["model_id"] == "mistral:latest"
    assert models[1]["note"] == "Ollama local — 7B"


def test_discover_ollama_unreachable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_path = tmp_path / "models.json"
    registry = ModelRegistry(registry_path)

    def mock_get(url: str, **kwargs: Any) -> None:
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx, "get", mock_get)
    models = registry.discover_ollama("http://localhost:11434")
    assert models == []


def test_load_registry_deepseek_complete_entry() -> None:
    reg = load_registry()
    assert "deepseek" in reg
    assert reg["deepseek"].base_url == "https://api.deepseek.com"
    assert reg["deepseek"].source == "bundled"
    caps = reg["deepseek"].capabilities
    assert caps is not None
    assert isinstance(caps.reasoning, bool)
    assert isinstance(caps.embedding, bool)


def test_build_provider_reads_api_key_env() -> None:
    from openreview_cli.gateway.registry import _build_provider

    info = {
        "name": "foo",
        "api_key_env": "FOO_API_KEY",
        "base_url": "http://x",
        "source": "custom",
        "capabilities": {},
    }
    provider = _build_provider("foo", info)
    assert provider.env_key == "FOO_API_KEY"


def test_load_registry_custom_provider_surfaces_env_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openreview_cli.gateway import registry as reg_mod

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    cfg = {
        "gateway": {
            "custom_providers": [
                {
                    "name": "foo",
                    "api_key_env": "FOO_API_KEY",
                    "base_url": "http://x",
                    "source": "custom",
                }
            ]
        }
    }
    (config_dir / "config.yml").write_text(yaml.safe_dump(cfg))
    monkeypatch.setattr(reg_mod, "_config_dir", lambda: config_dir)

    assert load_registry()["foo"].env_key == "FOO_API_KEY"


def test_load_registry_custom_provider_from_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openreview_cli.gateway import registry as reg_mod

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    cfg = {
        "gateway": {
            "custom_providers": [
                {
                    "name": "myllm",
                    "base_url": "https://myllm.example.com/v1",
                    "capabilities": {
                        "embedding": False,
                        "reasoning": True,
                        "context_window": 8192,
                        "tool_call": False,
                    },
                }
            ]
        }
    }
    (config_dir / "config.yml").write_text(yaml.safe_dump(cfg))
    monkeypatch.setattr(reg_mod, "_config_dir", lambda: config_dir)

    reg = load_registry()
    assert "myllm" in reg
    assert reg["myllm"].source == "custom"
    assert reg["myllm"].base_url == "https://myllm.example.com/v1"


def test_load_registry_merges_new_pre_listed_without_overwriting_user_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openreview_cli.gateway import registry as reg_mod

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    # User-edited pre-listed provider (ollama) + missing deepseek.
    user_models = {
        "providers": {
            "ollama": {
                "name": "Ollama (user edited)",
                "base_url": "http://user-edited:11434",
                "source": "user-edited",
                "models": {},
            }
        }
    }
    (config_dir / "models.json").write_text(json.dumps(user_models))
    monkeypatch.setattr(reg_mod, "_config_dir", lambda: config_dir)

    reg = load_registry()
    # User edit preserved.
    assert reg["ollama"].base_url == "http://user-edited:11434"
    assert reg["ollama"].source != "bundled"
    # New pre-listed provider merged in from bundled.
    assert "deepseek" in reg
    assert reg["deepseek"].source == "bundled"


def test_load_registry_keeps_user_custom_provider_when_bundled_gains_new(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-9: a user's OWN custom provider must survive when the bundled
    registry gains a new pre-listed provider (e.g. after an app update)."""
    from openreview_cli.gateway import registry as reg_mod

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    # User has a custom provider in config.yml...
    cfg = {
        "gateway": {
            "custom_providers": [
                {
                    "name": "myllm",
                    "base_url": "https://myllm.example.com/v1",
                    "api_key_env": "MYLLM_API_KEY",
                    "capabilities": {
                        "embedding": False,
                        "reasoning": True,
                        "context_window": 8192,
                        "tool_call": False,
                    },
                    "source": "custom",
                }
            ]
        }
    }
    (config_dir / "config.yml").write_text(yaml.safe_dump(cfg))
    monkeypatch.setattr(reg_mod, "_config_dir", lambda: config_dir)

    reg = load_registry()
    # User's custom provider still present...
    assert "myllm" in reg
    assert reg["myllm"].source == "custom"
    # ...and the new pre-listed provider bundled with the app is also present.
    assert "deepseek" in reg


def test_env_key_collision_message_matches_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-3 edge case: collision error wording must be
    'provider <name> derives to env var <X> already used by <existing>'."""
    from openreview_cli.gateway import registry as reg_mod

    # Point registry at an empty config dir so only bundled providers apply.
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr(reg_mod, "_config_dir", lambda: config_dir)

    # Supplying --env-key OPENAI_API_KEY collides with the bundled openai
    # provider's env_key -> real EnvKeyCollisionError path (name "mycustom"
    # does not collide, so we reach the env-key check).
    with pytest.raises(EnvKeyCollisionError) as exc_info:
        add_custom_provider("mycustom", "https://example.com/v1", api_key_env="OPENAI_API_KEY")
    msg = str(exc_info.value)
    assert msg == ("provider mycustom derives to env var OPENAI_API_KEY already used by OpenAI")
    assert exc_info.value.provider == "mycustom"
    assert exc_info.value.existing == "OpenAI"


def test_load_registry_voyage_native_entry() -> None:
    reg = load_registry()
    assert "voyage" in reg
    p = reg["voyage"]
    assert p.base_url == "https://api.voyageai.com/v1"
    assert p.env_key == "VOYAGE_API_KEY"
    assert p.source == "bundled"
    caps = p.capabilities
    assert caps.embedding is True
    assert caps.rerank is True
    assert caps.reasoning is False
    assert caps.tool_call is False
    assert "voyage-3.5" in p.models
    assert "rerank-2.5" in p.models


def test_load_registry_moonshot_native_entry() -> None:
    reg = load_registry()
    assert "moonshot" in reg
    p = reg["moonshot"]
    assert p.base_url == "https://api.moonshot.ai/v1"
    assert p.env_key == "MOONSHOT_API_KEY"
    assert p.source == "bundled"
    caps = p.capabilities
    assert caps.reasoning is True
    assert "kimi-k2" in p.models


def test_load_registry_mistral_native_entry() -> None:
    reg = load_registry()
    assert "mistral" in reg
    p = reg["mistral"]
    assert p.base_url == "https://api.mistral.ai/v1"
    assert p.env_key == "MISTRAL_API_KEY"
    assert p.source == "bundled"
    caps = p.capabilities
    assert caps.reasoning is True
    assert caps.tool_call is True
    assert "magistral-medium-2506" in p.models
    assert "mistral-large-latest" in p.models


def test_load_registry_zai_native_entry() -> None:
    reg = load_registry()
    assert "zai" in reg
    p = reg["zai"]
    assert p.base_url == "https://api.z.ai/v1"
    assert p.env_key == "ZAI_API_KEY"
    assert p.source == "bundled"
    caps = p.capabilities
    assert caps.reasoning is True
    assert "glm-4.7" in p.models


def test_registry_loads_multifield_providers_unconfigured() -> None:
    """Spec 034 US2 (T014): bedrock/vertex/azure expose multi-field
    credentials lists; registry tolerates empty models."""
    reg = load_registry()

    assert "bedrock" in reg
    assert "vertex" in reg
    assert "azure" in reg

    bedrock = reg["bedrock"]
    assert len(bedrock.credentials) >= 1
    assert bedrock.credentials[0].litellm_param == "aws_region_name"

    vertex = reg["vertex"]
    assert len(vertex.credentials) >= 1
    assert vertex.credentials[0].litellm_param == "vertex_project"

    azure = reg["azure"]
    assert len(azure.credentials) >= 1
    assert azure.credentials[0].litellm_param == "api_key"


def test_build_provider_without_credentials_defaults_empty() -> None:
    result = _build_provider("openai", {"name": "OpenAI", "env_key": "OPENAI_API_KEY"})
    assert result.credentials == []


def test_build_provider_forwards_credentials() -> None:
    result = _build_provider(
        "bedrock",
        {
            "name": "Bedrock",
            "credentials": [
                {
                    "env_key": "AWS_REGION_NAME",
                    "label": "Region",
                    "litellm_param": "aws_region_name",
                    "secret": False,
                    "required": True,
                    "is_file_path": False,
                }
            ],
        },
    )
    assert len(result.credentials) == 1
    assert result.credentials[0].litellm_param == "aws_region_name"


def test_provider_credential_status_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    """US3 FR-4: per-field credential health, secret VALUES never emitted."""
    from openreview_cli.gateway.models import CredentialField, ProviderInfo
    from openreview_cli.gateway.registry import provider_credential_status

    info = ProviderInfo(
        name="bedrock",
        credentials=[
            CredentialField(
                env_key="AWS_REGION_NAME",
                label="Region",
                litellm_param="aws_region_name",
                secret=False,
                required=True,
            ),
            CredentialField(
                env_key="AWS_ACCESS_KEY_ID",
                label="Access Key ID",
                litellm_param="aws_access_key_id",
                secret=True,
                required=True,
            ),
            CredentialField(
                env_key="AWS_SECRET_ACCESS_KEY",
                label="Secret Access Key",
                litellm_param="aws_secret_access_key",
                secret=True,
                required=True,
            ),
        ],
    )

    # Hermetic: clear any AWS_* leaked by earlier tests in the suite.
    for var in ("AWS_REGION_NAME", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(var, raising=False)

    # No env, empty auth -> not configured, all fields unresolved.
    result = provider_credential_status(info, {})
    assert result["configured"] is False
    assert len(result["credentials"]) == 3
    assert all(not c["resolved"] for c in result["credentials"])
    # No value-bearing keys anywhere.
    for c in result["credentials"]:
        assert "value" not in c
        assert "secret_value" not in c

    # Set only the region -> still not configured (2 missing), region resolved.
    monkeypatch.setenv("AWS_REGION_NAME", "us-east-1")
    result = provider_credential_status(info, {})
    assert result["configured"] is False
    assert result["credentials"][0]["resolved"] is True
    assert result["credentials"][1]["resolved"] is False
    assert result["credentials"][2]["resolved"] is False
    # The secret value must never appear in the serialized output.
    assert "us-east-1" not in json.dumps(result)

    # Set the secret too -> resolved, but its value still never emitted.
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake")
    result = provider_credential_status(info, {})
    assert result["credentials"][2]["resolved"] is True
    assert "fake" not in json.dumps(result)
