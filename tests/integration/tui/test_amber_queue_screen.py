"""Integration tests for the interactive Amber Queue triage screen (Phase 5).

Covers the guided step-by-step triage workflow reached from ``ResultScreen``:

* mounting with flagged/amber clauses,
* step navigation (Next / Previous),
* the Accept (A) / Reject (R) / Note (N) actions,
* switching between the guided card and the overview table (T / O),
* returning to ``ResultScreen`` and persisting the triage decisions,
* literal preservation of bracketed legal text (``markup=False``), and
* the empty-queue guard.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

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
    reasons: list[str] | None = None,
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
    assessment.amber_reasons = reasons if reasons is not None else ["low_confidence"]  # type: ignore[assignment]
    return assessment


def _report(assessments: list[ClauseAssessment], filename: str = "nda.docx") -> ReviewReport:
    return ReviewReport(
        document=DocMeta(
            filename=filename,
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


def _amber_report(*clause_ids: str) -> ReviewReport:
    return _report([_assessment(cid) for cid in clause_ids])


def _queue_screen(app):
    from openreview_cli.tui.screens.amber_queue import AmberQueueScreen

    for screen in app._screen_stack:
        if isinstance(screen, AmberQueueScreen):
            return screen
    return None


# ── Mounting ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_amber_queue_mounts_only_flagged_clauses() -> None:
    """Only amber clauses enter the queue; the guided card shows the first one."""
    from textual.widgets import DataTable, Label

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.amber_queue import AmberQueueScreen

    report = _report(
        [
            _assessment("c1", text="Amber clause c1"),
            _assessment("c2", color="green", text="Green clause c2"),
            _assessment("c3", text="Amber clause c3"),
        ]
    )

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = AmberQueueScreen(report=report)
        app.push_screen(screen)
        await pilot.pause()

        assert screen._state.total == 2
        assert [a.clause_id for a in screen._state.clauses] == ["c1", "c3"]
        assert screen._index == 0

        header = str(screen.query_one("#amber-header").render())
        assert "1 of 2" in header, header

        detail = str(screen.query_one("#amber-detail", Label).render())
        assert "c1" in detail, detail
        assert "Amber clause c1" in detail, detail
        assert "low_confidence" in detail, detail

        table = screen.query_one("#amber-overview", DataTable)
        assert table.row_count == 2
        assert table.get_cell("0", "c-decision") == "pending"
        assert table.get_cell("1", "c-decision") == "pending"


@pytest.mark.asyncio
async def test_amber_queue_empty_queue_is_inert() -> None:
    """A report with no amber clauses mounts without raising and disables actions."""
    from textual.widgets import Button

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.amber_queue import AmberQueueScreen

    report = _report([_assessment("c1", color="green"), _assessment("c2", color="red")])

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = AmberQueueScreen(report=report)
        app.push_screen(screen)
        await pilot.pause()

        assert screen._state.total == 0
        header = str(screen.query_one("#amber-header").render())
        assert "no amber" in header.lower(), header
        for btn_id in ("#btn-accept", "#btn-reject", "#btn-note", "#btn-next", "#btn-prev"):
            assert screen.query_one(btn_id, Button).disabled is True

        # Every action key is a safe no-op on an empty queue.
        for key in ("a", "r", "n", "s", "j", "k", "down", "up", "t", "o"):
            await pilot.press(key)
        await pilot.pause()

        assert screen._state.decided == 0
        assert app.screen is screen


# ── Step-by-step navigation ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_amber_queue_next_and_previous_keys_step_through_clauses() -> None:
    """S/J/Down advance, K/Up step back, both wrapping around the queue."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.amber_queue import AmberQueueScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = AmberQueueScreen(report=_amber_report("c1", "c2", "c3"))
        app.push_screen(screen)
        await pilot.pause()

        assert screen._index == 0

        await pilot.press("s")
        assert screen._index == 1
        await pilot.press("j")
        assert screen._index == 2
        await pilot.press("down")
        assert screen._index == 0, "next past the last clause wraps to the first"

        header = str(screen.query_one("#amber-header").render())
        assert "1 of 3" in header, header

        await pilot.press("k")
        assert screen._index == 2
        await pilot.press("up")
        assert screen._index == 1

        # The guided card follows the cursor.
        detail = str(screen.query_one("#amber-detail").render())
        assert "c2" in detail, detail


# ── Accept / Reject / Note ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_amber_queue_accept_and_reject_record_decisions() -> None:
    """A/R decide the current clause, auto-advance, and update the overview table."""
    from textual.widgets import DataTable

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.amber_queue import AmberQueueScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = AmberQueueScreen(report=_amber_report("c1", "c3"))
        app.push_screen(screen)
        await pilot.pause()

        await pilot.press("a")
        await pilot.pause()
        assert screen._state.accepted == 1
        assert screen._index == 1, "accepting auto-advances to the next pending clause"

        table = screen.query_one("#amber-overview", DataTable)
        assert table.get_cell("0", "c-decision") == "accepted"
        assert table.get_cell("1", "c-decision") == "pending"

        await pilot.press("r")
        await pilot.pause()
        assert screen._state.flagged == 1
        assert screen._state.decided == 2
        assert table.get_cell("1", "c-decision") == "flagged"

        header = str(screen.query_one("#amber-header").render())
        assert "queue complete" in header, header


@pytest.mark.asyncio
async def test_amber_queue_action_buttons_mirror_the_keys() -> None:
    """The nav buttons drive the same actions as the keybindings."""
    from textual.widgets import Button, DataTable

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.amber_queue import AmberQueueScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = AmberQueueScreen(report=_amber_report("c1", "c2"))
        app.push_screen(screen)
        await pilot.pause()

        # Labels use parentheses: Textual parses "[A]" in a Button label as markup.
        assert str(screen.query_one("#btn-accept", Button).label) == "Accept (A)"
        assert str(screen.query_one("#btn-reject", Button).label) == "Reject (R)"

        await pilot.click("#btn-accept")
        await pilot.pause()
        assert screen._state.accepted == 1
        assert screen._index == 1

        await pilot.click("#btn-reject")
        await pilot.pause()
        assert screen._state.flagged == 1
        assert screen.query_one("#amber-overview", DataTable).get_cell("1", "c-decision") == (
            "flagged"
        )

        await pilot.click("#btn-close")
        await pilot.pause()
        assert _queue_screen(app) is None


@pytest.mark.asyncio
async def test_amber_queue_note_modal_records_annotation() -> None:
    """N opens the note editor; Enter stores the annotation, Esc leaves it alone."""
    from textual.widgets import DataTable, Input, Label

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.amber_queue import AmberQueueScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = AmberQueueScreen(report=_amber_report("c1", "c2"))
        app.push_screen(screen)
        await pilot.pause()

        await pilot.press("n")
        await pilot.pause()
        assert app.screen is not screen, "N must open the annotate modal"

        note_input = app.screen.query_one("#annotate-input", Input)
        note_input.value = "Escalate [Party A] before signature"
        await pilot.press("enter")
        await pilot.pause()

        assert app.screen is screen, "saving the note returns to the queue"
        assert screen._state.current_note(0) == "Escalate [Party A] before signature"
        assert screen._state.decided == 0, "annotating is not a decision"

        table = screen.query_one("#amber-overview", DataTable)
        assert "Escalate [Party A] before signature" in str(table.get_cell("0", "c-note"))
        detail = str(screen.query_one("#amber-detail", Label).render())
        assert "Escalate [Party A] before signature" in detail, detail

        # A cancelled edit must not clobber the stored note.
        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#annotate-input", Input).value = "discard me"
        await pilot.press("escape")
        await pilot.pause()

        assert app.screen is screen
        assert screen._state.current_note(0) == "Escalate [Party A] before signature"


# ── Guided card <-> overview table ────────────────────────────────────


@pytest.mark.asyncio
async def test_amber_queue_toggles_between_card_and_overview() -> None:
    """T/O switch between the guided card and the overview table."""
    from textual.widgets import DataTable

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.amber_queue import AmberQueueScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = AmberQueueScreen(report=_amber_report("c1", "c2"))
        app.push_screen(screen)
        await pilot.pause()

        guided = screen.query_one("#amber-guided")
        table = screen.query_one("#amber-overview", DataTable)

        assert guided.display is True
        assert table.display is False, "the guided card is the default view"

        await pilot.press("t")
        await pilot.pause()
        assert table.display is True
        assert guided.display is False

        await pilot.press("o")
        await pilot.pause()
        assert table.display is False
        assert guided.display is True

        # The overview table is retained with one row per amber clause.
        assert table.row_count == 2


# ── Returning to ResultScreen ─────────────────────────────────────────


@pytest.mark.parametrize("key", ["escape", "q"])
@pytest.mark.asyncio
async def test_amber_queue_close_returns_to_result_screen_and_keeps_decisions(key: str) -> None:
    """Esc/Q return to the result screen with the triage decisions preserved."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.amber_queue import AmberQueueScreen
    from openreview_cli.tui.screens.result import ResultScreen

    report = _amber_report("c1", "c2")

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        result = ResultScreen(reports=[report], mode="precheck")
        app.push_screen(result)
        await pilot.pause()

        await pilot.click("#btn-amber-queue")
        await pilot.pause()

        queue = _queue_screen(app)
        assert isinstance(queue, AmberQueueScreen)

        await pilot.press("a")
        await pilot.pause()
        await pilot.press(key)
        await pilot.pause()

        assert app.screen is result
        assert result._amber_state is not None
        assert result._amber_state.accepted == 1


# ── Markup safety ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_amber_queue_preserves_bracketed_clause_text() -> None:
    """Bracketed legal text (including uppercase-initial tags) renders literally."""
    from textual.widgets import DataTable, Label

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.amber_queue import AmberQueueScreen

    report = _report(
        [
            _assessment(
                "c1",
                text="Confidentiality [intentionally omitted] term; notice to [Party A].",
            )
        ]
    )

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = AmberQueueScreen(report=report)
        app.push_screen(screen)
        await pilot.pause()

        detail = str(screen.query_one("#amber-detail", Label).render())
        assert "[intentionally omitted]" in detail, detail
        assert "[Party A]" in detail, detail

        # The overview table carries the same text (a Rich Text cell, never markup).
        cell = str(screen.query_one("#amber-overview", DataTable).get_cell("0", "c-text"))
        assert "[intentional" in cell, cell


# ── ResultScreen entry point ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_result_screen_offers_amber_queue_only_when_amber_exists() -> None:
    """The entry button appears with the amber count, and only then."""
    from textual.widgets import Button

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[_amber_report("c1", "c2")], mode="precheck"))
        await pilot.pause()

        button = app.screen.query_one("#btn-amber-queue", Button)
        assert str(button.label) == "Amber queue (2)"

        await pilot.click("#btn-amber-queue")
        await pilot.pause()
        assert _queue_screen(app) is not None


@pytest.mark.asyncio
async def test_result_screen_triage_binding_opens_amber_queue() -> None:
    """T opens triage from the result screen; Esc returns."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[_amber_report("c1")], mode="precheck"))
        await pilot.pause()

        await pilot.press("t")
        await pilot.pause()
        assert _queue_screen(app) is not None

        await pilot.press("escape")
        await pilot.pause()
        assert _queue_screen(app) is None


@pytest.mark.asyncio
async def test_result_screen_amber_queue_absent_without_amber() -> None:
    """No amber clauses means no entry point, and T stays a safe no-op."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    green_only = _report([_assessment("c1", color="green")])

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[green_only], mode="precheck"))
        await pilot.pause()

        assert list(app.screen.query("#btn-amber-queue")) == []

        await pilot.press("t")
        await pilot.pause()
        assert _queue_screen(app) is None
