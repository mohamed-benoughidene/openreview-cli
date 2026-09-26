"""Home tab — quick actions and recent reviews."""

from __future__ import annotations

import asyncio
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Label, ListItem, ListView, Static

from openreview_cli.tui.loading import LoadingState
from openreview_cli.tui.screens.review_wizard import ReviewWizard
from openreview_cli.tui.startup import defer_when_splashing


def fmt_counts(green: int, amber: int, red: int) -> str:
    """Format color counts as e.g. '3g/1a/0r'."""
    return f"{green}g/{amber}a/{red}r"


class HomeTab(Container):
    """Home tab with welcome message, quick actions, and recent reviews."""

    DEFAULT_CSS = """
    HomeTab { padding: 1 2; }
    #recent-list { height: 10; }
    #recent-list ListItem:hover { background: $accent; }
    #desc-bar { dock: bottom; height: 1; background: $boost; padding: 0 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._reviews: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Static("Welcome to openreview", id="welcome")
        with Horizontal(id="actions"):
            yield Button("New review", id="btn-new-review", variant="primary")
        yield Static("Recent reviews", id="recent-header")
        yield Button(
            "No reviews yet. Start one with New review.",
            id="empty-state",
            variant="primary",
        )
        yield LoadingState(id="home-loading")
        recent_list = ListView(id="recent-list")
        recent_list.display = False
        yield recent_list
        yield Static("", id="desc-bar")

    def on_mount(self) -> None:
        defer_when_splashing(self.app, self._start_load)

    def _start_load(self) -> None:
        """Show the spinner and fetch recent reviews off the event loop.

        The single load entry point: invoked once on mount (deferred behind the
        splash when enabled). There is no post-write caller.
        """
        loading = self.query_one(LoadingState)
        content = self.query_one("#recent-list", ListView)
        loading.begin(content)
        self.run_worker(
            self._load_async(),
            name="home-load",
            group="home-load",
            exclusive=True,
            exit_on_error=False,  # never take the app down for a tab fetch
        )

    async def _load_async(self) -> None:
        """Refresh the recent-reviews list from the database."""
        from openreview_cli.tui.domain.review import list_recent_reviews_via_tui

        loading = self.query_one(LoadingState)
        content = self.query_one("#recent-list", ListView)
        try:
            # to_thread: the SQLite read must not block the event loop.
            self._reviews = await asyncio.to_thread(list_recent_reviews_via_tui, limit=5)
        except Exception as exc:
            self.notify(f"Load failed: {exc}", severity="error", markup=False)
            # Always drop the spinner and reveal the list region. #empty-state is
            # left visible (M5): it must be actionable from the very first frame.
            loading.end(content)
            return

        empty = self.query_one("#empty-state", Button)
        lst = self.query_one("#recent-list", ListView)

        if not self._reviews:
            # Home has two mutually-exclusive content regions; the empty-state
            # button stays visible and the list stays hidden.
            empty.display = True
            lst.display = False
            lst.clear()
        else:
            empty.display = False
            lst.clear()
            for r in self._reviews:
                text = self._format_review_item(r)
                lst.append(ListItem(Label(text)))
            lst.display = True
            lst.index = 0

        loading.display = False

    @staticmethod
    def _format_review_item(r: dict[str, Any]) -> str:
        """Format a single review entry line."""
        filename = r.get("filename", "unknown")
        mode = r.get("mode", "—")
        date = r.get("created_at", "")[:10] if r.get("created_at") else ""
        green = r.get("green_count", 0)
        amber = r.get("amber_count", 0)
        red = r.get("red_count", 0)
        return f"{filename}  {mode}  {date}  {fmt_counts(green, amber, red)}"

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update description bar when focus changes."""
        if event.item is None or not self._reviews:
            return
        idx = event.list_view.index
        if idx is None or idx >= len(self._reviews):
            return
        r = self._reviews[idx]
        mode = r.get("mode", "—")
        date = r.get("created_at", "")[:10] if r.get("created_at") else ""
        green = r.get("green_count", 0)
        amber = r.get("amber_count", 0)
        red = r.get("red_count", 0)
        desc = self.query_one("#desc-bar", Static)
        desc.update(f"Mode: {mode}  Date: {date}  {fmt_counts(green, amber, red)}")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Open the selected review's result screen."""
        if event.item is None or not self._reviews:
            return
        idx = event.list_view.index
        if idx is None or idx >= len(self._reviews):
            return
        r = self._reviews[idx]
        report_id = r["id"]

        from openreview_cli.tui.domain.review import load_review_report_via_tui
        from openreview_cli.tui.screens.result import ResultScreen

        report = load_review_report_via_tui(report_id)
        if report is None:
            self.notify("Could not load review report.", severity="error")
            return
        self.app.push_screen(ResultScreen(reports=[report], mode=r.get("mode", "precheck")))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Open the review wizard for the Home quick-action buttons."""
        if event.button.id in ("btn-new-review", "empty-state"):
            self.app.push_screen(ReviewWizard())
