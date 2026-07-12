"""Integration tests for ClientForm modal (T021)."""

from __future__ import annotations

from unittest.mock import patch

from textual.widgets import Input

from openreview_cli.tui.screens.client_form import ClientForm


async def test_client_form_validation_empty_form() -> None:
    """Saving empty form shows validation error."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ClientForm())
        await pilot.pause()
        await pilot.click("#save")
        await pilot.pause()
        form = app.screen
        assert isinstance(form, ClientForm)
        error_label = form.query_one("#form-error")
        error_text = str(error_label.render())
        assert "required" in error_text.lower()


@patch("openreview_cli.tui.domain.clients.add_client_via_tui")
@patch("openreview_cli.tui.domain.clients.list_clients_via_tui")
async def test_client_form_save_calls_storage(
    mock_list_clients_via_tui, mock_add_client_via_tui
) -> None:
    """Fill form via Clients tab, save calls add_client_via_tui."""
    mock_list_clients_via_tui.return_value = []
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    async with app.run_test(size=(120, 40)) as pilot:
        # Navigate to Clients tab
        await pilot.press("3")
        await pilot.pause()
        # Click New client button
        await pilot.click("#btn-new-client")
        await pilot.pause()

        form = app.screen
        assert isinstance(form, ClientForm)

        # Fill form fields
        form.query_one("#form-client-id", Input).value = "acme"
        form.query_one("#form-name", Input).value = "Acme Corp"
        form.query_one("#form-notes", Input).value = "Test notes"

        await pilot.click("#save")
        await pilot.pause()

        mock_add_client_via_tui.assert_called_once_with("acme", "Acme Corp", "Test notes")
