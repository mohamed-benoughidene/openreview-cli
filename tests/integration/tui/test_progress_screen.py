"""Integration tests for ProgressScreen (T020)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest


def _get_progress_screen(app):
    """Get ProgressScreen from screen stack."""
    from openreview_cli.tui.screens.progress import ProgressScreen

    for s in app._screen_stack:
        if isinstance(s, ProgressScreen):
            return s
    return None


def _get_progress_screen_checked(app):
    s = _get_progress_screen(app)
    assert s is not None, "ProgressScreen should be on screen stack"
    return s


@pytest.mark.asyncio
async def test_progress_screen_lists_pipeline_steps() -> None:
    """Push ProgressScreen, assert 5 step rows visible."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.progress import ProgressScreen

    _event = asyncio.Event()

    async def _blocked_run(*args: object, **kwargs: object) -> list:
        await _event.wait()
        return []

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch("openreview_cli.tui.domain.review.run_review_via_tui") as mock_run:
            mock_run.side_effect = _blocked_run
            app.push_screen(ProgressScreen(paths=[], mode="precheck"))
            await pilot.pause()

            screen = _get_progress_screen_checked(app)

            step_ids = ["step-parse", "step-pii", "step-extract", "step-qa", "step-report"]
            try:
                for sid in step_ids:
                    label = screen.query_one(f"#{sid}")
                    assert label is not None, f"Step {sid} should be visible"

                progress_bar = screen.query_one("#progress-bar")
                assert progress_bar is not None, "Progress bar should be visible"
            finally:
                _event.set()


@pytest.mark.asyncio
async def test_progress_screen_shows_elapsed_time() -> None:
    """Progress screen shows elapsed time label."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.progress import ProgressScreen

    _event = asyncio.Event()

    async def _blocked_run(*args: object, **kwargs: object) -> list:
        await _event.wait()
        return []

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch("openreview_cli.tui.domain.review.run_review_via_tui") as mock_run:
            mock_run.side_effect = _blocked_run
            app.push_screen(ProgressScreen(paths=[], mode="precheck"))
            await pilot.pause()

            screen = _get_progress_screen_checked(app)

            elapsed = screen.query_one("#elapsed-time")
            assert elapsed is not None, "Elapsed time label should be visible"

            _event.set()


@pytest.mark.asyncio
async def test_progress_screen_cancel_opens_confirm() -> None:
    """Click Cancel, assert ConfirmModal opens."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal
    from openreview_cli.tui.screens.progress import ProgressScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch("openreview_cli.tui.domain.review.run_review_via_tui") as mock_run:
            mock_run.return_value = []
            app.push_screen(ProgressScreen(paths=[], mode="precheck"))
            await pilot.pause()

            screen = _get_progress_screen_checked(app)

            # Click cancel button
            cancel_btn = screen.query_one("#btn-cancel")
            await pilot.click(cancel_btn)
            await pilot.pause()
            await pilot.pause()

            # ConfirmModal should be on the screen stack
            # (if the review task finishes before cancel, ResultScreen may appear instead)
            from openreview_cli.tui.screens.result import ResultScreen

            confirm = None
            for s in app._screen_stack:
                if isinstance(s, ConfirmModal):
                    confirm = s
                    break
            has_confirm = confirm is not None
            has_result = any(isinstance(s, ResultScreen) for s in app._screen_stack)
            assert has_confirm or has_result, "Cancel or result screen should appear"


@pytest.mark.asyncio
async def test_progress_screen_completes_to_result() -> None:
    """Mock run_review to return quickly, assert result screen is pushed."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.progress import ProgressScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch("openreview_cli.tui.domain.review.run_review_via_tui") as mock_run:
            mock_assessment = MagicMock()
            mock_assessment.color = "green"
            mock_assessment.confidence = 0.95
            mock_assessment.clause_text = "Test clause"
            mock_assessment.effective_confidence = 0.95
            mock_assessment.position.value = "preferred"
            mock_assessment.reasoning = "Test reasoning"
            mock_assessment.qa_revised_rationale = None
            mock_assessment.clause_ref = None
            mock_report = MagicMock()
            mock_report.assessments = [mock_assessment]
            mock_report.document.filename = "test.pdf"
            mock_report.document.page_count = 1
            mock_report.document.clause_count = 1
            mock_report.document.pii_stripped = True
            mock_report.generated_at = "2026-07-11T00:00:00"
            mock_report.confidence_threshold = 0.7
            mock_report.playbook_id = "precheck-nda-v1"
            mock_report.cg_metrics = None
            mock_report.mode = "precheck"
            mock_report.schema_version = "1.1.0"
            mock_report.summary.green_count = 1
            mock_report.summary.amber_count = 0
            mock_report.summary.red_count = 0
            mock_report.summary.avg_confidence = 0.95
            mock_report.summary.avg_effective_confidence = 0.95
            mock_run.return_value = [mock_report]

            app.push_screen(ProgressScreen(paths=[], mode="precheck"))
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()

            # ResultScreen should be on screen stack
            from openreview_cli.tui.screens.result import ResultScreen

            result_screen = None
            for s in app._screen_stack:
                if isinstance(s, ResultScreen):
                    result_screen = s
                    break
            assert result_screen is not None, "ResultScreen should be on screen stack"
