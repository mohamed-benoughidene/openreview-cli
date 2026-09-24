"""Result screen — split view, layout toggle, export."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, Static

from openreview_cli.review.memo.filename import DEFAULT_OUTPUT_DIR
from openreview_cli.review.models import ClauseAssessment, ReviewReport

if TYPE_CHECKING:
    from openreview_cli.tui.domain.amber import AmberQueueState

CLAUSES_PER_PAGE = 100

# Textual colour names; "amber" is not one, so it maps to the CSS colour "orange".
_STATUS_COLOR_TAG: dict[str, str] = {
    "green": "green",
    "amber": "orange",
    "red": "red",
}


def status_color_tag(color: object) -> str:
    """Map an assessment colour value to a valid Textual colour name."""
    return _STATUS_COLOR_TAG.get(str(color), "white")


class ResultScreen(Screen[None]):
    """Result screen with split view, layout toggle, summary header, and export."""

    DEFAULT_CSS = """
    ResultScreen #result-container { height: 100%; }
    ResultScreen #result-header { text-style: bold; background: $primary; color: $text; padding: 1 2; }
    ResultScreen #doc-context { padding: 0 2; color: $text-muted; }
    ResultScreen .summary-header { text-style: bold; padding: 0 1; background: $boost; }
    ResultScreen #split-view { height: 1fr; }
    ResultScreen #clause-list-pane { width: 2fr; border: solid $primary; }
    ResultScreen #clause-detail-pane { width: 3fr; border: solid $primary; overflow-y: auto; padding: 0 1; }
    ResultScreen #full-screen-scroll { height: 1fr; overflow-y: auto; padding: 0 1; }
    ResultScreen #result-nav { dock: bottom; height: 3; padding: 0 1; align: center middle; }
    ResultScreen #result-nav Button { margin: 0 1; min-width: 12; }
    ResultScreen #export-view, ResultScreen #save-view { display: none; }
    """

    BINDINGS: ClassVar = [
        Binding("l", "toggle_layout", "Toggle layout"),
        Binding("t", "open_amber_queue", "Triage"),
        Binding("m", "open_amber_queue", "Amber queue", show=False),
        Binding("g", "open_clause_graph", "Clause graph"),
        Binding("]", "next_doc", "Next document"),
        Binding("[", "prev_doc", "Prev document"),
        Binding("right", "next_page", "Next page"),
        Binding("left", "prev_page", "Prev page"),
        Binding("escape", "close", "Close"),
    ]

    def __init__(
        self,
        reports: list[ReviewReport],
        mode: str = "precheck",
        error: str | None = None,
        document_paths: list[pathlib.Path] | None = None,
    ) -> None:
        super().__init__()
        self._reports = reports
        self._mode = mode
        self._error = error
        # Paths of the reviewed documents, in report order. Optional: the
        # history/search/client call sites load a saved report and genuinely
        # have no path to offer. Empty/None disables the clause-graph binding.
        self._document_paths = document_paths
        self._layout_split = True
        self._export_format: str = "md"
        self._right_labels: dict[str, Label] = {}
        self._current_page: int = 0
        # Index of the report in view when several documents come back in a batch.
        self._current_report: int = 0
        # Triage ledger handed back by the amber queue screen (Phase 5).
        self._amber_state: AmberQueueState | None = None

    # ── Batch (multi-document) helpers ────────────────────────────────

    def _active_report(self) -> ReviewReport | None:
        """Return the report currently in view, clamped to the batch bounds."""
        if not self._reports:
            return None
        index = min(max(self._current_report, 0), len(self._reports) - 1)
        return self._reports[index]

    def _active_assessments(self) -> list[ClauseAssessment]:
        report = self._active_report()
        if report is None:
            return []
        return list(getattr(report, "assessments", None) or [])

    @staticmethod
    def _report_filename(report: ReviewReport) -> str:
        filename = getattr(getattr(report, "document", None), "filename", None)
        return str(filename) if filename else "Untitled document"

    def _header_text(self, active: ReviewReport | None) -> str:
        if self._error:
            return f"Review failed: {self._error}"
        if active is None:
            return "Review complete"
        return f"Review complete \u2014 {self._report_filename(active)}"

    def _doc_context_text(self, active: ReviewReport, assessments: list[ClauseAssessment]) -> str:
        """Sub-header describing the active document and, for batches, the whole set."""
        count = len(assessments)
        noun = "clause" if count == 1 else "clauses"
        doc_count = len(self._reports)
        if doc_count <= 1:
            return f"{self._report_filename(active)} \u00b7 {count} {noun}"
        total = sum(len(getattr(r, "assessments", None) or []) for r in self._reports)
        total_noun = "clause" if total == 1 else "clauses"
        return (
            f"Document {self._current_report + 1} of {doc_count}: "
            f"{self._report_filename(active)} \u00b7 {count} {noun}\n"
            f"Batch: {doc_count} documents \u00b7 {total} {total_noun} total"
        )

    def compose(self) -> ComposeResult:  # noqa: PLR0915  # ponytail: one linear layout tree
        doc_count = len(self._reports)
        # Clamp the active index so a shrinking batch never points out of range.
        self._current_report = min(max(self._current_report, 0), doc_count - 1) if doc_count else 0
        active = self._active_report()
        assessments = self._active_assessments()
        total = len(assessments)
        total_pages = max(1, (total + CLAUSES_PER_PAGE - 1) // CLAUSES_PER_PAGE)
        # Counted here so the amber-queue entry point is safe on every branch,
        # including empty reports and error screens (amber == 0 there).
        amber = sum(1 for a in assessments if a.color == "amber")

        with Vertical(id="result-container"):
            yield Static(self._header_text(active), id="result-header", markup=False)
            if self._error:
                yield Container(id="step-content")
            elif active is None:
                yield Container(Static("No clauses found.", markup=False), id="step-content")
            else:
                with Container(id="step-content"):
                    yield Static(
                        self._doc_context_text(active, assessments),
                        id="doc-context",
                        markup=False,
                    )
                    if not assessments:
                        yield Static("No clauses found for this document.", markup=False)
                    else:
                        green = sum(1 for a in assessments if a.color == "green")
                        red = sum(1 for a in assessments if a.color == "red")
                        start = self._current_page * CLAUSES_PER_PAGE
                        end = min(start + CLAUSES_PER_PAGE, total)
                        page_assessments = assessments[start:end]
                        summary = (
                            f"{green} Green \u00b7 {amber} Amber \u00b7 {red} Red "
                            f"\u00b7 {total} clauses"
                        )
                        if total_pages > 1:
                            summary += f" \u00b7 Page {self._current_page + 1} of {total_pages}"
                        yield Static(summary, classes="summary-header")
                        yield self._build_split_view(page_assessments)
                        yield self._build_full_screen(page_assessments)
            with Container(id="export-view"):
                with Vertical():
                    yield Static("Select export format", id="export-title")
                    yield Button("Markdown (.md)", id="btn-fmt-md", variant="primary")
                    yield Button("JSON (.json)", id="btn-fmt-json", variant="primary")
                    yield Button("DOCX (.docx)", id="btn-fmt-docx", variant="primary")
                    yield Button("Cancel", id="btn-export-cancel", variant="default")
            with Container(id="save-view"):
                with Vertical():
                    yield Static(id="save-title")
                    yield Label(id="save-file-path")
                    yield Label(f"The file will be saved to {DEFAULT_OUTPUT_DIR}/")
                    yield Button("Save", id="btn-save", variant="primary")
                    yield Button("Cancel", id="btn-save-cancel", variant="default")
            yield Static("", id="description-bar")
            with Horizontal(id="result-nav"):
                if doc_count > 1:
                    yield Button(
                        "Prev doc",
                        id="btn-prev-doc",
                        variant="default",
                        disabled=self._current_report == 0,
                    )
                if total_pages > 1:
                    yield Button(
                        "Prev page",
                        id="btn-prev-page",
                        variant="default",
                        disabled=self._current_page == 0,
                    )
                yield Button("Export memo", id="btn-export", variant="primary")
                if amber:
                    yield Button(
                        f"Amber queue ({amber})",
                        id="btn-amber-queue",
                        variant="warning",
                    )
                # Discoverable affordance for the `g` binding: rendered under the
                # exact condition that enables it, so the button and the binding
                # can never disagree. `compose` clamped `_current_report` above,
                # and the helper is a no-op (never raises) on empty/error screens.
                if self._document_path_for_active_report() is not None:
                    yield Button("Clause graph", id="btn-clause-graph", variant="default")
                yield Button("Close", id="btn-close", variant="default")
                if total_pages > 1:
                    yield Button(
                        "Next page",
                        id="btn-next-page",
                        variant="default",
                        disabled=self._current_page >= total_pages - 1,
                    )
                if doc_count > 1:
                    yield Button(
                        "Next doc",
                        id="btn-next-doc",
                        variant="default",
                        disabled=self._current_report >= doc_count - 1,
                    )

    def _build_split_view(self, assessments: list[ClauseAssessment]) -> Horizontal:
        """Build split view with clause list (left) and detail (right)."""
        items = [
            ListItem(
                Label(
                    f"{i + 1}. [{status_color_tag(a.color)}] "
                    f"{(a.clause_text or getattr(a, 'clause_ref', None) or f'Clause {i}')[:50]}",
                    markup=False,
                )
            )
            for i, a in enumerate(assessments)
        ]
        first = assessments[0]
        labels: dict[str, Label] = {
            "status": Label(f"Status: {first.color}"),
            "confidence": Label(
                f"Confidence: {first.effective_confidence or first.confidence:.2f}"
            ),
            "clause": Label(f"Clause: {first.clause_text or '\u2014'}", markup=False),
            "position": Label(f"Position: {first.position.value}"),
        }
        reasoning = getattr(first, "reasoning", None) or getattr(
            first, "qa_revised_rationale", None
        )
        labels["reasoning"] = Label(
            f"Reasoning: {str(reasoning)[:200]}" if reasoning else "", markup=False
        )
        self._right_labels = labels
        return Horizontal(
            ListView(*items, id="clause-list-pane"),
            Vertical(*labels.values(), id="clause-detail-pane"),
            id="split-view",
        )

    def _build_full_screen(self, assessments: list[ClauseAssessment]) -> Vertical:
        """Build full-screen scroll view."""
        children: list[Label] = []
        for i, a in enumerate(assessments):
            text = a.clause_text or getattr(a, "clause_ref", None) or f"Clause {i}"
            children.append(Label(f"{i + 1}. [{status_color_tag(a.color)}] {text}", markup=False))
            children.append(Label(f"   Confidence: {a.effective_confidence or a.confidence:.2f}"))
            reasoning = getattr(a, "reasoning", None) or getattr(a, "qa_revised_rationale", None)
            if reasoning:
                children.append(Label(f"   Reasoning: {str(reasoning)[:100]}", markup=False))
        return Vertical(*children, id="full-screen-scroll")

    async def action_toggle_layout(self) -> None:
        """Toggle between split view and full-screen scroll."""
        if not self.query("#split-view"):
            return
        self._layout_split = not self._layout_split
        split_view = self.query_one("#split-view", Horizontal)
        full_scroll = self.query_one("#full-screen-scroll", Vertical)
        split_view.display = self._layout_split
        full_scroll.display = not self._layout_split

    def action_close(self) -> None:
        self.app.pop_screen()

    # ── Clause graph ──────────────────────────────────────────────────

    def _document_path_for_active_report(self) -> pathlib.Path | None:
        """On-disk path of the document currently in view, or ``None``.

        ``run_review_via_tui`` returns reports in input order, so the clamped
        batch index lines up with ``document_paths[index]``. It can, however,
        drop documents it failed to process, so the report batch may be shorter
        than the path batch; when the positional path does not name the report
        in view we fall back to matching the report filename to a basename.
        """
        if not self._document_paths:
            return None
        report = self._active_report()
        if report is None:
            return None
        index = min(max(self._current_report, 0), len(self._reports) - 1)
        filename = self._report_filename(report)
        if index < len(self._document_paths) and self._document_paths[index].name == filename:
            return self._document_paths[index]
        for candidate in self._document_paths:
            if candidate.name == filename:
                return candidate
        if index < len(self._document_paths):
            return self._document_paths[index]
        return None

    def action_open_clause_graph(self) -> None:
        """Open the read-only clause-graph summary for the active document."""
        path = self._document_path_for_active_report()
        if path is None:
            return
        from openreview_cli.tui.screens.graph import GraphSummaryScreen

        self.app.push_screen(GraphSummaryScreen(path))

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Disable the clause-graph binding when no document path is known.

        Unavailable for saved-report screens (no ``document_paths``), empty
        batches and error screens, and when the active index runs past the end
        of the supplied paths. Never raises on an error screen.
        """
        if action == "open_clause_graph":
            return self._document_path_for_active_report() is not None
        return super().check_action(action, parameters)

    def action_open_amber_queue(self) -> None:
        """Open the interactive amber triage screen (Phase 5)."""
        report = self._active_report()
        if report is None:
            return
        from openreview_cli.tui.domain.amber import collect_amber
        from openreview_cli.tui.screens.amber_queue import AmberQueueScreen

        if not collect_amber(report):
            self.notify("No amber clauses to triage.", severity="information")
            return
        self.app.push_screen(AmberQueueScreen(report=report), self._on_amber_triage_done)

    def _on_amber_triage_done(self, state: AmberQueueState | None) -> None:
        """Keep the triage decisions taken in the amber queue (Phase 5)."""
        if state is None:
            return
        self._amber_state = state
        if not (state.decided or state.notes):
            return
        self.notify(
            f"Amber triage: {state.accepted} accepted, {state.flagged} flagged, "
            f"{len(state.notes)} noted.",
            severity="information",
            timeout=5,
        )

    async def action_next_page(self) -> None:
        """Go to next page of clauses."""
        total = len(self._active_assessments())
        total_pages = max(1, (total + CLAUSES_PER_PAGE - 1) // CLAUSES_PER_PAGE)
        if self._current_page < total_pages - 1:
            self._current_page += 1
            await self.recompose()

    async def action_prev_page(self) -> None:
        """Go to previous page of clauses."""
        if self._current_page > 0:
            self._current_page -= 1
            await self.recompose()

    async def action_next_doc(self) -> None:
        """Switch to the next document when a batch holds several reports."""
        if self._current_report < len(self._reports) - 1:
            self._current_report += 1
            self._current_page = 0
            await self.recompose()

    async def action_prev_doc(self) -> None:
        """Switch to the previous document when a batch holds several reports."""
        if self._current_report > 0:
            self._current_report -= 1
            self._current_page = 0
            await self.recompose()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "clause-list-pane":
            return
        assessments = self._active_assessments()
        if not assessments or event.item is None:
            return
        self._update_focus(assessments)

    def _update_focus(self, assessments: list[ClauseAssessment]) -> None:
        """Update detail pane and description bar for focused clause."""
        idx = self.query_one("#clause-list-pane", ListView).index
        if idx is None or idx < 0:
            return
        start = self._current_page * CLAUSES_PER_PAGE
        full_idx = start + idx
        if full_idx < 0 or full_idx >= len(assessments):
            return
        focused = assessments[full_idx]
        if self._layout_split and self._right_labels:
            self._right_labels["status"].update(f"Status: {focused.color}")
            self._right_labels["confidence"].update(
                f"Confidence: {focused.effective_confidence or focused.confidence:.2f}"
            )
            self._right_labels["clause"].update(f"Clause: {focused.clause_text or '\u2014'}")
            self._right_labels["position"].update(f"Position: {focused.position.value}")
            reasoning = getattr(focused, "reasoning", None) or getattr(
                focused, "qa_revised_rationale", None
            )
            self._right_labels["reasoning"].update(
                f"Reasoning: {str(reasoning)[:200]}" if reasoning else ""
            )
        self.query_one("#description-bar", Static).update(
            f"Clause {full_idx + 1} \u2014 Status: {focused.color}  "
            f"Confidence: {focused.effective_confidence or focused.confidence:.2f}"
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-next-page":
            await self.action_next_page()
        elif btn_id == "btn-prev-page":
            await self.action_prev_page()
        elif btn_id == "btn-next-doc":
            await self.action_next_doc()
        elif btn_id == "btn-prev-doc":
            await self.action_prev_doc()
        elif btn_id == "btn-close":
            self.action_close()
        elif btn_id == "btn-amber-queue":
            self.action_open_amber_queue()
        elif btn_id == "btn-clause-graph":
            self.action_open_clause_graph()
        elif btn_id == "btn-export":
            self.query_one("#step-content", Container).display = False
            self.query_one("#export-view", Container).display = True
        elif btn_id in ("btn-fmt-md", "btn-fmt-json", "btn-fmt-docx"):
            self._export_format = btn_id.split("-")[-1]
            ext = f".{self._export_format}"
            self.query_one("#save-title", Static).update(f"Save as {self._export_format.upper()}")
            self.query_one("#save-file-path", Label).update(
                f"File: {DEFAULT_OUTPUT_DIR}/review-result{ext}"
            )
            self.query_one("#export-view", Container).display = False
            self.query_one("#save-view", Container).display = True
        elif btn_id == "btn-save":
            await self._do_save()
        elif btn_id in ("btn-export-cancel", "btn-save-cancel"):
            await self._reset_export()

    async def _do_save(self) -> None:
        """Write the currently viewed report using MemoExporter."""
        report = self._active_report()
        if report is None:
            self.notify("No report to export.", severity="error")
            await self._reset_export()
            return
        from openreview_cli.review.memo.exporter import MemoExporter
        from openreview_cli.review.memo.models import MemoFormat

        fmt_map = {"md": MemoFormat.MARKDOWN, "json": MemoFormat.JSON, "docx": MemoFormat.DOCX}
        memo_fmt = fmt_map.get(self._export_format)
        if memo_fmt is None:
            self.notify(f"Unsupported format: {self._export_format}", severity="error")
            await self._reset_export()
            return
        try:
            exporter = MemoExporter(
                report=report,
                mode=self._mode,
                output_dir=DEFAULT_OUTPUT_DIR,
                formats={memo_fmt},
            )
            result_paths = exporter.export()
            if result_paths:
                path = list(result_paths.values())[0]
                self.notify(f"Exported to {path}", severity="information", timeout=5)
            else:
                self.notify("Export failed: no files written.", severity="error")
        except Exception as exc:
            self.notify(f"Export error: {exc}", severity="error")
        await self._reset_export()

    async def _reset_export(self) -> None:
        """Return to main report view after export."""
        self.query_one("#export-view", Container).display = False
        self.query_one("#save-view", Container).display = False
        self.query_one("#step-content", Container).display = True
