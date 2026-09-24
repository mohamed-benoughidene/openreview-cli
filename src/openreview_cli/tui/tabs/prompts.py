"""Prompts tab — list prompts, browse version history, manage the library.

The tab is both the *list* surface and the *action* surface for the prompt
library (no intermediate detail screen).  The toolbar holds the create, import
and export-all entry points; the selection-gated action row holds the
per-prompt actions.  ``#btn-export-all-prompts`` is a toolbar button, so unlike
the six ``.prompt-action`` buttons it is reachable with no row selected and
covers the whole library.  Every screen it navigates to is imported lazily
inside the handler, so this module never depends on a screen at import time.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Label, ListItem, ListView, Static


class _PromptItem(ListItem):
    """ListItem carrying the prompt name and rendering name + latest version."""

    def __init__(self, name: str, latest_version: int) -> None:
        self.prompt_name = name
        # markup=False: a prompt name is user-authored and may contain
        # bracketed expressions (e.g. "[Party A]") that the markup parser
        # would otherwise consume.
        super().__init__(Label(f"{name} (v{latest_version})", markup=False))


class PromptsTab(Static):
    """Prompts tab: the list surface and the action surface for the library."""

    DEFAULT_CSS = """
    PromptsTab { padding: 1; }
    PromptsTab #prompts-header { text-style: bold; padding: 0 0 1 0; }
    PromptsTab #prompts-toolbar { margin: 0 0 1 0; height: auto; }
    PromptsTab #prompt-filter { width: 1fr; }
    PromptsTab #prompt-list { height: 1fr; min-height: 3; }
    PromptsTab #prompts-actions { margin: 1 0 0 0; height: auto; }
    /* Six action buttons must share one 80-column row: drop the Button
       min-width so each sizes to its label instead of overflowing. */
    PromptsTab #prompts-actions Button { min-width: 0; width: auto; margin: 0 1 0 0; }
    """

    EMPTY_STATE = "No prompts yet. Create one with [+ New prompt]."

    def __init__(self) -> None:
        super().__init__()
        self._prompts_data: list[dict[str, Any]] = []
        self._selected_name: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("Prompts", id="prompts-header")
        yield Horizontal(
            Input(placeholder="Type to filter prompts...", id="prompt-filter"),
            Button("+ New prompt", id="btn-new-prompt", variant="primary"),
            Button("+ Import", id="btn-import-prompt", variant="default"),
            Button("Export all\u2026", id="btn-export-all-prompts", variant="default"),
            id="prompts-toolbar",
        )
        yield ListView(id="prompt-list")
        yield Horizontal(
            Button("Edit\u2026", id="btn-edit-prompt", classes="prompt-action", disabled=True),
            Button("Bind\u2026", id="btn-bind-prompt", classes="prompt-action", disabled=True),
            Button(
                "Bindings\u2026",
                id="btn-prompt-bindings",
                classes="prompt-action",
                disabled=True,
            ),
            Button("Test\u2026", id="btn-test-prompt", classes="prompt-action", disabled=True),
            Button("Export\u2026", id="btn-export-prompt", classes="prompt-action", disabled=True),
            Button(
                "Delete selected",
                id="btn-delete-prompt",
                classes="prompt-action",
                variant="error",
                disabled=True,
            ),
            id="prompts-actions",
        )

    def on_mount(self) -> None:
        self._load()

    def _on_input_changed(self, event: Input.Changed) -> None:
        self._load()

    def _load(self) -> None:
        from openreview_cli.tui.domain.prompts import list_prompts_via_tui

        try:
            self._prompts_data = list_prompts_via_tui()
        except Exception as exc:
            # A store failure on the list path must never reach a Textual
            # handler; report it and leave the current list untouched.
            self.notify(f"Load failed: {exc}", severity="error", markup=False)
            return
        filter_text = self.query_one("#prompt-filter", Input).value

        if filter_text:
            lowered = filter_text.lower()
            self._prompts_data = [p for p in self._prompts_data if lowered in p["name"].lower()]

        list_view = self.query_one("#prompt-list", ListView)
        list_view.clear()

        # A reload drops the selection: the old row may be gone or have moved,
        # so every action stays gated until the user highlights a row again.
        self._selected_name = None
        self._set_actions_enabled(False)

        if not self._prompts_data:
            list_view.append(ListItem(Label(self.EMPTY_STATE, markup=False)))
            return

        for p in self._prompts_data:
            list_view.append(_PromptItem(name=p["name"], latest_version=p["latest_version"]))

    def _set_actions_enabled(self, enabled: bool) -> None:
        for btn in self.query(".prompt-action"):
            btn.disabled = not enabled

    def _on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Track the highlighted prompt and gate the action row on it.

        The empty-state row is a real, selectable ``ListItem`` and
        ``ListView.clear()`` posts ``Highlighted(None)``; both must leave every
        action disabled rather than indexing past ``_prompts_data``.
        """
        index = event.list_view.index
        in_range = index is not None and index < len(self._prompts_data)
        if index is not None and in_range:
            self._selected_name = self._prompts_data[index]["name"]
        else:
            self._selected_name = None
        for btn in self.query(".prompt-action"):
            btn.disabled = not in_range

    def _on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, _PromptItem):
            self._open_history(event.item.prompt_name)

    def _on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-new-prompt":
            self._open_new_form()
        elif btn_id == "btn-import-prompt":
            self._open_import()
        elif btn_id == "btn-export-all-prompts":
            self._open_export_all()
        elif btn_id == "btn-edit-prompt":
            self._open_edit_form()
        elif btn_id == "btn-bind-prompt":
            self._open_bind()
        elif btn_id == "btn-prompt-bindings":
            self._open_bindings()
        elif btn_id == "btn-test-prompt":
            self._open_test()
        elif btn_id == "btn-export-prompt":
            self._open_export()
        elif btn_id == "btn-delete-prompt":
            self._confirm_delete()

    def _latest_version_for(self, name: str) -> int:
        for prompt in self._prompts_data:
            if prompt["name"] == name:
                return int(prompt["latest_version"])
        return 0

    # ── Toolbar: create / import / export-all ──

    def _open_new_form(self) -> None:
        from openreview_cli.tui.screens.prompt_form import PromptFormScreen

        def on_result(result: dict[str, Any] | None) -> None:
            if not result:
                return
            from openreview_cli.tui.domain.prompts import create_prompt_via_tui

            try:
                create_prompt_via_tui(
                    result["name"],
                    result["content"],
                    tags=result.get("tags"),
                    description=result.get("description"),
                )
            except Exception as exc:
                self.notify(f"Create failed: {exc}", severity="error", markup=False)
                return
            self._load()

        self.app.push_screen(PromptFormScreen(), on_result)

    def _open_import(self) -> None:
        from openreview_cli.tui.screens.prompt_import import PromptImportModal

        self.app.push_screen(PromptImportModal(), self._on_import_result)

    def _on_import_result(self, _result: Any) -> None:
        # Import commits per item inside the modal; reload whenever it closes so
        # whatever landed is reflected in the list.
        self._load()

    def _open_export_all(self) -> None:
        """Open the export modal in library mode.

        Unlike the six selection-gated actions this needs no highlighted row: it
        exports the whole library, and the modal states the real total.
        """
        from openreview_cli.tui.screens.prompt_export import PromptExportModal

        self.app.push_screen(PromptExportModal())

    # ── Action row: per-prompt actions ──

    def _open_edit_form(self) -> None:
        name = self._selected_name
        if not name:
            return
        from openreview_cli.tui.domain.prompts import get_prompt_detail_via_tui

        try:
            detail = get_prompt_detail_via_tui(name)
        except Exception as exc:
            self.notify(f"Edit failed: {exc}", severity="error", markup=False)
            return
        if not detail["found"]:
            self.notify(f"Prompt '{name}' not found.", severity="error", markup=False)
            return

        from openreview_cli.tui.screens.prompt_form import PromptFormScreen

        def on_result(result: dict[str, Any] | None) -> None:
            if not result:
                return
            from openreview_cli.tui.domain.prompts import update_prompt_via_tui

            try:
                update_prompt_via_tui(
                    result["name"],
                    result["content"],
                    tags=result.get("tags"),
                    description=result.get("description"),
                )
            except Exception as exc:
                self.notify(f"Update failed: {exc}", severity="error", markup=False)
                return
            self._load()

        self.app.push_screen(
            PromptFormScreen(
                name=name,
                content=detail["content"],
                tags=detail["tags"],
                description=detail["description"] or "",
            ),
            on_result,
        )

    def _open_bind(self) -> None:
        name = self._selected_name
        if not name:
            return
        from openreview_cli.tui.screens.prompt_bindings import PromptBindModal

        def on_result(result: dict[str, Any] | None) -> None:
            if not result:
                return
            from openreview_cli.tui.domain.prompts import bind_prompt_via_tui

            try:
                bind_prompt_via_tui(result["slot"], name, int(result["version"]))
            except Exception as exc:
                self.notify(f"Bind failed: {exc}", severity="error", markup=False)
                return
            self._load()

        self.app.push_screen(PromptBindModal(prompt_name=name), on_result)

    def _open_bindings(self) -> None:
        name = self._selected_name
        if not name:
            return
        from openreview_cli.tui.screens.prompt_bindings import PromptBindingsScreen

        self.app.push_screen(PromptBindingsScreen(prompt_name=name), self._on_bindings_result)

    def _on_bindings_result(self, _result: Any) -> None:
        # Unbind happens inside the bindings screen; reload on close so the
        # prompt list is fresh and the action row is re-gated.
        self._load()

    def _open_test(self) -> None:
        name = self._selected_name
        if not name:
            return
        from openreview_cli.tui.screens.prompt_test import PromptTestModal

        self.app.push_screen(
            PromptTestModal(prompt_name=name, latest_version=self._latest_version_for(name))
        )

    def _open_export(self) -> None:
        name = self._selected_name
        if not name:
            return
        from openreview_cli.tui.screens.prompt_export import PromptExportModal

        self.app.push_screen(PromptExportModal(prompt_name=name))

    def _confirm_delete(self) -> None:
        name = self._selected_name
        if not name:
            return
        from openreview_cli.tui.domain.prompts import (
            get_prompt_detail_via_tui,
            list_bindings_via_tui,
        )

        try:
            detail = get_prompt_detail_via_tui(name)
            version_count = len(detail["versions"])
            slots = [
                binding["slot"]
                for binding in list_bindings_via_tui()
                if binding["prompt_name"] == name
            ]
        except Exception as exc:
            self.notify(f"Delete failed: {exc}", severity="error", markup=False)
            return

        message = (
            f"Delete prompt '{name}'? This permanently deletes {version_count} version(s) "
            f"and unbinds {len(slots)} slot(s): {', '.join(slots) or 'none'}. This cannot be undone."
        )

        def on_confirm(result: bool | None) -> None:
            if not result:
                return
            from openreview_cli.tui.domain.prompts import delete_prompt_via_tui

            try:
                delete_prompt_via_tui(name)
            except Exception as exc:
                self.notify(f"Delete failed: {exc}", severity="error", markup=False)
                return
            self._load()

        from openreview_cli.tui.screens.confirm import ConfirmModal

        self.app.push_screen(ConfirmModal("Delete prompt", message, danger=True), on_confirm)

    def _open_history(self, name: str) -> None:
        from openreview_cli.tui.domain.prompts import get_prompt_history_via_tui

        try:
            data = get_prompt_history_via_tui(name)
        except Exception as exc:
            # A store failure reading history must never reach a Textual handler.
            self.notify(f"History failed: {exc}", severity="error", markup=False)
            return
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
