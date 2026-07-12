"""Integration tests for global search SearchScreen (T040)."""

from __future__ import annotations

from unittest.mock import patch


class TestSearchScreen:
    """T040: Global search screen tests."""

    EXPECTED_MOCK = {
        "reviews": [
            {
                "id": "r-001",
                "filename": "employment-contract.pdf",
                "mode": "hirecheck",
                "green_count": 5,
                "amber_count": 0,
                "red_count": 2,
                "created_at": "2026-07-11T10:00:00",
            },
            {
                "id": "r-002",
                "filename": "nda-agreement.pdf",
                "mode": "precheck",
                "green_count": 2,
                "amber_count": 1,
                "red_count": 0,
                "created_at": "2026-07-10T10:00:00",
            },
        ],
        "clients": [
            {"id": "acme-corp", "name": "Acme Corporation"},
            {"id": "beta-inc", "name": "Beta Industries"},
        ],
        "playbooks": [
            {"playbook_id": "nda-v1"},
            {"playbook_id": "employment-v2"},
        ],
    }

    async def test_search_groups_by_type(self) -> None:
        """Search results grouped by type (review/client/playbook)."""
        from openreview_cli.tui.app import OpenReviewApp
        from openreview_cli.tui.screens.search import SearchScreen

        app = OpenReviewApp()
        with patch("openreview_cli.tui.domain.search.search_all_via_tui") as mock_search:
            mock_search.return_value = self.EXPECTED_MOCK
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

                # Type to trigger search (Input is focused by default)
                await pilot.press("p")
                await pilot.pause()

                # Check results grouped by _SearchItem.result_type
                lv = search_screen.query_one("#search-results")
                children = list(lv.children)

                reviews_found = sum(
                    1 for c in children if hasattr(c, "result_type") and c.result_type == "review"
                )
                clients_found = sum(
                    1 for c in children if hasattr(c, "result_type") and c.result_type == "client"
                )
                playbooks_found = sum(
                    1 for c in children if hasattr(c, "result_type") and c.result_type == "playbook"
                )

                assert reviews_found == 2, f"Expected 2 review results, got {reviews_found}"
                assert clients_found == 2, f"Expected 2 client results, got {clients_found}"
                assert playbooks_found == 2, f"Expected 2 playbook results, got {playbooks_found}"

    async def test_search_empty_state(self) -> None:
        """Typing a query with no matches shows empty state."""
        from openreview_cli.tui.app import OpenReviewApp
        from openreview_cli.tui.screens.search import SearchScreen

        app = OpenReviewApp()
        with patch("openreview_cli.tui.domain.search.search_all_via_tui") as mock_search:
            mock_search.return_value = {
                "reviews": [],
                "clients": [],
                "playbooks": [],
            }
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

                # Type a query
                await pilot.press("x", "y", "z")
                await pilot.pause()

                # List should have at least one item (empty state)
                lv = search_screen.query_one("#search-results")
                assert len(lv.children) > 0, "List should have an empty-state item"

                # mock_search should have been called with the query
                mock_search.assert_called()
