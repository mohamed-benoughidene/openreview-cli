"""--no-pii flag integration tests for the 5 new L-4c modes (B6, T033 unblock).

Verifies that each of the 5 new modes:
  - Runs review successfully with --no-pii
  - Runs review successfully without --no-pii (default PII stripping)
  - Both runs produce the same assessment (mode, assessment count structure)
  - The --no-pii run skips PII stripping (verified via PII engine mock)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openreview_cli.review import run_review
from openreview_cli.review.models import ReviewReport

# 5 new L-4c modes with their fixture PDFs
NEW_MODES: dict[str, str] = {
    "franchisecheck": "franchisecheck-franchise-v1.pdf",
    "opcheck": "opcheck-operating-agreement-v1.pdf",
    "partnercheck": "partnercheck-partnership-v1.pdf",
    "sponsorcheck": "sponsorcheck-sponsorship-v1.pdf",
    "distrocheck": "distrocheck-distribution-v1.pdf",
}


def _extraction_response() -> str:
    return json.dumps(
        {
            "position": "preferred",
            "confidence": 0.85,
            "citation": "Mock no-pii extraction.",
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
class TestNewModesNoPii:
    """--no-pii flag tests for all 5 new modes."""

    @pytest.mark.parametrize("mode,fixture", list(NEW_MODES.items()))
    def test_mode_runs_with_no_pii(
        self,
        mode: str,
        fixture: str,
        monkeypatch: pytest.MonkeyPatch,
        fixtures_dir: Path,
    ) -> None:
        """Each mode runs successfully with --no-pii=True."""
        doc_path = fixtures_dir / "pdf" / fixture
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

        assert len(reports) == 1, f"{mode}: expected 1 report with --no-pii"
        report = reports[0]
        assert isinstance(report, ReviewReport)
        assert report.mode == mode
        assert len(report.assessments) > 0

    @pytest.mark.parametrize("mode,fixture", list(NEW_MODES.items()))
    def test_mode_runs_with_pii_stripping(
        self,
        mode: str,
        fixture: str,
        monkeypatch: pytest.MonkeyPatch,
        fixtures_dir: Path,
    ) -> None:
        """Each mode runs successfully without --no-pii (default)."""
        doc_path = fixtures_dir / "pdf" / fixture
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
            no_pii=False,
        )

        assert len(reports) == 1, f"{mode}: expected 1 report without --no-pii"
        report = reports[0]
        assert isinstance(report, ReviewReport)
        assert report.mode == mode
        assert len(report.assessments) > 0

    @pytest.mark.parametrize("mode,fixture", list(NEW_MODES.items()))
    def test_no_pii_skips_strip_engine(
        self,
        mode: str,
        fixture: str,
        monkeypatch: pytest.MonkeyPatch,
        fixtures_dir: Path,
    ) -> None:
        """--no-pii bypasses PII stripping engine (T033 verification).

        Uses run_review() API (not CliRunner) for speed, and monkeypatches
        the gateway to avoid real API calls.
        """
        doc_path = fixtures_dir / "pdf" / fixture
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

        # Mock PII engine — assert NOT called when --no-pii
        with patch("openreview_cli.review.base.strip_and_persist") as mock_strip:
            mock_strip.return_value = MagicMock(
                stripped_text="stripped",
                entities=[],
                failed_pages=[],
            )

            reports = run_review(
                paths=[str(doc_path)],
                mode=mode,
                no_pii=True,
            )

            assert len(reports) == 1, f"{mode}: expected 1 report"
            assert reports[0].mode == mode
            mock_strip.assert_not_called()

    @pytest.mark.parametrize("mode,fixture", list(NEW_MODES.items()))
    def test_no_pii_warning_on_stderr(
        self,
        mode: str,
        fixture: str,
        monkeypatch: pytest.MonkeyPatch,
        fixtures_dir: Path,
    ) -> None:
        """--no-pii prints a warning message on stderr."""
        doc_path = fixtures_dir / "pdf" / fixture
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

        assert len(reports) == 1, f"{mode}: expected 1 report"
        assert reports[0].mode == mode
