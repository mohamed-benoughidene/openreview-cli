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


# ── Button affordance ─────────────────────────────────────────────────
# The `g` binding is invisible on screen (the app-level Footer renders only the
# app's own bindings), so the row carries a button instead. It must track the
# very condition that enables the binding: a known on-disk path for the
# document in view.


@pytest.mark.asyncio
async def test_clause_graph_button_opens_the_screen() -> None:
    """A visible button, not just the `g` binding, reaches the graph screen."""
    path = Path("/reviews/button/reviewed.pdf")

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _push_result(
            app, pilot, ResultScreen(reports=[_report("reviewed.pdf")], document_paths=[path])
        )
        assert screen.query("#btn-clause-graph")

        await pilot.click("#btn-clause-graph")
        await pilot.pause()

        assert isinstance(app.screen, GraphSummaryScreen)
        assert app.screen._document_path == path


@pytest.mark.asyncio
async def test_clause_graph_button_is_absent_without_document_paths() -> None:
    """Saved-report screens (no paths) must not offer the button either."""
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _push_result(app, pilot, ResultScreen(reports=[_report("reviewed.pdf")]))

        assert screen.check_action("open_clause_graph", ()) is False
        assert not screen.query("#btn-clause-graph")


@pytest.mark.asyncio
async def test_clause_graph_button_is_absent_on_an_error_screen() -> None:
    """An error screen has no reports; compose must not raise and shows no button."""
    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _push_result(
            app,
            pilot,
            ResultScreen(
                reports=[],
                mode="precheck",
                error="pipeline exploded",
                # Paths are known but there is no report to name one: the button
                # keys off the report in view, not off `_document_paths`.
                document_paths=[Path("/reviews/error/gone.pdf")],
            ),
        )

        assert screen.check_action("open_clause_graph", ()) is False
        assert not screen.query("#btn-clause-graph")


@pytest.mark.asyncio
async def test_clause_graph_button_follows_the_active_document_in_a_batch() -> None:
    """After paging with `]`, the button opens the path of the document in view."""
    paths = [Path("/reviews/button-batch/one.pdf"), Path("/reviews/button-batch/two.pdf")]
    reports = [_report("one.pdf"), _report("two.pdf")]

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _push_result(app, pilot, ResultScreen(reports=reports, document_paths=paths))

        await pilot.press("]")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ResultScreen)
        assert screen._current_report == 1
        assert screen.query("#btn-clause-graph")

        await pilot.click("#btn-clause-graph")
        await pilot.pause()

        assert isinstance(app.screen, GraphSummaryScreen)
        assert app.screen._document_path == paths[1]


@pytest.mark.asyncio
async def test_clause_graph_button_is_present_and_clickable_at_the_smallest_viewport() -> None:
    """The button must stay inside the nav row at the smallest supported size."""
    path = Path("/reviews/small/reviewed.pdf")

    app = OpenReviewApp()
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await _push_result(
            app, pilot, ResultScreen(reports=[_report("reviewed.pdf")], document_paths=[path])
        )

        button = screen.query_one("#btn-clause-graph")
        assert button is not None
        # Fully on screen: not clipped off the right edge of the nav row.
        assert button.region.width > 0
        assert button.region.right <= 80

        await pilot.click("#btn-clause-graph")
        await pilot.pause()

        assert isinstance(app.screen, GraphSummaryScreen)
        assert app.screen._document_path == path
