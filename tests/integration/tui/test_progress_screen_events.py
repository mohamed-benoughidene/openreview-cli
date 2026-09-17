"""Integration tests: ProgressScreen driven by real pipeline ProgressEvents (P1/T5).

These exercise the event plumbing added in Phase 3: the review pipeline emits
``ProgressEvent``s from a worker thread, and the screen marshals them back onto
the UI thread to advance the progress bar and the five step checkmarks.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest

from openreview_cli.pipeline.progress import ProgressEvent

_STEP_IDS = ("step-parse", "step-pii", "step-extract", "step-qa", "step-report")

# Unicode markers the screen renders for each step state.
_PENDING = "\u25cb"
_ACTIVE = "\u25cf"
_DONE = "\u2713"
_FAILED = "\u2717"


def _progress_screen(app: Any) -> Any:
    """Return the mounted ProgressScreen or fail the test."""
    from openreview_cli.tui.screens.progress import ProgressScreen

    for screen in app._screen_stack:
        if isinstance(screen, ProgressScreen):
            return screen
    raise AssertionError("ProgressScreen should be on the screen stack")


def _has_progress_screen(app: Any) -> bool:
    from openreview_cli.tui.screens.progress import ProgressScreen

    return any(isinstance(screen, ProgressScreen) for screen in app._screen_stack)


def _step_text(screen: Any, step_id: str) -> str:
    return str(screen.query_one(f"#{step_id}").render())


def _emitting_runner(
    events: list[ProgressEvent],
) -> Callable[..., list[Any]]:
    """Build a fake ``run_review_via_tui`` that replays *events* on its callback."""

    def fake_run_via_tui(**kwargs: Any) -> list[Any]:
        callback = kwargs["progress_callback"]
        for event in events:
            callback(event)
        return []

    return fake_run_via_tui


def _three_stage_events() -> list[ProgressEvent]:
    """The pipeline emits running/completed for parse, strip, and review."""
    return [
        ProgressEvent(0, 3, "parse", "running"),
        ProgressEvent(0, 3, "parse", "completed"),
        ProgressEvent(1, 3, "strip", "running"),
        ProgressEvent(1, 3, "strip", "completed"),
        ProgressEvent(2, 3, "review", "running"),
        ProgressEvent(2, 3, "review", "completed"),
    ]


@pytest.mark.asyncio
async def test_progress_screen_advances_on_pipeline_events() -> None:
    """ProgressBar and step labels must reflect emitted pipeline events (P1/T5)."""
    from textual.widgets import ProgressBar

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.progress import ProgressScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch(
            "openreview_cli.tui.domain.review.run_review_via_tui",
            side_effect=_emitting_runner(_three_stage_events()),
        ):
            app.call_later = lambda _cb: None  # type: ignore[method-assign]
            app.push_screen(ProgressScreen(paths=[], mode="precheck"))
            await asyncio.sleep(0.4)  # let the yield points + worker thread finish
            await pilot.pause()

            screen = _progress_screen(app)
            bar = screen.query_one("#progress-bar", ProgressBar)
            assert bar.progress == 5

            for step_id in _STEP_IDS:
                text = _step_text(screen, step_id)
                assert _DONE in text, (step_id, text)


@pytest.mark.asyncio
async def test_progress_screen_steps_start_pending() -> None:
    """Before any event arrives every step shows the pending marker."""
    from textual.widgets import ProgressBar

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.progress import ProgressScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch(
            "openreview_cli.tui.domain.review.run_review_via_tui",
            side_effect=_emitting_runner([]),
        ):
            app.call_later = lambda _cb: None  # type: ignore[method-assign]
            app.push_screen(ProgressScreen(paths=[], mode="precheck"))
            await pilot.pause()

            screen = _progress_screen(app)
            for step_id in _STEP_IDS:
                assert _PENDING in _step_text(screen, step_id), step_id

            assert screen.query_one("#progress-bar", ProgressBar).progress == 0


@pytest.mark.asyncio
async def test_progress_screen_marks_running_stage_active() -> None:
    """A ``running`` event marks its step as in progress and advances the bar."""
    from textual.widgets import ProgressBar

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.progress import ProgressScreen

    events = [
        ProgressEvent(0, 3, "parse", "running"),
        ProgressEvent(0, 3, "parse", "completed"),
        ProgressEvent(1, 3, "strip", "running"),
    ]

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch(
            "openreview_cli.tui.domain.review.run_review_via_tui",
            side_effect=_emitting_runner(events),
        ):
            app.call_later = lambda _cb: None  # type: ignore[method-assign]
            app.push_screen(ProgressScreen(paths=[], mode="precheck"))
            await asyncio.sleep(0.4)
            await pilot.pause()

            screen = _progress_screen(app)
            assert _DONE in _step_text(screen, "step-parse")
            assert _ACTIVE in _step_text(screen, "step-pii")
            assert _PENDING in _step_text(screen, "step-extract")
            assert screen.query_one("#progress-bar", ProgressBar).progress == 1


@pytest.mark.asyncio
async def test_progress_screen_marks_failed_stage() -> None:
    """A ``failed`` event marks its step with the failure marker."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.progress import ProgressScreen

    events = [
        ProgressEvent(0, 3, "parse", "running"),
        ProgressEvent(0, 3, "parse", "failed"),
    ]

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch(
            "openreview_cli.tui.domain.review.run_review_via_tui",
            side_effect=_emitting_runner(events),
        ):
            app.call_later = lambda _cb: None  # type: ignore[method-assign]
            app.push_screen(ProgressScreen(paths=[], mode="precheck"))
            await asyncio.sleep(0.4)
            await pilot.pause()

            screen = _progress_screen(app)
            assert _FAILED in _step_text(screen, "step-parse")


@pytest.mark.asyncio
async def test_progress_screen_surfaces_worker_error() -> None:
    """A worker exception must not freeze the screen; it reports the failure."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.progress import ProgressScreen
    from openreview_cli.tui.screens.result import ResultScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch(
            "openreview_cli.tui.domain.review.run_review_via_tui",
            side_effect=RuntimeError("pipeline exploded"),
        ):
            app.push_screen(ProgressScreen(paths=[], mode="precheck"))
            await asyncio.sleep(0.4)
            await pilot.pause()
            await pilot.pause()

            result = next(
                (s for s in app._screen_stack if isinstance(s, ResultScreen)),
                None,
            )
            assert result is not None, "an error ResultScreen should be pushed"
            assert result._error == "pipeline exploded"


@pytest.mark.asyncio
async def test_progress_screen_cancel_pops_cleanly() -> None:
    """Cancelling mid-run pops the screen and leaves the app responsive."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal
    from openreview_cli.tui.screens.progress import ProgressScreen

    def slow_run_via_tui(**_kwargs: Any) -> list[Any]:
        time.sleep(0.6)  # keep the worker busy so no result is pushed yet
        return []

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch(
            "openreview_cli.tui.domain.review.run_review_via_tui",
            side_effect=slow_run_via_tui,
        ):
            app.push_screen(ProgressScreen(paths=[], mode="precheck"))
            await asyncio.sleep(0.3)  # past the yield loop; worker now running
            await pilot.pause()

            screen = _progress_screen(app)
            await pilot.click(screen.query_one("#btn-cancel"))
            await pilot.pause()
            await pilot.pause()

            assert any(isinstance(s, ConfirmModal) for s in app._screen_stack)

            await pilot.click("#yes")
            await asyncio.sleep(0.1)
            await pilot.pause()
            await pilot.pause()

            # Cancellation completed and the event loop kept processing input
            # (a frozen app would have hung the clicks above until timeout).
            assert not _has_progress_screen(app)
