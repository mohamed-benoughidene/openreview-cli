"""Unit tests for terminal report colour output, width, and mode-derived title.

Covers P1/C1 (ANSI colour emission in ``format_terminal``), P2/C4 (wrap the
report to the real terminal width), and the hardcoded-title defect (the header
must be derived from ``report.mode`` instead of always saying "NDA").
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Position,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
)
from openreview_cli.review.report import format_terminal


def _make_report(mode: str = "precheck") -> ReviewReport:
    ca = ClauseAssessment(
        clause_id="c1",
        clause_text="Confidentiality term.",
        playbook_category="confidentiality-term",
        position=Position.PREFERRED,
        confidence=0.92,
        citation="clause c1",
        qa_verdict=QAVerdict.agree,
        extraction_model="m1",
        qa_model="m1",
    )
    dm = DocMeta(filename="nda.docx", page_count=1, clause_count=1, pii_stripped=True)
    return ReviewReport(
        document=dm,
        assessments=[ca],
        summary=ReviewSummary(preferred_count=1, avg_confidence=0.92),
        playbook_id="precheck-nda-v1",
        generated_at=datetime.now(UTC),
        mode=mode,
    )


# ── Colour (P1/C1) ──────────────────────────────────────────────────────


def test_format_terminal_color_true_emits_ansi() -> None:
    assert "\x1b[" in format_terminal(_make_report(), color=True)


def test_format_terminal_color_false_has_no_ansi() -> None:
    assert "\x1b[" not in format_terminal(_make_report(), color=False)


def test_format_terminal_default_respects_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto-detect uses Rich's native Console.is_terminal (FORCE_COLOR et al.)."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("TTY_COMPATIBLE", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert "\x1b[" in format_terminal(_make_report())

    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setenv("TTY_COMPATIBLE", "0")
    assert "\x1b[" not in format_terminal(_make_report())


def test_format_terminal_honours_no_color(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("NO_COLOR", "1")
    assert "\x1b[" not in format_terminal(_make_report())


def test_plain_text_content_is_unchanged() -> None:
    """Enabling colour must not alter the visible text."""
    colored = format_terminal(_make_report(), color=True)
    plain = format_terminal(_make_report(), color=False)
    assert "NDA Review Report" in plain
    assert "● OK" in plain
    assert "● OK" in colored  # substring survives the ANSI wrappers


# ── Width (P2/C4) ───────────────────────────────────────────────────────


def test_format_terminal_respects_explicit_width() -> None:
    narrow = format_terminal(_make_report(), color=False, width=60)
    wide = format_terminal(_make_report(), color=False, width=200)
    assert max(len(line) for line in narrow.splitlines()) <= 60
    # A wider console lets the table breathe (the fixed-width columns no longer collapse).
    assert max(len(line) for line in wide.splitlines()) > max(
        len(line) for line in narrow.splitlines()
    )


def test_format_terminal_default_uses_terminal_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "openreview_cli.review.report.shutil.get_terminal_size",
        lambda fallback=(100, 24): os.terminal_size((72, 24)),
    )
    out = format_terminal(_make_report(), color=False)
    assert max(len(line) for line in out.splitlines()) <= 72


# ── Mode-derived title ──────────────────────────────────────────────────


def test_report_title_derives_from_mode() -> None:
    """The header must reflect the review mode, not hardcode NDA for every mode."""
    precheck = format_terminal(_make_report(mode="precheck"), color=False)
    assert "NDA Review Report" in precheck

    licensecheck = format_terminal(_make_report(mode="licensecheck"), color=False)
    assert "Licensecheck Review Report" in licensecheck
    assert "NDA Review Report" not in licensecheck

    privacy_v2 = format_terminal(_make_report(mode="privacycheck_v2"), color=False)
    assert "Privacycheck V2 Review Report" in privacy_v2


def test_format_terminal_preserves_bracketed_legal_text() -> None:
    """Bracketed text such as [intentionally omitted] or [Party A] must not be eaten as markup."""
    ca = ClauseAssessment(
        clause_id="c1",
        clause_text="Confidentiality [intentionally omitted] and [Party A].",
        playbook_category="confidentiality-term",
        position=Position.PREFERRED,
        confidence=0.92,
        citation="clause c1",
        qa_verdict=QAVerdict.agree,
        extraction_model="m1",
        qa_model="m1",
    )
    dm = DocMeta(filename="nda.docx", page_count=1, clause_count=1, pii_stripped=True)
    report = ReviewReport(
        document=dm,
        assessments=[ca],
        summary=ReviewSummary(preferred_count=1, avg_confidence=0.92),
        playbook_id="precheck-nda-v1",
        generated_at=datetime.now(UTC),
        mode="precheck",
    )
    rendered = format_terminal(report, color=False)
    assert "[intentionally" in rendered
    assert "omitted]" in rendered
    assert "[Party A]" in rendered
