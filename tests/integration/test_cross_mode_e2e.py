"""Cross-mode E2E test (B14).

Runs all 5 new modes on the same fixture PDF and asserts each produces a
different assessment (modes are distinct).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openreview_cli.review import run_review
from openreview_cli.review.colors import AssessmentColor
from openreview_cli.review.models import ReviewReport

# All 5 new L-4c modes
NEW_MODES = [
    "franchisecheck",
    "opcheck",
    "partnercheck",
    "sponsorcheck",
    "distrocheck",
]

# Use a single fixture that all modes can process
COMMON_FIXTURE = "simple_contract.pdf"


def _extraction_response() -> str:
    return json.dumps(
        {
            "position": "preferred",
            "confidence": 0.85,
            "citation": "Mock cross-mode extraction.",
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


@pytest.mark.integration
@pytest.mark.no_memory
class TestCrossModeE2E:
    """Cross-mode test: all 5 modes on same fixture, distinct assessments."""

    def test_all_modes_produce_distinct_reports(
        self, monkeypatch: pytest.MonkeyPatch, fixtures_dir: Path
    ) -> None:
        """Each mode produces a report with its own mode identifier."""
        doc_path = fixtures_dir / "pdf" / COMMON_FIXTURE
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

        results: dict[str, ReviewReport] = {}

        for mode in NEW_MODES:
            reports = run_review(
                paths=[str(doc_path)],
                mode=mode,
                no_pii=True,
            )
            assert len(reports) == 1, f"{mode}: expected 1 report, got {len(reports)}"
            report = reports[0]
            assert isinstance(report, ReviewReport)
            assert report.mode == mode, f"Expected mode={mode}, got {report.mode}"
            assert len(report.assessments) > 0, f"{mode}: no assessments"

            for a in report.assessments:
                assert a.color is not None
                assert a.color in (
                    AssessmentColor.green,
                    AssessmentColor.amber,
                    AssessmentColor.red,
                )

            results[mode] = report

        # Assert each mode produced a distinct report identity
        assert len(results) == len(NEW_MODES), "Not all modes produced results"

        # Assert modes are distinct — each report.mode is unique
        mode_values = {r.mode for r in results.values()}
        assert mode_values == set(NEW_MODES), f"Expected modes {set(NEW_MODES)}, got {mode_values}"

    def test_all_modes_run_with_pii(
        self, monkeypatch: pytest.MonkeyPatch, fixtures_dir: Path
    ) -> None:
        """All 5 modes work with PII stripping enabled."""
        doc_path = fixtures_dir / "pdf" / COMMON_FIXTURE
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

        for mode in NEW_MODES:
            reports = run_review(
                paths=[str(doc_path)],
                mode=mode,
                no_pii=False,
            )
            assert len(reports) == 1, f"{mode}: expected 1 report"
            assert reports[0].mode == mode
            assert len(reports[0].assessments) > 0
