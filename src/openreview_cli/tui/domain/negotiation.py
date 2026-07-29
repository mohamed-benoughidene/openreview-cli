"""TUI domain wrapper around the openreview_cli.negotiation pipeline.

Builds assessments locally from document parse + playbook category matching
(same approach as the CLI `negotiate` command). No LLM calls in this path —
assessments use extraction_model="bundled". No PII stripping needed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openreview_cli.negotiation.models import NegotiationReport

logger = logging.getLogger(__name__)

_tui_cancel_requested: bool = False


def run_negotiation_via_tui(
    doc_path: str,
    *,
    solver: str = "qre",
    rationality: float = 1.0,
    depth: int = 2,
    weights: dict[str, float] | None = None,
    confidence_threshold: float = 0.7,
    playbook_path: str | None = None,
    cancel_requested: bool = False,
) -> NegotiationReport | None:
    """Run negotiation from the TUI — all local, no external API calls."""
    if cancel_requested or _tui_cancel_requested:
        return None

    path = Path(doc_path)

    # ── lazy imports: never pull gateway/litellm at module level ──
    from openreview_cli.negotiation import run_negotiation
    from openreview_cli.parsing.stream import parse_document
    from openreview_cli.review.extraction import match_category as _match_category
    from openreview_cli.review.models import ClauseAssessment, Position, QAVerdict
    from openreview_cli.review.playbook import load_bundled, load_playbook

    if playbook_path:
        pb_path = Path(playbook_path)
        if not pb_path.exists():
            raise FileNotFoundError(f"Playbook not found: {playbook_path}")
        playbook = load_playbook(pb_path)
    else:
        playbook = load_bundled()

    _doc, clauses = parse_document(str(path))

    assessments: list[ClauseAssessment] = []
    for clause in clauses:
        clause_text = getattr(clause, "text", str(clause)) or str(clause)
        clause_id_str = getattr(
            clause, "heading", getattr(clause, "id", f"clause_{len(assessments) + 1}")
        )
        heading = str(clause_id_str)
        cat = _match_category(heading, playbook)

        if cat is not None:
            playbook_cat_id = cat.id
            position = cat.default_position
            pb_confidence = 0.7
            if hasattr(cat, "preferred") and hasattr(cat.preferred, "description"):
                pb_confidence = 0.75
        else:
            playbook_cat_id = "no-match"
            position = Position.PREFERRED
            pb_confidence = 0.5

        assessment = ClauseAssessment(
            clause_id=clause_id_str,
            clause_text=str(clause_text)[:200],
            playbook_category=playbook_cat_id,
            position=position,
            confidence=pb_confidence,
            citation="",
            qa_verdict=QAVerdict.agree,
            extraction_model="bundled",
            qa_model="bundled",
        )
        assessments.append(assessment)

    if _tui_cancel_requested:
        return None

    if not assessments:
        return None

    report = run_negotiation(
        assessments=assessments,
        solver=solver,
        weights=weights,
        rationality=rationality,
        depth=depth,
        confidence_threshold=confidence_threshold,
        playbook_id=playbook.id if hasattr(playbook, "id") else "bundled",
    )

    if cancel_requested or _tui_cancel_requested:
        return None

    return report
