from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx
import litellm

if TYPE_CHECKING:
    from pathlib import Path

from litellm import completion, embedding

from openreview_cli.config.auth import key_to_env, load_auth
from openreview_cli.config.loader import load_config
from openreview_cli.config.paths import get_config_dir, get_data_dir
from openreview_cli.gateway.cost import CostTracker
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
from openreview_cli.gateway.models import (
    CapabilityRequirement,
    PrivacyTierReport,
    ProviderInfo,
    StreamingOutputEvent,
)
from openreview_cli.gateway.redaction import RedactingFilter, redact_key
from openreview_cli.gateway.registry import load_registry
from openreview_cli.slots import VALID_SLOTS
from openreview_cli.storage.costs import check_daily_limit, check_session_limit

logger = logging.getLogger(__name__)

# Track env vars seeded across all Gateway instances so long-lived
# processes (TUI) can clean them up without holding a Gateway reference.
_env_vars_seeded: set[str] = set()


def clear_seeded_env_vars() -> None:
    """Remove env vars seeded by any Gateway instance. User-owned vars untouched."""
    for name in list(_env_vars_seeded):
        os.environ.pop(name, None)
    _env_vars_seeded.clear()


def classify_provider(model: ProviderInfo) -> str:
    """Return "local" if the provider runs locally, else "cloud"."""
    if model.is_local:
        return "local"
    if model.base_url:
        try:
            host = urlparse(model.base_url).hostname or ""
        except Exception as exc:  # pragma: no cover - urlparse is robust
            raise ValueError(f"cannot classify provider {model.name!r}: {exc}") from exc
        if host in ("localhost", "127.0.0.1"):
            return "local"
        return "cloud"
    raise ValueError(f"cannot classify provider {model.name!r}: no base_url and not local")


_PROTECTED_KEYS = frozenset({"model", "messages", "input", "timeout"})
# Providers with known format quirks that reject empty content parts.
STRIP_EMPTY_CONTENT_PROVIDERS: frozenset[str] = frozenset({"anthropic"})

# FR-6: dual timeouts for streaming — 15s connect/header, 45s idle between chunks.
STREAM_CONNECT_TIMEOUT = 15.0
STREAM_READ_TIMEOUT = 45.0


def _is_empty_parts(parts: list[dict[str, Any]]) -> bool:
    if len(parts) == 0:
        return True
    for part in parts:
        if isinstance(part, dict) and part.get("type") == "text":
            if (part.get("text") or "").strip() != "":
                return False
        else:
            return False
    return True


_PRIMARY_ONLY_SLOTS = frozenset({"embedding", "reranking"})
_SLOT_METHOD_MAP: dict[str, str] = {
    "reasoning": "chat",
    "extraction": "chat",
    "embedding": "embed",
    "reranking": "rerank",
    "graph": "chat",
    "grounding": "chat",
}
_REDACT_PATTERNS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "COHERE_API_KEY",
    "HUGGINGFACE_API_KEY",
    "CUSTOM_API_KEY",
    "sk-",
    "sk-ant-",
]


class Gateway:
    def __init__(
        self,
        config_path: Path | None = None,
        auth_path: Path | None = None,
        data_path: Path | None = None,
    ) -> None:
        self._config_path = config_path or (get_config_dir() / "config.yml")
        self._auth_path = auth_path or (get_config_dir() / "auth.json")
        self._data_path = data_path or (get_data_dir() / "openreview.db")
        self._config = load_config(self._config_path)
        self._auth = load_auth(self._auth_path)
        self._cost_tracker = CostTracker(self._data_path)
        self._cloud_calls_made = 0

        _filter = RedactingFilter(_REDACT_PATTERNS)
        logging.getLogger().addFilter(_filter)

        # Track env vars seeded by this instance so user-owned vars survive cleanup.
        self._env_seeded: list[str] = []
        self._set_env_vars()

    def validate_capability(self, model: ProviderInfo, req: CapabilityRequirement) -> None:
        """Raise CapabilityMismatchError before any network call if unmet."""
        caps = model.capabilities
        if req.capability is not None and getattr(caps, req.capability) is not True:
            raise CapabilityMismatchError(model.name, f"requires capability '{req.capability}'")
        if req.min_context_window is not None:
            cw = caps.context_window
            if cw is None or cw < req.min_context_window:
                raise CapabilityMismatchError(
                    model.name,
                    f"context_window {cw} < required {req.min_context_window}",
                )
        if req.tool_call is True and caps.tool_call is not True:
            raise CapabilityMismatchError(model.name, "requires tool_call support")

    def _set_env_vars(self) -> None:
        for provider, creds in self._auth.items():
            if isinstance(creds, str):
                env_name = key_to_env(provider)
                if env_name and creds and env_name not in os.environ:
                    os.environ[env_name] = creds
                    self._env_seeded.append(env_name)
                    _env_vars_seeded.add(env_name)
                    logger.debug("Set %s to %s", env_name, redact_key(creds))
            elif isinstance(creds, dict):
                for env_key, val in creds.items():
                    if env_key and val and env_key not in os.environ:
                        os.environ[env_key] = val
                        self._env_seeded.append(env_key)
                        _env_vars_seeded.add(env_key)

    def clear_env_vars(self) -> None:
        """Remove only the env vars this instance seeded. User-owned vars untouched."""
        for name in self._env_seeded:
            os.environ.pop(name, None)
        self._env_seeded.clear()

    def _get_slot_config(self, slot: str) -> dict[str, Any]:
        models = self._config.get("gateway", {}).get("models", {})
        cfg: dict[str, Any] | None = models.get(slot)
        if not cfg:
            raise SlotNotConfiguredError(f"No model configured for slot '{slot}'")
        primary = cfg.get("primary")
        if not primary:
            raise SlotNotConfiguredError(f"Slot '{slot}' has no primary model")
        return cfg

    def _resolve_provider_info(self, slot: str) -> ProviderInfo | None:
        cfg = self._get_slot_config(slot)
        provider = cfg["primary"].split("/")[0]
        registry = load_registry()  # new registry source, not ModelRegistry.load()
        return registry.get(provider)

    def _apply_provider_credentials(self, info: ProviderInfo, kwargs: dict[str, Any]) -> None:
        """Map each declared CredentialField to its litellm kwarg.

        Resolution order: environment variable, then auth.json per-provider
        mapping ({provider: {env_key: value}}). Exact litellm param names come
        from each field's litellm_param (verified via Context7).
        """
        for field in info.credentials:
            value = os.environ.get(field.env_key)
            if value is None:
                stored = self._auth.get(info.name)
                if isinstance(stored, dict):
                    value = stored.get(field.env_key)
            if value is not None:
                kwargs[field.litellm_param] = value

    def _get_litellm_kwargs(self, slot: str) -> dict[str, Any]:
        cfg = self._get_slot_config(slot)
        kwargs: dict[str, Any] = {"model": cfg["primary"]}
        params = cfg.get("params")
        if params and isinstance(params, dict):
            if "temperature" in params:
                kwargs["temperature"] = params["temperature"]
            if "max_tokens" in params:
                kwargs["max_tokens"] = params["max_tokens"]
        extra = cfg.get("extra_params")
        if extra and isinstance(extra, dict):
            stripped = {k: v for k, v in extra.items() if k not in _PROTECTED_KEYS}
            protected_stripped = extra.keys() - stripped.keys()
            if protected_stripped:
                logger.warning(
                    "Stripped protected key(s) from extra_params: %s", protected_stripped
                )
            if stripped:
                logger.debug("Applying extra_params: %s", list(stripped.keys()))
            kwargs.update(stripped)
        # T008: populate api_base from real provider config for reachability
        info = self._resolve_provider_info(slot)
        if info is not None and info.base_url:
            kwargs["api_base"] = info.base_url
        # spec 034: map each declared credential field to its litellm kwarg.
        if info is not None and info.credentials:
            self._apply_provider_credentials(info, kwargs)
        # Custom OpenAI-compatible provider: litellm does not recognize the
        # provider prefix, so route via its openai provider with api_base set
        # above and inject the resolved key (litellm would otherwise look for
        # OPENAI_API_KEY). Bundled providers keep their real prefix.
        if info is not None and info.source == "custom" and info.base_url:
            original = kwargs["model"]
            model_only = original.split("/", 1)[1] if "/" in original else original
            kwargs["model"] = f"openai/{model_only}"
            key = (os.environ.get(info.env_key) if info.env_key else None) or self._auth.get(
                info.name
            )
            if key:
                kwargs["api_key"] = key
        return kwargs

    def _check_cost_limits(self, session_id: str | None) -> None:
        limits = self._config.get("gateway", {}).get("cost_limits", {})
        daily_cents = limits.get("daily_cents")
        per_review_cents = limits.get("per_review_cents")

        try:
            if daily_cents is not None and not check_daily_limit(self._data_path, daily_cents):
                logger.warning("Daily cost limit of %d¢ would be exceeded", daily_cents)
        except Exception:
            logger.warning("Failed to check daily cost limit", exc_info=True)

        if session_id and per_review_cents is not None:
            try:
                if not check_session_limit(self._data_path, session_id, per_review_cents):
                    logger.warning(
                        "Session cost limit of %d¢ would be exceeded for session %s",
                        per_review_cents,
                        session_id,
                    )
            except Exception:
                logger.warning("Failed to check session limit", exc_info=True)

    def _classify_error(self, exc: Exception, provider: str | None = None) -> Exception:
        msg = str(exc).lower()
        exc_type = type(exc).__name__.lower()
        status = getattr(exc, "status_code", None)

        # Best-effort OpenRouter error_type read (do not over-engineer).
        error_type = ""
        resp = getattr(exc, "response", None)
        if resp is not None and hasattr(resp, "json"):
            try:
                payload = resp.json()
                error_type = (payload.get("error", {}).get("error_type", "") or "").lower()
            except Exception:
                error_type = ""

        conn_indicators = {
            "connectionerror",
            "connecterror",
            "connection refused",
            "connection reset",
        }
        auth_indicators = {
            "auth",
            "401",
            "403",
            "unauthorized",
            "invalid api key",
            "api key expired",
        }
        rate_indicators = {
            "rate limit",
            "ratelimit",
            "429",
            "too many requests",
        }
        model_indicators = {"not found", "model_not_found", "404", "not_found"}

        def _prefix(s: str) -> str:
            return f"[{provider}] {s}" if provider is not None else s

        if (
            status == 401
            or error_type == "authentication"
            or any(i in msg for i in auth_indicators)
        ):
            return AuthError(provider or "unknown", str(exc))
        if status == 429 or error_type == "rate_limit" or any(i in msg for i in rate_indicators):
            return RateLimitError(provider or "unknown", str(exc))
        if status == 404 or any(i in msg for i in model_indicators):
            return ModelNotFoundError(provider or "unknown", str(exc))
        if any(i in exc_type for i in conn_indicators) or any(
            i in msg for i in ("connection refused", "connection reset", "connecterror")
        ):
            return ConnectionError(provider or "unknown", str(exc))
        return AllProvidersFailedError(_prefix(str(exc)))

    def _call_with_fallback(
        self,
        slot: str,
        call_fn: Any,
        call_kwargs: dict[str, Any],
    ) -> Any:
        cfg = self._get_slot_config(slot)
        provider = cfg["primary"].split("/")[0]
        fallback_cfg = self._config.get("gateway", {}).get("fallback", {})
        retries: int = fallback_cfg.get("retries", 2)
        retry_delay: float = fallback_cfg.get("retry_delay", 1.0)
        timeout: int = fallback_cfg.get("timeout", 60)
        call_kwargs["timeout"] = timeout

        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                return call_fn(**call_kwargs)
            except Exception as e:
                last_error = e
                if attempt < retries:
                    time.sleep(retry_delay)

        fallback = cfg.get("fallback")
        if slot in _PRIMARY_ONLY_SLOTS or not fallback:
            if last_error is not None:
                classified = self._classify_error(last_error, provider)
                raise classified from last_error
            raise AllProvidersFailedError("All providers failed")

        call_kwargs["model"] = fallback
        try:
            return call_fn(**call_kwargs)
        except Exception as e:
            classified = self._classify_error(e, provider)
            raise classified from e

    def _strip_empty_content_parts(
        self, messages: list[dict[str, Any]], provider: str
    ) -> list[dict[str, Any]]:
        if provider.lower() not in STRIP_EMPTY_CONTENT_PROVIDERS:
            return messages
        cleaned: list[dict[str, Any]] = []
        for m in messages:
            content = m.get("content")
            if isinstance(content, str) and content.strip() == "":
                continue
            if isinstance(content, list) and _is_empty_parts(content):
                continue
            cleaned.append(m)
        return cleaned

    def _prepare_chat(
        self,
        slot: str,
        messages: list[dict[str, str]],
        session_id: str | None,
        requirement: CapabilityRequirement | None,
    ) -> tuple[list[dict[str, str]], str]:
        """Shared chat preface: validation, capability gate, cost check, system prompt, empty-strip."""
        if slot not in VALID_SLOTS:
            raise SlotNotConfiguredError(f"Invalid slot '{slot}'")
        if requirement is not None:
            info = self._resolve_provider_info(slot)
            if info is not None:
                self.validate_capability(info, requirement)
        self._check_cost_limits(session_id)
        from openreview_cli.prompts.store import PromptStore
        from openreview_cli.prompts.variables import substitute as sub_vars

        store = PromptStore(self._data_path)
        resolved = store.resolve(slot)
        if resolved:
            resolved = sub_vars(resolved, slot, {})
            messages = [{"role": "system", "content": resolved}, *messages]
        provider_prefix = self._get_slot_config(slot)["primary"].split("/")[0]
        messages = self._strip_empty_content_parts(messages, provider_prefix)
        if not messages:
            raise EmptyMessagesError(
                f"no non-empty messages after format correction for provider '{provider_prefix}'"
            )
        return messages, provider_prefix

    def chat(
        self,
        slot: str,
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
        requirement: CapabilityRequirement | None = None,
        **kwargs: Any,
    ) -> str:
        messages, provider_prefix = self._prepare_chat(slot, messages, session_id, requirement)
        call_kwargs = self._get_litellm_kwargs(slot)
        call_kwargs["messages"] = messages
        call_kwargs.update(kwargs)
        response = self._call_with_fallback(slot, completion, call_kwargs)
        self._record_cloud_call(slot)
        # Cost logging must never block the AI call (T030): a logging failure
        # (e.g. missing session FK for non-review flows like grounding) is
        # non-fatal — warn and return the model response regardless.
        try:
            self._cost_tracker.log_call(
                session_id, slot, call_kwargs["model"], provider_prefix, response
            )
        except Exception as cost_err:
            logger.warning("Cost logging failed (non-fatal): %s", cost_err)
        return response.choices[0].message.content or ""

    def chat_stream(
        self,
        slot: str,
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
        requirement: CapabilityRequirement | None = None,
        **kwargs: Any,
    ) -> Iterator[StreamingOutputEvent]:
        """FR-6: streaming chat with dual timeouts (15s connect, 45s idle)."""
        cleaned_messages, provider_prefix = self._prepare_chat(
            slot, messages, session_id, requirement
        )
        call_kwargs = self._get_litellm_kwargs(slot)
        call_kwargs["messages"] = cleaned_messages
        call_kwargs["stream"] = True
        call_kwargs["num_retries"] = 0  # streaming fallback out of scope; one shot
        call_kwargs["timeout"] = httpx.Timeout(
            connect=STREAM_CONNECT_TIMEOUT,
            read=STREAM_READ_TIMEOUT,
            pool=STREAM_CONNECT_TIMEOUT,
            write=STREAM_CONNECT_TIMEOUT,
        )
        call_kwargs.update(kwargs)
        response = completion(**call_kwargs)
        self._record_cloud_call(slot)
        # ponytail: streaming `response` is a generator, so log_call sees no
        # `.usage` yet → cost recorded as 0. Capturing real cost needs the
        # final chunk; defer until a non-streaming cost path or stream-drain.
        # Cost logging must never kill the stream (mirrors chat() T030 fix).
        try:
            self._cost_tracker.log_call(
                session_id, slot, call_kwargs["model"], provider_prefix, response
            )
        except Exception as cost_err:
            logger.warning("Cost logging failed (non-fatal): %s", cost_err)
        yield from self._iter_stream(response, provider_prefix)

    def _iter_stream(self, response: Any, provider_prefix: str) -> Iterator[StreamingOutputEvent]:
        try:
            for chunk in response:
                delta = getattr(chunk.choices[0].delta, "content", None) if chunk.choices else None
                if delta:
                    yield StreamingOutputEvent(type="chunk", text=delta)
            yield StreamingOutputEvent(type="done")
        except Exception as exc:
            if isinstance(exc, httpx.ConnectTimeout):
                raise ConnectionError(
                    provider_prefix, f"stream header timeout: {exc}", timeout_kind="header"
                ) from exc
            if isinstance(exc, httpx.ReadTimeout):
                raise ConnectionError(
                    provider_prefix, f"stream idle timeout: {exc}", timeout_kind="idle"
                ) from exc
            msg = str(exc).lower()
            if (
                isinstance(
                    exc,
                    (litellm.exceptions.APIConnectionError, litellm.exceptions.Timeout),
                )
                or "timeout" in msg
                or "timed out" in msg
                or "read" in msg
            ):
                kind = "header" if ("connect" in msg or "header" in msg) else "idle"
                raise ConnectionError(
                    provider_prefix, f"stream idle timeout: {exc}", timeout_kind=kind
                ) from exc
            raise

    def embed(
        self,
        slot: str,
        texts: list[str],
        *,
        session_id: str | None = None,
        requirement: CapabilityRequirement | None = None,
    ) -> list[list[float]]:
        if slot not in VALID_SLOTS:
            raise SlotNotConfiguredError(f"Invalid slot '{slot}'")
        if requirement is not None:
            info = self._resolve_provider_info(slot)
            if info is not None:
                self.validate_capability(info, requirement)
        self._check_cost_limits(session_id)
        from openreview_cli.prompts.store import PromptStore
        from openreview_cli.prompts.variables import substitute as sub_vars

        store = PromptStore(self._data_path)
        resolved = store.resolve(slot)
        if resolved:
            resolved = sub_vars(resolved, slot, {})
            texts = [resolved, *texts]
        call_kwargs = self._get_litellm_kwargs(slot)
        call_kwargs["input"] = texts
        response = self._call_with_fallback(slot, embedding, call_kwargs)
        self._record_cloud_call(slot)
        orig_provider = self._get_slot_config(slot)["primary"].split("/")[0]
        try:
            self._cost_tracker.log_call(
                session_id, slot, call_kwargs["model"], orig_provider, response
            )
        except Exception as cost_err:
            logger.warning("Cost logging failed (non-fatal): %s", cost_err)
        return [item["embedding"] for item in response.data]

    def rerank(
        self,
        slot: str,
        query: str,
        documents: list[str],
        top_n: int = 5,
        *,
        session_id: str | None = None,
        requirement: CapabilityRequirement | None = None,
    ) -> list[dict[str, Any]]:
        if slot not in VALID_SLOTS:
            raise SlotNotConfiguredError(f"Invalid slot '{slot}'")
        if requirement is not None:
            info = self._resolve_provider_info(slot)
            if info is not None:
                self.validate_capability(info, requirement)
        self._check_cost_limits(session_id)
        from openreview_cli.prompts.store import PromptStore
        from openreview_cli.prompts.variables import substitute as sub_vars

        store = PromptStore(self._data_path)
        resolved = store.resolve(slot)
        if resolved:
            resolved = sub_vars(resolved, slot, {})
            query = f"{resolved}\n\n{query}"

        from litellm import rerank

        cfg = self._get_slot_config(slot)
        fallback_cfg = self._config.get("gateway", {}).get("fallback", {})
        timeout: int = fallback_cfg.get("timeout", 60)

        kwargs = self._get_litellm_kwargs(slot)
        try:
            response = rerank(
                query=query,
                documents=documents,
                top_n=top_n,
                timeout=timeout,
                **kwargs,
            )
        except Exception as e:
            classified = self._classify_error(e, provider=cfg["primary"].split("/")[0])
            raise classified from e

        try:
            self._cost_tracker.log_call(
                session_id, slot, cfg["primary"], cfg["primary"].split("/")[0], response
            )
        except Exception as cost_err:
            logger.warning("Cost logging failed (non-fatal): %s", cost_err)
        self._record_cloud_call(slot)
        return [
            {"index": r["index"], "relevance_score": r["relevance_score"]} for r in response.results
        ]

    def _record_cloud_call(self, slot: str) -> None:
        info = self._resolve_provider_info(slot)
        if info is None:
            return
        try:
            klass = classify_provider(info)
        except ValueError:
            # Local model with resolution error — surface naturally, do NOT
            # count as cloud, do NOT coerce to cloud.
            return
        if klass == "cloud":
            self._cloud_calls_made += 1

    def privacy_report(self) -> PrivacyTierReport:
        return PrivacyTierReport(cloud_calls_made=self._cloud_calls_made)

    def get_cost(self, session_id: str) -> dict[str, Any]:
        return dict(self._cost_tracker.get_session_cost(session_id))

    def health_check(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        models = self._config.get("gateway", {}).get("models", {})
        for slot_name in VALID_SLOTS:
            cfg = models.get(slot_name)
            if not cfg or not cfg.get("primary"):
                result[slot_name] = {"status": "not_configured"}
                continue
            provider = cfg["primary"].split("/")[0]
            env_key = key_to_env(provider)
            info = self._resolve_provider_info(slot_name)
            custom_env = info.env_key if info is not None else None
            if info is not None and (info.is_local or not info.auth_required):
                # Local/keyless providers (e.g. ollama) do not need an API key.
                has_key = True
            else:
                has_key = bool(
                    self._auth.get(provider)
                    or (env_key and os.environ.get(env_key))
                    or (custom_env and os.environ.get(custom_env))
                )
            if not has_key:
                result[slot_name] = {"status": "missing_api_key", "provider": provider}
            else:
                result[slot_name] = {"status": "configured", "provider": provider}
            extra = cfg.get("extra_params")
            if isinstance(extra, dict) and extra:
                result[slot_name]["extra_params"] = len(extra)
        return result
