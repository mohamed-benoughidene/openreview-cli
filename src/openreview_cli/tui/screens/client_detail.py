"""Client detail screen — review history for a specific client (FR-025a)."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, Static


class ClientDetailScreen(Screen[None]):
    """Client detail screen with review history list."""

    DEFAULT_CSS = """
    ClientDetailScreen { padding: 1; }
    #detail-header { text-style: bold; background: $primary; color: $text; padding: 1 2; margin: 0 0 1 0; }
    #detail-subtitle { padding: 0 0 0 1; margin: 0 0 1 0; color: $text-muted; }
    #review-list { height: 1fr; min-height: 3; }
    #btn-empty-review { width: 1fr; margin: 2 0; }
    #detail-actions { dock: bottom; height: 3; padding: 0 1; align: center middle; }
    #detail-actions Button { margin: 0 1; min-width: 12; }
    """

    BINDINGS: ClassVar = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(self, client_id: str) -> None:
        super().__init__()
        self._client_id = client_id
        self._reviews: list[dict[str, object]] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(id="detail-header")
            yield Static(id="detail-subtitle")
            yield ListView(id="review-list")
            yield Button(
                "No reviews for this client yet. Start one with [New review].",
                id="btn-empty-review",
                variant="primary",
            )
            with Horizontal(id="detail-actions"):
                yield Button("Back", id="btn-back", variant="default")

    def on_mount(self) -> None:
        from openreview_cli.tui.domain.clients import (
            get_client_via_tui,
            list_reviews_for_client_via_tui,
        )

        client = get_client_via_tui(self._client_id)
        name = client["name"] if client else self._client_id
        self.query_one("#detail-header", Static).update(f"Client: {name}")

        self._reviews = list_reviews_for_client_via_tui(self._client_id)

        review_list = self.query_one("#review-list", ListView)
        empty_btn = self.query_one("#btn-empty-review", Button)

        if not self._reviews:
            review_list.display = False
            empty_btn.display = True
            self.query_one("#detail-subtitle", Static).update("No reviews yet.")
        else:
            review_list.display = True
            empty_btn.display = False
            self.query_one("#detail-subtitle", Static).update(f"{len(self._reviews)} review(s)")
            for r in self._reviews:
                review_list.append(
                    ListItem(
                        Label(
                            f"{r['filename']} \u2014 {r['mode']}  "
                            f"[{r.get('green_count', 0)}\u2713 "
                            f"{r.get('amber_count', 0)}~ "
                            f"{r.get('red_count', 0)}\u2717]"
                        ),
                        id=f"review-{r['id']}",
                    )
                )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle review selection — load and show report."""
        if event.item.id and event.item.id.startswith("review-"):
            report_id = event.item.id.replace("review-", "")
            self._open_report(report_id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-empty-review":
            from openreview_cli.tui.screens.review_wizard import ReviewWizard

            self.app.push_screen(ReviewWizard(client_id=self._client_id))

    def action_pop_screen(self) -> None:
        self.app.pop_screen()

    def _open_report(self, report_id: str) -> None:
        """Load and display a saved review report."""
        from openreview_cli.tui.domain.review import load_review_report_via_tui
        from openreview_cli.tui.screens.result import ResultScreen

        report = load_review_report_via_tui(report_id)
        if report is None:
            self.notify("Report not found.", severity="error")
            return
        mode: str = "precheck"
        for r in self._reviews:
            if r["id"] == report_id:
                mode = str(r.get("mode", "precheck"))
                break
        self.app.push_screen(ResultScreen(reports=[report], mode=mode))
