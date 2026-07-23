"""Extraction agent — prompt building, category matching, AI Gateway routing.

The extraction agent receives a clause from ``stream_clauses()``, matches it
to a playbook category (via heading match or semantic fallback), builds a
structured prompt, routes it through the AI Gateway, and parses the response
into a ``ClauseAssessment``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openreview_cli.gateway.models import CapabilityRequirement
from openreview_cli.review._gateway import call_gateway_chat
from openreview_cli.review.models import Category, ClauseAssessment, Playbook, Position, QAVerdict
from openreview_cli.review.prompts import _build_extraction_messages_common

logger = logging.getLogger(__name__)


def match_category(clause_heading: str, playbook: Playbook) -> Category | None:
    """Match a clause heading to a playbook category via heading keyword match.

    Case-insensitive substring matching against category ``name`` and ``id``.
    This is the **fast path** — no model inference needed.

    Two-pass strategy:
    1. Prefer exact substring match on name or ID.
    2. Fall back to word-split match (any word in heading >3 chars found in name).
    This prevents common words (e.g. "processor", "data") in a later category's
    body from falsely winning against an exact ID match in an earlier category.
    """
    lower_heading = clause_heading.lower()

    # Pass 1: exact substring match on name or ID
    for cat in playbook.categories:
        if cat.name.lower() in lower_heading or cat.id.lower() in lower_heading:
            return cat

    # Pass 2: word-split fallback
    for cat in playbook.categories:
        for word in lower_heading.split():
            if len(word) > 3 and word in cat.name.lower():
                return cat

    return None


def extract_clause(
    clause_text: str,
    clause_id: str,
    category: Category | None,
    extraction_model: str,
    mode: str = "precheck",
    session_id: str | None = None,
) -> ClauseAssessment:
    """Run extraction for a single clause against a playbook category.

    Parameters
    ----------
    clause_text : str
        The clause text from ``stream_clauses()``.
    clause_id : str
        Unique clause identifier.
    category : Category | None
        The matched playbook category, or ``None`` if no match found.
    extraction_model : str
        Model slot name for extraction.

    Returns
    -------
    ClauseAssessment
        The extraction agent's assessment. QA fields are set to defaults
        (will be filled by the QA agent in the next pipeline stage).
    """
    if category is None:
        # No category match — return no-match assessment
        return ClauseAssessment(
            clause_id=clause_id,
            clause_text=clause_text,
            playbook_category="no-match",
            position=Position.UNCERTAIN,
            confidence=0.0,
            citation="",
            qa_verdict=QAVerdict.uncertain,
            extraction_model=extraction_model,
            qa_model=extraction_model,
        )

    messages = _build_extraction_messages_common(
        mode=mode,
        clause_text=clause_text,
        category_id=category.id,
        category_name=category.name,
        category_description="",
        preferred_desc=category.preferred.description,
        preferred_exemplars=category.preferred.exemplars,
        acceptable_desc=category.acceptable.description,
        acceptable_exemplars=category.acceptable.exemplars,
        walkaway_desc=category.walkaway.description,
        walkaway_exemplars=category.walkaway.exemplars,
        default_position=category.default_position.value,
    )

    try:
        raw_response = call_gateway_chat(
            extraction_model,
            messages,
            requirement=CapabilityRequirement(capability="reasoning"),
            session_id=session_id,
        )
        parsed = _parse_response(raw_response)
    except Exception as exc:
        logger.warning("Extraction failed for %s: %s", clause_id, exc)
        return ClauseAssessment(
            clause_id=clause_id,
            clause_text=clause_text,
            playbook_category=category.id,
            position=Position.UNCERTAIN,
            confidence=0.0,
            citation="",
            qa_verdict=QAVerdict.uncertain,
            extraction_model=extraction_model,
            qa_model=extraction_model,
            error=str(exc),
        )

    try:
        position = Position(parsed["position"])
    except ValueError:
        position = category.default_position

    return ClauseAssessment(
        clause_id=clause_id,
        clause_text=clause_text,
        playbook_category=category.id,
        position=position,
        confidence=parsed["confidence"],
        citation=parsed["citation"],
        qa_verdict=QAVerdict.agree,  # placeholder — QA agent will verify
        extraction_model=extraction_model,
        qa_model=extraction_model,
    )


def _parse_response(raw: str) -> dict[str, Any]:
    """Parse the extraction agent's JSON response, with fallback.

    Handles markdown-wrapped JSON (`` ```json ... ``` ``) which is a
    common LLM output format.
    """
    stripped = raw.strip()
    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    if stripped.startswith("```"):
        first_nl = stripped.find("\n")
        if first_nl >= 0:
            stripped = stripped[first_nl + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3].strip()

    try:
        data = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return {"position": "uncertain", "confidence": 0.0, "citation": "", "category_match": False}

    return {
        "position": str(data.get("position", "uncertain")),
        "confidence": float(data.get("confidence", 0.0)),
        "citation": str(data.get("citation", "")),
        "category_match": bool(data.get("category_match", False)),
    }
