"""Integration tests for the read-only clause-graph screen.

These drive the real ``nda_with_pii.pdf`` fixture through the real parse path,
so the numbers on screen are the numbers the parser measures. Loading runs on a
worker thread, so every wait awaits the screen's own load task instead of a
fixed sleep.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

from docx import Document
from textual.widgets import Static

from openreview_cli.tui.app import OpenReviewApp
from openreview_cli.tui.screens.graph import GraphSummaryScreen

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
REAL_PDF = FIXTURES / "nda_with_pii.pdf"


def _text(screen: GraphSummaryScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


def _body(screen: GraphSummaryScreen) -> str:
    return _text(screen, "#graph-body")


def _subtitle(screen: GraphSummaryScreen) -> str:
    return _text(screen, "#graph-subtitle")


async def _open(pilot: Any, app: OpenReviewApp, path: Path | None = None) -> GraphSummaryScreen:
    app.push_screen(GraphSummaryScreen(path))
    await pilot.pause()
    screen = app.screen
    assert isinstance(screen, GraphSummaryScreen)
    return screen


async def _await_load(pilot: Any, screen: GraphSummaryScreen) -> None:
    task = screen._load_task
    if task is not None:
        await task
    await pilot.pause()


async def test_real_pdf_renders_real_metrics_and_score() -> None:
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, REAL_PDF)
        await _await_load(pilot, screen)

        body = _body(screen)
        assert "Density: 0.000" in body
        assert "Max depth: 1" in body
        assert "Orphan ratio: 0.000" in body
        assert "Broken cross-refs: 0" in body
        assert "Definition coverage: 1.000" in body
        assert "Health score: 98/100" in body

        subtitle = _subtitle(screen)
        assert "nda_with_pii.pdf" in subtitle
        assert "5 nodes" in subtitle
        assert "0 edges" in subtitle


async def test_real_pdf_shows_the_no_hierarchy_caveat() -> None:
    """No clause parser populates parent_id, so the score needs the caveat."""
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, REAL_PDF)
        await _await_load(pilot, screen)

        body = _body(screen)
        assert "No clause hierarchy was detected in this document" in body


async def test_zero_clause_document_renders_no_clauses_and_no_score(tmp_path: Path) -> None:
    docx_path = tmp_path / "blank.docx"
    Document().save(str(docx_path))

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, docx_path)
        await _await_load(pilot, screen)

        body = _body(screen)
        assert "No clauses detected in this document." in body
        assert "Health score" not in body
        assert "Density" not in body
        assert "0 nodes" in _subtitle(screen)


async def test_missing_file_renders_the_error_line_and_survives(tmp_path: Path) -> None:
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, tmp_path / "gone.pdf")
        await _await_load(pilot, screen)

        assert "Could not read gone.pdf: the file no longer exists." in _body(screen)
        # The screen is still mounted and interactive: no traceback escaped.
        assert app.screen is screen


async def test_escape_pops_back_to_the_previous_screen() -> None:
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, REAL_PDF)
        await _await_load(pilot, screen)

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, GraphSummaryScreen)


async def test_no_path_renders_the_no_document_line() -> None:
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, None)

        assert "No document supplied" in _body(screen)
        assert screen._load_task is None


# ── Regression: a load that outlives the screen must not touch the DOM ──


async def test_escape_while_load_is_running_does_not_crash() -> None:
    """Escape before the load finishes must not leave a task that touches the DOM.

    Regression: ``on_mount`` started ``_load`` as a bare task, so a load that
    finished after the screen popped called ``_show`` -> ``query_one`` on a
    detached DOM -> ``NoMatches`` inside a task nobody awaits.
    """
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open(pilot, app, REAL_PDF)
        # Deliberately do NOT await the load task: Escape lands while the
        # worker thread may still be parsing.
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, GraphSummaryScreen)
        # Let a late-finishing load run; it must be dropped, not rendered.
        await pilot.pause(0.5)
        assert not isinstance(app.screen, GraphSummaryScreen)


async def test_load_finishing_after_escape_is_dropped(monkeypatch: Any) -> None:
    """A load released after Escape must not query the detached DOM.

    The stub blocks inside the worker thread so Escape always lands mid-load --
    the exact race the old code lost. Deterministic, no timing assumptions.
    """
    import openreview_cli.tui.screens.graph as graph_screen_module

    started = threading.Event()
    release = threading.Event()
    real_summary = graph_screen_module.graph_summary_via_tui

    def blocked_summary(path: Path) -> Any:
        started.set()
        assert release.wait(timeout=15)
        return real_summary(path)

    monkeypatch.setattr(graph_screen_module, "graph_summary_via_tui", blocked_summary)

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(GraphSummaryScreen(REAL_PDF))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, GraphSummaryScreen)

        # Wait until the worker thread is actually inside the (blocked) load.
        await asyncio.to_thread(started.wait, 10)
        assert screen._load_task is not None and not screen._load_task.done()

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, GraphSummaryScreen)
        # Popping the screen must cancel the in-flight load.
        assert screen._load_task is not None
        assert screen._load_task.cancelled()

        # Now let the load unwind into a screen that is gone.
        release.set()
        await pilot.pause(0.5)
        assert not isinstance(app.screen, GraphSummaryScreen)


async def test_show_is_a_noop_once_the_screen_is_unmounted() -> None:
    """``_show`` after unmount must return early instead of raising NoMatches."""
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _open(pilot, app, REAL_PDF)
        await _await_load(pilot, screen)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, GraphSummaryScreen)

        # Before the guard this raised NoMatches from the load task.
        screen._show(subtitle="late", body="late", status="late")
