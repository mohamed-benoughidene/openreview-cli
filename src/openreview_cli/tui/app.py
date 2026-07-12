"""Textual App class for the openreview TUI."""

from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Footer, Header, Static, TabbedContent, TabPane


class OpenReviewApp(App[None]):
    """Root TUI app for openreview."""

    CSS_PATH = "styles.tcss"
    TITLE = "openreview"

    BINDINGS: ClassVar = [
        ("ctrl+c", "quit_or_warn", "Quit"),
        ("1", "show_tab('home')", "Home"),
        ("2", "show_tab('review')", "Review"),
        ("3", "show_tab('clients')", "Clients"),
        ("4", "show_tab('playbooks')", "Playbooks"),
        ("5", "show_tab('settings')", "Settings"),
        ("/", "open_search", "Search"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._ctrl_c_warned = False

    def compose(self) -> ComposeResult:
        from openreview_cli.tui.tabs.clients import ClientsTab
        from openreview_cli.tui.tabs.home import HomeTab
        from openreview_cli.tui.tabs.playbooks import PlaybooksTab
        from openreview_cli.tui.tabs.review import ReviewTab
        from openreview_cli.tui.tabs.settings import SettingsTab

        yield Header(show_clock=False)
        with TabbedContent(initial="home", id="tabs"):
            with TabPane("Home", id="home"):
                yield HomeTab()
            with TabPane("Review", id="review"):
                yield ReviewTab()
            with TabPane("Clients", id="clients"):
                yield ClientsTab()
            with TabPane("Playbooks", id="playbooks"):
                yield PlaybooksTab()
            with TabPane("Settings", id="settings"):
                yield SettingsTab()
        with Horizontal(id="status-bar"):
            yield Static("Client: —", id="status-client")
            yield Static("Privacy: —", id="status-privacy")
            yield Button("Gateway: —", id="status-gateway")
            yield Static("Tier: —", id="status-tier")
        yield Footer()

    def action_show_tab(self, tab_id: str) -> None:
        tabs = self.query_one("#tabs", TabbedContent)
        tabs.active = tab_id

    def action_quit_or_warn(self) -> None:
        if self._ctrl_c_warned:
            self.exit()
            return
        self._ctrl_c_warned = True
        self.notify("Press Ctrl-C again to quit", timeout=2)

        self.set_timer(2.0, lambda: setattr(self, "_ctrl_c_warned", False))

    def action_open_search(self) -> None:
        """Open global search overlay (FR-040)."""
        from openreview_cli.tui.screens.search import SearchScreen

        self.push_screen(SearchScreen())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "status-gateway":
            self.action_show_tab("settings")

    def on_mount(self) -> None:
        try:
            from openreview_cli.tui.domain.privacy import read_privacy_tier

            self.query_one("#status-privacy", Static).update(f"Privacy: {read_privacy_tier()}")
        except Exception:
            pass
