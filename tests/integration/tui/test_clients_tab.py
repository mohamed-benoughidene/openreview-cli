"""Integration tests for ClientsTab (T020)."""

from __future__ import annotations

from unittest.mock import patch

from textual.widgets import Label, ListItem

from openreview_cli.tui.screens.client_form import ClientForm


def _list_item_text(item: ListItem) -> str:
    """Extract visible text from a ListItem."""
    try:
        label = item.query_one(Label)
        return str(label.render())
    except Exception:
        return str(item.render())


@patch("openreview_cli.tui.domain.clients.list_clients_via_tui")
async def test_clients_tab_shows_empty_state(mock_list_clients_via_tui) -> None:
    """Empty-state message visible when no clients."""
    mock_list_clients_via_tui.return_value = []
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        list_view = app.query_one("#client-list")
        items = list(list_view.children)
        assert len(items) == 1
        msg = _list_item_text(items[0])
        assert "No clients yet" in msg


@patch("openreview_cli.tui.domain.clients.list_clients_via_tui")
async def test_clients_tab_lists_clients(mock_list_clients_via_tui) -> None:
    """All 3 clients visible in list."""
    mock_list_clients_via_tui.return_value = [
        {"id": "acme", "name": "Acme Corp"},
        {"id": "beta", "name": "Beta Inc"},
        {"id": "gamma", "name": "Gamma LLC"},
    ]
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        items = list(app.query_one("#client-list").children)
        assert len(items) == 3
        all_text = " ".join(_list_item_text(item) for item in items)
        assert "acme" in all_text
        assert "beta" in all_text
        assert "gamma" in all_text


@patch("openreview_cli.tui.domain.clients.list_clients_via_tui")
async def test_clients_tab_type_to_filter(mock_list_clients_via_tui) -> None:
    """Typing in filter input narrows the displayed list."""
    mock_list_clients_via_tui.return_value = [
        {"id": "acme", "name": "Acme Corp"},
        {"id": "beta", "name": "Beta Inc"},
        {"id": "gamma", "name": "Gamma LLC"},
    ]
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        # Focus the filter input and type
        await pilot.click("#client-filter")
        await pilot.press("a", "c", "m", "e")
        await pilot.pause()
        items = list(app.query_one("#client-list").children)
        all_text = " ".join(_list_item_text(item) for item in items)
        assert "acme" in all_text
        assert "beta" not in all_text
        assert "gamma" not in all_text


@patch("openreview_cli.tui.domain.clients.list_clients_via_tui")
async def test_clients_tab_new_button_opens_form(
    mock_list_clients_via_tui,
) -> None:
    """Clicking 'New client' opens ClientForm modal."""
    mock_list_clients_via_tui.return_value = []
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        await pilot.click("#btn-new-client")
        await pilot.pause()
        assert isinstance(app.screen, ClientForm)


@patch("openreview_cli.tui.domain.clients.client_has_reviews", return_value=True)
@patch("openreview_cli.tui.domain.clients.list_clients_via_tui")
@patch("openreview_cli.tui.domain.clients.delete_client_via_tui")
async def test_clients_tab_delete_opens_confirm_modal(
    mock_delete_client_via_tui, mock_list_clients_via_tui, mock_client_has_reviews
) -> None:
    """Clicking delete on a client opens ConfirmModal."""
    mock_list_clients_via_tui.return_value = [
        {"id": "acme", "name": "Acme Corp"},
    ]
    mock_delete_client_via_tui.return_value = "has_reviews"
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.confirm import ConfirmModal

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        # Select the client by clicking the first list item
        items = list(app.query_one("#client-list").children)
        assert len(items) == 1
        await pilot.click(items[0])
        await pilot.pause()
        # Delete button should now be enabled
        delete_btn = app.query_one("#btn-delete")
        assert not delete_btn.disabled
        # Click delete
        await pilot.click("#btn-delete")
        await pilot.pause()
        # ConfirmModal should be the active screen
        assert isinstance(app.screen, ConfirmModal)
