from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from openreview_cli.gateway.errors import (
    AllProvidersFailedError,
    AuthError,
    CapabilityMismatchError,
    ConnectionError,
    EmptyMessagesError,
    ModelNotFoundError,
    RateLimitError,
    SlotNotConfiguredError,
)
from openreview_cli.gateway.models import Capability, CapabilityRequirement, ProviderInfo
from openreview_cli.gateway.router import Gateway, classify_provider


class _MockMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _MockChoice:
    def __init__(self, content: str) -> None:
        self.message = _MockMessage(content)


class _MockCompletionResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_MockChoice(content)]


class _MockEmbeddingResponse:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _MockRerankResponse:
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results


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

    def test_raises_all_providers_failed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import openreview_cli.gateway.router as router_mod

        def always_fail(**kw: Any) -> Any:
            raise RuntimeError("always fails")

        monkeypatch.setattr(router_mod, "completion", always_fail)
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        with pytest.raises(AllProvidersFailedError):
            gw.chat("reasoning", [{"role": "user", "content": "Hi"}])


class TestEmbed:
    def test_returns_vectors(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import openreview_cli.gateway.router as router_mod

        monkeypatch.setattr(
            router_mod,
            "embedding",
            lambda **kw: _MockEmbeddingResponse(
                [{"embedding": [0.1, 0.2, 0.3]}, {"embedding": [0.4, 0.5, 0.6]}]
            ),
        )
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        result = gw.embed("embedding", ["hello", "world"])
        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


class TestRerank:
    def test_returns_ranked_results(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import litellm

        monkeypatch.setattr(
            litellm,
            "rerank",
            lambda **kw: _MockRerankResponse(
                [{"index": 1, "relevance_score": 0.95}, {"index": 0, "relevance_score": 0.85}]
            ),
        )
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        result = gw.rerank("reranking", "test query", ["doc a", "doc b"])
        assert result == [
            {"index": 1, "relevance_score": 0.95},
            {"index": 0, "relevance_score": 0.85},
        ]

    def test_rerank_error_names_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import litellm

        def _boom(**kw: object) -> object:
            raise RuntimeError("connection refused")

        monkeypatch.setattr(litellm, "rerank", _boom)
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        with pytest.raises(Exception) as exc_info:
            gw.rerank("reranking", "test query", ["doc a", "doc b"])
        assert getattr(exc_info.value, "provider", None) == "cohere"


class TestGetLitellmKwargs:
    def test_returns_correct_kwargs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        gw = _gateway(tmp_path, monkeypatch, COMMON_CONFIG)
        kwargs = gw._get_litellm_kwargs("reasoning")
        assert kwargs["model"] == "openai/gpt-4"
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 2048
        assert kwargs["top_p"] == 0.9


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
        for slot in ("reasoning", "extraction", "embedding", "reranking", "graph"):
            assert slot in result
            assert "status" in result[slot]
        assert result["reasoning"]["status"] == "missing_api_key"

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
        registry = {
            "ollama": ProviderInfo(
                name="ollama", is_local=False, base_url=None, capabilities=Capability()
            )
        }
        gw = self._make_gateway(monkeypatch, registry)
        info = gw._resolve_provider_info("extraction")
        assert info is not None
        with pytest.raises(ValueError):
            classify_provider(info)  # must NOT coerce to "cloud"

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


def test_embedding_slot_chat_only_model_raises_pre_network() -> None:
    """FR-4: capability gate fires BEFORE any network call.

    A model declared without embedding capability, configured on the
    embedding slot, must raise CapabilityMismatchError and must NOT reach
    the litellm embedding call.
    """
    from unittest.mock import MagicMock

    import openreview_cli.gateway.router as router_mod

    # Embedding mock that would prove network happened if reached.
    embedding_mock = MagicMock(side_effect=AssertionError("network called"))

    gw = Gateway.__new__(Gateway)
    gw._config = {
        "gateway": {"models": {"embedding": {"primary": "openai/text-embedding-3-small"}}}
    }
    gw._cloud_calls_made = 0
    gw._cost_tracker = MagicMock()

    registry = {
        "openai": ProviderInfo(
            name="openai",
            base_url="https://api.openai.com/v1",
            is_local=False,
            capabilities=Capability(
                embedding=False, reasoning=True, context_window=8192, tool_call=False
            ),
        )
    }

    with (
        pytest.MonkeyPatch().context() as mp,
    ):
        mp.setattr(router_mod, "load_registry", lambda: registry)
        mp.setattr(router_mod, "embedding", embedding_mock)
        with pytest.raises(CapabilityMismatchError):
            gw.embed(
                "embedding",
                ["hello"],
                requirement=CapabilityRequirement(capability="embedding"),
            )

    # Gate must raise before the network call is ever made.
    embedding_mock.assert_not_called()


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

    def _fake_fallback(slot: str, call_fn: Any, call_kwargs: dict[str, Any]) -> Any:
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

    def _fake_fallback(slot: str, call_fn: Any, call_kwargs: dict[str, Any]) -> Any:
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
import types

import httpx

from openreview_cli.gateway.models import StreamingOutputEvent


def _make_chunk(content: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content=content))]
    )


def _build_gw() -> Gateway:
    gw = Gateway.__new__(Gateway)
    gw._config = {"gateway": {"models": {"extraction": {"primary": "anthropic/claude-3"}}}}
    gw._data_path = MagicMock()
    gw._cloud_calls_made = 0
    gw._cost_tracker = MagicMock()
    gw._check_cost_limits = lambda *a, **k: None  # type: ignore[method-assign]
    return gw


def test_chat_stream_yields_chunks_and_done(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = [_make_chunk("Hello"), _make_chunk(" world")]
    monkeypatch.setattr("openreview_cli.gateway.router.completion", lambda **kwargs: iter(chunks))
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
        return iter([])

    monkeypatch.setattr("openreview_cli.gateway.router.completion", fake_completion)
    monkeypatch.setattr(
        "openreview_cli.prompts.store.PromptStore",
        MagicMock(resolve=lambda *a, **k: None),
    )

    gw = _build_gw()
    list(gw.chat_stream("extraction", [{"role": "user", "content": "hi"}]))

    t = captured["timeout"]
    assert isinstance(t, httpx.Timeout)
    assert t.connect == 15.0
    assert t.read == 45.0


@pytest.mark.timeout(75)
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
