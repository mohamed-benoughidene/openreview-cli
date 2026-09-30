from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from openreview_cli.gateway.errors import (
    AllProvidersFailedError,
    AuthError,
    ConnectionError,
    EmptyMessagesError,
    ModelNotFoundError,
    RateLimitError,
    SlotNotConfiguredError,
    UnclassifiedProviderError,
)
from openreview_cli.gateway.models import Capability, ProviderInfo
from openreview_cli.gateway.router import Gateway, classify_provider


@pytest.fixture(autouse=True)
def _mark_pii_available() -> None:
    """Router tests exercise cloud dispatch under performance tier; the PII
    gate (spec 020) is tested separately in test_gateway_tier_enforcement."""
    from openreview_cli.gateway.router import mark_pii_available

    mark_pii_available()


class _MockMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _MockChoice:
    def __init__(self, content: str) -> None:
        self.message = _MockMessage(content)


class _MockCompletionResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_MockChoice(content)]


class _UnauthorizedError(Exception):
    """An injected 401: permanent, so the retry loop must not repeat it (#154)."""

    status_code = 401


def _gateway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config_text: str, auth_text: str | None = None
) -> Gateway:
    import uuid

    import openreview_cli.gateway.cost as cost_mod

    monkeypatch.setattr(cost_mod, "db_log_cost", lambda *a, **kw: str(uuid.uuid4()))
    monkeypatch.setattr(
        cost_mod,
        "db_get_session_cost",
        lambda *a, **kw: {"prompt_tokens": 0, "completion_tokens": 0, "cost_cents": 0},
    )
    monkeypatch.setattr(cost_mod, "completion_cost", lambda r: 0.0)

    config_path = tmp_path / "config.yml"
    config_path.write_text(config_text)
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(auth_text or json.dumps({"openai": "sk-test", "anthropic": "sk-ant-test"}))
    db_path = tmp_path / "data.db"
    from openreview_cli.storage.database import init_database

    init_database(db_path)
    return Gateway(config_path, auth_path, db_path)


COMMON_CONFIG = """\
privacy:
  tier: performance
gateway:
  models:
    reasoning:
      primary: openai/gpt-4
      fallback: anthropic/claude-3
      params:
        temperature: 0.7
        max_tokens: 2048
      extra_params:
        top_p: 0.9
    extraction:
      primary: openai/gpt-4o
    embedding:
      primary: openai/text-embedding-3-small
    reranking:
      primary: cohere/rerank-english-v3.0
  fallback:
    retries: 2
    retry_delay: 0.01
    timeout: 5
"""


class TestChat:
    def test_returns_response_text(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import openreview_cli.gateway.router as router_mod

        monkeypatch.setattr(
            router_mod, "completion", lambda **kw: _MockCompletionResponse("Hello!")
        )
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        result = gw.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert result == "Hello!"

    def test_chat_survives_cost_logging_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T030: a cost-logging failure (e.g. missing session FK for non-review
        flows like grounding) must NOT block the AI call. chat must still
        return the model response."""
        import openreview_cli.gateway.router as router_mod

        monkeypatch.setattr(
            router_mod, "completion", lambda **kw: _MockCompletionResponse("Hello!")
        )
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)

        def _boom(*args: object, **kwargs: object) -> str:
            raise RuntimeError("cost log exploded")

        gw._cost_tracker.log_call = _boom  # type: ignore[method-assign]
        result = gw.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert result == "Hello!"

    def test_raises_slot_not_configured_for_invalid_slot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        with pytest.raises(SlotNotConfiguredError, match="Invalid slot"):
            gw.chat("nonexistent", [{"role": "user", "content": "Hi"}])

    def test_raises_slot_not_configured_when_no_primary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = """\
gateway:
  models:
    reasoning:
      primary: ""
  fallback:
    retries: 1
    retry_delay: 0.01
    timeout: 5
"""
        gw = _gateway(tmp_path, monkeypatch, config)
        with pytest.raises(SlotNotConfiguredError, match="no primary model"):
            gw.chat("reasoning", [{"role": "user", "content": "Hi"}])

    def test_falls_back_to_fallback_model(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import openreview_cli.gateway.router as router_mod

        call_log: list[str] = []

        def failing_then_ok(**kw: Any) -> _MockCompletionResponse:
            call_log.append(kw["model"])
            if len(call_log) <= 3:
                msg = "primary failed"
                raise RuntimeError(msg)
            return _MockCompletionResponse("from fallback")

        monkeypatch.setattr(router_mod, "completion", failing_then_ok)
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        result = gw.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert result == "from fallback"
        assert call_log[-1] == "anthropic/claude-3"

    def test_fallback_dispatch_carries_the_fallback_providers_api_base_and_drops_the_primarys_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """#144/D2: the fallback dispatch is retargeted to its own provider.

        The primary is a ``source="custom"`` provider, so ``_get_litellm_kwargs``
        injects an explicit ``api_key``; litellm honours that over the provider
        env var, so leaving it in the reused ``call_kwargs`` would send the
        primary's credential to the fallback provider's host. The anchor is only
        meaningful with a custom primary — with a bundled primary the pop is
        behaviourally inert.
        """
        import openreview_cli.gateway.router as router_mod

        registry = {
            "openai": ProviderInfo(
                name="openai",
                env_key="OPENAI_API_KEY",
                base_url="https://api.openai.com/v1",
                source="custom",
                is_local=False,
                capabilities=Capability(reasoning=True),
            ),
            "anthropic": ProviderInfo(
                name="anthropic",
                env_key="ANTHROPIC_API_KEY",
                base_url="https://api.anthropic.com/v1",
                is_local=False,
                capabilities=Capability(reasoning=True),
            ),
        }
        monkeypatch.setattr(router_mod, "load_registry", lambda: registry)

        seen: list[dict[str, Any]] = []

        def recording_completion(**kw: Any) -> _MockCompletionResponse:
            seen.append(
                {
                    "model": kw["model"],
                    "api_base": kw.get("api_base"),
                    "api_key": kw.get("api_key"),
                }
            )
            if len(seen) <= 3:
                msg = "primary failed"
                raise RuntimeError(msg)
            return _MockCompletionResponse("from fallback")

        monkeypatch.setattr(router_mod, "completion", recording_completion)
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        result = gw.chat("reasoning", [{"role": "user", "content": "Hi"}])

        assert result == "from fallback"
        assert seen[0]["api_key"] == "sk-test"
        assert seen[0]["api_base"] == "https://api.openai.com/v1"
        assert seen[-1]["model"] == "anthropic/claude-3"
        assert seen[-1]["api_base"] == "https://api.anthropic.com/v1"
        assert seen[-1]["api_key"] is None

    def test_a_fallback_failure_names_the_fallback_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failure of the fallback dispatch is classified under the fallback's prefix.

        ``_classify_error`` stamps the provider name into the message, so
        classifying this failure under the primary's prefix would name a provider
        that never carried the failing request.
        """
        import openreview_cli.gateway.router as router_mod

        registry = {
            "openai": ProviderInfo(
                name="openai",
                env_key="OPENAI_API_KEY",
                base_url="https://api.openai.com/v1",
                source="custom",
                is_local=False,
                capabilities=Capability(reasoning=True),
            ),
            "anthropic": ProviderInfo(
                name="anthropic",
                env_key="ANTHROPIC_API_KEY",
                base_url="https://api.anthropic.com/v1",
                is_local=False,
                capabilities=Capability(reasoning=True),
            ),
        }
        monkeypatch.setattr(router_mod, "load_registry", lambda: registry)

        dispatched: list[str] = []

        def always_down(**kw: Any) -> Any:
            dispatched.append(kw["model"])
            raise RuntimeError("provider down")

        monkeypatch.setattr(router_mod, "completion", always_down)
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)

        with pytest.raises(UnclassifiedProviderError) as exc_info:
            gw.chat("reasoning", [{"role": "user", "content": "Hi"}])

        assert dispatched[-1] == "anthropic/claude-3", dispatched
        assert "[anthropic]" in str(exc_info.value), str(exc_info.value)
        assert "[openai]" not in str(exc_info.value), str(exc_info.value)

    def test_raises_all_providers_failed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R3-4 Test A — the catch-all in Gateway._classify_error must produce
        the new ``UnclassifiedProviderError``, NOT ``AllProvidersFailedError``
        (which now exclusively signals gateway-local exhaustion).
        """
        import openreview_cli.gateway.router as router_mod

        def always_fail(**kw: Any) -> Any:
            raise RuntimeError("always fails")

        monkeypatch.setattr(router_mod, "completion", always_fail)
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        with pytest.raises(UnclassifiedProviderError) as exc_info:
            gw.chat("reasoning", [{"role": "user", "content": "Hi"}])
        # And it must NOT be the exhaustion type.
        assert not isinstance(exc_info.value, AllProvidersFailedError), (
            "R3-4: catch-all must not be AllProvidersFailedError (exhaustion signal)"
        )

    def test_classify_error_catch_all_is_unclassified(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R3-4 Test A — direct _classify_error on an unhandled exception must
        return UnclassifiedProviderError, not AllProvidersFailedError."""
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        result = gw._classify_error(RuntimeError("totally unknown"), provider="openai")
        assert isinstance(result, UnclassifiedProviderError)
        assert not isinstance(result, AllProvidersFailedError)

    def test_each_attempt_is_counted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """#143: every attempt inside the retry loop earns one counter increment."""
        import openreview_cli.gateway.router as router_mod

        calls: list[str] = []

        def _fail_twice_then_ok(**kw: Any) -> _MockCompletionResponse:
            calls.append(kw["model"])
            if len(calls) <= 2:
                raise RuntimeError("transient")
            return _MockCompletionResponse("ok")

        monkeypatch.setattr(router_mod, "completion", _fail_twice_then_ok)
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)

        assert gw.chat("reasoning", [{"role": "user", "content": "Hi"}]) == "ok"

        assert len(calls) == 3, "the retry loop did not dispatch three times"
        assert gw._cloud_calls_made == 3, "every dispatch attempt must be counted"

    @pytest.mark.parametrize("shape", ["none", "empty_choices", "no_message"])
    def test_a_reply_with_no_usable_choice_is_a_typed_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str
    ) -> None:
        """#149/#150: a reply the caller can never read is a typed error, not a crash.

        ``None``, ``choices == []`` and a choice with no ``message`` all map to the
        same ``UnclassifiedProviderError`` naming the provider, validated BEFORE the
        cost row so no ``cost_logs`` row is written. The dispatch is still counted
        (#147/C2).
        """
        import types as _types

        import openreview_cli.gateway.router as router_mod

        replies: dict[str, Any] = {
            "none": None,
            "empty_choices": _types.SimpleNamespace(choices=[]),
            "no_message": _types.SimpleNamespace(choices=[_types.SimpleNamespace(message=None)]),
        }
        monkeypatch.setattr(router_mod, "completion", lambda **kw: replies[shape])
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        log_call = MagicMock()
        monkeypatch.setattr(gw._cost_tracker, "log_call", log_call)

        with pytest.raises(UnclassifiedProviderError) as exc_info:
            gw.chat("extraction", [{"role": "user", "content": "Hi"}])

        assert "openai" in str(exc_info.value)
        assert gw._cloud_calls_made == 1
        log_call.assert_not_called()

    def test_a_permanent_error_is_dispatched_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """#154: an auth failure is dispatched once, not ``retries + 1`` times.

        The socket-free anchor: the ``extraction`` slot has no fallback (the
        ``reasoning`` slot does, so C6 keeps one fallback dispatch available and it
        would give 2), so a permanent class short-circuits the retry loop after the
        single counted attempt.
        """
        import openreview_cli.gateway.router as router_mod

        calls: list[str] = []

        def always_unauthorized(**kw: Any) -> Any:
            calls.append(kw["model"])
            raise _UnauthorizedError("unauthorized")

        monkeypatch.setattr(router_mod, "completion", always_unauthorized)
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)

        with pytest.raises(AuthError):
            gw.chat("extraction", [{"role": "user", "content": "Hi"}])

        assert len(calls) == 1, f"a permanent error was dispatched {len(calls)} times"


class TestSlotPrimaryModel:
    def test_returns_configured_primary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        assert gw.slot_primary_model("extraction") == "openai/gpt-4o"

    def test_returns_none_for_unconfigured_slot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        assert gw.slot_primary_model("unknown_slot") is None


class TestGetLitellmKwargs:
    def test_returns_correct_kwargs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert kwargs["model"] == "openai/gpt-4"
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 2048
        assert kwargs["top_p"] == 0.9

    def test_get_litellm_kwargs_injects_bedrock_creds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from openreview_cli.gateway.models import CredentialField

        bedrock_info = ProviderInfo(
            name="bedrock",
            base_url=None,
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
                    label="Key",
                    litellm_param="aws_access_key_id",
                    secret=True,
                    required=True,
                ),
                CredentialField(
                    env_key="AWS_SECRET_ACCESS_KEY",
                    label="Secret",
                    litellm_param="aws_secret_access_key",
                    secret=True,
                    required=True,
                ),
            ],
        )
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: bedrock_info)
        monkeypatch.setenv("AWS_REGION_NAME", "us-east-1")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA_TEST")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret_test")
        try:
            kwargs = gw._get_litellm_kwargs("extraction")
            assert kwargs["aws_region_name"] == "us-east-1"
            assert kwargs["aws_access_key_id"] == "AKIA_TEST"
            assert kwargs["aws_secret_access_key"] == "secret_test"
        finally:
            monkeypatch.delenv("AWS_REGION_NAME", raising=False)
            monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
            monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    def test_get_litellm_kwargs_single_key_no_extra_creds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        openai_info = ProviderInfo(name="openai", base_url=None, credentials=[])
        monkeypatch.setattr(gw, "_resolve_provider_info", lambda slot: openai_info)

        kwargs = gw._get_litellm_kwargs("extraction")

        assert "aws_region_name" not in kwargs
        assert "vertex_project" not in kwargs
        assert "api_key" not in kwargs


class TestExtraParamsPassThrough:
    def test_keys_appear_in_kwargs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert kwargs.get("top_p") == 0.9

    def test_no_extra_params_yields_no_extra_keys(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        kwargs = gw._get_litellm_kwargs("extraction")
        assert "top_p" not in kwargs

    def test_empty_dict_adds_no_keys(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config = COMMON_CONFIG.replace(
            "      extra_params:\n        top_p: 0.9\n", "      extra_params: {}\n"
        )
        gw = _gateway(tmp_path, monkeypatch, config)
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert "top_p" not in kwargs

    def test_nested_values_pass_through(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = COMMON_CONFIG.replace(
            "      extra_params:\n        top_p: 0.9\n",
            "      extra_params:\n        options:\n          mirostat: 2\n",
        )
        gw = _gateway(tmp_path, monkeypatch, config)
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert kwargs.get("options") == {"mirostat": 2}

    def test_extra_params_overrides_standard_params(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = COMMON_CONFIG.replace(
            "      extra_params:\n        top_p: 0.9\n",
            "      extra_params:\n        temperature: 0.1\n",
        )
        gw = _gateway(tmp_path, monkeypatch, config)
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert kwargs["temperature"] == 0.1


class TestExtraParamsProtectedKeys:
    def test_model_key_stripped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config = COMMON_CONFIG.replace(
            "      extra_params:\n        top_p: 0.9\n",
            "      extra_params:\n        model: gpt-5\n",
        )
        gw = _gateway(tmp_path, monkeypatch, config)
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert kwargs["model"] == "openai/gpt-4"

    def test_messages_key_stripped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config = COMMON_CONFIG.replace(
            "      extra_params:\n        top_p: 0.9\n",
            "      extra_params:\n        messages: [bad]\n",
        )
        gw = _gateway(tmp_path, monkeypatch, config)
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert "messages" not in kwargs
        assert kwargs["model"] == "openai/gpt-4"

    def test_input_key_stripped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config = COMMON_CONFIG.replace(
            "      extra_params:\n        top_p: 0.9\n",
            "      extra_params:\n        input: bad\n",
        )
        gw = _gateway(tmp_path, monkeypatch, config)
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert "input" not in kwargs

    def test_timeout_key_stripped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config = COMMON_CONFIG.replace(
            "      extra_params:\n        top_p: 0.9\n",
            "      extra_params:\n        timeout: 999\n",
        )
        gw = _gateway(tmp_path, monkeypatch, config)
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert kwargs.get("timeout", None) != 999

    def test_non_dict_rejected_by_config_validation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pydantic_core import ValidationError as PydanticValidationError

        config = COMMON_CONFIG.replace(
            "      extra_params:\n        top_p: 0.9\n",
            "      extra_params: not_a_dict\n",
        )
        with pytest.raises(PydanticValidationError):
            _gateway(tmp_path, monkeypatch, config)


class TestExtraParamsLogging:
    def test_debug_logged_when_extra_params_applied(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG")
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        gw._get_litellm_kwargs("reasoning")
        assert any("extra_params" in msg and "top_p" in msg for msg in caplog.messages)

    def test_warning_logged_when_protected_key_stripped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("WARNING")
        config = COMMON_CONFIG.replace(
            "      extra_params:\n        top_p: 0.9\n",
            "      extra_params:\n        model: gpt-5\n",
        )
        gw = _gateway(tmp_path, monkeypatch, config)
        gw._get_litellm_kwargs("reasoning")
        assert any("Stripped protected key" in msg and "model" in msg for msg in caplog.messages)


class TestExtraParamsCrossProvider:
    def test_ollama_params_on_openai_does_not_crash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = COMMON_CONFIG.replace(
            "      extra_params:\n        top_p: 0.9\n",
            "      extra_params:\n        num_gpu: 0\n        num_ctx: 4096\n",
        )
        gw = _gateway(tmp_path, monkeypatch, config)
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert kwargs.get("num_gpu") == 0
        assert kwargs.get("num_ctx") == 4096


class TestHealthCheck:
    def test_returns_status_per_slot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config = """\
gateway:
  models:
    reasoning:
      primary: openai/gpt-4
"""
        gw = _gateway(tmp_path, monkeypatch, config, "{}")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = gw.health_check()
        for slot in ("reasoning", "extraction", "grounding"):
            assert slot in result
            assert "status" in result[slot]
        assert result["reasoning"]["status"] == "missing_api_key"

    def test_ollama_keyless_reports_configured(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Local/keyless providers (ollama) must report configured without any key."""
        config = """\
gateway:
  models:
    extraction:
      primary: ollama/qwen3:8b
"""
        gw = _gateway(tmp_path, monkeypatch, config, "{}")
        monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
        result = gw.health_check()
        assert result["extraction"]["status"] == "configured"

    def test_unknown_provider_still_requires_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A provider absent from the registry with no key anywhere must still report missing_api_key."""
        config = """\
gateway:
  models:
    extraction:
      primary: unknownprovider/some-model
"""
        gw = _gateway(tmp_path, monkeypatch, config, "{}")
        monkeypatch.delenv("UNKNOWNPROVIDER_API_KEY", raising=False)
        result = gw.health_check()
        assert result["extraction"]["status"] == "missing_api_key"

    def test_includes_extra_params_count_when_configured(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG, "{}")
        result = gw.health_check()
        assert result["reasoning"].get("extra_params") == 1

    def test_no_extra_params_key_when_not_configured(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG, "{}")
        result = gw.health_check()
        assert "extra_params" not in result["extraction"]

    def test_extra_params_count_with_multiple_keys(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = COMMON_CONFIG.replace(
            "      extra_params:\n        top_p: 0.9\n",
            "      extra_params:\n        num_gpu: 0\n        num_ctx: 4096\n        options:\n          mirostat: 2\n",
        )
        gw = _gateway(tmp_path, monkeypatch, config, "{}")
        result = gw.health_check()
        assert result["reasoning"].get("extra_params") == 3


class TestProviderClassificationTelemetry:
    def _make_gateway(self, monkeypatch: pytest.MonkeyPatch, registry: dict[str, Any]) -> Gateway:
        gw = Gateway.__new__(Gateway)
        gw._config = {"gateway": {"models": {"extraction": {"primary": "ollama/qwen3:8b"}}}}
        gw._cloud_calls_made = 0
        gw._cost_tracker = MagicMock()
        monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
        return gw

    def test_local_provider_resolves_and_no_cloud_count(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = {
            "ollama": ProviderInfo(
                name="ollama",
                is_local=True,
                base_url="http://localhost:11434/v1",
                capabilities=Capability(),
            )
        }
        gw = self._make_gateway(monkeypatch, registry)
        info = gw._resolve_provider_info("extraction")
        assert info is registry["ollama"]
        assert classify_provider(info) == "local"
        if classify_provider(info) == "cloud":
            gw._cloud_calls_made += 1
        assert gw._cloud_calls_made == 0

    def test_local_named_provider_without_base_url_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A provider that is neither flagged local nor ollama, and has no
        base_url, must raise rather than be coerced to "cloud" (fail closed)."""
        registry = {
            "lmstudio": ProviderInfo(
                name="lmstudio", is_local=False, base_url=None, capabilities=Capability()
            )
        }
        gw = self._make_gateway(monkeypatch, registry)
        gw._config["gateway"]["models"]["extraction"]["primary"] = "lmstudio/llama3.1"
        info = gw._resolve_provider_info("extraction")
        assert info is not None
        with pytest.raises(ValueError):
            classify_provider(info)  # must NOT coerce to "cloud"

    def test_ollama_is_local_even_without_base_url(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Decision (#176): ollama is user-run infrastructure and is always local,
        regardless of whether a base_url is set or where it points."""
        registry = {
            "ollama": ProviderInfo(
                name="ollama", is_local=False, base_url=None, capabilities=Capability()
            )
        }
        gw = self._make_gateway(monkeypatch, registry)
        info = gw._resolve_provider_info("extraction")
        assert info is not None
        assert classify_provider(info) == "local"

    def test_cloud_provider_classifies_cloud(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = {
            "deepseek": ProviderInfo(
                name="deepseek",
                base_url="https://api.deepseek.com",
                is_local=False,
                capabilities=Capability(),
            )
        }
        gw = self._make_gateway(monkeypatch, registry)
        gw._config["gateway"]["models"]["extraction"]["primary"] = "deepseek/chat"
        info = gw._resolve_provider_info("extraction")


def test_classify_error_429_names_provider() -> None:
    gw = Gateway.__new__(Gateway)

    class _Fake429Error(Exception):
        status_code = 429

    err = gw._classify_error(_Fake429Error("rate limited"), provider="deepseek")

    assert isinstance(err, RateLimitError)
    assert err.provider == "deepseek"


def test_classify_error_connection_names_provider() -> None:
    gw = Gateway.__new__(Gateway)

    class APIConnectionError(Exception):
        pass

    err = gw._classify_error(APIConnectionError("Connection refused"), provider="openrouter")

    assert isinstance(err, ConnectionError)
    assert err.provider == "openrouter"


def test_classify_error_no_longer_hardcodes_ollama() -> None:
    gw = Gateway.__new__(Gateway)

    class _FakeConnError(Exception):
        def __str__(self) -> str:
            return "Connection refused: timed out"

    err = gw._classify_error(_FakeConnError(), provider="openai")

    assert isinstance(err, ConnectionError)
    assert "Ollama not reachable at localhost:11434" not in str(err)
    assert err.provider == "openai"


def test_strip_empty_content_parts_anthropic() -> None:
    gw = Gateway.__new__(Gateway)
    msgs: list[dict[str, Any]] = [
        {"role": "system", "content": " "},
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "keep"},
        {"role": "user", "content": [{"type": "text", "text": ""}]},
    ]
    out = gw._strip_empty_content_parts(msgs, "anthropic")
    assert [m["role"] for m in out] == ["assistant"]


def test_no_strip_for_other_providers() -> None:
    gw = Gateway.__new__(Gateway)
    msgs = [
        {"role": "system", "content": " "},
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "keep"},
    ]
    out = gw._strip_empty_content_parts(msgs, "openai")
    assert out == msgs


def test_strip_in_chat_path_integrates(monkeypatch: pytest.MonkeyPatch) -> None:
    import types as _types

    monkeypatch.setattr(
        "openreview_cli.gateway.router.load_registry",
        lambda: {
            "anthropic": ProviderInfo(
                name="anthropic",
                base_url="https://api.anthropic.com/v1",
                is_local=False,
                capabilities=Capability(),
            )
        },
    )
    gw = Gateway.__new__(Gateway)
    gw._config = {"gateway": {"models": {"extraction": {"primary": "anthropic/claude-3"}}}}
    gw._data_path = MagicMock()
    gw._cloud_calls_made = 0
    gw._cost_tracker = MagicMock()
    monkeypatch.setattr(gw, "_check_cost_limits", lambda session_id: None)
    monkeypatch.setattr(
        "openreview_cli.prompts.store.PromptStore",
        lambda *a, **k: MagicMock(resolve=lambda slot: None),
    )

    captured: dict[str, Any] = {}

    def _fake_fallback(slot: str, call_fn: Any, call_kwargs: dict[str, Any], **_kw: Any) -> Any:
        captured["messages"] = call_kwargs["messages"]
        return _types.SimpleNamespace(
            choices=[_types.SimpleNamespace(message=_types.SimpleNamespace(content="ok"))]
        )

    monkeypatch.setattr(gw, "_call_with_fallback", _fake_fallback)

    gw.chat("extraction", [{"role": "user", "content": ""}, {"role": "user", "content": "real"}])
    assert [m["content"] for m in captured["messages"]] == ["real"]


def test_classify_error_auth_names_provider() -> None:
    class _FakeExcError(Exception):
        status_code = 401

    gw = Gateway.__new__(Gateway)
    err = gw._classify_error(_FakeExcError("unauthorized"), "anthropic")
    assert isinstance(err, AuthError)
    assert err.provider == "anthropic"


def test_classify_error_model_not_found_names_provider() -> None:
    class _FakeExcError(Exception):
        status_code = 404

    gw = Gateway.__new__(Gateway)
    err = gw._classify_error(_FakeExcError("not found"), "openrouter")
    assert isinstance(err, ModelNotFoundError)
    assert err.provider == "openrouter"


def test_auth_error_has_provider_attr() -> None:
    err = AuthError("anthropic", "x")
    assert err.provider == "anthropic"
    assert "auth failed for anthropic" in str(err)


def test_model_not_found_error_has_provider_attr() -> None:
    err = ModelNotFoundError("openai", "y")
    assert err.provider == "openai"
    assert "model not found for openai" in str(err)


def test_strip_empty_content_parts_all_empty() -> None:
    gw = Gateway.__new__(Gateway)
    out = gw._strip_empty_content_parts([{"role": "user", "content": ""}], "anthropic")
    assert out == []


def test_strip_all_empty_raises_empty_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "openreview_cli.gateway.router.load_registry",
        lambda: {
            "anthropic": ProviderInfo(
                name="anthropic",
                base_url="https://api.anthropic.com/v1",
                is_local=False,
                capabilities=Capability(),
            )
        },
    )
    gw = Gateway.__new__(Gateway)
    gw._config = {"gateway": {"models": {"extraction": {"primary": "anthropic/claude-3"}}}}
    gw._data_path = MagicMock()
    gw._cloud_calls_made = 0
    gw._cost_tracker = MagicMock()
    gw._check_cost_limits = lambda session_id: None  # type: ignore[method-assign]
    monkeypatch.setattr(
        "openreview_cli.prompts.store.PromptStore",
        lambda *a, **k: MagicMock(resolve=lambda slot: None),
    )
    gw._record_cloud_call = lambda *a, **k: None  # type: ignore[method-assign]

    called: dict[str, Any] = {}

    def _fake_fallback(slot: str, call_fn: Any, call_kwargs: dict[str, Any], **_kw: Any) -> Any:
        called["reached"] = True
        return None

    gw._call_with_fallback = _fake_fallback  # type: ignore[method-assign]

    with pytest.raises(EmptyMessagesError):
        gw.chat("extraction", [{"role": "user", "content": ""}], session_id=None)
    assert "reached" not in called


# --- FR-6 / US6: Phase 8 streaming with dual timeouts (T023/T024/T025) ---

import http.server
import socketserver
import threading
import time

import httpx

from openreview_cli.gateway.models import StreamingOutputEvent
from tests.helpers.stream_doubles import StreamChunk, TerminatedStream, TruncatedStream


def _build_gw() -> Gateway:
    gw = Gateway.__new__(Gateway)
    gw._config = {"gateway": {"models": {"extraction": {"primary": "anthropic/claude-3"}}}}
    gw._data_path = MagicMock()
    gw._cloud_calls_made = 0
    gw._cost_tracker = MagicMock()
    gw._check_cost_limits = lambda *a, **k: None  # type: ignore[method-assign]
    return gw


def test_chat_stream_survives_cost_logging_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """T030 replica for streaming: cost-logging raise must not kill stream."""
    stream = TerminatedStream([StreamChunk("Hello"), StreamChunk(" world")])
    monkeypatch.setattr("openreview_cli.gateway.router.completion", lambda **kwargs: stream)
    monkeypatch.setattr(
        "openreview_cli.prompts.store.PromptStore",
        MagicMock(resolve=lambda *a, **k: None),
    )

    gw = _build_gw()

    def _boom(*args: object, **kwargs: object) -> str:
        raise RuntimeError("cost log exploded")

    gw._cost_tracker.log_call = _boom  # type: ignore[method-assign]

    events = list(gw.chat_stream("extraction", [{"role": "user", "content": "hi"}]))
    # the row is now written on the post-terminal path, so `done` only follows a
    # cost-logging attempt that survived the raise above.
    assert events == [
        StreamingOutputEvent(type="chunk", text="Hello"),
        StreamingOutputEvent(type="chunk", text=" world"),
        StreamingOutputEvent(type="done"),
    ]


def test_chat_stream_yields_chunks_and_done(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = TerminatedStream([StreamChunk("Hello"), StreamChunk(" world")])
    monkeypatch.setattr("openreview_cli.gateway.router.completion", lambda **kwargs: stream)
    monkeypatch.setattr(
        "openreview_cli.prompts.store.PromptStore",
        MagicMock(resolve=lambda *a, **k: None),
    )

    gw = _build_gw()
    events = list(gw.chat_stream("extraction", [{"role": "user", "content": "hi"}]))

    assert events == [
        StreamingOutputEvent(type="chunk", text="Hello"),
        StreamingOutputEvent(type="chunk", text=" world"),
        StreamingOutputEvent(type="done"),
    ]


def test_stream_timeout_is_dual_not_single(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_completion(**kwargs: Any) -> Any:
        captured["timeout"] = kwargs.get("timeout")
        return TruncatedStream([])

    monkeypatch.setattr("openreview_cli.gateway.router.completion", fake_completion)
    monkeypatch.setattr(
        "openreview_cli.prompts.store.PromptStore",
        MagicMock(resolve=lambda *a, **k: None),
    )

    gw = _build_gw()
    with pytest.raises(ConnectionError):
        list(gw.chat_stream("extraction", [{"role": "user", "content": "hi"}]))

    t = captured["timeout"]
    assert isinstance(t, httpx.Timeout)
    assert t.connect == 15.0
    assert t.read == 45.0


def test_iter_stream_raises_for_a_stream_with_no_terminal_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unterminated stream is a typed connection error naming the provider."""
    stream = TruncatedStream([StreamChunk("a"), StreamChunk("b")])
    monkeypatch.setattr("openreview_cli.gateway.router.completion", lambda **kwargs: stream)
    monkeypatch.setattr(
        "openreview_cli.prompts.store.PromptStore",
        MagicMock(resolve=lambda *a, **k: None),
    )

    gw = _build_gw()
    with pytest.raises(ConnectionError) as exc:
        list(gw.chat_stream("extraction", [{"role": "user", "content": "hi"}]))
    assert "anthropic" in str(exc.value)


def test_a_truncated_stream_writes_no_cost_row_and_a_terminal_one_writes_exactly_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Socket-free twin of the chaos node: only a completed drain books a cost row."""
    monkeypatch.setattr(
        "openreview_cli.prompts.store.PromptStore",
        MagicMock(resolve=lambda *a, **k: None),
    )

    terminal = TerminatedStream([StreamChunk("Hello"), StreamChunk(" world")])
    monkeypatch.setattr("openreview_cli.gateway.router.completion", lambda **kwargs: terminal)
    gw = _build_gw()
    log_call = MagicMock()
    gw._cost_tracker.log_call = log_call  # type: ignore[method-assign]

    events = list(gw.chat_stream("extraction", [{"role": "user", "content": "hi"}]))
    assert log_call.call_count == 1
    assert events[-1] == StreamingOutputEvent(type="done")

    truncated = TruncatedStream([StreamChunk("a"), StreamChunk("b")])
    monkeypatch.setattr("openreview_cli.gateway.router.completion", lambda **kwargs: truncated)
    gw2 = _build_gw()
    log_call2 = MagicMock()
    gw2._cost_tracker.log_call = log_call2  # type: ignore[method-assign]

    with pytest.raises(ConnectionError):
        list(gw2.chat_stream("extraction", [{"role": "user", "content": "hi"}]))
    log_call2.assert_not_called()


@pytest.mark.timeout(75)
@pytest.mark.enable_socket  # local ThreadingTCPServer on 127.0.0.1, no internet
def test_stream_idle_timeout_cuts_stalled_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    STALL_BODY = (
        b'data: {"id":"x","object":"chat.completion.chunk",'
        b'"choices":[{"index":0,"delta":{"content":"hi"},'
        b'"finish_reason":null}]}\n\n'
    )

    class _Handler(http.server.BaseHTTPRequestHandler):
        def _stall(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            self.wfile.write(STALL_BODY)
            self.wfile.flush()
            time.sleep(50)  # >45s idle timeout; must be cut off before this

        def do_POST(self) -> None:
            self._stall()

        def do_GET(self) -> None:
            self._stall()

        def log_message(self, *args: Any, **kwargs: Any) -> None:  # silence test noise
            pass

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    gw = Gateway.__new__(Gateway)
    gw._config = {"gateway": {"models": {"extraction": {"primary": "openai/test-model"}}}}
    gw._data_path = MagicMock()
    gw._cloud_calls_made = 0
    gw._cost_tracker = MagicMock()
    gw._check_cost_limits = lambda *a, **k: None  # type: ignore[method-assign]
    gw._record_cloud_call = lambda *a, **k: None  # type: ignore[method-assign]

    monkeypatch.setattr(
        "openreview_cli.prompts.store.PromptStore",
        MagicMock(resolve=lambda *a, **k: None),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")
    monkeypatch.setattr(
        "openreview_cli.gateway.router.load_registry",
        lambda: {
            "openai": ProviderInfo(
                name="openai",
                base_url=f"http://127.0.0.1:{port}/v1",
                is_local=True,
                capabilities=Capability(),
            )
        },
    )

    events: list[StreamingOutputEvent] = []
    start = time.monotonic()
    try:
        with pytest.raises(Exception) as excinfo:
            for ev in gw.chat_stream("extraction", [{"role": "user", "content": "hi"}]):
                events.append(ev)
        elapsed = time.monotonic() - start
    finally:
        # Stop accepting new connections; the handler thread is daemon and
        # will exit at process end (it is mid-sleep and cannot be joined).
        httpd.shutdown()

    assert elapsed >= 40.0, f"idle timeout did not wait: elapsed={elapsed}"
    assert elapsed < 70.0, f"idle timeout not enforced: elapsed={elapsed}"
    assert (
        isinstance(excinfo.value, ConnectionError)
        or "timeout" in str(excinfo.value).lower()
        or "read" in str(excinfo.value).lower()
    )


class TestCustomProviderRouting:
    """Custom OpenAI-compatible providers must route via litellm's openai
    provider with api_base + key injected, and NOT be rewritten if bundled."""

    def test_custom_provider_routed_as_openai_with_api_base_and_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = {
            "scenariofoo": ProviderInfo(
                name="scenariofoo",
                base_url="https://api.scenariofoo.example/v1",
                is_local=False,
                source="custom",
                capabilities=Capability(),
                env_key="SCENARIOFOO_API_KEY",
            )
        }
        gw = Gateway.__new__(Gateway)
        gw._auth = {"scenariofoo": "fake-key-123"}
        gw._config = {"gateway": {"models": {"extraction": {"primary": "scenariofoo/some-model"}}}}
        monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)

        kw = gw._get_litellm_kwargs("extraction")

        assert kw["model"] == "openai/some-model"
        assert kw["api_base"] == "https://api.scenariofoo.example/v1"
        assert kw["api_key"] == "fake-key-123"

    def test_custom_provider_key_resolved_from_env_not_auth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Custom provider key lives ONLY in the env var (not auth.json)."""
        registry = {
            "scenariofoo": ProviderInfo(
                name="scenariofoo",
                base_url="https://api.scenariofoo.example/v1",
                is_local=False,
                source="custom",
                capabilities=Capability(),
                env_key="SCENARIOFOO_API_KEY",
            )
        }
        gw = Gateway.__new__(Gateway)
        gw._auth = {}  # no key in auth.json
        gw._config = {"gateway": {"models": {"extraction": {"primary": "scenariofoo/some-model"}}}}
        monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
        monkeypatch.setenv("SCENARIOFOO_API_KEY", "env-key-xyz")

        kw = gw._get_litellm_kwargs("extraction")

        assert kw["model"] == "openai/some-model"
        assert kw["api_key"] == "env-key-xyz"  # resolved from env, not auth.json

    def test_bundled_provider_not_rewritten(self, monkeypatch: pytest.MonkeyPatch) -> None:
        registry = {
            "openai": ProviderInfo(
                name="openai",
                base_url="https://api.openai.com/v1",
                is_local=False,
                source="bundled",
                capabilities=Capability(),
            )
        }
        gw = Gateway.__new__(Gateway)
        gw._auth = {"openai": "real-key"}
        gw._config = {"gateway": {"models": {"extraction": {"primary": "openai/gpt-4"}}}}
        monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)

        kw = gw._get_litellm_kwargs("extraction")

        assert kw["model"] == "openai/gpt-4"
        assert "api_key" not in kw

    def test_health_check_custom_provider_env_key_shows_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Custom provider key lives ONLY in env; must report configured."""
        registry = {
            "scenariofoo": ProviderInfo(
                name="scenariofoo",
                base_url="https://api.scenariofoo.example/v1",
                is_local=False,
                source="custom",
                capabilities=Capability(),
                env_key="SCENARIOFOO_API_KEY",
            )
        }
        gw = Gateway.__new__(Gateway)
        gw._auth = {}  # no key in auth.json
        gw._config = {"gateway": {"models": {"extraction": {"primary": "scenariofoo/some-model"}}}}
        monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
        monkeypatch.setenv("SCENARIOFOO_API_KEY", "fake")

        result = gw.health_check()

        assert result["extraction"]["status"] == "configured"

    def test_health_check_custom_provider_no_key_shows_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Custom provider with no key anywhere must report missing_api_key."""
        registry = {
            "scenariofoo": ProviderInfo(
                name="scenariofoo",
                base_url="https://api.scenariofoo.example/v1",
                is_local=False,
                source="custom",
                capabilities=Capability(),
                env_key="SCENARIOFOO_API_KEY",
            )
        }
        gw = Gateway.__new__(Gateway)
        gw._auth = {}
        gw._config = {"gateway": {"models": {"extraction": {"primary": "scenariofoo/some-model"}}}}
        monkeypatch.setattr("openreview_cli.gateway.router.load_registry", lambda: registry)
        monkeypatch.delenv("SCENARIOFOO_API_KEY", raising=False)

        result = gw.health_check()

        assert result["extraction"]["status"] == "missing_api_key"


def _config_with(
    primary: str,
    *,
    slot: str = "reasoning",
    fallback: str = "anthropic/claude-3",
    extra_params: dict[str, Any] | None = None,
) -> str:
    """A one-slot config: `slot` declares `primary`, `fallback` and `extra_params`.

    ``extra_params`` defaults to what the shipped config declares for the grounding
    slot (``config/loader.py``) — a JSON ``response_format``, the local-only key the
    gate tests observe at the dispatch seam — so ``slot="grounding"`` reproduces
    that shipped slot. Every other slot and key comes from the config defaults.
    """
    if extra_params is None:
        extra_params = {"response_format": {"type": "json_object"}}
    return (
        "privacy:\n"
        "  tier: performance\n"
        "gateway:\n"
        "  models:\n"
        f"    {slot}:\n"
        f"      primary: {primary}\n"
        f"      fallback: {fallback}\n"
        "      params:\n"
        "        temperature: 0.0\n"
        "        max_tokens: 1024\n"
        f"      extra_params: {json.dumps(extra_params)}\n"
        "  fallback:\n"
        "    retries: 2\n"
        "    retry_delay: 0.01\n"
        "    timeout: 5\n"
    )


def _capture_dispatches(
    monkeypatch: pytest.MonkeyPatch, *, failures_before_success: int = 0
) -> list[dict[str, Any]]:
    """Patch ``router.completion`` to record the kwargs each dispatch received.

    The gate runs at DISPATCH time, so a test must observe the kwargs at the
    litellm seam — a dict that is never dispatched hides an override leak.
    """
    import openreview_cli.gateway.router as router_mod

    seen: list[dict[str, Any]] = []

    def stub(**kwargs: Any) -> _MockCompletionResponse:
        seen.append(dict(kwargs))
        # `gateway.fallback.retries` is 2 in the configs here, so the primary is
        # attempted three times before the fallback is dispatched.
        if len(seen) <= failures_before_success:
            raise RuntimeError("primary unavailable")
        return _MockCompletionResponse("from fallback" if failures_before_success else "ok")

    monkeypatch.setattr(router_mod, "completion", stub)
    return seen


class TestLocalOnlyExtraParams:
    """`response_format` is a local-only hint; a cloud provider must never see it.

    An unsupported parameter raises in litellm rather than being dropped, so a
    leak here turns a degraded parse into a hard failure. The gate is enforced
    for the provider ACTUALLY dispatched, so these tests assert on the kwargs
    captured at the ``completion`` seam, never on ``_get_litellm_kwargs`` — a
    build-time dict a dispatch-time ``model=`` override can still rewrite.
    """

    JSON = {"type": "json_object"}

    def test_forwarded_to_a_local_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = _capture_dispatches(monkeypatch)
        gw = _gateway(tmp_path, monkeypatch, _config_with("ollama/granite4:3b"))
        assert gw.chat("reasoning", [{"role": "user", "content": "Hi"}]) == "ok"
        assert seen[0]["response_format"] == {"type": "json_object"}

    def test_dropped_for_a_cloud_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = _capture_dispatches(monkeypatch)
        gw = _gateway(tmp_path, monkeypatch, _config_with("openai/gpt-4"))
        gw.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert "response_format" not in seen[0]

    def test_dropped_for_an_unknown_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = _capture_dispatches(monkeypatch)
        gw = _gateway(tmp_path, monkeypatch, _config_with("nosuchprovider/model-x"))
        gw.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert "response_format" not in seen[0]

    def test_a_cloud_fallback_does_not_receive_the_param(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = _capture_dispatches(monkeypatch, failures_before_success=3)
        gw = _gateway(tmp_path, monkeypatch, _config_with("ollama/granite4:3b"))
        assert gw.chat("reasoning", [{"role": "user", "content": "Hi"}]) == "from fallback"
        assert seen[0]["response_format"] == {"type": "json_object"}
        assert "response_format" not in seen[-1]

    def test_a_local_fallback_still_receives_the_param(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A guard, not a fail-first test: the strip must not over-reach."""
        seen = _capture_dispatches(monkeypatch, failures_before_success=3)
        cfg = _config_with("ollama/granite4:3b", fallback="ollama/granite4:3b")
        gw = _gateway(tmp_path, monkeypatch, cfg)
        assert gw.chat("reasoning", [{"role": "user", "content": "Hi"}]) == "from fallback"
        assert seen[-1]["response_format"] == {"type": "json_object"}

    def test_a_model_override_to_cloud_carries_no_param(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The leak: a dispatch-time `model=` override to a cloud provider.

        The kwargs were built for the slot's local primary (so the key is
        present), then the override rewrote `model=`. The gate must follow the
        provider that actually receives the call.
        """
        seen = _capture_dispatches(monkeypatch)
        gw = _gateway(tmp_path, monkeypatch, _config_with("ollama/granite4:3b", slot="grounding"))
        gw.chat("grounding", [{"role": "user", "content": "Hi"}], model="openai/gpt-4")
        assert seen[0]["model"] == "openai/gpt-4"
        assert "response_format" not in seen[0]

    def test_a_caller_supplied_param_is_dropped_for_cloud(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A caller kwarg bypasses the slot's extra_params entirely."""
        seen = _capture_dispatches(monkeypatch)
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)  # reasoning: openai/gpt-4
        gw.chat(
            "reasoning",
            [{"role": "user", "content": "Hi"}],
            response_format={"type": "json_object"},
        )
        assert "response_format" not in seen[0]
        # Other extra_params must still reach a cloud provider untouched.
        assert seen[0]["top_p"] == 0.9

    def test_a_local_fallback_is_restored_for_a_cloud_primary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The starvation: the build-time strip never restores the local value."""
        seen = _capture_dispatches(monkeypatch, failures_before_success=3)
        cfg = _config_with("openai/gpt-4", slot="grounding", fallback="ollama/granite4:3b")
        gw = _gateway(tmp_path, monkeypatch, cfg)
        assert gw.chat("grounding", [{"role": "user", "content": "Hi"}]) == "from fallback"
        assert all("response_format" not in k for k in seen[:3])
        assert seen[-1]["response_format"] == {"type": "json_object"}

    def test_stream_drops_the_param_for_a_model_override_to_cloud(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`chat_stream` shares the dispatch seam, so case 1 must hold there too."""
        from tests.helpers.stream_doubles import StreamChunk, TerminatedStream

        seen: list[dict[str, Any]] = []

        def stub(**kwargs: Any) -> TerminatedStream:
            seen.append(dict(kwargs))
            return TerminatedStream([StreamChunk("hi")])

        monkeypatch.setattr("openreview_cli.gateway.router.completion", stub)
        gw = _gateway(tmp_path, monkeypatch, _config_with("ollama/granite4:3b", slot="grounding"))
        events = list(
            gw.chat_stream("grounding", [{"role": "user", "content": "Hi"}], model="openai/gpt-4")
        )
        assert [e.type for e in events] == ["chunk", "done"]
        assert seen[0]["model"] == "openai/gpt-4"
        assert "response_format" not in seen[0]
