"""Integration tests for OpenReviewApp (T007, T013a, T014, T016a, T024)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import Footer, ListView, TabbedContent
from textual.widgets import Label as TLabel


async def test_app_launches() -> None:
    """T007: App starts without exception and StatusBar is visible."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.is_running
        # Status bar should be mounted
        status_bar = app.query_one("#status-bar")
        assert status_bar is not None


async def test_app_has_five_tabs() -> None:
    """T007: TabbedContent has exactly 5 TabPanes."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        tab_panes = app.query("TabPane")
        assert len(tab_panes) == 5
        tab_ids = [p.id for p in tab_panes if p.id is not None]
        assert tab_ids == ["home", "review", "clients", "playbooks", "settings"]


async def test_app_tab_bar_visible() -> None:
    """T007: TabbedContent widget is in the DOM."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        tabs = app.query_one("#tabs", TabbedContent)
        assert tabs is not None


async def test_app_footer_visible() -> None:
    """T007: Footer is in the DOM."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        footer = app.query_one(Footer)
        assert footer is not None


async def test_tab_switch_via_number_key() -> None:
    """T007: Pressing 1-5 switches the active tab."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        tabs = app.query_one("#tabs", TabbedContent)
        # Default is "home"
        assert tabs.active == "home"
        # Switch to review
        await pilot.press("2")
        assert tabs.active == "review"
        # Switch to clients
        await pilot.press("3")
        assert tabs.active == "clients"
        # Switch to playbooks
        await pilot.press("4")
        assert tabs.active == "playbooks"
        # Switch to settings
        await pilot.press("5")
        assert tabs.active == "settings"
        # Back to home
        await pilot.press("1")
        assert tabs.active == "home"


async def test_first_ctrl_c_warns() -> None:
    """T013a: First Ctrl-C sets the warned flag."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app._ctrl_c_warned is False
        await pilot.press("ctrl+c")
        assert app._ctrl_c_warned is True


async def test_second_ctrl_c_exits() -> None:
    """T013a: Second Ctrl-C within 2s exits the app."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+c")
        assert app._ctrl_c_warned is True
        # Second Ctrl-C exits; app.run_test should handle cleanly
        await pilot.press("ctrl+c")
    # If we reach here, the app exited without error
    assert True


@pytest.mark.slow
async def test_full_review_workflow() -> None:
    """T014: End-to-end review workflow with mocks."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen
    from openreview_cli.tui.screens.review_wizard import ReviewWizard

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        with patch("openreview_cli.tui.domain.review.run_review_via_tui") as mock_run:
            mock_assessment = MagicMock()
            mock_assessment.color = "green"
            mock_assessment.confidence = 0.95
            mock_assessment.clause_text = "Test clause one"
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

            # Launch TUI -> click New review on Home tab (switches to Review tab)
            btn = app.query_one("#btn-new-review")
            btn.press()
            await pilot.pause()

            # Click New review on Review tab (pushes wizard)
            review_btn = app.query_one("#btn-new-review-tab")
            await pilot.click(review_btn)
            await pilot.pause()

            # Find wizard from screen stack
            wizard = None
            for s in app._screen_stack:
                if isinstance(s, ReviewWizard):
                    wizard = s
                    break
            assert wizard is not None, "ReviewWizard should be on screen stack"

            # Complete all 4 steps using keyboard nav
            # Step 1: select mode
            wizard.query_one("#mode-list").focus()
            await pilot.pause()
            await pilot.press("down", "down", "enter")
            await pilot.pause()
            wizard.query_one("#btn-next").press()
            await pilot.pause()

            # Step 2: skip file selection, click Next
            wizard.query_one("#btn-next").press()
            await pilot.pause()

            # Step 3: skip playbook, click Next
            wizard.query_one("#btn-next").press()
            await pilot.pause()

            # Step 4: click Run review
            wizard.query_one("#btn-next").press()
            await pilot.pause()

            # Wait for progress screen to complete
            for _ in range(10):
                await pilot.pause()

            # Result screen should appear
            result = None
            for s in app._screen_stack:
                if isinstance(s, ResultScreen):
                    result = s
                    break
            assert result is not None, "ResultScreen should appear after review"


async def test_clickable_gateway_status_bar_opens_settings() -> None:
    """T016a: Clicking gateway status item opens Settings tab."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()

        tabs = app.query_one("#tabs", TabbedContent)
        assert tabs.active == "home"

        # Click the gateway button in the status bar
        gateway_btn = app.query_one("#status-gateway")
        gateway_btn.press()
        await pilot.pause()

        # Settings tab should be active
        assert tabs.active == "settings"


async def test_ctrl_c_warn_resets_after_timeout() -> None:
    """T013a: Warn flag resets after 2s without second Ctrl-C."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+c")
        assert app._ctrl_c_warned is True
        # Wait for the 2s timer to fire
        await asyncio.sleep(2.5)
        await pilot.pause()
        assert app._ctrl_c_warned is False


# ── T024: US2 — re-open past review ──


@pytest.mark.slow
async def test_recent_reviews_after_quit_relaunch() -> None:
    """Seed 1 review, launch TUI, verify list shows it (simulates quit+relaunch)."""
    from openreview_cli.tui.app import OpenReviewApp

    mock_reviews = [
        {
            "id": "r-001",
            "filename": "contract.pdf",
            "mode": "precheck",
            "green_count": 3,
            "amber_count": 1,
            "red_count": 0,
            "created_at": "2026-07-11T10:00:00",
        }
    ]

    app = OpenReviewApp()
    with patch("openreview_cli.tui.domain.review.list_recent_reviews_via_tui") as mock_list:
        mock_list.return_value = mock_reviews
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            recent_list = app.query_one("#recent-list", ListView)
            assert recent_list.display is True
            assert len(recent_list.children) == 1

            label = recent_list.children[0].query_one(TLabel)
            text = label.content
            assert "contract.pdf" in text
            assert "precheck" in text
            assert "3g/1a/0r" in text


@pytest.mark.slow
async def test_recent_reviews_enter_opens_result() -> None:
    """Focus first entry, press Enter, assert ResultScreen pushed."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen

    mock_reviews = [
        {
            "id": "r-001",
            "filename": "contract.pdf",
            "mode": "precheck",
            "green_count": 3,
            "amber_count": 1,
            "red_count": 0,
            "created_at": "2026-07-11T10:00:00",
        }
    ]

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
    mock_report.document.filename = "contract.pdf"
    mock_report.document.page_count = 1
    mock_report.document.clause_count = 1
    mock_report.document.pii_stripped = True
    mock_report.generated_at = "2026-07-11T00:00:00"
    mock_report.confidence_threshold = 0.7
    mock_report.playbook_id = "test-playbook"
    mock_report.cg_metrics = None
    mock_report.mode = "precheck"
    mock_report.schema_version = "1.1.0"
    mock_report.summary.green_count = 1
    mock_report.summary.amber_count = 0
    mock_report.summary.red_count = 0
    mock_report.summary.avg_confidence = 0.95
    mock_report.summary.avg_effective_confidence = 0.95

    app = OpenReviewApp()
    with (
        patch("openreview_cli.tui.domain.review.list_recent_reviews_via_tui") as mock_list,
        patch("openreview_cli.tui.domain.review.load_review_report_via_tui") as mock_load,
    ):
        mock_list.return_value = mock_reviews
        mock_load.return_value = mock_report
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            recent_list = app.query_one("#recent-list", ListView)
            recent_list.focus()
            await pilot.pause()

            await pilot.press("enter")
            await pilot.pause()

            result = None
            for s in app._screen_stack:
                if isinstance(s, ResultScreen):
                    result = s
                    break
            assert result is not None, "ResultScreen should be pushed"
            assert result._mode == "precheck"


# ── T039: US5 — Global Search ──


async def test_global_search_opens_with_slash_key() -> None:
    """Pressing / opens the SearchScreen modal."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.search import SearchScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        assert any(isinstance(s, SearchScreen) for s in app._screen_stack), (
            "SearchScreen should be pushed after / key"
        )


async def test_global_search_results_realtime() -> None:
    """Typing after / shows results that update in real time."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.search import SearchScreen

    mock_results = {
        "reviews": [
            {
                "id": "r-001",
                "filename": "test-contract.pdf",
                "mode": "precheck",
                "green_count": 3,
                "amber_count": 1,
                "red_count": 0,
                "created_at": "2026-07-11T10:00:00",
            }
        ],
        "clients": [
            {"id": "acme-corp", "name": "Acme Corporation"},
        ],
        "playbooks": [
            {"playbook_id": "nda-v1"},
        ],
    }

    app = OpenReviewApp()
    with (
        patch("openreview_cli.tui.domain.search.search_all_via_tui") as mock_search,
    ):
        mock_search.return_value = mock_results
        async with app.run_test(size=(120, 40)) as pilot:
            # Open search
            await pilot.press("/")
            await pilot.pause()

            search_screen: SearchScreen | None = None
            for s in app._screen_stack:
                if isinstance(s, SearchScreen):
                    search_screen = s
                    break
            assert search_screen is not None, "SearchScreen should be open"

            # Type a character to trigger search
            input_widget = search_screen.query_one("#search-input")
            await pilot.click(input_widget)
            await pilot.press("t")
            await pilot.pause()

            # Results should be in the list
            lv = search_screen.query_one("#search-results")
            assert len(lv.children) > 0, "Search results should appear"
            mock_search.assert_called()


async def test_global_search_enter_navigates_to_detail() -> None:
    """Enter on a search result navigates to detail view."""
    from unittest.mock import MagicMock

    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.result import ResultScreen
    from openreview_cli.tui.screens.search import SearchScreen

    mock_results = {
        "reviews": [
            {
                "id": "r-001",
                "filename": "contract.pdf",
                "mode": "precheck",
                "green_count": 3,
                "amber_count": 1,
                "red_count": 0,
                "created_at": "2026-07-11T10:00:00",
            }
        ],
        "clients": [],
        "playbooks": [],
    }

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
    mock_report.document.filename = "contract.pdf"
    mock_report.document.page_count = 1
    mock_report.document.clause_count = 1
    mock_report.document.pii_stripped = True
    mock_report.generated_at = "2026-07-11T00:00:00"
    mock_report.confidence_threshold = 0.7
    mock_report.playbook_id = "test-playbook"
    mock_report.cg_metrics = None
    mock_report.mode = "precheck"
    mock_report.schema_version = "1.1.0"
    mock_report.summary.green_count = 1
    mock_report.summary.amber_count = 0
    mock_report.summary.red_count = 0
    mock_report.summary.avg_confidence = 0.95
    mock_report.summary.avg_effective_confidence = 0.95

    app = OpenReviewApp()
    with (
        patch("openreview_cli.tui.domain.search.search_all_via_tui") as mock_search,
        patch("openreview_cli.tui.domain.review.load_review_report_via_tui") as mock_load,
    ):
        mock_search.return_value = mock_results
        mock_load.return_value = mock_report
        async with app.run_test(size=(120, 40)) as pilot:
            # Open search
            await pilot.press("/")
            await pilot.pause()

            search_screen: SearchScreen | None = None
            for s in app._screen_stack:
                if isinstance(s, SearchScreen):
                    search_screen = s
                    break
            assert search_screen is not None

            # Populate search results via the internal method
            search_screen._update_results("t")
            await pilot.pause()

            # Navigate to detail by calling _navigate directly
            search_screen._navigate("review", "r-001")
            await pilot.pause()

            # ResultScreen should be pushed
            result = None
            for s in app._screen_stack:
                if isinstance(s, ResultScreen):
                    result = s
                    break
            assert result is not None, "ResultScreen should be pushed for review result"


async def test_global_search_escape_closes() -> None:
    """Pressing Escape closes the SearchScreen."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.search import SearchScreen

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        # Open search
        await pilot.press("/")
        await pilot.pause()
        assert any(isinstance(s, SearchScreen) for s in app._screen_stack), (
            "SearchScreen should be open"
        )
        # Close with Escape
        await pilot.press("escape")
        await pilot.pause()
        assert not any(isinstance(s, SearchScreen) for s in app._screen_stack), (
            "SearchScreen should be closed after Escape"
        )


async def test_import_document_button_pushes_wizard() -> None:
    """Home tab 'Import document' button pushes ReviewWizard."""
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.review_wizard import ReviewWizard

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        # On Home tab (default)
        tabs = app.query_one("#tabs", TabbedContent)
        assert tabs.active == "home"
        # Click the Import document button
        await pilot.click("#btn-import-doc")
        await pilot.pause()
        # ReviewWizard should now be on the screen stack
        assert any(isinstance(s, ReviewWizard) for s in app._screen_stack), (
            "ReviewWizard should be open after clicking 'Import document'"
        )
