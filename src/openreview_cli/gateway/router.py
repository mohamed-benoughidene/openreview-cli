from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import httpx
import litellm

if TYPE_CHECKING:
    from pathlib import Path

from litellm import completion

from openreview_cli.config.auth import key_to_env, load_auth
from openreview_cli.config.loader import load_config
from openreview_cli.config.paths import get_config_dir, get_data_dir
from openreview_cli.errors import cost_limit_error
from openreview_cli.gateway.cost import CostTracker
from openreview_cli.gateway.errors import (
    AllProvidersFailedError,
    AuthError,
    CapabilityMismatchError,
    ConnectionError,
    EmptyMessagesError,
    ModelNotFoundError,
    NoMatchingProviderError,
    PIIUnavailableError,
    RateLimitError,
    SlotNotConfiguredError,
    UnclassifiedProviderError,
)
from openreview_cli.gateway.models import (
    CapabilityRequirement,
    PrivacyTierReport,
    ProviderInfo,
    StreamingOutputEvent,
    classify_provider,
    get_total_cloud_calls,
    record_cloud_call,
    reset_total_cloud_calls,
)
from openreview_cli.gateway.redaction import install_on_root_handlers, redact_key, redact_text
from openreview_cli.gateway.registry import load_registry
from openreview_cli.gateway.tier_config import TierConfig
from openreview_cli.slots import VALID_SLOTS
from openreview_cli.storage.costs import check_daily_limit, check_session_limit

logger = logging.getLogger(__name__)

# Explicit re-exports (mypy no_implicit_reexport): the cloud-call counter and the
# provider classifier live in the litellm-free ``gateway.models`` — the classifier
# had to move there so the TUI can classify egress without pulling litellm (#145).
# Re-exported here so existing importers (``review.base``, ``app``, tests) keep working.
__all__ = [
    "classify_provider",
    "get_total_cloud_calls",
    "record_cloud_call",
    "reset_total_cloud_calls",
]

# Track env vars seeded across all Gateway instances so long-lived
# processes (TUI) can clean them up without holding a Gateway reference.
_env_vars_seeded: set[str] = set()


def clear_seeded_env_vars() -> None:
    """Remove env vars seeded by any Gateway instance. User-owned vars untouched."""
    for name in list(_env_vars_seeded):
        os.environ.pop(name, None)
    _env_vars_seeded.clear()


# PII-before-egress gate (spec 020 FR-03/FR-04): a process-wide flag set after a
# successful PII strip and read by _enforce_tier. It is per-operation evidence,
# not an "ever stripped" cache — callers reset it at operation start.
_pii_available = False


def mark_pii_available() -> None:
    """Record that a PII strip succeeded in this process (cloud egress allowed)."""
    global _pii_available  # noqa: PLW0603 — module-level flag by design
    _pii_available = True


def reset_pii_available() -> None:
    """Clear the PII-availability flag (operation start / no-pii / test isolation)."""
    global _pii_available  # noqa: PLW0603 — module-level flag by design
    _pii_available = False


def pii_available() -> bool:
    """Return whether a PII strip succeeded in this process."""
    return _pii_available


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


def _enforce_local_only_params(
    kwargs: dict[str, Any],
    extra_params: dict[str, Any] | None,
    provider_prefix: str,
) -> None:
    """Enforce local-only request parameters for the provider ACTUALLY dispatched.

    ``response_format`` becomes Ollama's ``format: json``. A provider that does
    not accept it raises in litellm rather than ignoring it, so the key must be
    present for a local provider and absent for every other one.

    This runs at dispatch time, against ``provider_prefix`` — not at build time
    against the slot's configured primary — because a dispatch-time ``model=``
    override or a caller-supplied kwarg can point the call at a provider the
    built kwargs never saw. It also RESTORES the declared value for a local
    target, since an earlier non-local dispatch may have stripped it: the gate
    is per-dispatch, not a permanent mutation.

    Locality reuses ``classify_provider``, the codebase's one notion of local, so
    a localhost custom provider counts as local exactly as it does for tier
    enforcement. An unknown or unclassifiable prefix is remote.
    """
    info = load_registry().get(provider_prefix)
    is_local = False
    if info is not None:
        try:
            is_local = classify_provider(info) == "local"
        except ValueError:
            # No base_url and not flagged local: unclassifiable, so remote.
            is_local = False
    if not is_local:
        # ponytail: one key today — a set-and-loop earns its keep when a second arrives.
        if "response_format" in kwargs:
            kwargs.pop("response_format")
            logger.debug("Dropped local-only response_format for non-local %r", provider_prefix)
        return
    if "response_format" not in kwargs and extra_params and "response_format" in extra_params:
        kwargs["response_format"] = extra_params["response_format"]


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
        self._tier_config = TierConfig.from_config(self._config)

        install_on_root_handlers()

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

    def slot_primary_model(self, slot: str) -> str | None:
        """Return the configured primary model id for a slot, or None.

        Unlike ``_get_slot_config``, an unknown or unconfigured slot returns None
        instead of raising: callers use this for validation bookkeeping, where a
        missing slot must fall back to a default.
        """
        models = self._config.get("gateway", {}).get("models", {})
        cfg = models.get(slot)
        if not isinstance(cfg, dict):
            return None
        primary = cfg.get("primary")
        return primary if isinstance(primary, str) and primary else None

    def _enforce_tier(  # noqa: PLR0911, PLR0912 — tier rules branch on override vs slot, registry presence, klass, call_type, local_only, and PII gate, and fail closed on an unregistered provider prefix (R3-5, R-01)
        self,
        slot: str,
        call_type: str,
        provider_prefix: str | None = None,
    ) -> None:
        """Block cloud dispatch that the configured privacy tier forbids.

        ``call_type`` is "llm" (chat/chat_stream) — the only transport that
        remains after spec 035 removed the embedding and reranking sockets.
        Local providers are always allowed; cloud providers are gated by the
        tier's local-only rule before any network.

        ``provider_prefix`` is the ACTUAL provider being dispatched (e.g. the
        prefix of a recovery-driven ``model=`` override). When supplied, tier
        enforcement evaluates that provider rather than the slot primary.
        R3-5: the tier must be enforced against the model that will actually
        hit the network, not the slot's configured primary.
        """
        tier_config = getattr(self, "_tier_config", None)
        if tier_config is None:
            return
        if provider_prefix is not None:
            registry = load_registry()
            info = registry.get(provider_prefix)
            if info is None:
                # Override provider is not in the registry (custom or unknown).
                # Fail closed for tier-restricted call types: block dispatch
                # rather than allowing a possible cloud call. The slot primary
                # is irrelevant — the caller supplied an override and the
                # gateway must verify it.
                if call_type == "llm":
                    local_only = tier_config.llm_local_only
                else:
                    return
                if local_only:
                    tier = tier_config.tier.upper()
                    raise NoMatchingProviderError(
                        f"{tier} privacy tier requires a local provider for "
                        f"{call_type}. Unknown provider '{provider_prefix}' "
                        f"(not in registry) cannot be classified as local. "
                        f"Install Ollama and configure a local model, or "
                        f"change privacy tier to 'balanced'."
                    )
                # Under balanced an unknown override still gets the PII gate.
                if tier_config.pii_required_before_cloud and not _pii_available:
                    raise PIIUnavailableError(
                        f"{tier_config.tier.title()} privacy tier requires "
                        "PII stripping before cloud calls. No successful "
                        "strip was recorded for this operation. Run without "
                        "--no-pii / --allow-partial-pii, or use a local provider."
                    )
                return
            klass: str
            try:
                klass = classify_provider(info)
            except ValueError:
                # Unclassifiable non-local override (e.g. bedrock/vertex with
                # base_url=None). Fail closed: if the tier requires a local
                # provider, block it rather than allowing a possible cloud call.
                klass = "cloud"
        else:
            info = self._resolve_provider_info(slot)
            if info is None:
                # The slot primary's provider prefix is not in the registry (a
                # custom or unknown provider). Fail closed for tier-restricted
                # call types, mirroring the override branch above (:252-272):
                # the slot primary is the model that will actually hit the
                # network, so an unclassifiable destination must never reach the
                # dispatch seam while the tier requires a local provider.
                slot_prefix = self._get_slot_config(slot)["primary"].split("/")[0]
                if call_type == "llm":
                    local_only = tier_config.llm_local_only
                else:
                    return
                if local_only:
                    tier = tier_config.tier.upper()
                    raise NoMatchingProviderError(
                        f"{tier} privacy tier requires a local provider for "
                        f"{call_type}. Unknown provider '{slot_prefix}' "
                        f"(not in registry) cannot be classified as local. "
                        f"Install Ollama and configure a local model, or "
                        f"change privacy tier to 'balanced'."
                    )
                # Under balanced an unknown slot primary still gets the PII gate.
                if tier_config.pii_required_before_cloud and not _pii_available:
                    raise PIIUnavailableError(
                        f"{tier_config.tier.title()} privacy tier requires "
                        "PII stripping before cloud calls. No successful "
                        "strip was recorded for this operation. Run without "
                        "--no-pii / --allow-partial-pii, or use a local provider."
                    )
                return
            try:
                klass = classify_provider(info)
            except ValueError:
                # Unclassifiable non-local provider (e.g. bedrock/vertex with
                # base_url=None). Fail closed: if the tier requires a local
                # provider, block it rather than allowing a possible cloud call.
                klass = "cloud"
        if klass != "cloud":
            return

        if call_type == "llm":
            local_only = tier_config.llm_local_only
        else:
            return

        if local_only:
            tier = tier_config.tier.upper()
            raise NoMatchingProviderError(
                f"{tier} privacy tier requires a local provider for {call_type}. "
                f"No local provider configured for slot '{slot}'. Install Ollama and "
                "configure a local model, or change privacy tier to 'balanced'."
            )

        # PII-before-egress gate (spec 020 FR-03/FR-04/SC-02/SC-03): a cloud
        # call that would otherwise proceed under balanced requires
        # a successful PII strip in this process. Fail closed before any network.
        if tier_config.pii_required_before_cloud and not _pii_available:
            raise PIIUnavailableError(
                f"{tier_config.tier.title()} privacy tier requires PII stripping "
                "before cloud calls. No successful strip was recorded for this "
                "operation. Run without --no-pii / --allow-partial-pii, or use a "
                "local provider."
            )

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
        # The local-only gate runs at dispatch, not here: see _enforce_local_only_params.
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
        """Enforce cost limits per spec 001 US4/AC3-4 + spec 005
        US5/AC2 + spec 033 FR-6.

        On breach: call cost_limit_error (exit 6) with the
        spec-mandated message. On check exception: log WARNING
        and re-raise (FR-6 / R8). The previous
        'would be exceeded' warning is replaced by the hard
        exit; that signal now reaches the user via stderr.
        """
        limits = self._config.get("gateway", {}).get("cost_limits", {}) or {}
        daily_cents = limits.get("daily_cents")
        per_review_cents = limits.get("per_review_cents")

        if daily_cents is not None:
            try:
                within = check_daily_limit(self._data_path, daily_cents)
            except Exception:
                logger.warning("Failed to check daily cost limit", exc_info=True)
                raise
            if not within:
                cost_limit_error(
                    f"Daily cost limit reached (${daily_cents / 100:.2f}). "
                    "Reset at UTC midnight or increase limit in config.yml"
                )

        if session_id and per_review_cents is not None:
            try:
                within = check_session_limit(self._data_path, session_id, per_review_cents)
            except Exception:
                logger.warning(
                    "Failed to check session cost limit for session %s",
                    session_id,
                    exc_info=True,
                )
                raise
            if not within:
                cost_limit_error(
                    f"Per-review cost limit reached "
                    f"(${per_review_cents / 100:.2f}). "
                    "Increase limit in config.yml or use a cheaper model"
                )

    def _classify_error(self, exc: Exception, provider: str | None = None) -> Exception:
        msg = str(exc).lower()
        detail = redact_text(str(exc))
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
            return AuthError(provider or "unknown", detail)
        if status == 429 or error_type == "rate_limit" or any(i in msg for i in rate_indicators):
            return RateLimitError(provider or "unknown", detail)
        if status == 404 or any(i in msg for i in model_indicators):
            return ModelNotFoundError(provider or "unknown", detail)
        if any(i in exc_type for i in conn_indicators) or any(
            i in msg for i in ("connection refused", "connection reset", "connecterror")
        ):
            return ConnectionError(provider or "unknown", detail)
        # R3-4: catch-all is UnclassifiedProviderError (recoverable, transient),
        # NOT AllProvidersFailedError (which exclusively signals gateway-local
        # exhaustion and remains terminal at the recovery layer).
        return UnclassifiedProviderError(_prefix(detail))

    def _call_with_fallback(
        self,
        slot: str,
        call_fn: Any,
        call_kwargs: dict[str, Any],
        *,
        call_type: str = "llm",  # "llm" — the only remaining transport (spec 035)
        provider_prefix: str | None = None,  # the prefix of the model actually dispatched
    ) -> Any:
        cfg = self._get_slot_config(slot)
        provider = provider_prefix or cfg["primary"].split("/", 1)[0]
        # Local-only gate for the provider actually dispatched: see _enforce_local_only_params.
        extra_params = cfg.get("extra_params")
        _enforce_local_only_params(call_kwargs, extra_params, provider)
        fallback_cfg = self._config.get("gateway", {}).get("fallback", {})
        retries: int = fallback_cfg.get("retries", 2)
        retry_delay: float = fallback_cfg.get("retry_delay", 1.0)
        timeout: int = fallback_cfg.get("timeout", 60)
        # FR-6: chat_stream sets the dual httpx.Timeout (15s connect / 45s idle)
        # BEFORE dispatch; overwriting it with an int would destroy the idle-timeout
        # contract and break test_stream_timeout_is_dual_not_single. Only a stream
        # keeps its own timeout; every non-stream caller (chat) takes
        # the configured one exactly as before — a caller-supplied `timeout=` must
        # not widen it. (Expressed as one expression to stay inside PLR0912.)
        call_kwargs["timeout"] = (
            call_kwargs.get("timeout", timeout) if "stream" in call_kwargs else timeout
        )

        last_error: Exception | None = None
        for attempt in range(retries + 1):
            # C1/#147: the counter counts DISPATCHES, not logical calls. The count
            # sits before the try, so an attempt that raised is still counted; the
            # value is therefore an upper bound on egress, never an under-report.
            self._record_cloud_call(slot, provider_prefix=provider)
            try:
                return call_fn(**call_kwargs)
            except Exception as e:
                last_error = e
                # C6/#154: a retry cannot fix a bad credential or a missing model.
                # _classify_error already produces AuthError for 401/403/auth and
                # ModelNotFoundError for 404/not-found, so there is no second table.
                if isinstance(self._classify_error(e, provider), (AuthError, ModelNotFoundError)):
                    break
                if attempt < retries:
                    time.sleep(retry_delay)

        fallback = cfg.get("fallback")
        if not fallback:
            if last_error is not None:
                classified = self._classify_error(last_error, provider)
                raise classified from last_error
            raise AllProvidersFailedError("All providers failed")

        fallback_prefix = fallback.split("/", 1)[0]
        # Same gate as the primary, against the ACTUAL model (router.py:240-244).
        self._enforce_tier(slot, call_type, provider_prefix=fallback_prefix)
        # Undo the primary's provider block, then apply the fallback's. Dropping the
        # primary's keys is load-bearing for a `source == "custom"` primary: litellm
        # honours an explicit `api_key` over the provider env var, so leaving it in
        # would send the PRIMARY's credential to the fallback provider's host (#144).
        primary = self._resolve_provider_info(slot)
        if primary is not None:
            for field in primary.credentials:
                call_kwargs.pop(field.litellm_param, None)
        call_kwargs.pop("api_base", None)
        call_kwargs.pop("api_key", None)
        info = load_registry().get(fallback_prefix)
        if info is not None and info.base_url:
            call_kwargs["api_base"] = info.base_url
        if info is not None and info.credentials:
            self._apply_provider_credentials(info, call_kwargs)
        # Re-gated for the fallback's own locality: see _enforce_local_only_params.
        _enforce_local_only_params(call_kwargs, extra_params, fallback_prefix)
        call_kwargs["model"] = fallback
        self._record_cloud_call(slot, provider_prefix=fallback_prefix)
        try:
            return call_fn(**call_kwargs)
        except Exception as e:
            # The error names the provider the failing request actually went to.
            classified = self._classify_error(e, fallback_prefix)
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
        if slot not in VALID_SLOTS:
            raise SlotNotConfiguredError(f"Invalid slot '{slot}'")
        # R3-5: thread the actual dispatched model into tier enforcement so a
        # recovery-driven ``model=`` override cannot bypass the privacy tier
        # by masquerading as the slot primary.
        override_model = kwargs.get("model")
        override_prefix = override_model.split("/", 1)[0] if override_model else None
        self._enforce_tier(slot, "llm", provider_prefix=override_prefix)
        messages, provider_prefix = self._prepare_chat(slot, messages, session_id, requirement)
        call_kwargs = self._get_litellm_kwargs(slot)
        call_kwargs["messages"] = messages
        call_kwargs.update(kwargs)
        response = self._call_with_fallback(
            slot, completion, call_kwargs, provider_prefix=override_prefix
        )
        # #149/#150: validate the reply BEFORE the cost row, so a reply the caller can
        # never read leaves no ledger entry. Reuses UnclassifiedProviderError (the
        # existing _classify_error catch-all) instead of adding a class; the message
        # carries the provider name, mirroring _classify_error's "[provider] detail".
        reply_provider = override_prefix or provider_prefix
        choices = getattr(response, "choices", None)
        if not choices:
            raise UnclassifiedProviderError(f"[{reply_provider}] reply carried no usable choice")
        message = getattr(choices[0], "message", None)
        if message is None:
            raise UnclassifiedProviderError(f"[{reply_provider}] reply choice carried no message")
        content = getattr(message, "content", None) or ""
        # Cost logging must never block the AI call (T030): a logging failure
        # (e.g. missing session FK for non-review flows like grounding) is
        # non-fatal — warn and return the model response regardless.
        try:
            self._cost_tracker.log_call(
                session_id, slot, call_kwargs["model"], provider_prefix, response
            )
        except Exception as cost_err:
            logger.warning("Cost logging failed (non-fatal): %s", cost_err)
        return content

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
        if slot not in VALID_SLOTS:
            raise SlotNotConfiguredError(f"Invalid slot '{slot}'")
        # R3-5: same tier-against-actual-model enforcement as chat().
        override_model = kwargs.get("model")
        override_prefix = override_model.split("/", 1)[0] if override_model else None
        self._enforce_tier(slot, "llm", provider_prefix=override_prefix)
        cleaned_messages, provider_prefix = self._prepare_chat(
            slot, messages, session_id, requirement
        )
        call_kwargs = self._get_litellm_kwargs(slot)
        call_kwargs["messages"] = cleaned_messages
        call_kwargs["stream"] = True
        # litellm must not retry underneath; the gateway owns the retry layer
        call_kwargs["num_retries"] = 0
        call_kwargs["timeout"] = httpx.Timeout(
            connect=STREAM_CONNECT_TIMEOUT,
            read=STREAM_READ_TIMEOUT,
            pool=STREAM_CONNECT_TIMEOUT,
            write=STREAM_CONNECT_TIMEOUT,
        )
        call_kwargs.update(kwargs)
        response = self._call_with_fallback(
            slot, completion, call_kwargs, provider_prefix=override_prefix
        )
        # Mirror chat's reply_provider: a `model=` override names the provider that
        # actually streamed, so a stream error is attributed to it.
        yield from self._iter_stream(response, override_prefix or provider_prefix)
        # #150: the row is written only after the terminal marker was seen, so a
        # truncated or never-yielding stream leaves none. Streaming rows are still
        # 0-cost (log_call reads .usage, absent on the dash wrapper) — noted for a
        # follow-up issue, out of scope here.
        try:
            self._cost_tracker.log_call(
                session_id, slot, call_kwargs["model"], provider_prefix, response
            )
        except Exception as cost_err:
            logger.warning("Cost logging failed (non-fatal): %s", cost_err)
        yield StreamingOutputEvent(type="done")

    def _iter_stream(self, response: Any, provider_prefix: str) -> Iterator[StreamingOutputEvent]:
        try:
            for chunk in response:
                delta = getattr(chunk.choices[0].delta, "content", None) if chunk.choices else None
                if delta:
                    yield StreamingOutputEvent(type="chunk", text=delta)
        except Exception as exc:
            if isinstance(exc, httpx.ConnectTimeout):
                raise ConnectionError(
                    provider_prefix,
                    f"stream header timeout: {redact_text(str(exc))}",
                    timeout_kind="header",
                ) from exc
            if isinstance(exc, httpx.ReadTimeout):
                raise ConnectionError(
                    provider_prefix,
                    f"stream idle timeout: {redact_text(str(exc))}",
                    timeout_kind="idle",
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
                    provider_prefix,
                    f"stream idle timeout: {redact_text(str(exc))}",
                    timeout_kind=kind,
                ) from exc
            raise self._classify_error(exc, provider_prefix) from exc
        # The terminal marker is the RESPONSE-level attribute: litellm's
        # CustomStreamWrapper fabricates a chunk ``finish_reason="stop"`` on EOF,
        # so a chunk's finish_reason cannot be trusted (measured against
        # tests/chaos/_w7_probe.LocalSSEServer: a truncated stream's last chunk
        # carries 'stop' while ``received_finish_reason`` stays None).
        # ``intermittent_finish_reason`` never differs from it in any measured
        # mode, so only this one attribute is read.
        if not getattr(response, "received_finish_reason", None):
            raise ConnectionError(
                provider_prefix,
                "stream ended without a terminal finish_reason (truncated or interrupted)",
            )

    def _record_cloud_call(self, slot: str, provider_prefix: str | None = None) -> None:
        """Increment the cloud-call counter for the actual dispatched provider.

        R3-5: when ``provider_prefix`` is supplied (a recovery-driven
        ``model=`` override), classify the override instead of the slot
        primary. Otherwise the counter under-reports cloud egress and the
        privacy footer misrepresents actual network activity.

        #143: an unclassifiable provider resolves as cloud here exactly as
        ``_enforce_tier`` resolves it — one state, one resolution — for every
        dispatch that names its ``provider_prefix``. A slot primary the registry
        cannot resolve (the no-prefix branch below) still returns uncounted:
        ``_enforce_tier``, not this counter, is the fail-closed gate.
        """
        if provider_prefix is not None:
            registry = load_registry()
            info = registry.get(provider_prefix)
            if info is None:
                # Unknown override — treat as cloud (fail-closed for the
                # privacy counter; the actual dispatch path is the concern of
                # _enforce_tier, not this counter).
                self._cloud_calls_made += 1
                record_cloud_call()
                return
        else:
            info = self._resolve_provider_info(slot)
        if info is None:
            return
        try:
            klass = classify_provider(info)
        except ValueError:
            # One state, one resolution (#143): _enforce_tier treats an
            # unclassifiable provider as cloud, so the counter must too.
            klass = "cloud"
        if klass == "cloud":
            self._cloud_calls_made += 1
            record_cloud_call()

    def privacy_report(self) -> PrivacyTierReport:
        tier_config = getattr(self, "_tier_config", None)
        tier = tier_config.tier if tier_config is not None else "maximum"
        return PrivacyTierReport(tier=tier, cloud_calls_made=self._cloud_calls_made)

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
