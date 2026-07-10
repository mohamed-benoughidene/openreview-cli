"""Unit tests for per-tier accuracy constants."""

from openreview_cli.gateway.tier_accuracy import (
    TIER_ACCURACY_TARGETS,
    TierAccuracyTarget,
    get_target,
)
from openreview_cli.gateway.tier_config import PrivacyTier


class TestTierAccuracyTargets:
    """All three tiers have valid targets."""

    def test_all_tiers_have_targets(self) -> None:
        assert len(TIER_ACCURACY_TARGETS) == 3
        for tier in (PrivacyTier.MAXIMUM, PrivacyTier.BALANCED, PrivacyTier.PERFORMANCE):
            assert tier in TIER_ACCURACY_TARGETS

    def test_targets_are_frozen_dataclass(self) -> None:
        target = TIER_ACCURACY_TARGETS[PrivacyTier.MAXIMUM]
        assert isinstance(target, TierAccuracyTarget)

    def test_precision_monotonically_increasing(self) -> None:
        max_t = TIER_ACCURACY_TARGETS[PrivacyTier.MAXIMUM]
        bal_t = TIER_ACCURACY_TARGETS[PrivacyTier.BALANCED]
        perf_t = TIER_ACCURACY_TARGETS[PrivacyTier.PERFORMANCE]
        assert max_t.min_precision < bal_t.min_precision < perf_t.min_precision

    def test_recall_monotonically_increasing(self) -> None:
        max_t = TIER_ACCURACY_TARGETS[PrivacyTier.MAXIMUM]
        bal_t = TIER_ACCURACY_TARGETS[PrivacyTier.BALANCED]
        perf_t = TIER_ACCURACY_TARGETS[PrivacyTier.PERFORMANCE]
        assert max_t.min_recall < bal_t.min_recall < perf_t.min_recall

    def test_f1_monotonically_increasing(self) -> None:
        max_t = TIER_ACCURACY_TARGETS[PrivacyTier.MAXIMUM]
        bal_t = TIER_ACCURACY_TARGETS[PrivacyTier.BALANCED]
        perf_t = TIER_ACCURACY_TARGETS[PrivacyTier.PERFORMANCE]
        assert max_t.min_f1 < bal_t.min_f1 < perf_t.min_f1

    def test_pii_score_thresholds_within_bounds(self) -> None:
        for target in TIER_ACCURACY_TARGETS.values():
            assert 0.0 <= target.pii_score_threshold <= 1.0

    def test_threshold_ordering_max_broadest(self) -> None:
        """Maximum tier has lowest threshold (broadest capture)."""
        max_t = TIER_ACCURACY_TARGETS[PrivacyTier.MAXIMUM]
        bal_t = TIER_ACCURACY_TARGETS[PrivacyTier.BALANCED]
        perf_t = TIER_ACCURACY_TARGETS[PrivacyTier.PERFORMANCE]
        assert max_t.pii_score_threshold < bal_t.pii_score_threshold < perf_t.pii_score_threshold

    def test_get_target_returns_correct(self) -> None:
        target = get_target(PrivacyTier.BALANCED)
        assert target.min_f1 == 0.80
        assert target.min_precision == 0.75
        assert target.min_recall == 0.85
        assert target.pii_score_threshold == 0.6

    def test_exact_values(self) -> None:
        max_t = TIER_ACCURACY_TARGETS[PrivacyTier.MAXIMUM]
        assert max_t.min_f1 == 0.70
        assert max_t.min_precision == 0.65
        assert max_t.min_recall == 0.75
        assert max_t.pii_score_threshold == 0.4

        bal_t = TIER_ACCURACY_TARGETS[PrivacyTier.BALANCED]
        assert bal_t.min_f1 == 0.80
        assert bal_t.min_precision == 0.75
        assert bal_t.min_recall == 0.85
        assert bal_t.pii_score_threshold == 0.6

        perf_t = TIER_ACCURACY_TARGETS[PrivacyTier.PERFORMANCE]
        assert perf_t.min_f1 == 0.90
        assert perf_t.min_precision == 0.85
        assert perf_t.min_recall == 0.95
        assert perf_t.pii_score_threshold == 0.8
