"""Clause-graph screen -- read-only metrics and health score for one document.

The numbers come from ``graph_summary_via_tui``, which runs the same
parse -> build -> metrics -> health pipeline the CLI uses, so the screen and
``openreview graph`` can never disagree.

Parsing is synchronous and measured at ~2.8 s for a 500-page contract, so it
runs on a worker thread via ``asyncio.to_thread`` and the screen shows a
"computing" line before it starts. The screen is read-only: the only binding
is Escape, which pops back to whatever was beneath it.
"""

from __future__ import annotations

import asyncio
from dataclasses import fields
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from openreview_cli.tui.domain.graph import GraphSummary, graph_summary_via_tui

if TYPE_CHECKING:
    from openreview_cli.graph.metrics import GraphMetrics

#: One row per ``GraphMetrics`` field: field name -> (label, format spec).
#: Iterated over ``dataclasses.fields`` so a future sixth metric cannot be
#: silently omitted; the labels and specs live here so they stay in one place.
_METRIC_ROWS: dict[str, tuple[str, str]] = {
    "density": ("Density", ".3f"),
    "max_depth": ("Max depth", "d"),
    "orphan_ratio": ("Orphan ratio", ".3f"),
    "broken_ref_count": ("Broken cross-refs", "d"),
    "definition_coverage": ("Definition coverage", ".3f"),
}

_NO_DOCUMENT_MESSAGE = (
    "No document supplied \u2014 open this from a finished review to see its clause graph."
)
_NO_CLAUSES_MESSAGE = "No clauses detected in this document."
_HIERARCHY_CAVEAT = (
    "No clause hierarchy was detected in this document (clause parsers assign no "
    "parent section), so this score is near-maximal for almost any flat graph."
)


def _metric_lines(metrics: GraphMetrics) -> list[str]:
    """Render one ``Label: value`` line per field of the real ``GraphMetrics``."""
    lines: list[str] = []
    for field in fields(metrics):
        label, spec = _METRIC_ROWS[field.name]
        value = getattr(metrics, field.name)
        lines.append(f"{label}: {format(value, spec)}")
    return lines


class GraphSummaryScreen(Screen[None]):
    """Show a document's clause-graph metrics and health score (read-only)."""

    DEFAULT_CSS: ClassVar[str] = """
    GraphSummaryScreen { padding: 1; }
    #graph-header { text-style: bold; background: $primary; color: $text; padding: 1 2; margin: 0 0 1 0; }
    #graph-subtitle { padding: 0 0 0 1; margin: 0 0 1 0; color: $text-muted; }
    #graph-body { height: 1fr; padding: 1 2; }
    #graph-status { dock: bottom; height: 1; padding: 0 1; color: $text-muted; }
    """

    BINDINGS: ClassVar = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(self, document_path: Path | None = None) -> None:
        super().__init__()
        self._document_path = document_path
        self._load_task: asyncio.Task[None] | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Clause graph", id="graph-header", markup=False)
            yield Static(id="graph-subtitle", markup=False)
            yield Static(id="graph-body", markup=False)
            yield Static(id="graph-status", markup=False)

    def on_mount(self) -> None:
        if self._document_path is None:
            self._show(body=_NO_DOCUMENT_MESSAGE, status="No document to inspect.")
            return

        filename = self._document_path.name
        self._show(
            subtitle=filename,
            body=f"Reading {filename} and computing graph metrics\u2026",
            status="Computing\u2026",
        )
        self._load_task = asyncio.create_task(self._load())

    async def _load(self) -> None:
        """Compute the summary off the event loop, then render it."""
        from openreview_cli.parsing.models import ParseError

        path = self._document_path
        if path is None:
            self._show(body=_NO_DOCUMENT_MESSAGE, status="No document to inspect.")
            return

        filename = path.name
        try:
            summary = await asyncio.to_thread(graph_summary_via_tui, path)
        except FileNotFoundError:
            self._show(
                subtitle=filename,
                body=f"Could not read {filename}: the file no longer exists.",
                status="Could not read the document.",
            )
            return
        except ParseError as exc:
            self._show(
                subtitle=filename,
                body=f"Could not read {filename}: {exc.message}",
                status="Could not read the document.",
            )
            return
        except OSError as exc:
            self._show(
                subtitle=filename,
                body=f"Could not read {filename}: {exc}",
                status="Could not read the document.",
            )
            return

        self._render_summary(summary)

    def _render_summary(self, summary: GraphSummary) -> None:
        subtitle = (
            f"{summary.filename} \u00b7 {summary.node_count} nodes \u00b7 "
            f"{summary.edge_count} edges"
        )
        if summary.node_count == 0:
            self._show(subtitle=subtitle, body=_NO_CLAUSES_MESSAGE, status="Done.")
            return

        lines = _metric_lines(summary.metrics)
        lines.append("")
        lines.append(f"Health score: {summary.score}/100")
        if summary.parent_child_edge_count == 0:
            lines.append(_HIERARCHY_CAVEAT)
        self._show(subtitle=subtitle, body="\n".join(lines), status="Done.")

    def _show(self, *, subtitle: str = "", body: str = "", status: str = "") -> None:
        """Update the subtitle/body/status blocks (never shadows Widget._render).

        A no-op once the screen has stopped running. ``_load`` resumes on the
        event loop after the worker thread finishes, so it can run *after*
        Escape popped the screen; ``query_one`` on a detached DOM raises
        ``NoMatches`` in a task nobody awaits.

        ``Widget.is_mounted`` cannot express "still live" here: in Textual
        8.2.8 it is ``False`` while ``on_mount`` runs (so a guard on it would
        drop the first paint) and stays ``True`` after unmount (so it would
        not block the late one). ``is_running`` is ``True`` during ``on_mount``
        and becomes ``False`` when the screen's message loop ends, which happens
        before ``on_unmount`` is dispatched, so the guard also covers a late
        render.
        """
        if not self.is_running:
            return
        self.query_one("#graph-subtitle", Static).update(subtitle)
        self.query_one("#graph-body", Static).update(body)
        self.query_one("#graph-status", Static).update(status)

    def action_pop_screen(self) -> None:
        self.app.pop_screen()

    def on_unmount(self) -> None:
        """Cancel an in-flight load so it cannot touch a detached screen.

        Mirrors ``ProgressScreen.on_unmount``: popping the screen while the
        worker thread is still parsing must not leave a task that resumes and
        renders into a DOM that is no longer ours.
        """
        if self._load_task is not None and not self._load_task.done():
            self._load_task.cancel()


__all__ = ["GraphSummaryScreen"]
