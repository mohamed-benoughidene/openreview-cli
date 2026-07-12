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


async def test_enter_saves_form() -> None:
    """Pressing Enter dismisses form with form data (FR-024)."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    result: dict[str, str] | None = None

    def on_result(r: dict[str, str] | None) -> None:
        nonlocal result
        result = r

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ClientForm(name="Test Corp", notes="Notes"), on_result)
        await pilot.pause()

        form = app.screen
        assert isinstance(form, ClientForm)
        form.query_one("#form-client-id", Input).value = "testcorp"

        await pilot.press("enter")
        await pilot.pause()

        assert result is not None
        assert result["client_id"] == "testcorp"
        assert result["name"] == "Test Corp"
        assert result["notes"] == "Notes"


async def test_escape_cancels_form() -> None:
    """Pressing Escape dismisses form with None (FR-024)."""
    from openreview_cli.tui.app import OpenReviewApp

    app = OpenReviewApp()
    result: dict[str, str] | None = {"dummy": "value"}

    def on_result(r: dict[str, str] | None) -> None:
        nonlocal result
        result = r

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ClientForm(client_id="acme", name="Acme Corp"), on_result)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert result is None
