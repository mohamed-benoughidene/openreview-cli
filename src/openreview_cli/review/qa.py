"""QA verification agent — position verification, disagreement detection, Amber flagging.

The QA agent runs after every extraction and verifies: (1) the assigned position
matches the clause text, (2) the playbook category is correct, (3) the citation
is accurate, and (4) the confidence score is appropriate. If QA disagrees with
extraction, the assessment is flagged Amber with a revised position.
"""

from __future__ import annotations

import logging
from typing import Any

from openreview_cli.gateway.models import CapabilityRequirement
from openreview_cli.review._gateway import call_gateway_chat
from openreview_cli.review.models import Category, ClauseAssessment, Position, QAVerdict
from openreview_cli.review.prompts import _parse_json, build_qa_messages

logger = logging.getLogger(__name__)


def verify_assessment(
    assessment: ClauseAssessment,
    category: Category,
    qa_model: str,
) -> ClauseAssessment:
    """Run QA verification on a single clause assessment.

    Builds a verification prompt, calls the AI Gateway, parses the response,
    and returns an updated ``ClauseAssessment`` with QA fields filled.

    Parameters
    ----------
    assessment : ClauseAssessment
        The extraction agent's output to verify.
    category : Category
        The playbook category used for extraction.
    qa_model : str
        Model slot name for QA verification.

    Returns
    -------
    ClauseAssessment
        The assessment with QA fields set. ``is_amber`` is auto-calculated.
    """
    messages = build_qa_messages(
        clause_text=assessment.clause_text,
        extracted_position=assessment.position.value,
        confidence=assessment.confidence,
        citation=assessment.citation,
        category_id=category.id,
        category_name=category.name,
        preferred_desc=category.preferred.description,
        preferred_exemplars=category.preferred.exemplars,
        acceptable_desc=category.acceptable.description,
        acceptable_exemplars=category.acceptable.exemplars,
        walkaway_desc=category.walkaway.description,
        walkaway_exemplars=category.walkaway.exemplars,
    )

    try:
        raw_response = call_gateway_chat(
            qa_model,
            messages,
            requirement=CapabilityRequirement(capability="reasoning"),
        )
        parsed = _parse_qa_response(raw_response)
    except Exception as exc:
        logger.warning("QA call failed for %s: %s", assessment.clause_id, exc)
        assessment.qa_verdict = QAVerdict.uncertain
        assessment.error = str(exc)
        assessment.is_amber = True
        return assessment

    try:
        assessment.qa_verdict = QAVerdict(parsed["verdict"])
    except ValueError:
        assessment.qa_verdict = QAVerdict.uncertain

    revised_pos = parsed.get("revised_position")
    if revised_pos and revised_pos != assessment.position.value:
        try:
            assessment.qa_revised_position = Position(revised_pos)
            assessment.qa_revised_rationale = parsed.get("rationale", "")
        except ValueError:
            pass

    assessment.is_amber = _calculate_amber(assessment, parsed)
    return assessment


def _parse_qa_response(raw: str) -> dict[str, Any]:
    """Parse QA JSON response with fallback."""
    fallback: dict[str, Any] = {
        "verdict": "uncertain",
        "revised_position": None,
        "rationale": "Unparseable QA response",
        "citation_valid": False,
        "position_valid": False,
        "category_valid": False,
        "confidence_valid": False,
    }
    data = _parse_json(raw, fallback)
    if data is fallback:
        return fallback

    return {
        "verdict": str(data.get("verdict", "uncertain")),
        "revised_position": data.get("revised_position"),
        "rationale": str(data.get("rationale", "")),
        "citation_valid": bool(data.get("citation_valid", True)),
        "position_valid": bool(data.get("position_valid", True)),
        "category_valid": bool(data.get("category_valid", True)),
        "confidence_valid": bool(data.get("confidence_valid", True)),
    }


def _calculate_amber(assessment: ClauseAssessment, parsed: dict[str, Any]) -> bool:
    """Determine if a clause should be flagged Amber.

    Amber if: QA disagreed, QA uncertain, or any validation check failed.
    """
    if assessment.qa_verdict in (QAVerdict.disagree, QAVerdict.uncertain):
        return True
    if assessment.error is not None or assessment.confidence < 0.5:
        return True
    if not parsed.get("citation_valid", True) or not parsed.get("position_valid", True):
        return True
    return not parsed.get("category_valid", True)
