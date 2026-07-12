"""Global search overlay — ModalScreen with real-time results (T040)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView, Static


class _SearchItem(ListItem):
    """ListItem carrying result_type and result_id for navigation."""

    def __init__(self, result_type: str, result_id: str, text: str) -> None:
        self.result_type = result_type
        self.result_id = result_id
        super().__init__(Label(text))


_GROUPS: list[tuple[str, str, Callable[[Any], tuple[str, str]]]] = [
    ("reviews", "review", lambda r: (r["id"], f"Review: {r['filename']} ({r.get('mode', '—')})")),
    ("clients", "client", lambda c: (c["id"], f"Client: {c['id']} \u2014 {c['name']}")),
    ("playbooks", "playbook", lambda p: (p["playbook_id"], f"Playbook: {p['playbook_id']}")),
]


class SearchScreen(ModalScreen[None]):
    """Global search overlay accessible via ``/`` from any tab."""

    DEFAULT_CSS = """
    SearchScreen { align: center top; }
    SearchScreen #search-container { width: 60; max-height: 80%; margin: 3 0 0 0; background: $surface; border: thick $primary; }
    SearchScreen #search-input { dock: top; margin: 1; }
    SearchScreen #search-status { padding: 0 1; color: $text-muted; }
    SearchScreen #search-results { height: 1fr; min-height: 3; overflow-y: auto; margin: 0 1 1 1; }
    """

    BINDINGS: ClassVar = [
        Binding("escape", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="search-container"):
            yield Input(placeholder="Search reviews, clients, playbooks...", id="search-input")
            yield Static("", id="search-status")
            yield ListView(id="search-results")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._update_results(event.value)

    def _update_results(self, query: str) -> None:
        from openreview_cli.tui.domain.search import search_all_via_tui

        lv = self.query_one("#search-results", ListView)
        lv.clear()

        if not query.strip():
            self.query_one("#search-status", Static).update("")
            return

        results = search_all_via_tui(query)
        total = sum(len(v) for v in results.values())
        status = self.query_one("#search-status", Static)

        if total == 0:
            status.update("No results found.")
            lv.append(ListItem(Label("No results found.")))
            return

        status.update(f"{total} result(s)")

        for key, result_type, fmt in _GROUPS:
            for item in results.get(key, []):
                rid, text = fmt(item)
                lv.append(_SearchItem(result_type, rid, text))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not isinstance(event.item, _SearchItem):
            return
        self._navigate(event.item.result_type, event.item.result_id)

    def _navigate(self, result_type: str, result_id: str) -> None:
        self.app.pop_screen()

        if result_type == "review":
            from openreview_cli.tui.domain.review import load_review_report_via_tui
            from openreview_cli.tui.screens.result import ResultScreen

            report = load_review_report_via_tui(result_id)
            if report is not None:
                self.app.push_screen(ResultScreen(reports=[report]))
            else:
                self.notify("Could not load review report.", severity="error")
        elif result_type == "client":
            self.app.action_show_tab("clients")  # type: ignore[attr-defined]
        elif result_type == "playbook":
            self.app.action_show_tab("playbooks")  # type: ignore[attr-defined]

    def action_close(self) -> None:
        self.app.pop_screen()
