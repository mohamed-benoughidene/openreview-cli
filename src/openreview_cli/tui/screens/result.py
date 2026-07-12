"""Result screen — split view, layout toggle, export."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, Static

from openreview_cli.review.models import ClauseAssessment, ReviewReport

CLAUSES_PER_PAGE = 100


class ResultScreen(Screen[None]):
    """Result screen with split view, layout toggle, summary header, and export."""

    DEFAULT_CSS = """
    ResultScreen #result-container { height: 100%; }
    ResultScreen #result-header { text-style: bold; background: $primary; color: $text; padding: 1 2; }
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
        Binding("right", "next_page", "Next page"),
        Binding("left", "prev_page", "Prev page"),
        Binding("escape", "close", "Close"),
    ]

    def __init__(
        self,
        reports: list[ReviewReport],
        mode: str = "precheck",
        error: str | None = None,
    ) -> None:
        super().__init__()
        self._reports = reports
        self._mode = mode
        self._error = error
        self._layout_split = True
        self._export_format: str = "md"
        self._right_labels: dict[str, Label] = {}
        self._current_page: int = 0

    def compose(self) -> ComposeResult:
        total_pages = 1
        if self._reports and self._reports[0].assessments:
            total = len(self._reports[0].assessments)
            total_pages = max(1, (total + CLAUSES_PER_PAGE - 1) // CLAUSES_PER_PAGE)
        with Vertical(id="result-container"):
            yield Static(
                "Review complete" if not self._error else f"Review failed: {self._error}",
                id="result-header",
            )
            if self._error:
                yield Container(id="step-content")
            elif not self._reports or not self._reports[0].assessments:
                yield Container(Static("No clauses found."), id="step-content")
            else:
                all_assessments = self._reports[0].assessments
                total = len(all_assessments)
                green = sum(1 for a in all_assessments if a.color and a.color == "green")
                amber = sum(1 for a in all_assessments if a.color and a.color == "amber")
                red = sum(1 for a in all_assessments if a.color and a.color == "red")
                start = self._current_page * CLAUSES_PER_PAGE
                end = min(start + CLAUSES_PER_PAGE, total)
                page_assessments = all_assessments[start:end]
                summary = (
                    f"{green} Green \u00b7 {amber} Amber \u00b7 {red} Red \u00b7 {total} clauses"
                )
                if total_pages > 1:
                    summary += f" \u00b7 Page {self._current_page + 1} of {total_pages}"
                with Container(id="step-content"):
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
                    yield Label("The file will be saved to /tmp/")
                    yield Button("Save", id="btn-save", variant="primary")
                    yield Button("Cancel", id="btn-save-cancel", variant="default")
            yield Static("", id="description-bar")
            with Horizontal(id="result-nav"):
                if total_pages > 1:
                    yield Button(
                        "Prev page",
                        id="btn-prev-page",
                        variant="default",
                        disabled=self._current_page == 0,
                    )
                yield Button("Export memo", id="btn-export", variant="primary")
                yield Button("Close", id="btn-close", variant="default")
                if total_pages > 1:
                    yield Button(
                        "Next page",
                        id="btn-next-page",
                        variant="default",
                        disabled=self._current_page >= total_pages - 1,
                    )

    def _build_split_view(self, assessments: list[ClauseAssessment]) -> Horizontal:
        """Build split view with clause list (left) and detail (right)."""
        items = [
            ListItem(
                Label(
                    f"{i + 1}. [{a.color}] "
                    f"{(a.clause_text or getattr(a, 'clause_ref', None) or f'Clause {i}')[:50]}",
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
            "clause": Label(f"Clause: {first.clause_text or '\u2014'}"),
            "position": Label(f"Position: {first.position.value}"),
        }
        reasoning = getattr(first, "reasoning", None) or getattr(
            first, "qa_revised_rationale", None
        )
        labels["reasoning"] = Label(f"Reasoning: {str(reasoning)[:200]}" if reasoning else "")
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
            children.append(Label(f"{i + 1}. [{a.color}] {text}"))
            children.append(Label(f"   Confidence: {a.effective_confidence or a.confidence:.2f}"))
            reasoning = getattr(a, "reasoning", None) or getattr(a, "qa_revised_rationale", None)
            if reasoning:
                children.append(Label(f"   Reasoning: {str(reasoning)[:100]}"))
        return Vertical(*children, id="full-screen-scroll")

    async def action_toggle_layout(self) -> None:
        """Toggle between split view and full-screen scroll."""
        self._layout_split = not self._layout_split
        split_view = self.query_one("#split-view", Horizontal)
        full_scroll = self.query_one("#full-screen-scroll", Vertical)
        split_view.display = self._layout_split
        full_scroll.display = not self._layout_split

    def action_close(self) -> None:
        self.app.pop_screen()

    async def action_next_page(self) -> None:
        """Go to next page of clauses."""
        total_pages = 1
        if self._reports and self._reports[0].assessments:
            total = len(self._reports[0].assessments)
            total_pages = max(1, (total + CLAUSES_PER_PAGE - 1) // CLAUSES_PER_PAGE)
        if self._current_page < total_pages - 1:
            self._current_page += 1
            await self.recompose()

    async def action_prev_page(self) -> None:
        """Go to previous page of clauses."""
        if self._current_page > 0:
            self._current_page -= 1
            await self.recompose()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "clause-list-pane":
            return
        assessments = self._reports[0].assessments if self._reports else []
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
        elif btn_id == "btn-close":
            self.action_close()
        elif btn_id == "btn-export":
            self.query_one("#step-content", Container).display = False
            self.query_one("#export-view", Container).display = True
        elif btn_id in ("btn-fmt-md", "btn-fmt-json", "btn-fmt-docx"):
            self._export_format = btn_id.split("-")[-1]
            ext = f".{self._export_format}"
            self.query_one("#save-title", Static).update(f"Save as {self._export_format.upper()}")
            self.query_one("#save-file-path", Label).update(f"File: /tmp/review-result{ext}")
            self.query_one("#export-view", Container).display = False
            self.query_one("#save-view", Container).display = True
        elif btn_id == "btn-save":
            await self._do_save()
        elif btn_id in ("btn-export-cancel", "btn-save-cancel"):
            await self._reset_export()

    async def _do_save(self) -> None:
        """Write file using MemoExporter."""
        if not self._reports:
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
                report=self._reports[0],
                mode=self._mode,
                output_dir=Path("/tmp"),
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
