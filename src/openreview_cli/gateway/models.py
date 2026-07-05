from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


class ProviderInfo(BaseModel):
    name: str
    env_key: str | None = None
    auth_required: bool = True
    models: dict[str, ModelEntry] = {}


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
            "balanced": "local embeddings, cloud LLM (PII stripped)",
            "performance": "cloud inference (PII stripped before egress)",
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
                f"Embeddings processed locally. Cloud LLM received PII-stripped text{entities}."
            )
        elif self.tier == "performance":
            entities = (
                f" ({self.pii_entities_stripped} entities redacted)"
                if self.pii_entities_stripped
                else ""
            )
            parts.append(
                "Processed under Performance privacy tier. "
                f"All inference used cloud providers. PII was stripped before all external calls{entities}."
            )
        else:
            parts.append(f"Processed under {self.tier.title()} privacy tier.")
        if self.cloud_calls_made > 0:
            parts.append(f"Cloud calls: {self.cloud_calls_made}")
        return "\n".join(parts)
