"""Amber Queue triage state machine (Phase 5).

Pure-data tests for ``openreview_cli.tui.domain.amber``: amber collection plus
the decision/annotation ledger used by ``AmberQueueScreen``.  Kept free of any
Textual import so it runs in the fast (<1 s) feedback loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from openreview_cli.tui.domain.amber import (
    DECISION_ACCEPTED,
    DECISION_FLAGGED,
    DECISION_PENDING,
    AmberQueueState,
    collect_amber,
)


@dataclass
class _Assessment:
    """Minimal stand-in for ``ClauseAssessment`` (only the amber-relevant fields)."""

    clause_id: str
    clause_text: str = ""
    color: str | None = "amber"
    is_amber: bool = False
    confidence: float = 0.5
    effective_confidence: float | None = None
    amber_reasons: list[str] = field(default_factory=list)


@dataclass
class _Report:
    assessments: list[_Assessment]


def _report(*assessments: _Assessment) -> _Report:
    return _Report(assessments=list(assessments))


# ── collect_amber ─────────────────────────────────────────────────────


def test_collect_amber_returns_only_amber_in_document_order() -> None:
    report = _report(
        _Assessment("c1", color="green"),
        _Assessment("c2", color="amber"),
        _Assessment("c3", color="red"),
        _Assessment("c4", color="amber"),
        _Assessment("c5", color="amber"),
    )

    assert [a.clause_id for a in collect_amber(report)] == ["c2", "c4", "c5"]


def test_collect_amber_honours_is_amber_when_no_colour_assigned() -> None:
    """A legacy assessment flagged via ``is_amber`` (colour never assigned) counts."""
    report = _report(
        _Assessment("c1", color=None, is_amber=True),
        _Assessment("c2", color=None, is_amber=False),
    )

    assert [a.clause_id for a in collect_amber(report)] == ["c1"]


def test_collect_amber_tolerates_missing_assessments() -> None:
    class _NoAssessments:
        pass

    assert collect_amber(_NoAssessments()) == []  # type: ignore[arg-type]
    assert collect_amber(_report()) == []


# ── AmberQueueState ───────────────────────────────────────────────────


def _state() -> AmberQueueState:
    return AmberQueueState(
        clauses=collect_amber(
            _report(
                _Assessment("c1", color="green"),
                _Assessment("c2", color="amber", clause_text="text c2"),
                _Assessment("c3", color="red"),
                _Assessment("c4", color="amber", clause_text="text c4"),
                _Assessment("c5", color="amber", clause_text="text c5"),
            )
        )
    )


def test_state_seeds_every_clause_as_pending() -> None:
    state = _state()

    assert (state.total, state.decided) == (3, 0)
    assert [state.current_decision(i) for i in range(state.total)] == [DECISION_PENDING] * 3


def test_state_tracks_decisions_with_a_counter() -> None:
    state = _state()
    state.decide(0, DECISION_ACCEPTED)
    state.decide(1, DECISION_FLAGGED)

    assert state.accepted == 1
    assert state.flagged == 1
    assert state.decided == 2
    assert state.current_decision(2) == DECISION_PENDING


def test_decisions_can_be_revised() -> None:
    state = _state()
    state.decide(0, DECISION_ACCEPTED)
    state.decide(0, DECISION_FLAGGED)

    assert (state.accepted, state.flagged) == (0, 1)


def test_next_pending_skips_decided_and_wraps() -> None:
    state = _state()
    state.decide(0, DECISION_ACCEPTED)

    assert state.next_pending(0) == 1
    # Wrapping past the end skips the decided clause at index 0.
    assert state.next_pending(2) == 1

    state.decide(1, DECISION_ACCEPTED)
    state.decide(2, DECISION_FLAGGED)

    assert state.next_pending(2) is None  # everything decided


def test_prev_pending_skips_decided_and_wraps() -> None:
    state = _state()
    state.decide(2, DECISION_FLAGGED)

    assert state.prev_pending(0) == 1
    assert state.prev_pending(1) == 0

    state.decide(0, DECISION_ACCEPTED)
    state.decide(1, DECISION_ACCEPTED)

    assert state.prev_pending(0) is None


def test_empty_queue_is_inert() -> None:
    state = AmberQueueState(clauses=[])

    assert (state.total, state.decided, state.accepted, state.flagged) == (0, 0, 0, 0)
    assert state.next_pending(0) is None
    assert state.prev_pending(0) is None


def test_annotate_stores_and_clears_notes() -> None:
    state = _state()
    state.annotate(0, "Escalate to counsel")
    state.annotate(1, "")

    assert state.current_note(0) == "Escalate to counsel"
    assert state.current_note(1) == ""
    assert state.notes == {"c2": "Escalate to counsel"}


def test_annotate_keeps_notes_off_the_decision_ledger() -> None:
    state = _state()
    state.annotate(2, "only a note")

    assert state.decided == 0
    assert state.current_decision(2) == DECISION_PENDING


def test_row_reports_id_short_text_and_decision() -> None:
    state = _state()
    state.decide(0, DECISION_ACCEPTED)

    assert state.row(0) == ("c2", "text c2", DECISION_ACCEPTED)
    assert state.row(1) == ("c4", "text c4", DECISION_PENDING)
