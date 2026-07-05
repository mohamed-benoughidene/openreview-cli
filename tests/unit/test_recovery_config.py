"""Unit tests for recovery configuration."""

import pytest

from openreview_cli.config import RecoveryConfig


class TestRecoveryConfig:
    def test_default_values(self) -> None:
        config = RecoveryConfig()
        assert config.max_retries == 4
        assert config.base_interval_s == 1.0
        assert config.memory_threshold_pct == 80.0
        assert config.enabled_strategies is None

    def test_custom_values_override(self) -> None:
        config = RecoveryConfig(
            max_retries=3,
            base_interval_s=2.0,
            memory_threshold_pct=90.0,
            enabled_strategies=["auto_retry", "provider_fallback"],
        )
        assert config.max_retries == 3
        assert config.base_interval_s == 2.0
        assert config.memory_threshold_pct == 90.0
        assert config.enabled_strategies == [
            "auto_retry",
            "provider_fallback",
        ]

    def test_invalid_max_retries_rejected(self) -> None:
        with pytest.raises(ValueError):
            RecoveryConfig(max_retries=0)

    def test_invalid_base_interval_rejected(self) -> None:
        with pytest.raises(ValueError):
            RecoveryConfig(base_interval_s=-1.0)

        with pytest.raises(ValueError):
            RecoveryConfig(base_interval_s=0.0)

    def test_invalid_memory_threshold_low(self) -> None:
        with pytest.raises(ValueError):
            RecoveryConfig(memory_threshold_pct=5.0)

    def test_invalid_memory_threshold_high(self) -> None:
        with pytest.raises(ValueError):
            RecoveryConfig(memory_threshold_pct=101.0)

    def test_partial_config_merges_with_defaults(self) -> None:
        """Setting only some fields leaves others at defaults."""
        config = RecoveryConfig(max_retries=2)
        assert config.max_retries == 2
        assert config.base_interval_s == 1.0  # default
        assert config.memory_threshold_pct == 80.0  # default
        assert config.enabled_strategies is None  # default

    def test_edge_case_threshold_boundaries(self) -> None:
        """Boundary values should be accepted."""
        config_low = RecoveryConfig(memory_threshold_pct=10.0)
        assert config_low.memory_threshold_pct == 10.0

        config_high = RecoveryConfig(memory_threshold_pct=100.0)
        assert config_high.memory_threshold_pct == 100.0
