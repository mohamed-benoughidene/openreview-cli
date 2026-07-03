"""Comparison agent — divergence detection between two aligned clauses.

The comparison agent receives two single-party assessments (extraction + QA)
and the original clause texts, builds a structured prompt using the RCBSF
5-dimension taxonomy, calls the AI Gateway, and parses the response into
a ``PairedAssessment``.

Reuses the extraction model slot per FR-3/Q3 — there is no ``--comparison-model``.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from openreview_cli.bilateral.models import (
    DivergenceVerdict,
    PairedAssessment,
    RCBSFDimension,
)
from openreview_cli.bilateral.prompts import build_comparison_messages
from openreview_cli.review._gateway import call_gateway_chat

if TYPE_CHECKING:
    from openreview_cli.bilateral.models import AlignmentPair
    from openreview_cli.review.models import Category, ClauseAssessment

logger = logging.getLogger(__name__)

# Valid RCBSF dimension values that indicate actual divergence
DIVERGENCE_DIMENSIONS = {
    "category",
    "location",
    "evidence",
    "issue",
    "suggestion",
}


def compare_pair(
    alignment: AlignmentPair,
    party_a_assessment: ClauseAssessment,
    party_b_assessment: ClauseAssessment,
    playbook_category: Category | None,
    model: str,
) -> PairedAssessment:
    """Compare a single aligned clause pair and classify divergence.

    Parameters
    ----------
    alignment : AlignmentPair
        The aligned clause pair.
    party_a_assessment : ClauseAssessment
        Single-party assessment for Party A's clause.
    party_b_assessment : ClauseAssessment
        Single-party assessment for Party B's clause.
    playbook_category : Category | None
        The playbook category, if matched.
    model : str
        AI Gateway model slot name (reuses extraction model slot per FR-3/Q3).

    Returns
    -------
    PairedAssessment
        Comparison result. ``color`` is ``None`` — set later by ``assign_paired_colors()``.
    """
    messages = build_comparison_messages(
        clause_a_text=alignment.clause_a.text,
        clause_b_text=alignment.clause_b.text,
        assessment_a=party_a_assessment,
        assessment_b=party_b_assessment,
        category=playbook_category,
    )

    try:
        raw_response = call_gateway_chat(model, messages)
    except Exception as exc:
        logger.warning("Gateway call failed for %s: %s", alignment.pair_id, exc)
        return PairedAssessment(
            pair_id=alignment.pair_id,
            alignment=alignment,
            party_a_assessment=party_a_assessment,
            party_b_assessment=party_b_assessment,
            divergence=DivergenceVerdict.uncertain,
            error=f"Gateway call failed: {exc}",
        )

    parsed = _parse_comparison_response(raw_response)

    return PairedAssessment(
        pair_id=alignment.pair_id,
        alignment=alignment,
        party_a_assessment=party_a_assessment,
        party_b_assessment=party_b_assessment,
        divergence=parsed["divergence"],
        primary_dimension=parsed["primary_dimension"],
        rcbsf_details=parsed["rcbsf_details"],
        alignment_quality=alignment.score,
        confidence=parsed.get("confidence", 0.0),
        citations=parsed.get("citations", []),
        rationale=parsed.get("rationale", ""),
        error=parsed.get("error"),
    )


def _parse_comparison_response(raw: str) -> dict[str, Any]:
    """Parse the comparison agent's JSON response.

    Parameters
    ----------
    raw : str
        Raw response string from the AI Gateway.

    Returns
    -------
    dict
        Parsed fields: divergence, primary_dimension, rcbsf_details, error.
    """
    fallback: dict[str, Any] = {
        "divergence": DivergenceVerdict.uncertain,
        "primary_dimension": None,
        "rcbsf_details": {},
        "error": "Unparseable comparison agent response",
    }

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Invalid JSON from comparison agent: %s", raw[:200])
        return fallback

    if not isinstance(data, dict) or "divergence" not in data:
        return fallback

    divergence_str = str(data["divergence"])
    confidence = max(0.0, min(1.0, data.get("confidence", 0.0)))

    # Determine divergence verdict
    if divergence_str == "no_divergence":
        divergence = DivergenceVerdict.aligned
        primary_dimension = None
        rcbsf_details: dict[str, Any] = {}
    elif divergence_str in DIVERGENCE_DIMENSIONS:
        divergence = DivergenceVerdict.divergent
        try:
            primary_dimension = RCBSFDimension(divergence_str)
        except ValueError:
            primary_dimension = None
        rcbsf_details = {divergence_str: str(data.get("rationale", ""))}
    else:
        # Unknown divergence string — treat as uncertain
        return {
            "divergence": DivergenceVerdict.uncertain,
            "primary_dimension": None,
            "rcbsf_details": {},
            "error": f"Unknown divergence value: {divergence_str}",
        }

    citations = data.get("citations", [])
    if not isinstance(citations, list):
        citations = []

    rationale = str(data.get("rationale", ""))

    return {
        "divergence": divergence,
        "primary_dimension": primary_dimension,
        "rcbsf_details": rcbsf_details,
        "confidence": confidence,
        "citations": citations,
        "rationale": rationale,
        "error": None,
    }
