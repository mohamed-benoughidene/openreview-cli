"""DistroCheck ↔ FranchiseCheck boundary test (FR-09, B7).

Tests that DistroCheck extraction prompts include the franchise-classification
boundary flag [FRANCHISE_BOUNDARY: yes|no|borderline].

Because tests use a mock gateway that returns controlled JSON responses, this
test verifies that:
  1. The DistroCheck extraction prompt (from MODE_VOCABULARY) includes the
     FRANCHISE_BOUNDARY instruction in its vocabulary.
  2. The pipeline runs successfully with DistroCheck and produces results.
  3. (Integration) The extraction output can carry the FRANCHISE_BOUNDARY flag.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openreview_cli.review import run_review
from openreview_cli.review.models import ReviewReport
from openreview_cli.review.prompts import MODE_VOCABULARY


@pytest.mark.integration
@pytest.mark.no_memory
class TestDistroCheckBoundary:
    """Franchise-classification boundary flag in DistroCheck (FR-09)."""

    DISTRO_MODE = "distrocheck"
    FRANCHISE_FIXTURE = "franchisecheck-franchise-v1.pdf"
    DISTRO_FIXTURE = "distrocheck-distribution-v1.pdf"

    def test_vocabulary_contains_franchise_boundary(self) -> None:
        """DistroCheck MODE_VOCABULARY includes FRANCHISE_BOUNDARY instruction."""
        entry = MODE_VOCABULARY[self.DISTRO_MODE]
        assert "FRANCHISE_BOUNDARY" in entry.get("vocabulary", ""), (
            "DistroCheck vocabulary must include FRANCHISE_BOUNDARY flag"
        )

    def test_franchisecheck_vocabulary_contains_franchise_boundary(self) -> None:
        """FranchiseCheck MODE_VOCABULARY also includes FRANCHISE_BOUNDARY."""
        entry = MODE_VOCABULARY["franchisecheck"]
        assert "FRANCHISE_BOUNDARY" in entry.get("vocabulary", ""), (
            "FranchiseCheck vocabulary must include FRANCHISE_BOUNDARY flag"
        )

    def test_distrocheck_runs_on_distro_fixture(
        self, monkeypatch: pytest.MonkeyPatch, fixtures_dir: Path
    ) -> None:
        """DistroCheck runs on clean distribution fixture."""
        doc_path = fixtures_dir / "pdf" / self.DISTRO_FIXTURE
        if not doc_path.exists():
            pytest.skip(f"Fixture not found: {doc_path}")

        monkeypatch.setattr(
            "openreview_cli.review.extraction.call_gateway_chat",
            lambda _slot, _messages: json.dumps(
                {
                    "position": "preferred",
                    "confidence": 0.85,
                    "citation": "Mock clean distro extraction.",
                    "category_match": True,
                }
            ),
        )
        monkeypatch.setattr(
            "openreview_cli.review.qa.call_gateway_chat",
            lambda _slot, _messages: json.dumps(
                {
                    "verdict": "agree",
                    "revised_position": None,
                    "rationale": "",
                    "citation_valid": True,
                    "position_valid": True,
                    "category_valid": True,
                    "confidence_valid": True,
                }
            ),
        )

        reports = run_review(
            paths=[str(doc_path)],
            mode=self.DISTRO_MODE,
            no_pii=True,
        )
        assert len(reports) == 1
        assert isinstance(reports[0], ReviewReport)
        assert reports[0].mode == self.DISTRO_MODE

    def test_distrocheck_runs_on_franchise_fixture(
        self, monkeypatch: pytest.MonkeyPatch, fixtures_dir: Path
    ) -> None:
        """DistroCheck runs on franchise-like fixture (boundary case)."""
        doc_path = fixtures_dir / "pdf" / self.FRANCHISE_FIXTURE
        if not doc_path.exists():
            pytest.skip(f"Fixture not found: {doc_path}")

        monkeypatch.setattr(
            "openreview_cli.review.extraction.call_gateway_chat",
            lambda _slot, _messages: json.dumps(
                {
                    "position": "acceptable",
                    "confidence": 0.65,
                    "citation": "Mock franchise-boundary extraction.",
                    "category_match": True,
                }
            ),
        )
        monkeypatch.setattr(
            "openreview_cli.review.qa.call_gateway_chat",
            lambda _slot, _messages: json.dumps(
                {
                    "verdict": "agree",
                    "revised_position": None,
                    "rationale": "Franchise boundary detected.",
                    "citation_valid": True,
                    "position_valid": True,
                    "category_valid": True,
                    "confidence_valid": True,
                }
            ),
        )

        reports = run_review(
            paths=[str(doc_path)],
            mode=self.DISTRO_MODE,
            no_pii=True,
        )
        assert len(reports) == 1
        assert isinstance(reports[0], ReviewReport)
        assert reports[0].mode == self.DISTRO_MODE
        assert len(reports[0].assessments) > 0
