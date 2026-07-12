"""ClientForm — modal form for adding/editing clients."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class ClientForm(ModalScreen[dict[str, Any] | None]):
    """Client add/edit form, returns dict or None if cancelled."""

    DEFAULT_CSS = """
    ClientForm { align: center middle; }
    ClientForm > Vertical { width: 50; padding: 1 2; background: $surface; border: thick $primary; }
    ClientForm #form-title { text-style: bold; margin: 0 0 1 0; }
    ClientForm Input { margin: 0 0 1 0; }
    ClientForm #form-error { color: $error; margin: 0 0 1 0; }
    ClientForm Horizontal { align: center middle; }
    ClientForm Button { margin: 0 1; }
    """

    def __init__(
        self,
        client_id: str | None = None,
        name: str | None = None,
        notes: str | None = None,
    ) -> None:
        super().__init__()
        self._initial_id = client_id or ""
        self._initial_name = name or ""
        self._initial_notes = notes or ""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Add Client", id="form-title")
            yield Input(placeholder="Client ID", value=self._initial_id, id="form-client-id")
            yield Input(placeholder="Name", value=self._initial_name, id="form-name")
            yield Input(placeholder="Notes (optional)", value=self._initial_notes, id="form-notes")
            yield Label("", id="form-error")
            with Horizontal():
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self._save()
        elif event.button.id == "cancel":
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "enter":
            self._save()
        elif event.key == "escape":
            self.dismiss(None)

    def _save(self) -> None:
        client_id = self.query_one("#form-client-id", Input).value.strip()
        name = self.query_one("#form-name", Input).value.strip()
        notes = self.query_one("#form-notes", Input).value.strip()
        error_label = self.query_one("#form-error", Label)

        if not client_id:
            error_label.update("Client ID is required")
            return
        if not name:
            error_label.update("Name is required")
            return

        self.dismiss({"client_id": client_id, "name": name, "notes": notes})
