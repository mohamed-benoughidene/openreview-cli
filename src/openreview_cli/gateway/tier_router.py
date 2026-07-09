"""TierRouter — privacy enforcement layer wrapping the AI Gateway."""

from __future__ import annotations

import re
import urllib.parse
from typing import TYPE_CHECKING, Any, cast

from openreview_cli.gateway.errors import NoMatchingProviderError, PIIUnavailableError

if TYPE_CHECKING:
    from openreview_cli.gateway.router import Gateway
    from openreview_cli.gateway.tier_config import TierConfig
    from openreview_cli.gateway.tier_tracker import TierTracker
    from openreview_cli.pii.engine import PiiEngine

_LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})
_UNIX_SOCKET_RE = re.compile(r"^(unix:)?/.*")
# Known local provider prefixes from model string (e.g., "ollama/qwen3:8b")
_LOCAL_PROVIDER_PREFIXES = frozenset({"ollama", "local"})


class TierRouter:
    """Wraps Gateway and enforces privacy tier rules before every call.

    TierConfig is passed at construction and stays fixed for the operation
    lifetime. Provider location (local vs cloud) is determined by URL
    inspection via classify_provider().
    """

    def __init__(
        self,
        gateway: Gateway,
        config: TierConfig,
        pii_engine: PiiEngine | None = None,
        tracker: TierTracker | None = None,
    ) -> None:
        self._gateway = gateway
        self._config = config
        self._pii_engine = pii_engine
        self._pii_available = pii_engine.is_available() if pii_engine else False
        self._cloud_calls_made: int = 0
        self._tracker = tracker

    @property
    def config(self) -> TierConfig:
        return self._config

    @property
    def cloud_calls_made(self) -> int:
        return self._cloud_calls_made

    def check_tier_change(self) -> str | None:
        """Check if privacy tier changed since last operation.

        Delegates to the optional TierTracker. Returns a diff message
        ("Tier changed from X to Y") or None if no tracker or no change.
        """
        if not self._tracker:
            return None
        return self._tracker.check_and_record(self._config.tier)

    @staticmethod
    def classify_provider(provider_config: dict[str, Any]) -> str:
        """Classify provider as 'local' or 'cloud'.

        Checks in order:
        1. Explicit local/cloud flag in provider config
        2. Model string prefix (e.g., 'ollama/' -> local)
        3. URL hostname: localhost, 127.0.0.1, ::1 -> local
        4. Unix socket path -> local
        5. Everything else -> cloud
        """
        # Explicit flag takes precedence
        if "local" in provider_config:
            return "local" if provider_config["local"] else "cloud"

        # Model string prefix (e.g., "ollama/llama3.1" -> local)
        model: str = provider_config.get("model", "") or ""
        if model and model.partition("/")[0].lower() in _LOCAL_PROVIDER_PREFIXES:
            return "local"

        # URL-based classification
        api_base = provider_config.get("api_base", "") or provider_config.get("host", "")
        if not api_base:
            return "cloud"

        # Unix socket paths
        if api_base.startswith("/") or api_base.startswith("unix:"):
            return "local"

        try:
            parsed = urllib.parse.urlparse(api_base)
            if parsed.hostname in _LOCAL_HOSTNAMES:
                return "local"
        except Exception:
            pass

        return "cloud"

    def _route_call(
        self,
        method_name: str,
        slot: str,
        *args: Any,
        local_only: bool,
        call_type: str,
        **kwargs: Any,
    ) -> Any:
        """Enforce tier rules for a Gateway call, then dispatch.

        Shared by chat() and embed(). Handles PII gate, provider
        classification, local-only enforcement, and cloud call tracking.
        """
        self._enforce_cloud_pii_gate(call_type)
        provider_cfg = self._get_provider_cfg(slot)
        location = self.classify_provider(provider_cfg)

        if local_only and location == "cloud":
            self._raise_no_matching(method_name, slot, call_type)

        if location == "cloud" and not local_only:
            # PII gate already passed — safe to count as cloud call
            self._cloud_calls_made += 1

        gateway_method = getattr(self._gateway, method_name)
        return gateway_method(slot, *args, **kwargs)

    def chat(
        self,
        slot: str,
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Enforce tier rules for LLM chat calls, then delegate to Gateway."""
        return cast(
            "str",
            self._route_call(
                "chat",
                slot,
                messages,
                local_only=self._config.llm_local_only,
                call_type="LLM",
                session_id=session_id,
                **kwargs,
            ),
        )

    def embed(
        self,
        slot: str,
        texts: list[str],
        *,
        session_id: str | None = None,
    ) -> list[list[float]]:
        """Enforce tier rules for embedding calls, then delegate to Gateway."""
        return cast(
            "list[list[float]]",
            self._route_call(
                "embed",
                slot,
                texts,
                local_only=self._config.embeddings_local_only,
                call_type="embedding",
                session_id=session_id,
            ),
        )

    def _get_provider_cfg(self, slot: str) -> dict[str, Any]:
        """Get the provider config dict for a given slot from the gateway config.

        Extracts the base URL from the slot's model config to classify provider.
        """
        try:
            model_str = self._gateway._get_litellm_kwargs(slot).get("model", "")
        except Exception:
            model_str = ""
        return {"api_base": "", "model": model_str}

    def _enforce_cloud_pii_gate(self, call_type: str) -> None:
        """Check PII availability if we might need cloud (Balanced/Performance)."""
        if self._config.pii_required_before_cloud and not self._pii_available:
            raise PIIUnavailableError(
                f"PII stripping unavailable. Cannot dispatch {call_type} call to "
                "cloud provider without privacy guarantee.\n"
                "Actions:\n"
                "  A. Switch to Maximum tier for local-only inference\n"
                "  B. Fix PII engine (install spaCy model)\n"
                "  C. Use --no-pii only on confirmed-safe documents"
            )

    def _raise_no_matching(self, method: str, slot: str, call_type: str) -> None:
        """Raise NoMatchingProviderError with tier-specific message."""
        tier_name = self._config.tier.upper()
        raise NoMatchingProviderError(
            f"{tier_name} privacy tier requires a local provider for {call_type}. "
            f"No local provider configured for slot '{slot}'. "
            f"Install Ollama and configure a local model, or change privacy tier "
            f"to 'balanced' or 'performance'.",
        )
