"""Playbooks tab — import, view, compare playbooks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static


class _PlaybookItem(ListItem):
    """ListItem carrying playbook_id for detail view lookup."""

    def __init__(
        self,
        playbook_id: str,
        latest_version: int,
        current_version: int,
        mode: str = "",
        corrupt: bool = False,
    ) -> None:
        self.playbook_id = playbook_id
        cur_mark = ""
        if current_version != latest_version:
            cur_mark = f" [current: v{current_version}]"
        label = f"{playbook_id} (v{latest_version}{cur_mark})"
        if corrupt:
            label = f"{label} (corrupt)"
        if mode:
            label = f"{label} [{mode}]"
        super().__init__(Label(label))


class PlaybooksTab(Static):
    """Playbooks tab with filterable list, import, detail view."""

    DEFAULT_CSS = """
    PlaybooksTab { padding: 1; }
    PlaybooksTab #playbooks-header { text-style: bold; padding: 0 0 1 0; }
    PlaybooksTab #playbooks-toolbar { margin: 0 0 1 0; height: auto; }
    PlaybooksTab #playbook-filter { width: 1fr; }
    PlaybooksTab #playbook-list { height: 1fr; min-height: 3; }
    PlaybooksTab #playbooks-actions { margin: 1 0 0 0; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._playbooks_data: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Static("Playbooks", id="playbooks-header")
        yield Horizontal(
            Input(placeholder="Type to filter playbooks...", id="playbook-filter"),
            id="playbooks-toolbar",
        )
        yield ListView(id="playbook-list")
        yield Horizontal(
            Button("+ Import playbook", id="btn-import", variant="primary"),
            id="playbooks-actions",
        )

    def on_mount(self) -> None:
        self._load()

    def _on_input_changed(self, event: Input.Changed) -> None:
        self._load()

    def _load(self) -> None:
        from openreview_cli.tui.domain.playbooks import list_playbooks_via_tui

        self._playbooks_data = list_playbooks_via_tui()
        filter_text = self.query_one("#playbook-filter", Input).value

        if filter_text:
            lowered = filter_text.lower()
            self._playbooks_data = [p for p in self._playbooks_data if lowered in p["id"].lower()]

        list_view = self.query_one("#playbook-list", ListView)
        list_view.clear()

        if not self._playbooks_data:
            list_view.append(
                ListItem(Label("No playbooks yet. Import one with [+ Import playbook]."))
            )
            return

        for p in self._playbooks_data:
            list_view.append(
                _PlaybookItem(
                    playbook_id=p["id"],
                    latest_version=p["latest_version"],
                    current_version=p["current_version"],
                    corrupt=p.get("corrupt", False),
                )
            )

    def _on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, _PlaybookItem):
            self._open_detail(event.item.playbook_id)

    def _on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-import":
            self._open_import_flow()

    def _open_detail(self, playbook_id: str) -> None:
        from openreview_cli.tui.domain.playbooks import get_playbook_detail_via_tui

        playbook = get_playbook_detail_via_tui(playbook_id)
        if playbook is None:
            self.notify(f"Playbook '{playbook_id}' not found or corrupt.", timeout=3)
            return

        from openreview_cli.tui.screens.playbook_detail import PlaybookDetailScreen

        self.app.push_screen(PlaybookDetailScreen(playbook=playbook, current_version=0))

    def _open_import_flow(self) -> None:
        self.app.push_screen(_ImportModal(), self._on_import_confirm)

    def _on_import_confirm(self, result: dict[str, Any] | None) -> None:
        if result is None:
            return
        path = result["path"]
        try:
            from openreview_cli.tui.domain.playbooks import import_playbook_via_tui

            info = import_playbook_via_tui(path)
            self.notify(
                f"Imported '{info['playbook_id']}' ({info['mode']}) "
                f"with {info['category_count']} categories.",
                timeout=3,
            )
            self._load()
        except Exception as exc:
            self.notify(f"Import failed: {exc}", timeout=5, severity="error")


class _ImportModal(ModalScreen[dict[str, Any] | None]):
    """Playbook import — path input, preview, confirm in one screen."""

    DEFAULT_CSS = """
    _ImportModal { align: center middle; }
    _ImportModal > Vertical { width: 70; padding: 1 2; background: $surface; border: thick $primary; }
    _ImportModal #import-title { text-style: bold; margin: 0 0 1 0; }
    _ImportModal #preview-content { height: 1fr; min-height: 5; margin: 1 0; }
    _ImportModal #preview-validation { margin: 0 0 1 0; }
    _ImportModal Horizontal { align: center middle; }
    _ImportModal Button { margin: 0 1; min-width: 10; }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Import playbook from YAML", id="import-title")
            yield Label("Enter path to .yaml/.yml file:")
            yield Input(placeholder="/path/to/playbook.yaml", id="import-path-input")
            yield Static("", id="preview-content")
            yield Label("", id="preview-validation")
            yield Horizontal(
                Button("Browse\u2026", id="import-browse"),
                Button("Import", id="preview-import", variant="primary"),
                Button("Cancel", id="import-cancel"),
            )

    def on_mount(self) -> None:
        self._path: Path | None = None
        self.query_one("#preview-content", Static).display = False
        self.query_one("#preview-validation", Label).display = False
        self.query_one("#preview-import", Button).display = False

    def on_input_changed(self, event: Input.Changed) -> None:
        path_str = event.value.strip()
        if not path_str:
            self._clear_preview()
            return
        path = Path(path_str).expanduser().resolve()
        if path.exists() and path.suffix in (".yaml", ".yml"):
            self._show_preview(path)
        else:
            self._clear_preview()

    def _clear_preview(self) -> None:
        self.query_one("#preview-content", Static).display = False
        self.query_one("#preview-validation", Label).display = False
        self.query_one("#preview-import", Button).display = False
        self._path = None

    def _show_preview(self, path: Path) -> None:
        from openreview_cli.review.playbook import load_playbook

        try:
            playbook = load_playbook(path)
            lines = [
                f"ID: {playbook.id}",
                f"Mode: {playbook.mode}",
                f"Version: {playbook.metadata.version}",
                f"Categories: {len(playbook.categories)}",
                "",
                "Categories:",
            ]
            for cat in playbook.categories:
                lines.append(f"  - {cat.name} [{cat.default_position.value}]")
            self.query_one("#preview-content", Static).update("\n".join(lines))
            self.query_one("#preview-validation", Label).update("[green]\u2713 Valid playbook[/]")
            self._path = path
        except Exception as exc:
            self.query_one("#preview-content", Static).update(f"[red]Validation error:[/]\n{exc}")
            self.query_one("#preview-validation", Label).update(f"[red]\u2717 {exc}[/]")
            self._path = None
        self.query_one("#preview-content", Static).display = True
        self.query_one("#preview-validation", Label).display = True
        self.query_one("#preview-import", Button).display = self._path is not None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "import-browse":
            self._browse()
        elif event.button.id == "preview-import":
            if self._path:
                self.dismiss({"path": self._path})
        elif event.button.id == "import-cancel":
            self.dismiss(None)

    def _browse(self) -> None:
        path = self.query_one("#import-path-input", Input).value.strip()
        if path:
            p = Path(path).expanduser().resolve()
            if p.exists() and p.suffix in (".yaml", ".yml"):
                self._show_preview(p)
                return
        self.notify("Type a full path to a .yaml file.", timeout=2)
