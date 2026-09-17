"""Pre-flight egress-review modal — confirm the outbound data boundary (Phase 4)."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from openreview_cli.tui.domain.egress import EgressSummary


class EgressReviewModal(ModalScreen[bool]):
    """Shows what leaves the machine; Continue returns True, Cancel returns False."""

    DEFAULT_CSS = """
    EgressReviewModal { align: center middle; }
    EgressReviewModal #egress-box {
        width: 72; height: auto; padding: 1 2; border: thick $primary; background: $surface;
    }
    EgressReviewModal #egress-title { text-style: bold; padding: 0 0 1 0; }
    EgressReviewModal #egress-body { padding: 0 0 1 0; }
    EgressReviewModal #egress-buttons { height: 3; align: right middle; }
    EgressReviewModal #egress-buttons Button { margin: 0 1; }
    """

    BINDINGS: ClassVar = [
        Binding("escape", "cancel", "Cancel"),
        Binding("c", "confirm", "Continue"),
    ]

    def __init__(self, summary: EgressSummary) -> None:
        super().__init__()
        self._summary = summary

    def compose(self) -> ComposeResult:
        with Vertical(id="egress-box"):
            yield Static("Before this review runs", id="egress-title")
            yield Label("\n".join(self._summary.lines()), id="egress-body", markup=False)
            with Horizontal(id="egress-buttons"):
                yield Button("Cancel", id="btn-egress-cancel", variant="default")
                yield Button("Continue", id="btn-egress-continue", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-egress-continue":
            self.action_confirm()
        elif event.button.id == "btn-egress-cancel":
            self.action_cancel()

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
