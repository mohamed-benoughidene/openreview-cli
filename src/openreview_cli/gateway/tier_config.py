"""Tier configuration — reads/validates privacy.tier from config."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class PrivacyTier(enum.StrEnum):
    """Privacy tier — enum members are plain strings."""

    MAXIMUM = "maximum"
    BALANCED = "balanced"
    PERFORMANCE = "performance"

    @classmethod
    def parse(cls, value: str) -> tuple[str, str | None]:
        """Parse a tier value, returning (normalized_tier, warning_or_None).

        Case-insensitive. Falls back to MAXIMUM with warning on invalid/absent.
        """
        valid = frozenset({"maximum", "balanced", "performance"})
        if not value:
            return "maximum", "privacy.tier not configured. Defaulting to Maximum."
        lower = value.strip().lower()
        if lower not in valid:
            valid_str = ", ".join(sorted(valid))
            return (
                "maximum",
                f"Invalid privacy.tier '{value}'. Valid: {valid_str}. Defaulting to Maximum.",
            )
        return lower, None


@dataclass
class TierConfig:
    """Loaded from config.yml at privacy.tier key. Captured once per operation."""

    tier: str = PrivacyTier.MAXIMUM
    tier_source: str = "default"
    warning: str | None = field(default=None)

    # Tier rule accessors — computed from tier value
    @property
    def embeddings_local_only(self) -> bool:
        return self.tier in (PrivacyTier.MAXIMUM, PrivacyTier.BALANCED)

    @property
    def llm_local_only(self) -> bool:
        return self.tier == PrivacyTier.MAXIMUM

    @property
    def pii_required_before_cloud(self) -> bool:
        return self.tier in (PrivacyTier.BALANCED, PrivacyTier.PERFORMANCE)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> TierConfig:
        """Read privacy.tier from config dict, validate, return TierConfig."""
        raw: Any = config.get("privacy", {})
        tier_value = raw.get("tier", "") if isinstance(raw, dict) else ""

        tier, warning = PrivacyTier.parse(tier_value)
        source = "default" if warning else "config"
        return cls(tier=tier, tier_source=source, warning=warning)
