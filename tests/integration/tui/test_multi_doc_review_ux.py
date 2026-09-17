"""Integration tests for multi-document batch review UX in ``ResultScreen``.

Phase 3 / P2T4 — ``run_review`` returns one :class:`ReviewReport` per document
and ``ProgressScreen`` forwards that whole list to ``ResultScreen``.  These
tests pin the batch-review contract:

* the active document's filename / context is shown in the header,
* multiple documents can be summarised and switched between,
* a 0-clause document (single or one of many) never blanks the screen or
  raises ``UnboundLocalError``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_assessment(
    color: str = "green",
    confidence: float = 0.92,
    text: str = "Test clause",
    position: str = "preferred",
) -> MagicMock:
    a = MagicMock()
    a.color = color
    a.confidence = confidence
    a.effective_confidence = confidence
    a.clause_text = text
    a.position.value = position
    a.reasoning = "Test reasoning"
    a.qa_revised_rationale = None
    a.clause_ref = None
    return a


def _make_report(
    assessments: list | None = None,
    filename: str = "test.pdf",
) -> MagicMock:
    r = MagicMock()
    asm = list(assessments or [])
    r.assessments = asm
    r.document.filename = filename
    r.document.page_count = 1
    r.document.clause_count = len(asm)
    r.mode = "precheck"
    r.confidence_threshold = 0.7
    return r


def _get_result_screen(app):
    """Return the ResultScreen on the screen stack, if any."""
    from openreview_cli.tui.screens.result import ResultScreen

    for s in app._screen_stack:
        if isinstance(s, ResultScreen):
            return s
    return None


def _get_result_screen_checked(app):
    s = _get_result_screen(app)
    assert s is not None, "ResultScreen should be on screen stack"
    return s


def _all_static_text(screen) -> str:
    from textual.widgets import Static

    return "\n".join(str(w.render()) for w in screen.query(Static))


# ── Document context / filename in the header ─────────────────────────


@pytest.mark.asyncio
async def test_single_document_shows_filename_in_header() -> None:
    """A single report must surface its document filename in the header."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    report = _make_report([_make_assessment()], filename="nda-acme.pdf")

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[report], mode="precheck"))
        await pilot.pause()

        screen = _get_result_screen_checked(app)
        header = str(screen.query_one("#result-header").render())
        assert "nda-acme.pdf" in header, header

        # A single document has nothing to switch between.
        assert len(screen.query("#btn-next-doc")) == 0
        assert len(screen.query("#btn-prev-doc")) == 0


@pytest.mark.asyncio
async def test_multi_document_context_and_batch_summary() -> None:
    """Multiple reports show ``Document i of n`` plus an aggregate summary."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    doc_a = _make_report(
        [_make_assessment(color="green", text="A1"), _make_assessment(text="A2")],
        filename="doc-a.pdf",
    )
    doc_b = _make_report(
        [_make_assessment(color="red", text="B1"), _make_assessment(color="amber", text="B2")],
        filename="doc-b.pdf",
    )

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[doc_a, doc_b], mode="precheck"))
        await pilot.pause()

        screen = _get_result_screen_checked(app)
        header = str(screen.query_one("#result-header").render())
        assert "doc-a.pdf" in header, header

        context = str(screen.query_one("#doc-context").render())
        assert "Document 1 of 2" in context, context
        assert "doc-a.pdf" in context, context
        # Aggregate across the whole batch (2 + 2 clauses in 2 documents).
        assert "2 documents" in context, context
        assert "4 clauses" in context, context

        # A document switcher is offered.
        assert screen.query_one("#btn-next-doc") is not None
        assert screen.query_one("#btn-prev-doc") is not None


# ── Switching between documents ───────────────────────────────────────


@pytest.mark.asyncio
async def test_next_doc_button_switches_active_document() -> None:
    """Clicking the next-document control swaps the visible report."""
    from textual.widgets import Label, ListView

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    doc_a = _make_report([_make_assessment(text="A clause")], filename="doc-a.pdf")
    doc_b = _make_report([_make_assessment(color="red", text="B clause")], filename="doc-b.pdf")

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[doc_a, doc_b], mode="precheck"))
        await pilot.pause()

        await pilot.click("#btn-next-doc")
        await pilot.pause()

        screen = _get_result_screen_checked(app)
        context = str(screen.query_one("#doc-context").render())
        assert "Document 2 of 2" in context, context
        assert "doc-b.pdf" in context, context

        clause_text = str(screen.query_one("#clause-list-pane", ListView).query_one(Label).render())
        assert "B clause" in clause_text, clause_text

        # At the last document the forward control is disabled.
        assert screen.query_one("#btn-next-doc").disabled is True
        assert screen.query_one("#btn-prev-doc").disabled is False


@pytest.mark.asyncio
async def test_bracket_keys_switch_documents_both_ways() -> None:
    """The ``[`` / ``]`` bindings move between batch documents and back."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    doc_a = _make_report([_make_assessment(text="A clause")], filename="doc-a.pdf")
    doc_b = _make_report([_make_assessment(text="B clause")], filename="doc-b.pdf")

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[doc_a, doc_b], mode="precheck"))
        await pilot.pause()

        await pilot.press("]")
        await pilot.pause()
        screen = _get_result_screen_checked(app)
        assert "doc-b.pdf" in str(screen.query_one("#doc-context").render())

        await pilot.press("[")
        await pilot.pause()
        screen = _get_result_screen_checked(app)
        context = str(screen.query_one("#doc-context").render())
        assert "doc-a.pdf" in context, context
        assert "Document 1 of 2" in context, context


# ── Degenerate inputs: 0 clauses / 0 reports ──────────────────────────


@pytest.mark.asyncio
async def test_single_document_zero_clauses_does_not_blank_or_crash() -> None:
    """One report with no clauses renders an informative empty state."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    report = _make_report([], filename="empty.pdf")

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[report], mode="precheck"))
        await pilot.pause()

        screen = _get_result_screen_checked(app)
        assert "empty.pdf" in str(screen.query_one("#result-header").render())
        assert "No clauses found" in _all_static_text(screen)
        # Export remains reachable rather than the screen going blank.
        assert screen.query_one("#btn-export") is not None


@pytest.mark.asyncio
async def test_zero_clause_document_in_batch_can_switch_to_populated_doc() -> None:
    """A 0-clause document in a batch must not block reaching the others."""
    from textual.widgets import Label, ListView

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    empty = _make_report([], filename="empty.pdf")
    full = _make_report([_make_assessment(text="Full clause")], filename="full.pdf")

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[empty, full], mode="precheck"))
        await pilot.pause()

        screen = _get_result_screen_checked(app)
        assert "No clauses found" in _all_static_text(screen)

        await pilot.click("#btn-next-doc")
        await pilot.pause()

        screen = _get_result_screen_checked(app)
        assert "full.pdf" in str(screen.query_one("#doc-context").render())
        clause_text = str(screen.query_one("#clause-list-pane", ListView).query_one(Label).render())
        assert "Full clause" in clause_text, clause_text


@pytest.mark.asyncio
async def test_empty_reports_list_is_not_blank() -> None:
    """No reports at all still yields a usable screen header and empty state."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[], mode="precheck"))
        await pilot.pause()

        screen = _get_result_screen_checked(app)
        assert screen.query_one("#result-header") is not None
        assert "No clauses found" in _all_static_text(screen)
        assert screen.query_one("#btn-export") is not None


# ── Exporting the document currently in view ──────────────────────────


@pytest.mark.asyncio
async def test_export_targets_active_document_after_switch() -> None:
    """After switching documents, export writes the visible report."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    doc_a = _make_report([_make_assessment(text="A clause")], filename="doc-a.pdf")
    doc_b = _make_report([_make_assessment(text="B clause")], filename="doc-b.pdf")

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch("openreview_cli.review.memo.exporter.MemoExporter") as mock_exporter_cls:
            mock_exporter = MagicMock()
            mock_exporter.export.return_value = {MagicMock(): "review_results/review-result.md"}
            mock_exporter_cls.return_value = mock_exporter

            app.push_screen(ResultScreen(reports=[doc_a, doc_b], mode="precheck"))
            await pilot.pause()

            await pilot.click("#btn-next-doc")
            await pilot.pause()
            await pilot.click("#btn-export")
            await pilot.pause()
            await pilot.click("#btn-fmt-md")
            await pilot.pause()
            await pilot.click("#btn-save")
            await pilot.pause()

            assert mock_exporter_cls.call_args.kwargs["report"] is doc_b
