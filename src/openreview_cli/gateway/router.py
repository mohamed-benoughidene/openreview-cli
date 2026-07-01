from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

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
    ModelNotFoundError,
    SlotNotConfiguredError,
)
from openreview_cli.gateway.redaction import RedactingFilter, redact_key
from openreview_cli.storage.database import check_daily_limit, check_session_limit

logger = logging.getLogger(__name__)

_PROTECTED_KEYS = frozenset({"model", "messages", "input", "timeout"})
VALID_SLOTS = frozenset({"reasoning", "extraction", "embedding", "reranking", "graph"})
_PRIMARY_ONLY_SLOTS = frozenset({"embedding", "reranking"})
_SLOT_METHOD_MAP: dict[str, str] = {
    "reasoning": "chat",
    "extraction": "chat",
    "embedding": "embed",
    "reranking": "rerank",
    "graph": "chat",
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

        _filter = RedactingFilter(_REDACT_PATTERNS)
        logging.getLogger().addFilter(_filter)

        self._set_env_vars()

    def _set_env_vars(self) -> None:
        for provider, key in self._auth.items():
            from openreview_cli.config.auth import key_to_env

            env_name = key_to_env(provider)
            if env_name and key:
                import os

                os.environ.setdefault(env_name, key)
                logger.debug("Set %s to %s", env_name, redact_key(key))

    def _get_slot_config(self, slot: str) -> dict[str, Any]:
        models = self._config.get("gateway", {}).get("models", {})
        cfg: dict[str, Any] | None = models.get(slot)
        if not cfg:
            raise SlotNotConfiguredError(f"No model configured for slot '{slot}'")
        primary = cfg.get("primary")
        if not primary:
            raise SlotNotConfiguredError(f"Slot '{slot}' has no primary model")
        return cfg

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
        return kwargs

    def _check_cost_limits(self, session_id: str | None) -> None:
        limits = self._config.get("gateway", {}).get("cost_limits", {})
        daily_cents = limits.get("daily_cents")
        per_review_cents = limits.get("per_review_cents")

        try:
            if daily_cents is not None and not check_daily_limit(self._data_path, daily_cents):
                logger.warning("Daily cost limit of %d¢ would be exceeded", daily_cents)
        except Exception:
            logger.debug("Failed to check daily cost limit", exc_info=True)

        if session_id and per_review_cents is not None:
            try:
                if not check_session_limit(self._data_path, session_id, per_review_cents):
                    logger.warning(
                        "Session cost limit of %d¢ would be exceeded for session %s",
                        per_review_cents,
                        session_id,
                    )
            except Exception:
                logger.debug("Failed to check session limit", exc_info=True)

    def _classify_error(self, exc: Exception) -> Exception:
        msg = str(exc).lower()
        exc_type = type(exc).__name__.lower()
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
        model_indicators = {"not found", "model_not_found", "404", "not_found"}

        if any(i in exc_type for i in conn_indicators) or any(
            i in msg for i in ("connection refused", "connection reset", "connecterror")
        ):
            return AllProvidersFailedError(
                "Ollama not reachable at localhost:11434 — ensure Ollama is running"
            )
        if any(i in msg for i in auth_indicators):
            return AuthError(str(exc))
        if any(i in msg for i in model_indicators):
            return ModelNotFoundError(str(exc))
        return AllProvidersFailedError(str(exc))

    def _call_with_fallback(
        self,
        slot: str,
        call_fn: Any,
        call_kwargs: dict[str, Any],
    ) -> Any:
        cfg = self._get_slot_config(slot)
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
                classified = self._classify_error(last_error)
                raise classified from last_error
            raise AllProvidersFailedError("All providers failed")

        call_kwargs["model"] = fallback
        try:
            return call_fn(**call_kwargs)
        except Exception as e:
            classified = self._classify_error(e)
            raise classified from e

    def chat(
        self,
        slot: str,
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        if slot not in VALID_SLOTS:
            raise SlotNotConfiguredError(f"Invalid slot '{slot}'")
        self._check_cost_limits(session_id)
        call_kwargs = self._get_litellm_kwargs(slot)
        call_kwargs["messages"] = messages
        call_kwargs.update(kwargs)
        response = self._call_with_fallback(slot, completion, call_kwargs)
        self._cost_tracker.log_call(
            session_id, slot, call_kwargs["model"], call_kwargs["model"].split("/")[0], response
        )
        return response.choices[0].message.content or ""

    def embed(
        self,
        slot: str,
        texts: list[str],
        *,
        session_id: str | None = None,
    ) -> list[list[float]]:
        if slot not in VALID_SLOTS:
            raise SlotNotConfiguredError(f"Invalid slot '{slot}'")
        self._check_cost_limits(session_id)
        call_kwargs = self._get_litellm_kwargs(slot)
        call_kwargs["input"] = texts
        response = self._call_with_fallback(slot, embedding, call_kwargs)
        self._cost_tracker.log_call(
            session_id, slot, call_kwargs["model"], call_kwargs["model"].split("/")[0], response
        )
        return [item["embedding"] for item in response.data]

    def rerank(
        self,
        slot: str,
        query: str,
        documents: list[str],
        top_n: int = 5,
        *,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if slot not in VALID_SLOTS:
            raise SlotNotConfiguredError(f"Invalid slot '{slot}'")
        self._check_cost_limits(session_id)

        from litellm import rerank

        cfg = self._get_slot_config(slot)
        fallback_cfg = self._config.get("gateway", {}).get("fallback", {})
        timeout: int = fallback_cfg.get("timeout", 60)

        try:
            response = rerank(
                model=cfg["primary"],
                query=query,
                documents=documents,
                top_n=top_n,
                timeout=timeout,
            )
        except Exception as e:
            classified = self._classify_error(e)
            raise classified from e

        self._cost_tracker.log_call(
            session_id, slot, cfg["primary"], cfg["primary"].split("/")[0], response
        )
        return [
            {"index": r["index"], "relevance_score": r["relevance_score"]} for r in response.results
        ]

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
            if env_key and not self._auth.get(provider):
                result[slot_name] = {"status": "missing_api_key", "provider": provider}
            else:
                result[slot_name] = {"status": "configured", "provider": provider}
            extra = cfg.get("extra_params")
            if isinstance(extra, dict) and extra:
                result[slot_name]["extra_params"] = len(extra)
        return result
