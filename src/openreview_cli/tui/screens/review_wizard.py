"""4-step review wizard."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Checkbox,
    DirectoryTree,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

logger = logging.getLogger(__name__)

# 22 product modes grouped by category per FR-013
PRODUCT_MODES: dict[str, list[str]] = {
    "Basic": [
        "precheck",
    ],
    "Employment": [
        "hirecheck",
        "consultcheck",
        "engagecheck",
        "workcheck",
    ],
    "Commercial": [
        "dealcheck",
        "leasecheck",
        "licensecheck",
        "buycheck",
        "assetcheck",
        "distrocheck",
        "franchisecheck",
        "partnercheck",
        "guaranteecheck",
    ],
    "Specialized": [
        "loicheck",
        "subcheck",
        "opcheck",
        "privacycheck",
        "loancheck",
        "indemnitycheck",
        "sponsorcheck",
    ],
    "Settlement": [
        "settlementcheck",
    ],
}


def _swap_content(container: Container, *new_children: Widget) -> None:
    container.remove_children()
    container.mount(*new_children)


class FilteredDirectoryTree(DirectoryTree):
    """DirectoryTree with hidden file filtering and name filtering per FR-033, FR-034."""

    def __init__(
        self,
        path: str | Path,
        *,
        show_hidden: bool = False,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(path, name=name, id=id, classes=classes, disabled=disabled)
        self._filter_text = ""
        self._show_hidden = show_hidden

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Filter hidden files and/or by name fragment."""
        for p in paths:
            if not self._show_hidden and p.name.startswith("."):
                continue
            if self._filter_text and self._filter_text.lower() not in p.name.lower():
                continue
            yield p


class ReviewWizard(Screen[None]):
    """4-step review wizard with mode/file/playbook/confirm steps."""

    DEFAULT_CSS = """
    ReviewWizard #wizard-container { height: 100%; }
    ReviewWizard #step-indicator { text-style: bold; background: $primary; color: $text; padding: 1 2; margin: 0 0 1 0; }
    ReviewWizard #step-content { height: 1fr; overflow-y: auto; padding: 0 1; }
    ReviewWizard .nav-bar { dock: bottom; height: 3; padding: 0 1; align: center middle; }
    ReviewWizard .nav-bar Button { margin: 0 1; min-width: 12; }
    ReviewWizard #mode-filter { margin: 0 0 1 0; }
    ReviewWizard #file-filter { margin: 0 0 1 0; }
    ReviewWizard .category-header { text-style: bold; padding: 0 0 0 1; }
    """

    BINDINGS: ClassVar = [
        Binding("escape", "cancel_wizard", "Cancel"),
        Binding("ctrl+h", "toggle_hidden", "Hidden files"),
    ]

    def __init__(self, client_id: str | None = None) -> None:
        super().__init__()
        self._step = 1
        self._selected_mode: str | None = None
        self._selected_file: str | None = None
        self._selected_playbook: str | None = None
        self._disable_pii = False
        self._override_model: str | None = None
        self._mode_filter_text = ""
        self._client_id = client_id

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard-container"):
            yield Static("Step 1 of 4 — Select mode", id="step-indicator")
            yield Container(id="step-content")
            with Horizontal(id="nav-buttons", classes="nav-bar"):
                yield Button("Back", id="btn-back", variant="default", disabled=True)
                yield Button("Cancel", id="btn-cancel", variant="error")
                yield Button("Next", id="btn-next", variant="primary", disabled=True)

    def on_mount(self) -> None:
        self._render_step1()

    # ── Step rendering ──

    def _render_step1(self) -> None:
        """Step 1: mode picker with type-to-filter."""
        self._step = 1
        self.query_one("#step-indicator", Static).update("Step 1 of 4 — Select mode")
        _swap_content(
            self.query_one("#step-content", Container),
            Input(placeholder="Type to filter modes...", id="mode-filter"),
            ListView(id="mode-list"),
        )
        self._rebuild_mode_list("")
        self.query_one("#btn-back", Button).disabled = True
        self.query_one("#btn-next", Button).disabled = True

    def _on_mode_filter_input_changed(self, event: Input.Changed) -> None:
        self._mode_filter_text = event.value
        self._rebuild_mode_list(event.value)

    def _rebuild_mode_list(self, filter_text: str) -> None:
        """Rebuild mode list filtered by text, grouped by category per FR-013."""
        lowered = filter_text.lower()
        items: list[ListItem] = []
        for category, mode_list in PRODUCT_MODES.items():
            matched = [m for m in mode_list if not filter_text or lowered in m.lower()]
            if not matched:
                continue
            items.append(
                ListItem(
                    Label(category),
                    id=f"cat-{category}",
                    disabled=True,
                    classes="category-header",
                )
            )
            for m in matched:
                items.append(ListItem(Label(m), id=f"mode-{m}"))
        lv = self.query_one("#mode-list", ListView)
        lv.remove_children()
        if not items:
            items.append(ListItem(Label("No modes match your filter.")))
            self.query_one("#btn-next", Button).disabled = True
        lv.mount(*items)

    def _on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle mode selection."""
        if self._step == 1 and event.item.id and event.item.id.startswith("mode-"):
            self._selected_mode = event.item.id.replace("mode-", "")
            self.query_one("#btn-next", Button).disabled = False

    def _render_step2(self) -> None:
        """Step 2: file picker."""
        self._step = 2
        self.query_one("#step-indicator", Static).update("Step 2 of 4 — Select document")

        _swap_content(
            self.query_one("#step-content", Container),
            Input(placeholder="Type to filter files or enter path...", id="file-filter"),
            FilteredDirectoryTree(path=Path.cwd(), id="file-tree", show_hidden=False),
        )
        self.query_one("#btn-back", Button).disabled = False
        self.query_one("#btn-next", Button).disabled = False

    def _on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self._selected_file = str(event.path)
        self.query_one("#btn-next", Button).disabled = False

    def _on_file_filter_input_changed(self, event: Input.Changed) -> None:
        """Filter file tree or navigate to direct path per FR-033."""
        if self._step != 2:
            return
        tree = self.query_one("#file-tree", FilteredDirectoryTree)
        value = event.value
        if value.startswith("/") or value.startswith("~"):
            p = Path(value).expanduser()
            if p.exists():
                tree.path = p if p.is_dir() else p.parent
                tree._filter_text = ""
                tree.reload()
        else:
            tree._filter_text = value
            tree.reload()

    def _render_step3(self) -> None:
        """Step 3: playbook picker."""
        self._step = 3
        self.query_one("#step-indicator", Static).update("Step 3 of 4 — Select playbook")
        mode_str = self._selected_mode or "this mode"
        playbook_opts = [
            ("default", f"Use default for {mode_str}"),
            ("strict", "Strict — conservative assessments"),
            ("lenient", "Lenient — permissive assessments"),
        ]
        _swap_content(
            self.query_one("#step-content", Container),
            ListView(
                *(ListItem(Label(desc), id=f"pb-{pb_id}") for pb_id, desc in playbook_opts),
                id="playbook-list",
            ),
        )
        self.query_one("#btn-back", Button).disabled = False
        self.query_one("#btn-next", Button).disabled = False

    def _on_playbook_list_selected(self, event: ListView.Selected) -> None:
        """Handle playbook selection."""
        if self._step == 3 and event.item.id and event.item.id.startswith("pb-"):
            self._selected_playbook = event.item.id.replace("pb-", "")
            self.query_one("#btn-next", Button).disabled = False

    def _render_step4(self) -> None:
        """Step 4: confirmation with checkboxes."""
        self._step = 4
        self.query_one("#step-indicator", Static).update("Step 4 of 4 — Confirm settings")

        mode_str = self._selected_mode or "—"
        file_str = self._selected_file or "—"
        file_name = Path(file_str).name if file_str != "—" else "—"
        pb_str = self._selected_playbook or "default"
        _swap_content(
            self.query_one("#step-content", Container),
            Label(f"Mode: {mode_str}", id="summary-mode"),
            Label(f"Document: {file_name}", id="summary-file"),
            Label(f"Playbook: {pb_str}", id="summary-pb"),
            Label(""),
            Vertical(
                Checkbox("Disable PII stripping", id="cb-disable-pii", value=False),
                Checkbox(
                    "Override model (uses default if unchecked)",
                    id="cb-override-model",
                    value=False,
                ),
                classes="checkbox-group",
            ),
        )
        self.query_one("#btn-back", Button).disabled = False
        self.query_one("#btn-next", Button).disabled = False
        self.query_one("#btn-next", Button).label = "Run review"

    def _on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "cb-disable-pii":
            self._disable_pii = event.value

    # ── Navigation ──

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-next":
            await self._handle_next()
        elif btn_id == "btn-back":
            self._handle_back()
        elif btn_id == "btn-cancel":
            self.action_cancel_wizard()

    async def _handle_next(self) -> None:
        if self._step == 1:
            self._render_step2()
        elif self._step == 2:
            self._render_step3()
        elif self._step == 3:
            self._render_step4()
        elif self._step == 4:
            await self._run_review()

    def _handle_back(self) -> None:
        if self._step == 2:
            self._render_step1()
        elif self._step == 3:
            self._render_step2()
        elif self._step == 4:
            self._render_step3()

    def action_toggle_hidden(self) -> None:
        """Toggle hidden file visibility per FR-034."""
        if self._step == 2:
            tree = self.query_one("#file-tree", FilteredDirectoryTree)
            tree._show_hidden = not tree._show_hidden
            tree.reload()

    def action_cancel_wizard(self) -> None:
        self.app.pop_screen()

    async def _run_review(self) -> None:
        """Execute review and push progress screen."""
        from openreview_cli.tui.screens.progress import ProgressScreen

        self.app.switch_screen(
            ProgressScreen(
                paths=[self._selected_file] if self._selected_file else [],
                mode=self._selected_mode or "precheck",
                disable_pii=self._disable_pii,
                playbook_id=self._selected_playbook
                if self._selected_playbook and self._selected_playbook != "default"
                else None,
                client_id=self._client_id,
            )
        )
