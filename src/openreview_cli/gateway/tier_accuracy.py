"""Per-tier accuracy targets for privacy tier model inference.

Each tier defines minimum acceptable precision, recall, and F1 scores
for model inference, plus the PII score threshold to use during stripping.
"""

from __future__ import annotations

from dataclasses import dataclass

from openreview_cli.gateway.tier_config import PrivacyTier


@dataclass(frozen=True)
class TierAccuracyTarget:
    """Accuracy and PII threshold targets for a single privacy tier.

    Attributes
    ----------
    min_f1 : float
        Minimum acceptable F1 score (0.0-1.0).
    min_precision : float
        Minimum acceptable precision (0.0-1.0).
    min_recall : float
        Minimum acceptable recall (0.0-1.0).
    pii_score_threshold : float
        Presidio score threshold for PII detection (0.0-1.0).
        Lower values catch more potential PII (broader capture).
    """

    min_f1: float
    min_precision: float
    min_recall: float
    pii_score_threshold: float


# User research established these targets:
#   Courts accept 80% F1 for TAR; human first-pass review ~85%.
#   PII false negatives are worse than false positives,
#   so Maximum tier uses the lowest PII threshold (broadest capture).
TIER_ACCURACY_TARGETS: dict[str, TierAccuracyTarget] = {
    PrivacyTier.MAXIMUM: TierAccuracyTarget(
        min_f1=0.70,
        min_precision=0.65,
        min_recall=0.75,
        pii_score_threshold=0.4,
    ),
    PrivacyTier.BALANCED: TierAccuracyTarget(
        min_f1=0.80,
        min_precision=0.75,
        min_recall=0.85,
        pii_score_threshold=0.6,
    ),
    PrivacyTier.PERFORMANCE: TierAccuracyTarget(
        min_f1=0.90,
        min_precision=0.85,
        min_recall=0.95,
        pii_score_threshold=0.8,
    ),
}


def get_target(tier: str) -> TierAccuracyTarget:
    """Return accuracy target for given tier string.

    Parameters
    ----------
    tier : str
        One of ``"maximum"``, ``"balanced"``, ``"performance"``.

    Returns
    -------
    TierAccuracyTarget
        The accuracy and PII threshold targets for this tier.

    Raises
    ------
    KeyError
        If *tier* is not a recognised privacy tier.
    """
    if tier not in TIER_ACCURACY_TARGETS:
        valid = ", ".join(sorted(TIER_ACCURACY_TARGETS))
        raise KeyError(f"Unknown tier '{tier}'. Valid: {valid}")
    return TIER_ACCURACY_TARGETS[tier]


__all__ = ["TIER_ACCURACY_TARGETS", "TierAccuracyTarget", "get_target"]
