"""Retrieve tab — launches the guided chunk/ingest/search screen.

The flow itself lives on ``RetrieveScreen``; this tab is only a launcher, so
the capability is discoverable before it is opened.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Button, Static

from openreview_cli.tui.screens.retrieve import RetrieveScreen


class RetrieveTab(Static):
    """Retrieve tab with a single button that opens the guided flow."""

    DEFAULT_CSS = """
    RetrieveTab { padding: 1 2; }
    RetrieveTab #retrieve-tab-title { text-style: bold; margin: 1 0 0 0; }
    RetrieveTab #retrieve-tab-description { margin: 0 0 1 0; color: $text-muted; }
    RetrieveTab Button { margin: 1 0; }
    """

    def compose(self) -> ComposeResult:
        yield Static("Search inside a document", id="retrieve-tab-title", markup=False)
        yield Static(
            "Chunk and index a contract, then search its text.",
            id="retrieve-tab-description",
            markup=False,
        )
        yield Button("Open retrieve", id="btn-open-retrieve", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-open-retrieve":
            self.app.push_screen(RetrieveScreen())


__all__ = ["RetrieveTab"]
