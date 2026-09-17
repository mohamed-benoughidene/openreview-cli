"""Amber Queue triage screen — step through the clauses needing a human call (Phase 5).

Guided workflow keys::

    A accept · R reject · N note · S / J / Down next · K / Up previous
    T / O toggle the overview table · Esc / Q done (back to the result screen)

Two views share one ledger: the guided card (default) walks the queue one clause
at a time, the overview table lists every amber clause with its decision and note
(hidden by default, kept per the audit decision so the whole queue stays visible).

Textual notes:
* button hints use parentheses — the markup parser reads ``[A]`` in a Button
  label as a style tag and drops it;
* the clause text is rendered with ``markup=False`` (Labels) or as a Rich
  ``Text`` (DataTable cells), because ``escape()`` does not protect
  uppercase-initial brackets such as ``[Party A]``;
* the DataTable is non-focusable and cells/columns are addressed by explicit keys
  so ``update_cell`` can never raise ``CellDoesNotExist`` and Up/Down keep
  driving the queue instead of the table cursor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Input, Label, Static

from openreview_cli.tui.domain.amber import (
    DECISION_ACCEPTED,
    DECISION_FLAGGED,
    AmberQueueState,
    collect_amber,
)

if TYPE_CHECKING:
    from openreview_cli.review.models import ReviewReport

#: Overview columns, each with an explicit key so ``update_cell`` is key-addressed.
_OVERVIEW_COLUMNS: list[tuple[str, str]] = [
    ("#", "c-num"),
    ("Clause", "c-clause"),
    ("Text", "c-text"),
    ("Decision", "c-decision"),
    ("Note", "c-note"),
]


class AnnotateModal(ModalScreen[str | None]):
    """Prompt for a free-text note about the clause currently in view."""

    DEFAULT_CSS = """
    AnnotateModal { align: center middle; }
    AnnotateModal > Vertical {
        width: 70; padding: 1 2; background: $surface; border: thick $primary;
    }
    AnnotateModal #annotate-title { text-style: bold; margin: 0 0 1 0; }
    AnnotateModal #annotate-input { margin: 0 0 1 0; }
    AnnotateModal Horizontal { align: right middle; height: auto; }
    AnnotateModal Button { margin: 0 0 0 1; }
    """

    BINDINGS: ClassVar = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, note: str = "") -> None:
        super().__init__()
        self._note = note

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Note for this clause — Enter saves, Esc cancels", id="annotate-title")
            yield Input(value=self._note, id="annotate-input")
            with Horizontal():
                yield Button("Save (Enter)", id="btn-note-save", variant="primary")
                yield Button("Cancel (Esc)", id="btn-note-cancel", variant="default")

    def on_mount(self) -> None:
        note_input = self.query_one("#annotate-input", Input)
        note_input.focus()
        note_input.cursor_position = len(self._note)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-note-save":
            self.dismiss(self.query_one("#annotate-input", Input).value)
        else:
            self.dismiss(None)


class AmberQueueScreen(Screen[AmberQueueState]):
    """Step-by-step triage of the amber clauses in one review report."""

    DEFAULT_CSS = """
    AmberQueueScreen #amber-container { height: 100%; padding: 1 2; }
    AmberQueueScreen #amber-header { text-style: bold; padding: 0 0 1 0; }
    AmberQueueScreen #amber-guided { height: auto; }
    AmberQueueScreen #amber-detail { height: auto; padding: 0 1; border: solid $primary; }
    AmberQueueScreen #amber-overview { height: 1fr; min-height: 5; }
    AmberQueueScreen #amber-actions {
        dock: bottom; height: 3; padding: 0 1; align: center middle;
    }
    AmberQueueScreen #amber-actions Button { margin: 0 1; min-width: 14; }
    """

    BINDINGS: ClassVar = [
        Binding("a", "accept", "Accept"),
        Binding("r", "reject", "Reject"),
        Binding("n", "annotate", "Note"),
        Binding("s", "next", "Next"),
        Binding("j", "next", "Next", show=False),
        Binding("down", "next", "Next", show=False),
        Binding("k", "previous", "Previous"),
        Binding("up", "previous", "Previous", show=False),
        Binding("t", "toggle_overview", "Overview"),
        Binding("o", "toggle_overview", "Overview", show=False),
        Binding("escape", "close", "Done"),
        Binding("q", "close", "Done", show=False),
    ]

    def __init__(self, report: ReviewReport) -> None:
        super().__init__()
        self._state = AmberQueueState(clauses=collect_amber(report))
        self._index = 0
        self._overview = False

    # ── Layout ────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Vertical(id="amber-container"):
            yield Static("", id="amber-header", markup=False)
            with Vertical(id="amber-guided"):
                yield Label("", id="amber-detail", markup=False)
            table: DataTable[str | Text] = DataTable(id="amber-overview")
            # Up/Down drive the queue, so the table must never take focus.
            table.can_focus = False
            yield table
            with Horizontal(id="amber-actions"):
                yield Button("Accept (A)", id="btn-accept", variant="success")
                yield Button("Reject (R)", id="btn-reject", variant="error")
                yield Button("Note (N)", id="btn-note", variant="default")
                yield Button("Prev (K)", id="btn-prev", variant="default")
                yield Button("Next (S)", id="btn-next", variant="default")
                yield Button("Overview (T)", id="btn-overview", variant="default")
                yield Button("Done (Esc)", id="btn-close", variant="default")

    def on_mount(self) -> None:
        table = self.query_one("#amber-overview", DataTable)
        table.add_columns(*_OVERVIEW_COLUMNS)
        for index in range(self._state.total):
            clause_id, short_text, decision = self._state.row(index)
            table.add_row(
                Text(str(index + 1), no_wrap=True, end=""),
                Text(clause_id, no_wrap=True, end=""),
                Text(short_text, no_wrap=True, end=""),
                decision,
                Text(self._state.current_note(index), no_wrap=True, end=""),
                key=str(index),
            )
        self._refresh()

    # ── View ──────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        """Re-render the active view (guided card or overview table) and the header."""
        header = self.query_one("#amber-header", Static)
        detail = self.query_one("#amber-detail", Label)
        guided = self.query_one("#amber-guided", Vertical)
        table = self.query_one("#amber-overview", DataTable)

        guided.display = not self._overview
        table.display = self._overview

        if self._state.total == 0:
            header.update("Amber queue — no amber clauses to triage.")
            detail.update("")
            for button_id in (
                "#btn-accept",
                "#btn-reject",
                "#btn-note",
                "#btn-next",
                "#btn-prev",
            ):
                self.query_one(button_id, Button).disabled = True
            return

        header.update(self._header_text())
        detail.update(self._detail_text(self._index))
        table.move_cursor(row=self._index)

    def _header_text(self) -> str:
        state = self._state
        text = (
            f"Amber {self._index + 1} of {state.total} — "
            f"{state.accepted} accepted · {state.flagged} flagged · "
            f"{state.total - state.decided} pending"
        )
        if state.decided == state.total:
            text += "  —  queue complete"
        return text

    def _detail_text(self, index: int) -> str:
        state = self._state
        clause = state.clauses[index]
        reasons = ", ".join(str(r) for r in getattr(clause, "amber_reasons", None) or []) or "—"
        confidence = getattr(clause, "effective_confidence", None)
        if confidence is None:
            confidence = getattr(clause, "confidence", 0.0)
        return (
            f"{state.current_decision(index).upper()} · Clause {clause.clause_id} "
            f"(confidence {confidence:.2f})\n"
            f"Reason(s): {reasons}\n"
            f"Note: {state.current_note(index) or '—'}\n\n"
            f"{clause.clause_text or ''}"
        )

    # ── Actions ───────────────────────────────────────────────────────

    def action_accept(self) -> None:
        self._decide(DECISION_ACCEPTED)

    def action_reject(self) -> None:
        self._decide(DECISION_FLAGGED)

    def action_next(self) -> None:
        self._move(1)

    def action_previous(self) -> None:
        self._move(-1)

    def action_toggle_overview(self) -> None:
        self._overview = not self._overview
        self._refresh()

    def action_annotate(self) -> None:
        """Open the note prompt for the clause currently in view."""
        if self._state.total == 0:
            return
        self.app.push_screen(AnnotateModal(self._state.current_note(self._index)), self._on_note)

    def action_close(self) -> None:
        """Return to the result screen, handing back the triage ledger."""
        self.dismiss(self._state)

    # ── Internals ─────────────────────────────────────────────────────

    def _move(self, step: int) -> None:
        """Step to the next/previous clause, preferring one still pending."""
        if self._state.total == 0:
            return
        found = (
            self._state.next_pending(self._index)
            if step > 0
            else self._state.prev_pending(self._index)
        )
        if found is None:
            # Everything is decided: keep stepping so the queue stays browsable.
            found = (self._index + step) % self._state.total
        self._index = found
        self._refresh()

    def _decide(self, decision: str) -> None:
        """Record a decision and auto-advance to the next pending clause."""
        if self._state.total == 0:
            return
        self._state.decide(self._index, decision)
        self._sync_row(self._index)
        pending = self._state.next_pending(self._index)
        if pending is not None:
            self._index = pending
        self._refresh()

    def _on_note(self, note: str | None) -> None:
        """Keep the note returned by the annotate modal (``None`` = cancelled)."""
        if note is None or self._state.total == 0:
            return
        self._state.annotate(self._index, note)
        self._sync_row(self._index)
        self._refresh()
        self.notify("Note saved.", timeout=2)

    def _sync_row(self, index: int) -> None:
        """Update the decision/note cells of one row via explicit column keys."""
        table = self.query_one("#amber-overview", DataTable)
        _, _, decision = self._state.row(index)
        table.update_cell(str(index), "c-decision", decision)
        table.update_cell(
            str(index),
            "c-note",
            Text(self._state.current_note(index), no_wrap=True, end=""),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        handlers = {
            "btn-accept": self.action_accept,
            "btn-reject": self.action_reject,
            "btn-note": self.action_annotate,
            "btn-prev": self.action_previous,
            "btn-next": self.action_next,
            "btn-overview": self.action_toggle_overview,
            "btn-close": self.action_close,
        }
        handler = handlers.get(event.button.id or "")
        if handler is not None:
            handler()
