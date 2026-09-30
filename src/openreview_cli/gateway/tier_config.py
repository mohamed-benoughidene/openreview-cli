"""Tier configuration — reads/validates privacy.tier from config."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

# Spec 035 T1.4: only two modes ship. ``performance`` was identical to
# ``balanced`` and is retained as an accepted legacy value (see parse); it is
# deliberately not an enum member or a valid tier.
_LEGACY_TIER_ALIASES: dict[str, str] = {"performance": "balanced"}


class PrivacyTier(enum.StrEnum):
    """Privacy tier — enum members are plain strings."""

    MAXIMUM = "maximum"
    BALANCED = "balanced"

    @classmethod
    def parse(cls, value: str) -> tuple[str, str | None]:
        """Parse a tier value, returning (normalized_tier, warning_or_None).

        Case-insensitive. Falls back to MAXIMUM with warning on invalid/absent.
        A legacy ``performance`` value is normalized to ``balanced`` so an old
        config keeps working exactly as it did.
        """
        valid = frozenset({"maximum", "balanced"})
        if not value:
            return "maximum", "privacy.tier not configured. Defaulting to Maximum."
        lower = _LEGACY_TIER_ALIASES.get(value.strip().lower(), value.strip().lower())
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
    def llm_local_only(self) -> bool:
        return self.tier == PrivacyTier.MAXIMUM

    @property
    def pii_required_before_cloud(self) -> bool:
        return self.tier == PrivacyTier.BALANCED

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> TierConfig:
        """Read privacy.tier from config dict, validate, return TierConfig."""
        raw: Any = config.get("privacy", {})
        tier_value = raw.get("tier", "") if isinstance(raw, dict) else ""

        tier, warning = PrivacyTier.parse(tier_value)
        source = "default" if warning else "config"
        return cls(tier=tier, tier_source=source, warning=warning)
