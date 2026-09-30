"""Graph build screen -- build one contract's clause graph and show it as a tree.

One screen, one key: the document is parsed and its clause graph built in a
worker thread (``asyncio.to_thread``), then rendered as a foldable Textual
``Tree``. The graph comes from ``graph_summary_via_tui`` -- the same
parse -> build path the read-only metrics screen uses and the same
``ClauseHierarchyBuilder`` the CLI's ``graph build`` calls -- so the tree, the
counts and ``openreview graph view`` cannot disagree.

Nothing is written on mount, on parse or on Escape. The only writer is the
save key, which writes the CLI's own graph JSON (``ContractGraph.to_file``) to
``<source stem>.graph.json`` beside the document.

Node labels are Rich ``Text`` objects, never markup strings: contract text
contains square brackets (``[Party A]``), and Rich would consume them if the
label were parsed as markup. The CLI text renderer and this tree share
``openreview_cli.graph.view.compute_annotations`` so their annotations agree.

``openreview_cli.graph.*`` / ``openreview_cli.parsing.*`` are imported inside
the methods that need them, per the TUI's module-level-import policy.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static, Tree

from openreview_cli.tui.domain.graph import GraphSummary, graph_summary_via_tui

if TYPE_CHECKING:
    from textual.widgets.tree import TreeNode

    from openreview_cli.graph.models import ContractGraph, GraphNode

#: Same 60-character, newline-collapsed slice ``graph.view.render_tree`` uses.
#: The tree and the CLI's text tree must truncate identically or they disagree
#: about what a node shows.
_SNIPPET_LENGTH = 60

_WORKING_STATUS = "\u25cf Building the clause tree\u2026"
_NOTHING_TO_SAVE_STATUS = "\u2717 Nothing to save: no clause graph was built."
_EMPTY_STATUS = "No clauses detected in this document."
_FLAT_NOTE = (
    "No clause hierarchy was detected in this document, so the clauses are shown as a flat list."
)

_BUTTON_IDS = ("#btn-graph-save", "#btn-graph-back")


def _node_label(node: GraphNode, annotations: list[str]) -> Text:
    """Render one tree row as Rich ``Text``: literal node text, then annotations.

    Built from a plain string with ``append``, so no part of the label is ever
    parsed as Rich markup: braces in clause text survive verbatim. The plain
    text matches ``render_tree``'s ``"{label}  {snippet}"`` line exactly.
    """
    snippet = node.text[:_SNIPPET_LENGTH].replace("\n", " ").strip()
    label = Text(f"{node.label}  {snippet}", no_wrap=True)
    if annotations:
        label.append("  ")
        label.append(" ".join(annotations), style="dim")
    return label


class GraphBuildScreen(Screen[None]):
    """Build a document's clause graph and show it as a foldable tree."""

    DEFAULT_CSS: ClassVar[str] = """
    GraphBuildScreen { padding: 1; }
    #graph-build-header { text-style: bold; background: $primary; color: $text; padding: 1 2; margin: 0 0 1 0; }
    #graph-tree { height: 1fr; padding: 1 2; }
    #graph-build-status { padding: 0 1; margin: 1 0 0 0; color: $text-muted; }
    #graph-build-actions { dock: bottom; height: 3; padding: 0 1; align: center middle; }
    #graph-build-actions Button { margin: 0 1; min-width: 12; }
    """

    BINDINGS: ClassVar = [
        Binding("escape", "go_back", "Back"),
        Binding("s", "save_graph", "Save graph"),
    ]

    def __init__(self, document_path: Path) -> None:
        super().__init__()
        self._document_path = document_path
        self._filename = document_path.name
        self._busy = False
        self._summary: GraphSummary | None = None
        self._load_task: asyncio.Task[None] | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(id="graph-build-header", markup=False)
            yield Tree(Text(self._filename, no_wrap=True), id="graph-tree")
            yield Static(id="graph-build-status", markup=False)
            with Horizontal(id="graph-build-actions"):
                yield Button("Save graph (S)", id="btn-graph-save", variant="primary")
                yield Button("Back (Esc)", id="btn-graph-back", variant="default")

    def on_mount(self) -> None:
        # The guard is set synchronously, before the worker starts: a flag set
        # after an await would let a second handler read ``False`` in the same
        # event-loop turn.
        self._set_busy(True)
        self._show(header=self._filename, status=_WORKING_STATUS)
        self._load_task = asyncio.create_task(self._load())

    async def _load(self) -> None:
        """Build the graph off the event loop, then render the tree."""
        from openreview_cli.parsing.models import ParseError

        try:
            try:
                summary = await asyncio.to_thread(graph_summary_via_tui, self._document_path)
            except FileNotFoundError:
                self._show_read_failure("the file no longer exists.")
                return
            except ParseError as exc:
                self._show_read_failure(exc.message)
                return
            except OSError as exc:
                self._show_read_failure(str(exc))
                return

            self._summary = summary
            self._populate_tree(summary.graph)
            self._show(header=_counts(summary), status=_built_status(summary))
        finally:
            self._set_busy(False)

    # ── tree ──

    def _populate_tree(self, graph: ContractGraph) -> None:
        """Rebuild the whole tree from *graph*, nesting by ``parent_child`` edges.

        The walk is the one ``render_tree`` uses: roots from ``graph.roots``,
        children from the adjacency's ``parent_child`` edges, and a ``visited``
        set so a malformed cycle cannot nest forever. Root nodes are expanded
        one level deep so the hierarchy is visible immediately; deeper subtrees
        start collapsed and are foldable with the Tree's own keys.
        """
        if not self.is_running:
            return

        from openreview_cli.graph.models import EdgeType
        from openreview_cli.graph.view import compute_annotations

        tree = self.query_one("#graph-tree", Tree)
        tree.reset(Text(self._filename, no_wrap=True))

        annotations = compute_annotations(graph)
        adjacency = graph.adjacency
        visited: set[str] = set()

        def add(parent: TreeNode[Any], node_id: str, depth: int) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            node = graph.nodes.get(node_id)
            if node is None:
                return
            tree_node = parent.add(
                _node_label(node, annotations.get(node_id, [])), expand=depth == 0
            )
            for edge in adjacency.get(node_id, []):
                if edge.edge_type == EdgeType.parent_child:
                    add(tree_node, edge.target_id, depth + 1)

        for root in graph.roots:
            add(tree.root, root, 0)
        tree.root.expand()

    # ── actions ──

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Escape and save must not run under an uncancellable worker thread."""
        return not (action in ("go_back", "save_graph") and self._busy)

    async def action_save_graph(self) -> None:
        """Write the CLI's graph JSON beside the source document, on demand only."""
        if self._busy:
            return
        summary = self._summary
        if summary is None:
            self._set_status(_NOTHING_TO_SAVE_STATUS)
            return

        target = self._document_path.with_suffix(".graph.json")
        self._set_busy(True)
        try:
            try:
                await asyncio.to_thread(summary.graph.to_file, target)
            except OSError as exc:
                self._set_status(f"\u2717 Could not write {target.resolve()}: {exc}")
                return
            self._set_status(f"\u2713 Saved the clause graph to {target.resolve()}.")
        finally:
            self._set_busy(False)

    async def action_go_back(self) -> None:
        self.app.pop_screen()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        handlers = {
            "btn-graph-save": self.action_save_graph,
            "btn-graph-back": self.action_go_back,
        }
        handler = handlers.get(event.button.id or "")
        if handler is not None:
            await handler()

    # ── state ──

    def _set_busy(self, busy: bool) -> None:
        """Set the guard, then disable both buttons while the worker owns the screen.

        The DOM half is skipped once the screen has stopped running: ``_load``
        un-busies itself from a ``finally`` that can run after Escape popped the
        screen, and ``query_one`` on the pruned tree raises ``NoMatches`` in a
        task nobody awaits.
        """
        self._busy = busy
        if not self.is_running:
            return
        for button_id in _BUTTON_IDS:
            self.query_one(button_id, Button).disabled = busy
        if not busy:
            # Saving is the one action that needs a built graph: a failed parse
            # must not leave an enabled control that cannot do anything.
            self.query_one("#btn-graph-save", Button).disabled = self._summary is None

    def _show_read_failure(self, reason: str) -> None:
        """One clean line, no traceback -- the metrics screen's failure path."""
        self._show(
            header=self._filename, status=f"\u2717 Could not read {self._filename}: {reason}"
        )

    def _set_status(self, message: str) -> None:
        if not self.is_running:
            return
        self.query_one("#graph-build-status", Static).update(message)

    def _show(self, *, header: str, status: str) -> None:
        """Update the header/status blocks, once the screen has stopped running.

        ``_load`` resumes on the event loop after the worker thread finishes, so
        it can run *after* Escape popped the screen; ``query_one`` on a detached
        DOM raises ``NoMatches`` in a task nobody awaits. ``is_running`` is
        ``True`` during ``on_mount`` (so the first paint lands) and becomes
        ``False`` when the screen's message loop ends -- before ``on_unmount`` --
        so the guard also covers a late render.
        """
        if not self.is_running:
            return
        self.query_one("#graph-build-header", Static).update(header)
        self.query_one("#graph-build-status", Static).update(status)

    def on_unmount(self) -> None:
        """Cancel an in-flight build so it cannot touch a detached screen."""
        if self._load_task is not None and not self._load_task.done():
            self._load_task.cancel()


def _counts(summary: GraphSummary) -> str:
    """The metrics screen's own subtitle form, so the two cannot disagree."""
    return f"{summary.filename} \u00b7 {summary.node_count} nodes \u00b7 {summary.edge_count} edges"


def _built_status(summary: GraphSummary) -> str:
    """The terminal status line for a built graph: hierarchical or plainly flat."""
    if summary.node_count == 0:
        return _EMPTY_STATUS
    if summary.parent_child_edge_count == 0:
        return f"\u2713 Built {summary.node_count} nodes, 0 edges. {_FLAT_NOTE}"
    return (
        f"\u2713 Built {summary.node_count} nodes, {summary.edge_count} edges. "
        "Press S to save, or Esc to go back."
    )


__all__ = ["GraphBuildScreen"]
