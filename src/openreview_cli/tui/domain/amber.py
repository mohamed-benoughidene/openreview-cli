"""Amber Queue triage helpers — collect amber clauses and track decisions (Phase 5).

The ledger stays deliberately simple (Ponytail trim): decisions are a
``list[str]`` with one entry per clause and the tallies are derived with
``collections.Counter``; annotations are a ``dict[str, str]`` keyed by clause id
so notes survive re-indexing.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openreview_cli.review.models import ClauseAssessment, ReviewReport

DECISION_PENDING = "pending"
DECISION_ACCEPTED = "accepted"
DECISION_FLAGGED = "flagged"


def collect_amber(report: ReviewReport | None) -> list[ClauseAssessment]:
    """Return the amber assessments of ``report`` in document order.

    A clause counts as amber when its assigned colour is ``amber``, or when the
    legacy ``is_amber`` flag is set (colour never assigned).
    """
    assessments: list[ClauseAssessment] = list(getattr(report, "assessments", None) or [])
    return [
        a
        for a in assessments
        if str(getattr(a, "color", None) or "") == "amber" or getattr(a, "is_amber", False) is True
    ]


@dataclass
class AmberQueueState:
    """Triage ledger for the amber queue: one decision and one note per clause."""

    clauses: list[ClauseAssessment]
    decisions: list[str] = field(init=False)
    notes: dict[str, str] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.decisions = [DECISION_PENDING] * len(self.clauses)

    # ── Tallies ───────────────────────────────────────────────────────

    @property
    def total(self) -> int:
        return len(self.clauses)

    @property
    def counts(self) -> Counter[str]:
        return Counter(self.decisions)

    @property
    def decided(self) -> int:
        return self.total - self.counts[DECISION_PENDING]

    @property
    def accepted(self) -> int:
        return self.counts[DECISION_ACCEPTED]

    @property
    def flagged(self) -> int:
        return self.counts[DECISION_FLAGGED]

    # ── Decisions & annotations ───────────────────────────────────────

    def current_decision(self, index: int) -> str:
        return self.decisions[index]

    def current_note(self, index: int) -> str:
        return self.notes.get(self._note_key(index), "")

    def decide(self, index: int, decision: str) -> None:
        self.decisions[index] = decision

    def annotate(self, index: int, note: str) -> None:
        """Store a clause note; an empty ``note`` clears it."""
        key = self._note_key(index)
        if note:
            self.notes[key] = note
        else:
            self.notes.pop(key, None)

    def next_pending(self, after: int) -> int | None:
        """Index of the first pending clause after ``after`` (wrapping), else ``None``."""
        return self._find_pending(after, step=1)

    def prev_pending(self, before: int) -> int | None:
        """Index of the last pending clause before ``before`` (wrapping), else ``None``."""
        return self._find_pending(before, step=-1)

    # ── Table row ─────────────────────────────────────────────────────

    def row(self, index: int) -> tuple[str, str, str]:
        """``(clause id, truncated text, decision)`` for the overview table."""
        clause = self.clauses[index]
        return (str(clause.clause_id), (clause.clause_text or "")[:40], self.decisions[index])

    # ── Internals ─────────────────────────────────────────────────────

    def _note_key(self, index: int) -> str:
        clause_id = getattr(self.clauses[index], "clause_id", None)
        return str(clause_id) if clause_id else f"#{index}"

    def _find_pending(self, start: int, *, step: int) -> int | None:
        for offset in range(1, self.total + 1):
            index = (start + offset * step) % self.total
            if self.decisions[index] == DECISION_PENDING:
                return index
        return None
