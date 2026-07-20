from __future__ import annotations

import json

import pytest

from openreview_cli.gateway.models import CredentialField, ProviderInfo


def _fake_registry() -> dict[str, ProviderInfo]:
    bedrock = ProviderInfo(
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
    openai = ProviderInfo(name="openai", env_key="OPENAI_API_KEY")
    return {"bedrock": bedrock, "openai": openai}


def test_providers_json_emits_per_field_status(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """US3 FR-4: `gateway providers --json` reports per-field status, no value leak."""
    from openreview_cli import app

    monkeypatch.setattr("openreview_cli.gateway.registry.load_registry", _fake_registry)
    monkeypatch.setattr("openreview_cli.config.auth.load_auth", lambda path: {})

    # Region set in env -> must NOT appear in printed JSON.
    monkeypatch.setenv("AWS_REGION_NAME", "us-east-1")

    app.gateway_providers(json_mode=True)
    out = capsys.readouterr().out
    data = json.loads(out)

    providers = {p["name"]: p for p in data["providers"]}
    bedrock_out = providers["bedrock"]

    # New fields present.
    assert "configured" in bedrock_out
    assert isinstance(bedrock_out["configured"], bool)
    assert isinstance(bedrock_out["credentials"], list)
    assert len(bedrock_out["credentials"]) == 3
    for c in bedrock_out["credentials"]:
        assert isinstance(c["resolved"], bool)
        assert isinstance(c["secret"], bool)
        assert "resolved" in c and "secret" in c and "required" in c

    # Backward-compatible fields retained.
    assert "api_key_env" in bedrock_out

    # Secret value never printed.
    assert "us-east-1" not in out
