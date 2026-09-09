"""End-to-end pipeline test for privacycheck_v2 mode (D7 evidence).

Proves that the privacycheck_v2 CLI command can execute through the
full review pipeline with the dpa-v2 playbook, produce assessments,
and exercise the v2-specific categories (cross-border-transfer,
sub-processor-change-notification).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openreview_cli.review import run_review
from openreview_cli.review.colors import AssessmentColor
from openreview_cli.review.models import ReviewReport
from openreview_cli.review.playbook import load_playbook

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
DPA_V2_YAML = (
    Path(__file__).resolve().parent.parent.parent
    / "src"
    / "openreview_cli"
    / "review"
    / "playbooks"
    / "dpa-v2.yaml"
)

V2_SPECIFIC_CATEGORIES = {
    "cross-border-transfer",
    "sub-processor-change-notification",
}


def _extraction_response() -> str:
    return json.dumps(
        {
            "position": "preferred",
            "confidence": 0.85,
            "citation": "Mock E2E pipeline clause assessment.",
            "category_match": True,
        }
    )


def _qa_response() -> str:
    return json.dumps(
        {
            "verdict": "agree",
            "revised_position": None,
            "rationale": "",
            "citation_valid": True,
            "position_valid": True,
            "category_valid": True,
            "confidence_valid": True,
        }
    )


class TestPrivacyCheckV2E2E:
    """End-to-end privacycheck_v2 pipeline test (D7 closure evidence)."""

    @pytest.mark.integration
    def test_dpa_v2_playbook_has_v2_categories(self) -> None:
        """D7: dpa-v2.yaml must define the v2-specific categories."""
        playbook = load_playbook(DPA_V2_YAML)
        cat_ids = {c.id for c in playbook.categories}
        for cat_id in V2_SPECIFIC_CATEGORIES:
            assert cat_id in cat_ids, f"dpa-v2.yaml missing v2-specific category: {cat_id}"

    @pytest.mark.integration
    def test_privacycheck_v2_e2e_pipeline(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """D7: privacycheck_v2 mode runs through the full review pipeline.

        Uses the dpa-v2 playbook explicitly and a fixture DPA PDF with
        v2-specific category clauses. Monkeypatches gateway calls (same
        pattern as orphan modes e2e). Proves the pipeline produces
        assessments that exercise the v2-specific categories.
        """
        doc_path = FIXTURES_DIR / "benchmark" / "privacycheck" / "doc_1_v2.pdf"
        if not doc_path.exists():
            pytest.skip(f"Fixture not found: {doc_path}")

        monkeypatch.setattr(
            "openreview_cli.review.extraction.call_gateway_chat",
            lambda _slot, _messages: _extraction_response(),
        )
        monkeypatch.setattr(
            "openreview_cli.review.qa.call_gateway_chat",
            lambda _slot, _messages: _qa_response(),
        )

        reports = run_review(
            paths=[str(doc_path)],
            playbook_path=str(DPA_V2_YAML),
            mode="privacycheck_v2",
            no_pii=True,
        )

        assert len(reports) == 1
        report = reports[0]
        assert isinstance(report, ReviewReport)
        assert len(report.assessments) > 0, "privacycheck_v2 pipeline produced no assessments"

        matched_categories = {a.playbook_category for a in report.assessments}
        dpa_v2_cat_ids = {c.id for c in load_playbook(DPA_V2_YAML).categories}

        assert matched_categories <= dpa_v2_cat_ids, (
            f"Assessment categories not in dpa-v2 playbook: {matched_categories - dpa_v2_cat_ids}"
        )

        assert matched_categories >= V2_SPECIFIC_CATEGORIES, (
            f"V2-specific categories not exercised by pipeline: "
            f"{V2_SPECIFIC_CATEGORIES - matched_categories}"
        )

        for a in report.assessments:
            assert a.color is not None
            assert a.color in (
                AssessmentColor.green,
                AssessmentColor.amber,
                AssessmentColor.red,
            )
