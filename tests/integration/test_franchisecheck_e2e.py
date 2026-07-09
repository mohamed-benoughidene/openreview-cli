"""End-to-end pipeline tests for FranchiseCheck mode."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openreview_cli.review import run_review
from openreview_cli.review.colors import AssessmentColor
from openreview_cli.review.models import ReviewReport

MODE = "franchisecheck"
FIXTURE = "franchisecheck-franchise-v1.pdf"


def _extraction_response() -> str:
    return json.dumps(
        {
            "position": "preferred",
            "confidence": 0.85,
            "citation": "Mock franchise extraction.",
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
class TestFranchiseCheckE2E:
    """FranchiseCheck pipeline tests."""

    def test_mode_e2e(self, monkeypatch: pytest.MonkeyPatch, fixtures_dir: Path) -> None:
        """Basic E2E: parse, assess, produce ReviewReport with correct mode."""
        doc_path = fixtures_dir / "pdf" / FIXTURE
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
            mode=MODE,
            no_pii=True,
        )

        assert len(reports) == 1
        report = reports[0]
        assert isinstance(report, ReviewReport)
        assert report.mode == MODE
        assert len(report.assessments) > 0

        for a in report.assessments:
            assert a.color is not None
            assert a.color in (
                AssessmentColor.green,
                AssessmentColor.amber,
                AssessmentColor.red,
            )

    def test_mode_e2e_with_pii(self, monkeypatch: pytest.MonkeyPatch, fixtures_dir: Path) -> None:
        """E2E with PII stripping enabled (no --no-pii)."""
        doc_path = fixtures_dir / "pdf" / FIXTURE
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
            mode=MODE,
            no_pii=False,
        )

        assert len(reports) == 1
        report = reports[0]
        assert isinstance(report, ReviewReport)
        assert report.mode == MODE
        assert len(report.assessments) > 0

        for a in report.assessments:
            assert a.color is not None
            assert a.color in (
                AssessmentColor.green,
                AssessmentColor.amber,
                AssessmentColor.red,
            )

    @pytest.mark.filterwarnings("ignore:.*PII stripping disabled.*:UserWarning")
    def test_no_pii_flag_preserves_assessment(
        self, monkeypatch: pytest.MonkeyPatch, fixtures_dir: Path
    ) -> None:
        """--no-pii and default both produce same assessment mode and structure."""
        doc_path = fixtures_dir / "pdf" / FIXTURE
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

        reports_no_pii = run_review(
            paths=[str(doc_path)],
            mode=MODE,
            no_pii=True,
        )
        reports_default = run_review(
            paths=[str(doc_path)],
            mode=MODE,
            no_pii=False,
        )

        assert len(reports_no_pii) == 1
        assert len(reports_default) == 1
        assert reports_no_pii[0].mode == MODE
        assert reports_default[0].mode == MODE

    def test_multi_page_pdf(self, monkeypatch: pytest.MonkeyPatch, fixtures_dir: Path) -> None:
        """FranchiseCheck handles multi-page PDF (B9)."""
        doc_path = fixtures_dir / "pdf" / "50_page.pdf"
        if not doc_path.exists():
            pytest.skip(f"Multi-page fixture not found: {doc_path}")

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
            mode=MODE,
            no_pii=True,
        )

        assert len(reports) == 1
        report = reports[0]
        assert report.mode == MODE
        assert report.document.page_count > 1, (
            f"Expected multi-page PDF, got {report.document.page_count} page(s)"
        )
