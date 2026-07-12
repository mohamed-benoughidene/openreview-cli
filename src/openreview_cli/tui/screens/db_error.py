"""DatabaseErrorScreen — modal shown when database init fails."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from openreview_cli.storage.database import init_database


class DatabaseErrorScreen(ModalScreen[bool]):
    """Modal shown when database initialization fails.

    Offers "Reinitialize" (retry) and "Quit" (exit).
    """

    DEFAULT_CSS = """
    DatabaseErrorScreen { align: center middle; }
    DatabaseErrorScreen > Vertical { width: 50; padding: 1 2; background: $surface; border: thick $error; }
    DatabaseErrorScreen #db-error-title { text-style: bold; margin: 0 0 1 0; }
    DatabaseErrorScreen #db-error-message { margin: 0 0 1 0; }
    DatabaseErrorScreen Horizontal { align: center middle; }
    DatabaseErrorScreen Button { margin: 0 1; }
    """

    def __init__(self, error_message: str) -> None:
        super().__init__()
        self._error_message = error_message

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Database Error", id="db-error-title")
            yield Label(self._error_message, id="db-error-message")
            with Horizontal():
                yield Button("Reinitialize", variant="primary", id="reinitialize")
                yield Button("Quit", variant="error", id="quit")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "reinitialize":
            try:
                from openreview_cli.config.paths import get_data_dir

                db_path = get_data_dir() / "openreview.db"
                init_database(db_path)
                self.dismiss(True)
            except Exception:
                self.dismiss(False)
        else:
            self.dismiss(False)
            self.app.exit()

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(False)
            self.app.exit()
