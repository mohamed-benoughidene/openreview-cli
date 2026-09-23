"""Wiring tests: reaching the clause-graph screen from a finished review.

``ResultScreen`` grew a ``document_paths`` batch and a ``g`` binding that pushes
``GraphSummaryScreen`` for the document currently in view. These drive the real
screens with lightweight report doubles; they never parse a document, so the
graph screen is expected to land on its "file no longer exists" state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from openreview_cli.tui.app import OpenReviewApp
from openreview_cli.tui.screens.graph import GraphSummaryScreen
from openreview_cli.tui.screens.result import ResultScreen


def _report(filename: str) -> Any:
    """Minimal ReviewReport double: only the fields ResultScreen reads."""
    report = MagicMock()
    report.assessments = []
    report.document.filename = filename
    report.summary.green_count = 0
    report.summary.amber_count = 0
    report.summary.red_count = 0
    return report


async def _push_result(app: Any, pilot: Any, screen: ResultScreen) -> ResultScreen:
    app.push_screen(screen)
    await pilot.pause()
    current = app.screen
    assert isinstance(current, ResultScreen)
    return current


@pytest.mark.asyncio
async def test_g_opens_graph_summary_for_the_active_document() -> None:
    """`g` on a finished review opens the graph screen for the reviewed file."""
    path = Path("/reviews/one/reviewed.pdf")

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _push_result(
            app, pilot, ResultScreen(reports=[_report("reviewed.pdf")], document_paths=[path])
        )

        await pilot.press("g")
        await pilot.pause()

        assert isinstance(app.screen, GraphSummaryScreen)
        assert app.screen._document_path == path


@pytest.mark.asyncio
async def test_g_is_unavailable_without_document_paths() -> None:
    """Saved-report screens (no paths) must not offer the graph binding."""
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _push_result(app, pilot, ResultScreen(reports=[_report("reviewed.pdf")]))

        assert screen.check_action("open_clause_graph", ()) is False

        await pilot.press("g")
        await pilot.pause()

        assert isinstance(app.screen, ResultScreen)


@pytest.mark.asyncio
async def test_g_is_unavailable_on_an_error_screen() -> None:
    """An error screen has no reports; `check_action` must not raise."""
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _push_result(
            app,
            pilot,
            ResultScreen(reports=[], mode="precheck", error="pipeline exploded"),
        )

        assert screen.check_action("open_clause_graph", ()) is False

        await pilot.press("g")
        await pilot.pause()

        assert isinstance(app.screen, ResultScreen)


@pytest.mark.asyncio
async def test_g_follows_the_active_document_in_a_batch() -> None:
    """The path opened tracks the document paged to with `]`."""
    paths = [Path("/reviews/batch/one.pdf"), Path("/reviews/batch/two.pdf")]
    reports = [_report("one.pdf"), _report("two.pdf")]

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _push_result(app, pilot, ResultScreen(reports=reports, document_paths=paths))

        await pilot.press("]")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ResultScreen)
        assert screen._current_report == 1

        await pilot.press("g")
        await pilot.pause()

        assert isinstance(app.screen, GraphSummaryScreen)
        assert app.screen._document_path == paths[1]


@pytest.mark.asyncio
async def test_g_is_unavailable_when_the_index_runs_past_the_paths() -> None:
    """More reports than paths: the out-of-range document has no graph."""
    paths = [Path("/reviews/partial/one.pdf")]
    reports = [_report("one.pdf"), _report("two.pdf")]

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _push_result(app, pilot, ResultScreen(reports=reports, document_paths=paths))
        assert screen.check_action("open_clause_graph", ()) is True

        await pilot.press("]")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ResultScreen)
        assert screen._current_report == 1
        assert screen.check_action("open_clause_graph", ()) is False

        await pilot.press("g")
        await pilot.pause()

        assert isinstance(app.screen, ResultScreen)


@pytest.mark.asyncio
async def test_g_falls_back_to_a_basename_match_when_a_report_was_dropped() -> None:
    """``run_review`` drops documents it cannot process, shifting the batch.

    ``one.pdf`` produced no report, so the batch is ``[two.pdf]`` while the
    path batch still holds both; the index alone would open the wrong file, so
    the filename match wins.
    """
    paths = [Path("/reviews/dropped/one.pdf"), Path("/reviews/dropped/two.pdf")]
    reports = [_report("two.pdf")]

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _push_result(app, pilot, ResultScreen(reports=reports, document_paths=paths))

        await pilot.press("g")
        await pilot.pause()

        assert isinstance(app.screen, GraphSummaryScreen)
        assert app.screen._document_path == paths[1]
