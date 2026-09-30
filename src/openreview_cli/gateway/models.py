from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class Capability(BaseModel):
    embedding: bool = False
    reasoning: bool = False
    context_window: int | None = None
    tool_call: bool = False
    rerank: bool = False


class CredentialField(BaseModel):
    """A single provider credential that the wizard collects and the gateway
    resolves into a litellm kwarg.

    Grounded on spec 034 data-model.md.
    """

    env_key: str
    label: str
    secret: bool = False
    required: bool = True
    litellm_param: str
    is_file_path: bool = False


class ProviderInfo(BaseModel):
    name: str
    env_key: str | None = None
    auth_required: bool = True
    base_url: str | None = None
    is_local: bool = False
    source: str = "bundled"  # "bundled" | "custom" | "discovered"
    capabilities: Capability = Capability()
    models: dict[str, ModelEntry] = {}
    # ponytail: default [] keeps single-key providers backward compatible (FR-2)
    credentials: list[CredentialField] = Field(default_factory=list)


def classify_provider(model: ProviderInfo) -> str:
    """Return "local" if the provider runs locally, else "cloud"."""
    if model.is_local:
        return "local"
    # ollama is user-run infrastructure (their machine, LAN, or a server they
    # control), not a third-party cloud API, so it stays "local" even when
    # OLLAMA_HOST points somewhere other than loopback: the maximum privacy tier
    # must not block it for being off-localhost.
    if model.name == "ollama":
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


class ModelEntry(BaseModel):
    slots: list[str]
    context: int | None = None
    dimensions: int | None = None
    ram: str | None = None
    recommended: bool = False
    status: str | None = None
    note: str | None = None
    extra_params: dict[str, Any] | None = None


class CostRecord(BaseModel):
    id: str
    session_id: str | None = None
    slot: str | None = None
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    cost_cents: int
    created_at: str


class CapabilityRequirement(BaseModel):
    capability: str | None = None  # one of "embedding","reasoning","tool_call"
    min_context_window: int | None = None
    tool_call: bool | None = None


class StreamingOutputEvent(BaseModel):
    type: str  # "chunk" | "done" | "error"
    text: str | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None
    timeout_kind: str | None = None


@dataclass
class PrivacyTierReport:
    """Tier report attached to operation result.

    Provides progress banner (start of output) and report footer
    (end of output) for tier visibility (FR-08, SC-05).
    """

    tier: str = "maximum"
    cloud_calls_made: int = 0
    pii_entities_stripped: int = 0

    def progress_banner(self) -> str:
        """Return one-line progress banner for this tier."""
        tier_upper = self.tier.upper()
        descriptions = {
            "maximum": "all inference local",
            "balanced": "cloud chat allowed (PII stripped)",
        }
        desc = descriptions.get(self.tier, f"tier: {tier_upper}")
        return f"Privacy tier: {tier_upper} — {desc}"

    def report_footer(self) -> str:
        """Return multi-line report footer for this tier."""
        parts: list[str] = []
        if self.tier == "maximum":
            parts.append(
                "Processed under Maximum privacy tier. No data was sent to external services."
            )
        elif self.tier == "balanced":
            entities = (
                f" ({self.pii_entities_stripped} entities redacted)"
                if self.pii_entities_stripped
                else ""
            )
            parts.append(
                "Processed under Balanced privacy tier. "
                f"Cloud LLM received PII-stripped text{entities}."
            )
        else:
            parts.append(f"Processed under {self.tier.title()} privacy tier.")
        if self.cloud_calls_made > 0:
            parts.append(f"Cloud calls: {self.cloud_calls_made}")
        return "\n".join(parts)


# D-10: process-wide count of cloud provider calls actually dispatched, so the
# privacy footer can report truthfully. Defined here (not in ``router``) so the
# TUI can read it without importing litellm.
_total_cloud_calls = 0


def record_cloud_call() -> None:
    """Increment the count of cloud provider calls dispatched in this process."""
    global _total_cloud_calls  # noqa: PLW0603 — module-level counter by design
    _total_cloud_calls += 1


def get_total_cloud_calls() -> int:
    """Return the number of cloud provider calls dispatched in this process."""
    return _total_cloud_calls


def reset_total_cloud_calls() -> None:
    """Reset the process-wide cloud call counter (test isolation)."""
    global _total_cloud_calls  # noqa: PLW0603 — module-level counter by design
    _total_cloud_calls = 0
