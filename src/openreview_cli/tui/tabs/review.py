"""Review tab — launches review wizard."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Button, Static


class ReviewTab(Container):
    """Review tab with 'New review' button that opens the wizard."""

    DEFAULT_CSS = """
    ReviewTab {
        padding: 1 2;
    }
    ReviewTab #review-welcome {
        margin: 1 0;
    }
    ReviewTab Button {
        margin: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Review a document", id="review-welcome")
        yield Button("New review", id="btn-new-review-tab", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Open the review wizard on button press."""
        if event.button.id == "btn-new-review-tab":
            from openreview_cli.tui.screens.review_wizard import ReviewWizard

            self.app.push_screen(ReviewWizard())
