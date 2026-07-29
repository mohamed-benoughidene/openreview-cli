"""Live integration test for AWS Bedrock (multi-field provider auth, spec 034).

Live Bedrock call. Skips without AWS_* env vars. This is the real-credential
counterpart to the mocked T012/T13 unit tests — a skip here is EXPECTED,
not a failure.

Unlike the mocked unit tests (which inject MagicMock gateways with canned
responses), this test drives Gateway.chat through the REAL
`_get_litellm_kwargs` multi-field path against AWS Bedrock with actual
credentials, proving the Bedrock wiring actually works end to end.

It is skipped unless AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and
AWS_REGION_NAME are all present in the environment, so it never fails CI on
machines without credentials.
"""

from __future__ import annotations

import os

import pytest


def _aws_creds_present() -> bool:
    return bool(
        os.environ.get("AWS_ACCESS_KEY_ID")
        and os.environ.get("AWS_SECRET_ACCESS_KEY")
        and os.environ.get("AWS_REGION_NAME")
    )


requires_aws = pytest.mark.skipif(
    not _aws_creds_present(),
    reason="requires live AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME",
)


@pytest.mark.live
@requires_aws
def test_bedrock_live_chat_returns_nonempty(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Real Bedrock call through Gateway.chat: a simple prompt must return a
    non-empty string, exercising the real _get_litellm_kwargs path."""
    from openreview_cli.gateway.router import Gateway

    auth_dir = tmp_path / "auth"
    auth_dir.mkdir()
    # Bedrock creds come from AWS_* env vars directly (litellm reads them),
    # so an empty auth file is fine — the real path is the env vars.
    (auth_dir / "auth.json").write_text("{}")

    gateway = Gateway(auth_path=auth_dir / "auth.json")
    # bedrock/anthropic.claude-v2 is a well-known Bedrock model id; if the
    # account has not been granted access, litellm raises and the test fails
    # loudly (that is the point of a live test).
    response = gateway.chat(
        "bedrock/anthropic.claude-v2",
        [{"role": "user", "content": "say hi"}],
    )
    assert isinstance(response, str)
    assert response.strip() != ""
