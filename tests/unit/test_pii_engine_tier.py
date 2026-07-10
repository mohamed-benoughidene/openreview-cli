"""Unit tests for tier-aware PII stripping entry point."""

from typing import Any

import pytest

from openreview_cli.gateway.tier_config import PrivacyTier
from openreview_cli.pii.models import PiiResult


class TestStripPiiForTier:
    """Verify strip_pii_for_tier uses per-tier threshold in PiiEngine."""

    def test_importable(self) -> None:
        from openreview_cli.pii.engine import strip_pii_for_tier

        assert callable(strip_pii_for_tier)

    @pytest.fixture
    def sample_clauses(self) -> list[Any]:
        from openreview_cli.parsing.models import Clause

        return [
            Clause(
                id="1",
                title="Test Clause",
                text=(
                    "This agreement is between John Smith (SSN: 123-45-6789) "
                    "and Acme Corp at 123 Main St, New York, NY 10001. "
                    "The effective date is January 1, 2026."
                ),
                level=1,
                parent_id=None,
                source_page=None,
                source_paragraph=0,
                source_span=(0, 200),
            ),
        ]

    @pytest.fixture
    def sample_document(self) -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(
            source_path="/tmp/test_doc.pdf",
            author="Test Author",
            title="Test Document",
            company="Test Company",
            page_count=1,
        )

    def test_strip_pii_for_tier_returns_pii_result(
        self, sample_clauses: list[Any], sample_document: Any
    ) -> None:
        from openreview_cli.pii.engine import strip_pii_for_tier

        result = strip_pii_for_tier(
            text=sample_clauses[0].text,
            tier=PrivacyTier.BALANCED,
            document=sample_document,
        )
        assert isinstance(result, PiiResult)
        assert result.page_count >= 1

    def test_strip_pii_for_tier_accepts_all_tiers(
        self, sample_clauses: list[Any], sample_document: Any
    ) -> None:
        from openreview_cli.pii.engine import strip_pii_for_tier

        for tier in (PrivacyTier.MAXIMUM, PrivacyTier.BALANCED, PrivacyTier.PERFORMANCE):
            result = strip_pii_for_tier(
                text=sample_clauses[0].text,
                tier=tier,
                document=sample_document,
            )
            assert isinstance(result, PiiResult)

    def test_strip_pii_for_tier_uses_different_thresholds(
        self, sample_clauses: list[Any], sample_document: Any
    ) -> None:
        """Maximum (0.4) should catch more entities than Performance (0.8)."""
        from openreview_cli.pii.engine import strip_pii_for_tier

        max_result = strip_pii_for_tier(
            text=sample_clauses[0].text,
            tier=PrivacyTier.MAXIMUM,
            document=sample_document,
        )
        perf_result = strip_pii_for_tier(
            text=sample_clauses[0].text,
            tier=PrivacyTier.PERFORMANCE,
            document=sample_document,
        )

        # Maximum (lower threshold) should catch at least as many entities
        # as Performance (higher threshold)
        assert len(max_result.entities) >= len(perf_result.entities)

    def test_does_not_mutate_existing_signature(self) -> None:
        """Confirm the original strip_pii still accepts its signature unchanged."""
        import inspect

        from openreview_cli.pii.engine import strip_pii

        sig = inspect.signature(strip_pii)
        param_names = list(sig.parameters.keys())
        assert "clauses" in param_names
        assert "document" in param_names
        assert "threshold" in param_names
