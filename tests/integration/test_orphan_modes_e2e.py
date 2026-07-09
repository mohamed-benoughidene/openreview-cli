"""End-to-end pipeline tests for 9 orphan review modes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openreview_cli.review import run_review
from openreview_cli.review.colors import AssessmentColor
from openreview_cli.review.models import ReviewReport


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


ORPHAN_MODES = [
    "licensecheck",
    "leasecheck",
    "privacycheck",
    "indemnitycheck",
    "consultcheck",
    "workcheck",
    "loicheck",
    "subcheck",
    "settlementcheck",
]


@pytest.mark.parametrize("mode", ORPHAN_MODES)
def test_orphan_mode_e2e(
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
    fixtures_dir: Path,
) -> None:
    doc_path = fixtures_dir / "benchmark" / mode / "doc_1.pdf"
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
        mode=mode,
        no_pii=True,
    )

    assert len(reports) == 1
    report = reports[0]
    assert isinstance(report, ReviewReport)
    assert len(report.assessments) > 0

    for a in report.assessments:
        assert a.color is not None
        assert a.color in (
            AssessmentColor.green,
            AssessmentColor.amber,
            AssessmentColor.red,
        )
