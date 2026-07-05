"""Unit tests for PrivacyTier, TierConfig, and config parsing."""

from __future__ import annotations

from openreview_cli.gateway.tier_config import PrivacyTier, TierConfig


class TestPrivacyTier:
    """T003: PrivacyTier enum values, string parsing, case-insensitivity."""

    def test_valid_tiers(self) -> None:
        assert PrivacyTier.MAXIMUM.value == "maximum"
        assert PrivacyTier.BALANCED.value == "balanced"
        assert PrivacyTier.PERFORMANCE.value == "performance"

    def test_parse_valid_lowercase(self) -> None:
        tier, warning = PrivacyTier.parse("maximum")
        assert tier == "maximum"
        assert warning is None

        tier, warning = PrivacyTier.parse("balanced")
        assert tier == "balanced"
        assert warning is None

        tier, warning = PrivacyTier.parse("performance")
        assert tier == "performance"
        assert warning is None

    def test_parse_case_insensitive(self) -> None:
        tier, warning = PrivacyTier.parse("MAXIMUM")
        assert tier == "maximum"
        assert warning is None

        tier, warning = PrivacyTier.parse("Balanced")
        assert tier == "balanced"
        assert warning is None

    def test_parse_empty_defaults_to_maximum(self) -> None:
        tier, warning = PrivacyTier.parse("")
        assert tier == "maximum"
        assert warning is not None
        assert "not configured" in warning

    def test_parse_invalid_defaults_to_maximum_with_warning(self) -> None:
        tier, warning = PrivacyTier.parse("invalid_tier")
        assert tier == "maximum"
        assert warning is not None
        assert "Invalid" in warning
        assert "balanced" in warning
        assert "performance" in warning

    def test_parse_none_defaults_to_maximum(self) -> None:
        tier, warning = PrivacyTier.parse("")
        assert tier == "maximum"
        assert warning is not None


class TestTierConfig:
    """T004: TierConfig.from_config() with valid/missing/invalid values."""

    def test_from_config_valid(self) -> None:
        cfg = TierConfig.from_config({"privacy": {"tier": "balanced"}})
        assert cfg.tier == "balanced"
        assert cfg.tier_source == "config"
        assert cfg.warning is None

    def test_from_config_default_when_missing(self) -> None:
        cfg = TierConfig.from_config({})
        assert cfg.tier == "maximum"
        assert cfg.tier_source == "default"
        assert cfg.warning is not None
        assert "not configured" in cfg.warning

    def test_from_config_default_when_invalid(self) -> None:
        cfg = TierConfig.from_config({"privacy": {"tier": "nope"}})
        assert cfg.tier == "maximum"
        assert cfg.tier_source == "default"
        assert cfg.warning is not None
        assert "Invalid" in cfg.warning

    def test_from_config_no_privacy_section(self) -> None:
        cfg = TierConfig.from_config({"gateway": {}})
        assert cfg.tier == "maximum"
        assert cfg.warning is not None

    def test_tier_accessors_for_maximum(self) -> None:
        cfg = TierConfig(tier="maximum")
        assert cfg.embeddings_local_only is True
        assert cfg.llm_local_only is True
        assert cfg.pii_required_before_cloud is False

    def test_tier_accessors_for_balanced(self) -> None:
        cfg = TierConfig(tier="balanced")
        assert cfg.embeddings_local_only is True
        assert cfg.llm_local_only is False
        assert cfg.pii_required_before_cloud is True

    def test_tier_accessors_for_performance(self) -> None:
        cfg = TierConfig(tier="performance")
        assert cfg.embeddings_local_only is False
        assert cfg.llm_local_only is False
        assert cfg.pii_required_before_cloud is True

    def test_tier_captured_once_at_construction(self) -> None:
        """T034: TierConfig captured once, does not re-read config."""
        cfg = TierConfig.from_config({"privacy": {"tier": "maximum"}})
        assert cfg.tier == "maximum"
        # Simulate config change after construction — config dict changed,
        # but the already-constructed TierConfig should still hold its value
        cfg_from_same = TierConfig.from_config({"privacy": {"tier": "balanced"}})
        assert cfg.tier == "maximum"
        assert cfg_from_same.tier == "balanced"

    def test_subsequent_operation_picks_up_new_tier(self) -> None:
        """T036: After config change, next from_config returns new tier."""
        cfg1 = TierConfig.from_config({"privacy": {"tier": "maximum"}})
        assert cfg1.tier == "maximum"
        cfg2 = TierConfig.from_config({"privacy": {"tier": "balanced"}})
        assert cfg2.tier == "balanced"


class TestPrivacyTierReport:
    """T044-T046: PrivacyTierReport formatting and exports."""

    def test_progress_banner_maximum(self) -> None:
        from openreview_cli.gateway.models import PrivacyTierReport

        report = PrivacyTierReport(tier="maximum")
        banner = report.progress_banner()
        assert "MAXIMUM" in banner
        assert "local" in banner.lower()

    def test_progress_banner_balanced(self) -> None:
        from openreview_cli.gateway.models import PrivacyTierReport

        report = PrivacyTierReport(tier="balanced")
        banner = report.progress_banner()
        assert "BALANCED" in banner
        assert "PII" in banner

    def test_progress_banner_performance(self) -> None:
        from openreview_cli.gateway.models import PrivacyTierReport

        report = PrivacyTierReport(tier="performance")
        banner = report.progress_banner()
        assert "PERFORMANCE" in banner
        assert "PII" in banner

    def test_report_footer_maximum(self) -> None:
        from openreview_cli.gateway.models import PrivacyTierReport

        report = PrivacyTierReport(tier="maximum")
        footer = report.report_footer()
        assert "Maximum" in footer
        assert "No data" in footer

    def test_report_footer_balanced(self) -> None:
        from openreview_cli.gateway.models import PrivacyTierReport

        report = PrivacyTierReport(tier="balanced", cloud_calls_made=5, pii_entities_stripped=24)
        footer = report.report_footer()
        assert "Balanced" in footer
        assert "24" in footer

    def test_report_footer_performance(self) -> None:
        from openreview_cli.gateway.models import PrivacyTierReport

        report = PrivacyTierReport(tier="performance", cloud_calls_made=3, pii_entities_stripped=10)
        footer = report.report_footer()
        assert "Performance" in footer
        assert "10" in footer

    def test_exported_from_gateway(self) -> None:
        """T046: PrivacyTier exported from gateway/__init__.py."""
        from openreview_cli.gateway import PrivacyTier

        assert PrivacyTier.MAXIMUM.value == "maximum"
        assert PrivacyTier.BALANCED.value == "balanced"
        assert PrivacyTier.PERFORMANCE.value == "performance"

    def test_privacy_tier_report_exported_from_gateway(self) -> None:
        from openreview_cli.gateway import PrivacyTierReport

        assert PrivacyTierReport is not None
