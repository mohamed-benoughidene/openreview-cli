"""Exploratory probes: amber queue triage state machine.

``openreview_cli.tui.domain.amber`` backs the interactive triage screen.  These
probes push the pure-data ledger past the committed unit tests: duplicate
clause ids, missing ids, out-of-range indices, arbitrary decision strings and
the strictness of ``collect_amber``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from openreview_cli.review.models import (
    ClauseAssessment,
    Position,
    QAVerdict,
)
from openreview_cli.tui.domain.amber import (
    DECISION_ACCEPTED,
    DECISION_FLAGGED,
    DECISION_PENDING,
    AmberQueueState,
    collect_amber,
)


@dataclass
class _Stub:
    """Minimal stand-in for a ``ClauseAssessment``."""

    clause_id: str | None
    clause_text: str = ""
    color: str | None = "amber"
    is_amber: bool = False
    confidence: float = 0.5
    effective_confidence: float | None = None
    amber_reasons: list[str] = field(default_factory=list)


class _Report:
    def __init__(self, assessments: list[object]) -> None:
        self.assessments = assessments


def _state(*ids: str | None) -> AmberQueueState:
    return AmberQueueState(clauses=[_Stub(i) for i in ids])


# ── Empty queue ────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_empty_queue_is_inert() -> None:
    state = AmberQueueState(clauses=[])
    assert (state.total, state.decided, state.accepted, state.flagged) == (0, 0, 0, 0)
    assert state.next_pending(0) is None
    assert state.prev_pending(0) is None
    assert state.notes == {}


# ── Tallies ────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_all_accepted_and_all_flagged_tallies() -> None:
    accepted = _state("c1", "c2", "c3")
    for i in range(accepted.total):
        accepted.decide(i, DECISION_ACCEPTED)
    assert (accepted.accepted, accepted.flagged, accepted.decided) == (3, 0, 3)
    assert accepted.next_pending(0) is None

    flagged = _state("c1", "c2")
    for i in range(flagged.total):
        flagged.decide(i, DECISION_FLAGGED)
    assert (flagged.accepted, flagged.flagged, flagged.decided) == (0, 2, 2)


@pytest.mark.fast
def test_decisions_can_be_revised_between_states() -> None:
    state = _state("c1")
    state.decide(0, DECISION_ACCEPTED)
    state.decide(0, DECISION_FLAGGED)
    state.decide(0, DECISION_PENDING)
    assert (state.accepted, state.flagged, state.decided) == (0, 0, 0)


@pytest.mark.fast
def test_arbitrary_decision_string_counts_as_decided_but_not_accepted_or_flagged() -> None:
    """FINDING (edge case): ``decide`` accepts any string verbatim.

    An unrecognised decision increments ``decided`` (``total -
    counts[pending]``) yet is invisible to ``accepted``/``flagged``, so the
    header tally can read ``0 accepted · 0 flagged`` while claiming progress.
    The screen only ever passes the two constants, so it is not user-reachable.
    """
    state = _state("c1", "c2")
    state.decide(0, "banana")
    assert state.decided == 1
    assert (state.accepted, state.flagged) == (0, 0)
    assert dict(state.counts) == {"banana": 1, DECISION_PENDING: 1}


# ── Notes ──────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_notes_add_and_clear() -> None:
    state = _state("c1", "c2")
    state.annotate(0, "Escalate to counsel")
    assert state.current_note(0) == "Escalate to counsel"
    assert state.notes == {"c1": "Escalate to counsel"}

    state.annotate(0, "")
    assert state.current_note(0) == ""
    assert state.notes == {}


@pytest.mark.fast
def test_annotating_does_not_change_decisions() -> None:
    state = _state("c1")
    state.annotate(0, "note only")
    assert state.decided == 0
    assert state.current_decision(0) == DECISION_PENDING


@pytest.mark.fast
def test_duplicate_clause_ids_share_one_note() -> None:
    """FINDING (edge case): notes are keyed by ``clause_id``, so two clauses
    with the same id collide and silently share a single annotation."""
    state = _state("dup", "dup")
    state.annotate(0, "note for first")
    assert state.current_note(0) == "note for first"
    assert state.current_note(1) == "note for first", "second clause shares the note"
    assert state.notes == {"dup": "note for first"}


@pytest.mark.fast
def test_missing_clause_id_falls_back_to_index_keys() -> None:
    state = _state(None, None)
    state.annotate(0, "zero")
    state.annotate(1, "one")
    assert state.notes == {"#0": "zero", "#1": "one"}
    assert state.current_note(0) == "zero"
    assert state.current_note(1) == "one"


@pytest.mark.fast
def test_row_with_missing_clause_id_stringifies_none() -> None:
    """FINDING (cosmetic): a clause without an id renders its id as ``"None"``
    in the overview table rather than an empty/placeholder label."""
    state = _state(None)
    clause_id, _text, decision = state.row(0)
    assert clause_id == "None"
    assert decision == DECISION_PENDING


@pytest.mark.fast
def test_row_truncates_text_to_40_chars() -> None:
    long = "x" * 100
    state = AmberQueueState(clauses=[_Stub("c1", clause_text=long)])
    clause_id, short, _ = state.row(0)
    assert clause_id == "c1"
    assert len(short) == 40
    assert short == "x" * 40


# ── Navigation ─────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_next_prev_pending_skip_decided_and_wrap() -> None:
    state = _state("c1", "c2", "c3")
    state.decide(1, DECISION_ACCEPTED)
    assert state.next_pending(0) == 2
    assert state.next_pending(1) == 2
    assert state.next_pending(2) == 0  # wraps past the end
    assert state.prev_pending(0) == 2
    assert state.prev_pending(1) == 0
    assert state.prev_pending(2) == 0


@pytest.mark.fast
def test_single_clause_navigation_wraps_to_itself_then_none() -> None:
    """FINDING (behaviour): with one pending clause, ``next_pending(0)`` wraps
    to ``0`` (itself).  Only once it is decided does it return ``None``; the
    screen then falls back to a plain ``(index + step) % total``."""
    state = _state("c1")
    assert state.next_pending(0) == 0
    assert state.prev_pending(0) == 0
    state.decide(0, DECISION_ACCEPTED)
    assert state.next_pending(0) is None
    assert state.prev_pending(0) is None


# ── Out-of-range / boundary indices ────────────────────────────────────────


@pytest.mark.fast
@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("decide", (5, DECISION_ACCEPTED)),
        ("decide", (100, DECISION_ACCEPTED)),
        ("annotate", (5, "x")),
        ("current_note", (5,)),
        ("current_decision", (5,)),
        ("row", (5,)),
    ],
)
def test_out_of_range_indices_raise_index_error(method: str, args: tuple[object, ...]) -> None:
    """FINDING (latent): the ledger does no bounds checking; an out-of-range
    index propagates ``IndexError``.  The screen clamps its cursor so this is
    not user-reachable today, but it is an unguarded contract."""
    state = _state("c1")
    with pytest.raises(IndexError):
        getattr(state, method)(*args)


@pytest.mark.fast
def test_negative_index_is_accepted_by_decide() -> None:
    """Python negative indexing silently aliases ``decide(-1)`` to the last."""
    state = _state("c1", "c2")
    state.decide(-1, DECISION_FLAGGED)
    assert state.current_decision(1) == DECISION_FLAGGED


# ── collect_amber ──────────────────────────────────────────────────────────


@pytest.mark.fast
def test_collect_amber_returns_amber_in_document_order() -> None:
    report = _Report(
        [
            _Stub("c1", color="green"),
            _Stub("c2", color="amber"),
            _Stub("c3", color="red"),
            _Stub("c4", color="amber"),
        ]
    )
    assert [a.clause_id for a in collect_amber(report)] == ["c2", "c4"]  # type: ignore[attr-defined]


@pytest.mark.fast
def test_collect_amber_is_case_sensitive_and_identity_strict() -> None:
    """FINDING (edge case): ``color`` comparison is case-sensitive (``"AMBER"``
    is ignored) and the legacy ``is_amber`` check uses ``is True`` identity, so
    a truthy non-bool (e.g. ``1``) is *not* counted."""
    report = _Report(
        [
            _Stub("upper", color="AMBER"),
            _Stub("truthy-int", color=None, is_amber=1),  # type: ignore[arg-type]
            _Stub("bool-true", color=None, is_amber=True),
        ]
    )
    assert [a.clause_id for a in collect_amber(report)] == ["bool-true"]  # type: ignore[attr-defined]


@pytest.mark.fast
def test_collect_amber_tolerates_missing_or_nonlist_assessments() -> None:
    class _NoAssessments:
        pass

    assert collect_amber(_NoAssessments()) == []  # type: ignore[arg-type]
    assert collect_amber(_Report([])) == []
    assert collect_amber(None) == []


@pytest.mark.fast
def test_collect_amber_accepts_real_assessment_enum_colour() -> None:
    """The real ``AssessmentColor`` StrEnum stringifies to ``"amber"`` and is
    matched by the collector."""
    assessment = ClauseAssessment(
        clause_id="c1",
        clause_text="t",
        playbook_category="confidentiality-term",
        position=Position.ACCEPTABLE,
        confidence=0.4,
        citation="c",
        qa_verdict=QAVerdict.agree,
        extraction_model="m",
        qa_model="m",
    )
    assessment.color = "amber"  # type: ignore[assignment]
    report = _Report([assessment])
    assert [a.clause_id for a in collect_amber(report)] == ["c1"]  # type: ignore[attr-defined]


@pytest.mark.fast
def test_amber_queue_seeded_from_real_report_is_consistent() -> None:
    def _real(cid: str, color: str) -> ClauseAssessment:
        a = ClauseAssessment(
            clause_id=cid,
            clause_text=f"text {cid}",
            playbook_category="confidentiality-term",
            position=Position.ACCEPTABLE,
            confidence=0.4,
            citation="c",
            qa_verdict=QAVerdict.agree,
            extraction_model="m",
            qa_model="m",
        )
        a.color = color  # type: ignore[assignment]
        return a

    report = _Report([_real("c1", "green"), _real("c2", "amber"), _real("c3", "amber")])
    state = AmberQueueState(clauses=collect_amber(report))  # type: ignore[arg-type]
    assert state.total == 2
    assert state.row(0) == ("c2", "text c2", DECISION_PENDING)
