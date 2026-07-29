"""Textual App class for the openreview TUI."""

from __future__ import annotations

import contextlib
import signal
from typing import Any, ClassVar

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Footer, Header, Static, TabbedContent, TabPane

from openreview_cli.slots import VALID_SLOTS
from openreview_cli.tui.domain.gateway import gateway_health_check, get_slot_configs


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
        self._orig_sigterm: Any = signal.SIG_DFL
        self._orig_sigint: Any = signal.SIG_DFL

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
            yield Static("Pricing: —", id="status-tier")
            yield Button("Quit", id="btn-quit", variant="error")
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

    def _refresh_gateway_status(self) -> None:
        """Refresh gateway status label per FR-007."""
        configs = get_slot_configs()
        health = gateway_health_check()

        configured = {s for s in VALID_SLOTS if configs.get(s, {}).get("configured")}

        if not configured:
            self.query_one(
                "#status-gateway", Button
            ).label = "Gateway: \u26a0 No providers configured"
            return

        failing: list[tuple[str, str]] = []
        for slot in sorted(configured):
            if health.get(slot, {}).get("status") != "configured":
                provider = configs.get(slot, {}).get("provider", "")
                failing.append((slot, provider))

        btn = self.query_one("#status-gateway", Button)
        if not failing:
            btn.label = "Gateway: \u2713 All healthy"
        elif len(failing) == 1:
            slot, provider = failing[0]
            error = health.get(slot, {}).get("error", "unknown error")
            btn.label = f"Gateway: \u26a0 {slot} ({provider}): {error}"
        elif len(failing) == len(VALID_SLOTS):
            btn.label = "Gateway: \u2717 All slots unreachable"
        else:
            names = ", ".join(s for s, _ in failing)
            btn.label = f"Gateway: \u26a0 {len(failing)}/6 slots: {names}"

    def action_open_search(self) -> None:
        """Open global search overlay (FR-040)."""
        from openreview_cli.tui.screens.search import SearchScreen

        self.push_screen(SearchScreen())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "status-gateway":
            self.action_show_tab("settings")
            from openreview_cli.tui.tabs.settings import SettingsTab

            settings_tab = self.query_one(SettingsTab)
            settings_tab.select_section("gateway")
        elif event.button.id == "btn-quit":
            self.exit()

    def on_mount(self) -> None:
        try:
            from openreview_cli.tui.domain.privacy import read_privacy_tier

            self.query_one("#status-privacy", Static).update(f"Privacy: {read_privacy_tier()}")
        except Exception:
            pass

        self._refresh_gateway_status()
        self._gateway_timer = self.set_interval(5.0, self._refresh_gateway_status)

        self._register_signal_handlers()

    def on_unmount(self) -> None:
        """Clean up process-global resources installed by on_mount."""
        signal.signal(signal.SIGTERM, self._orig_sigterm)
        signal.signal(signal.SIGINT, self._orig_sigint)
        self._gateway_timer.stop()
        # Prevent API key leakage to crash-dump / subprocess after TUI exits.
        from openreview_cli.gateway.router import clear_seeded_env_vars

        clear_seeded_env_vars()

    def _register_signal_handlers(self) -> None:
        """Register handlers for SIGTERM and SIGINT (Edge case 6).

        When the terminal is closed mid-review the OS sends SIGTERM (or SIGHUP
        on some emulators). This handler cancels the in-flight ProgressScreen
        review task, sets the cancel-requested flag so the review's results are
        never persisted, pops the progress screen, and exits with the
        conventional exit code (128 + signum).
        """

        def _on_signal(signum: int, _frame: object) -> None:
            import openreview_cli.tui.domain.negotiation as _neg_mod
            import openreview_cli.tui.domain.review as _review_mod
            from openreview_cli.tui.screens.negotiation_progress import (
                NegotiationProgressScreen,
            )
            from openreview_cli.tui.screens.progress import ProgressScreen

            # Toggle the module-level flag so run_review_via_tui skips DB
            # persistence even if it is currently mid-execution.
            _review_mod._tui_cancel_requested = True
            _neg_mod._tui_cancel_requested = True

            for screen in list(self._screen_stack):
                if isinstance(screen, (ProgressScreen, NegotiationProgressScreen)):
                    screen._cancelled = True
                    if screen._review_task and not screen._review_task.done():
                        screen._review_task.cancel()
                    with contextlib.suppress(Exception):
                        self.pop_screen()
                    break

            self.exit()

        self._orig_sigterm = signal.signal(signal.SIGTERM, _on_signal)
        self._orig_sigint = signal.signal(signal.SIGINT, _on_signal)
