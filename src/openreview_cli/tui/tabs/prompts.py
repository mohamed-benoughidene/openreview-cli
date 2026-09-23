"""Prompts tab — list prompts, browse version history."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Label, ListItem, ListView, Static


class _PromptItem(ListItem):
    """ListItem carrying the prompt name and rendering name + latest version."""

    def __init__(self, name: str, latest_version: int) -> None:
        self.prompt_name = name
        # markup=False: a prompt name is user-authored and may contain
        # bracketed expressions (e.g. "[Party A]") that the markup parser
        # would otherwise consume.
        super().__init__(Label(f"{name} (v{latest_version})", markup=False))


class PromptsTab(Static):
    """Prompts tab with a filterable list and version-history detail view."""

    DEFAULT_CSS = """
    PromptsTab { padding: 1; }
    PromptsTab #prompts-header { text-style: bold; padding: 0 0 1 0; }
    PromptsTab #prompts-toolbar { margin: 0 0 1 0; height: auto; }
    PromptsTab #prompt-filter { width: 1fr; }
    PromptsTab #prompt-list { height: 1fr; min-height: 3; }
    """

    EMPTY_STATE = (
        "No prompts yet. Create one with: openreview prompt create --name <name> --content <text>."
    )

    def __init__(self) -> None:
        super().__init__()
        self._prompts_data: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Static("Prompts", id="prompts-header")
        yield Horizontal(
            Input(placeholder="Type to filter prompts...", id="prompt-filter"),
            id="prompts-toolbar",
        )
        yield ListView(id="prompt-list")

    def on_mount(self) -> None:
        self._load()

    def _on_input_changed(self, event: Input.Changed) -> None:
        self._load()

    def _load(self) -> None:
        from openreview_cli.tui.domain.prompts import list_prompts_via_tui

        self._prompts_data = list_prompts_via_tui()
        filter_text = self.query_one("#prompt-filter", Input).value

        if filter_text:
            lowered = filter_text.lower()
            self._prompts_data = [p for p in self._prompts_data if lowered in p["name"].lower()]

        list_view = self.query_one("#prompt-list", ListView)
        list_view.clear()

        if not self._prompts_data:
            list_view.append(ListItem(Label(self.EMPTY_STATE, markup=False)))
            return

        for p in self._prompts_data:
            list_view.append(_PromptItem(name=p["name"], latest_version=p["latest_version"]))

    def _on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, _PromptItem):
            self._open_history(event.item.prompt_name)

    def _open_history(self, name: str) -> None:
        from openreview_cli.tui.domain.prompts import get_prompt_history_via_tui

        data = get_prompt_history_via_tui(name)
        if not data["found"]:
            # markup=False: the name is user-authored content.
            self.notify(f"Prompt '{name}' not found.", timeout=3, markup=False)
            return

        from openreview_cli.tui.screens.prompt_detail import PromptHistoryScreen

        self.app.push_screen(
            PromptHistoryScreen(
                prompt_name=name,
                rows=data["rows"],
                current_version=data["current_version"],
            )
        )
