"""Privacy tier reader — wraps TierConfig.from_config."""

from __future__ import annotations

from pathlib import Path

from openreview_cli.config.loader import load_config
from openreview_cli.config.paths import get_config_dir

VALID_TIERS = ("maximum", "balanced")


def read_privacy_tier() -> str:
    """Read the current privacy tier from config.

    Returns one of: 'maximum', 'balanced', 'unknown' if the
    configured value is not valid, or '\u2014' (em dash) if no tier is set.
    A legacy ``performance`` value is normalized to ``balanced`` by the
    config loader.
    """
    try:
        from openreview_cli.gateway.tier_config import TierConfig

        config_dir: Path = get_config_dir()
        raw_config = load_config(config_dir / "config.yml")
        config = TierConfig.from_config(raw_config)
        tier: str = config.tier
        if tier in VALID_TIERS:
            return tier
        return "unknown"
    except Exception:
        return "\u2014"
