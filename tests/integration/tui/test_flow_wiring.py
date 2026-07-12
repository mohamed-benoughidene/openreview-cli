"""Integration tests for T023 — end-to-end flow wiring.

HomeTab → ReviewTab → wizard → ProgressScreen → ResultScreen → close → HomeTab.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_home_to_review_to_wizard_to_progress_to_result() -> None:
    """End-to-end: Home → New review → Review tab → wizard → progress → result."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

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
            mock_report.summary.preferred_count = 1
            mock_report.summary.acceptable_count = 0
            mock_report.summary.walkaway_count = 0
            mock_report.summary.avg_confidence = 0.95
            mock_report.summary.avg_effective_confidence = 0.95
            mock_run.return_value = [mock_report]

            # Click HomeTab New review
            btn = app.query_one("#btn-new-review")
            btn.press()
            await pilot.pause()

            # Should switch to Review tab
            tabs = app.query_one("#tabs")
            assert tabs.active == "review", "Should switch to Review tab"

            # Click Review tab New review button
            review_btn = app.query_one("#btn-new-review-tab")
            await pilot.click(review_btn)
            await pilot.pause()

            # Wizard should be on screen stack
            from openreview_cli.tui.screens.review_wizard import ReviewWizard

            wizard = None
            for s in app._screen_stack:
                if isinstance(s, ReviewWizard):
                    wizard = s
                    break
            assert wizard is not None, "ReviewWizard should be on screen stack"

            # Navigate through wizard steps
            await _select_first_mode(wizard, pilot)
            await pilot.pause()
            wizard.query_one("#btn-next").press()
            await pilot.pause()
            wizard.query_one("#btn-next").press()
            await pilot.pause()
            # Step 3: first playbook is pre-selected; Next always enabled
            wizard.query_one("#btn-next").press()
            await pilot.pause()
            # Step 4: click Run review
            wizard.query_one("#btn-next").press()
            await pilot.pause()

            # Wait for switch and progress to complete
            for _ in range(10):
                await pilot.pause()

            # ResultScreen should appear
            result = None
            for s in app._screen_stack:
                if isinstance(s, ResultScreen):
                    result = s
                    break
            assert result is not None, "ResultScreen should be on screen stack"


async def _select_first_mode(wizard, pilot):
    """Select first real mode (skip category header)."""
    mode_list = wizard.query_one("#mode-list")
    mode_list.focus()
    await pilot.pause()
    await pilot.press("down", "down", "enter")


@pytest.mark.asyncio
async def test_result_close_returns_to_home() -> None:
    """Push result, dismiss, assert Home tab visible."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    report = MagicMock()
    report.assessments = []

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ResultScreen(reports=[report], mode="precheck"))
        await pilot.pause()

        # Find ResultScreen and click Close
        result_screen = None
        for s in app._screen_stack:
            if isinstance(s, ResultScreen):
                result_screen = s
                break
        assert result_screen is not None

        close_btn = result_screen.query_one("#btn-close")
        await pilot.click(close_btn)
        await pilot.pause()

        # Should be back to home tab
        tabs = app.query_one("#tabs")
        assert tabs.active == "home", "Should return to Home tab after close"
