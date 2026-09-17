"""Exploratory probes for the Amber Queue triage *screen*.

The committed ``test_amber_queue_screen.py`` covers the happy paths.  These
probes stress the same screen: rapid navigation wrapping, repeated card/table
toggles, note add-then-clear, notes surviving navigation, duplicate clause ids,
multibyte clause text, and the empty-queue header.  Everything runs inside a
single ``app.run_test`` session so the (expensive) Textual cold start is paid
once.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from textual.widgets import Button, DataTable, Input, Label

from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Position,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
)


def _assessment(
    clause_id: str,
    color: str = "amber",
    *,
    text: str | None = None,
    confidence: float = 0.4,
) -> ClauseAssessment:
    assessment = ClauseAssessment(
        clause_id=clause_id,
        clause_text=text if text is not None else f"Clause {clause_id} text",
        playbook_category="confidentiality-term",
        position=Position.ACCEPTABLE,
        confidence=confidence,
        citation=f"clause {clause_id}",
        qa_verdict=QAVerdict.agree,
        extraction_model="m1",
        qa_model="m1",
    )
    assessment.color = color  # type: ignore[assignment]
    assessment.effective_confidence = confidence
    assessment.amber_reasons = ["low_confidence"]  # type: ignore[assignment]
    return assessment


def _report(assessments: list[ClauseAssessment]) -> ReviewReport:
    return ReviewReport(
        document=DocMeta(
            filename="nda.docx",
            page_count=1,
            clause_count=len(assessments),
            pii_stripped=True,
        ),
        assessments=assessments,
        summary=ReviewSummary(
            amber_count=sum(1 for a in assessments if a.color == "amber"),
        ),
        playbook_id="precheck-nda-v1",
        generated_at=datetime.now(UTC),
    )


@pytest.mark.slow
@pytest.mark.asyncio
async def test_amber_queue_screen_stress() -> None:
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.amber_queue import AmberQueueScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        # ── 1. Empty queue: header + disabled actions + inert keys/toggles ──
        empty = AmberQueueScreen(report=_report([_assessment("g", color="green")]))
        app.push_screen(empty)
        await pilot.pause()

        assert empty._state.total == 0
        header = str(empty.query_one("#amber-header").render())
        assert "no amber" in header.lower(), header
        for btn_id in ("#btn-accept", "#btn-reject", "#btn-note", "#btn-next", "#btn-prev"):
            assert empty.query_one(btn_id, Button).disabled is True
        # Rapid key mashing on an empty queue must be a safe no-op.
        await pilot.press("a", "r", "n", "s", "k", "t", "o", "t", "o")
        await pilot.pause()
        assert empty._state.decided == 0
        assert empty._overview is False, "even toggles leave the card view active"
        app.pop_screen()
        await pilot.pause()

        # ── 2. Navigation wrapping + all-accepted + all-flagged ─────────────
        screen = AmberQueueScreen(report=_report([_assessment(c) for c in ("c1", "c2", "c3")]))
        app.push_screen(screen)
        await pilot.pause()

        # Rapid "next": 7 steps on a 3-item queue wraps back to index 1.
        for _ in range(7):
            await pilot.press("s")
        assert screen._index == 1, screen._index
        # Rapid "previous": 5 steps back from index 1 -> (1 - 5) mod 3 == 2.
        for _ in range(5):
            await pilot.press("k")
        assert screen._index == 2, screen._index

        # Repeated card <-> table toggling: 9 flips lands on the overview.
        for _ in range(9):
            await pilot.press("t")
            await pilot.pause()
        guided = screen.query_one("#amber-guided")
        table = screen.query_one("#amber-overview", DataTable)
        assert table.display is True and guided.display is False
        assert screen._overview is True
        # One more flip returns to the card.
        await pilot.press("t")
        await pilot.pause()
        assert table.display is False and guided.display is True

        # Accept/Reject every clause; the header announces completion.
        await pilot.press("a")
        await pilot.press("r")
        await pilot.press("a")
        await pilot.pause()
        assert screen._state.accepted == 2
        assert screen._state.flagged == 1
        assert screen._state.decided == 3
        assert "queue complete" in str(screen.query_one("#amber-header").render())

        # Navigation still browses (no pending left, so it just steps linearly).
        before = screen._index
        await pilot.press("s")
        assert screen._index == (before + 1) % 3
        await pilot.press("k")
        assert screen._index == before

        # Overview cells reflect the decisions: clause 0 was rejected while the
        # cursor sat at index 2 (accept auto-advanced it to 0), then 1 and 2
        # were accepted in turn.
        assert table.get_cell("0", "c-decision") == "flagged"
        assert table.get_cell("1", "c-decision") == "accepted"
        assert table.get_cell("2", "c-decision") == "accepted"
        app.pop_screen()
        await pilot.pause()

        # ── 3. Notes: add, survive navigation, then clear via empty save ────
        notes = AmberQueueScreen(report=_report([_assessment("n1"), _assessment("n2")]))
        app.push_screen(notes)
        await pilot.pause()

        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#annotate-input", Input).value = "Escalate [Party A]"
        await pilot.press("enter")
        await pilot.pause()
        assert notes._state.current_note(0) == "Escalate [Party A]"
        detail = str(notes.query_one("#amber-detail", Label).render())
        assert "Escalate [Party A]" in detail

        # Navigate to the second clause and back; the note must persist.
        await pilot.press("s")
        await pilot.pause()
        assert notes._index == 1
        assert notes._state.current_note(1) == ""
        await pilot.press("k")
        await pilot.pause()
        assert notes._state.current_note(0) == "Escalate [Party A]"
        table = notes.query_one("#amber-overview", DataTable)
        assert "Escalate [Party A]" in str(table.get_cell("0", "c-note"))

        # Clear the note with an empty value.
        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#annotate-input", Input).value = ""
        await pilot.press("enter")
        await pilot.pause()
        assert notes._state.current_note(0) == ""
        assert notes._state.notes == {}
        assert str(table.get_cell("0", "c-note")) == ""
        app.pop_screen()
        await pilot.pause()

        # ── 4. Duplicate clause ids share a note (collision, screen level) ──
        dup = AmberQueueScreen(
            report=_report(
                [
                    _assessment("dup", text="first dup clause"),
                    _assessment("dup", text="second dup clause"),
                ]
            )
        )
        app.push_screen(dup)
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#annotate-input", Input).value = "shared note"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        second_detail = str(dup.query_one("#amber-detail", Label).render())
        assert "shared note" in second_detail, "duplicate ids share one note"
        app.pop_screen()
        await pilot.pause()

        # ── 5. Multibyte clause text renders literally in card + table ──────
        mb = AmberQueueScreen(
            report=_report([_assessment("mb", text="保密条款 — notice to [Party A] 😀")])
        )
        app.push_screen(mb)
        await pilot.pause()
        mb_detail = str(mb.query_one("#amber-detail", Label).render())
        assert "保密条款" in mb_detail
        assert "[Party A]" in mb_detail
        assert "😀" in mb_detail
        mb_cell = str(mb.query_one("#amber-overview", DataTable).get_cell("0", "c-text"))
        assert "保密条款" in mb_cell
        assert app.screen is mb
