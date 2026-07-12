"""ConfirmModal — generic Yes/No confirmation dialog."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmModal(ModalScreen[bool]):
    """Yes/No confirmation dialog, returns True on Yes."""

    DEFAULT_CSS = """
    ConfirmModal { align: center middle; }
    ConfirmModal > Vertical { width: 40; padding: 1 2; background: $surface; border: thick $primary; }
    ConfirmModal #confirm-title { text-style: bold; margin: 0 0 1 0; }
    ConfirmModal #confirm-message { margin: 0 0 1 0; }
    ConfirmModal Horizontal { align: center middle; }
    ConfirmModal Button { margin: 0 1; }
    """

    def __init__(self, title: str, message: str, danger: bool = False) -> None:
        super().__init__()
        self._title = title
        self._message = message
        self._danger = danger

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title, id="confirm-title")
            yield Label(self._message, id="confirm-message")
            with Horizontal():
                yield Button(
                    "Yes",
                    variant="error" if self._danger else "primary",
                    id="yes",
                )
                yield Button("No", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(False)
