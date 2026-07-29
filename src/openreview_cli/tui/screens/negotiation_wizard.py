"""2-step negotiation wizard — file picker, solver options."""

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
    DirectoryTree,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

logger = logging.getLogger(__name__)


def _swap_content(container: Container, *new_children: Widget) -> None:
    container.remove_children()
    container.mount(*new_children)


class FilteredDirectoryTree(DirectoryTree):
    """DirectoryTree with hidden file filtering and name filtering."""

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
        for p in paths:
            if not self._show_hidden and p.name.startswith("."):
                continue
            if self._filter_text and self._filter_text.lower() not in p.name.lower():
                continue
            yield p


SOLVERS = [
    ("qre", "QRE — Quantal Response Equilibrium (bounded rationality)"),
    ("nash", "Nash — Pure Nash equilibrium (fully rational)"),
    ("level_k", "Level-k — Iterative best-response (depth-limited)"),
]


class NegotiationWizard(Screen[None]):
    """2-step negotiation wizard: document + solver options."""

    DEFAULT_CSS = """
    NegotiationWizard #wizard-container { height: 100%; }
    NegotiationWizard #step-indicator { text-style: bold; background: $primary; color: $text; padding: 1 2; margin: 0 0 1 0; }
    NegotiationWizard #step-content { height: 1fr; overflow-y: auto; padding: 0 1; }
    NegotiationWizard .nav-bar { dock: bottom; height: 3; padding: 0 1; align: center middle; }
    NegotiationWizard .nav-bar Button { margin: 0 1; min-width: 12; }
    NegotiationWizard #file-filter { margin: 0 0 1 0; }
    NegotiationWizard #solver-params { margin: 1 0; }
    NegotiationWizard #param-error { color: $error; margin: 0 0 1 0; }
    """

    BINDINGS: ClassVar = [
        Binding("escape", "cancel_wizard", "Cancel"),
        Binding("ctrl+h", "toggle_hidden", "Hidden files"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._step = 1
        self._selected_file: str | None = None
        self._selected_solver: str = "qre"
        self._rationality: str = "1.0"
        self._depth: str = "2"

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard-container"):
            yield Static("Step 1 of 2 — Select document", id="step-indicator")
            yield Container(id="step-content")
            with Horizontal(id="nav-buttons", classes="nav-bar"):
                yield Button("Back", id="btn-back", variant="default", disabled=True)
                yield Button("Cancel", id="btn-cancel", variant="error")
                yield Button("Next", id="btn-next", variant="primary", disabled=True)

    def on_mount(self) -> None:
        self._render_step1()

    # ── Step 1: file picker ──

    def _render_step1(self) -> None:
        self._step = 1
        self.query_one("#step-indicator", Static).update("Step 1 of 2 — Select document")
        _swap_content(
            self.query_one("#step-content", Container),
            Input(placeholder="Type to filter files or enter path...", id="file-filter"),
            FilteredDirectoryTree(path=Path.cwd(), id="file-tree", show_hidden=False),
        )
        self.query_one("#btn-back", Button).disabled = True
        self.query_one("#btn-next", Button).disabled = False

    def _on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self._selected_file = str(event.path)
        self.query_one("#btn-next", Button).disabled = False

    def _on_file_filter_input_changed(self, event: Input.Changed) -> None:
        if self._step != 1:
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

    def action_toggle_hidden(self) -> None:
        if self._step == 1:
            tree = self.query_one("#file-tree", FilteredDirectoryTree)
            tree._show_hidden = not tree._show_hidden
            tree.reload()

    # ── Step 2: solver options ──

    def _render_step2(self) -> None:
        self._step = 2
        self.query_one("#step-indicator", Static).update("Step 2 of 2 — Solver options")
        items = [ListItem(Label(desc), id=f"solver-{s_id}") for s_id, desc in SOLVERS]
        # Pre-focus qre
        children: list[Widget] = [
            Static("Select equilibrium solver:", id="solver-label"),
            ListView(*items, id="solver-list"),
            Static("", id="param-error"),
        ]
        # Add rationality/depth inputs
        children.append(
            Vertical(
                Input(value=self._rationality, placeholder="1.0", id="input-rationality"),
                Label("Rationality (λ) — higher = more rational (QRE only)"),
                Input(value=self._depth, placeholder="2", id="input-depth"),
                Label("Depth (k) — iterations (level-k only)"),
                id="solver-params",
            )
        )
        _swap_content(self.query_one("#step-content", Container), *children)
        self.query_one("#btn-back", Button).disabled = False
        self.query_one("#btn-next", Button).disabled = False
        self.query_one("#btn-next", Button).label = "Run negotiation"

    def _on_list_view_selected(self, event: ListView.Selected) -> None:
        if self._step == 2 and event.item.id and event.item.id.startswith("solver-"):
            self._selected_solver = event.item.id.replace("solver-", "")

    def _on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "input-rationality":
            self._rationality = event.value
        elif event.input.id == "input-depth":
            self._depth = event.value

    def action_cancel_wizard(self) -> None:
        self.app.pop_screen()

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
            # Validate inputs
            error_label = self.query_one("#param-error", Static)
            try:
                rationality_val = float(self._rationality)
                if rationality_val <= 0:
                    error_label.update("Rationality must be > 0")
                    return
            except ValueError:
                error_label.update("Rationality must be a number (e.g. 1.0)")
                return
            try:
                depth_val = int(self._depth)
                if depth_val < 1:
                    error_label.update("Depth must be >= 1")
                    return
            except ValueError:
                error_label.update("Depth must be an integer (e.g. 2)")
                return
            error_label.update("")
            await self._run_negotiation()

    def _handle_back(self) -> None:
        if self._step == 2:
            self._render_step1()

    async def _run_negotiation(self) -> None:
        """Launch negotiation progress screen."""
        # lazy imports inside method — never at module level
        from openreview_cli.tui.screens.negotiation_progress import (
            NegotiationProgressScreen,
        )

        self.app.switch_screen(
            NegotiationProgressScreen(
                doc_path=self._selected_file or "",
                solver=self._selected_solver,
                rationality=float(self._rationality),
                depth=int(self._depth),
            )
        )
