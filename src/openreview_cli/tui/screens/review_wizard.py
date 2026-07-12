"""4-step review wizard."""

from __future__ import annotations

import logging
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

# Top 5 modes — text filter covers the rest
PRODUCT_MODES = ["precheck", "hirecheck", "dealcheck", "leasecheck", "fullreview"]


def _swap_content(container: Container, *new_children: Widget) -> None:
    container.remove_children()
    container.mount(*new_children)


class ReviewWizard(Screen[None]):
    """4-step review wizard with mode/file/playbook/confirm steps."""

    DEFAULT_CSS = """
    ReviewWizard #wizard-container { height: 100%; }
    ReviewWizard #step-indicator { text-style: bold; background: $primary; color: $text; padding: 1 2; margin: 0 0 1 0; }
    ReviewWizard #step-content { height: 1fr; overflow-y: auto; padding: 0 1; }
    ReviewWizard .nav-bar { dock: bottom; height: 3; padding: 0 1; align: center middle; }
    ReviewWizard .nav-bar Button { margin: 0 1; min-width: 12; }
    ReviewWizard #mode-filter { margin: 0 0 1 0; }
    """

    BINDINGS: ClassVar = [
        Binding("escape", "cancel_wizard", "Cancel"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._step = 1
        self._selected_mode: str | None = None
        self._selected_file: str | None = None
        self._selected_playbook: str | None = None
        self._disable_pii = False
        self._override_model: str | None = None
        self._mode_filter_text = ""

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
        """Rebuild mode list filtered by text."""
        lowered = filter_text.lower()
        items = [
            ListItem(Label(m), id=f"mode-{m}")
            for m in PRODUCT_MODES
            if not filter_text or lowered in m.lower()
        ]
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
        import os

        _swap_content(
            self.query_one("#step-content", Container),
            DirectoryTree(path=os.getcwd(), id="file-tree"),
        )
        self.query_one("#btn-back", Button).disabled = False
        self.query_one("#btn-next", Button).disabled = False

    def _on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self._selected_file = str(event.path)
        self.query_one("#btn-next", Button).disabled = False

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
        from pathlib import Path

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
            )
        )
