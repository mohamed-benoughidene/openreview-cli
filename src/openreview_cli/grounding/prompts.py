"""Grounding prompt templates for the Citation Grounding Discriminator.

Sends batched claims (5-10 per call) to the AI Gateway for grounding
discrimination. Prompt instructs the LLM to respond with structured JSON
per claim.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openreview_cli.grounding.models import CitationProvenance, GroundingVerdict
    from openreview_cli.parsing.models import Clause

logger = logging.getLogger(__name__)

GROUNDING_PROMPT_TEMPLATE = """You are a citation grounding discriminator for contract analysis. Your task is to determine whether each assessment claim is actually supported by the source document clause it cites.

For each claim, determine:
1. Is the claim supported by the cited clause text? (GROUNDED)
2. Is the claim NOT supported? (UNGROUNDED)
3. Is it unclear or ambiguous? (UNCERTAIN)

Source clauses:
{clauses_text}

Claims to evaluate:
{claims_text}

For each claim, respond with a JSON object containing:
- claim_index: int (the claim number)
- verdict: "grounded" | "ungrounded" | "uncertain"
- provenances: list of {{"clause_id": str, "paragraph_index": int, "confidence": float}} — clause(s) that support the claim, or empty list
- confidence: float (0.0-1.0) — overall confidence in this verdict
- reason: str | None — explanation if ungrounded or uncertain

Respond with a JSON array of these objects, one per claim, in the same order as the input claims."""


def build_grounding_messages(
    source_clauses: list[Clause],
    claims: list[tuple[int, str, str]],
) -> list[dict[str, str]]:
    """Build system+user messages for the grounding gateway call.

    Args:
        source_clauses: List of Clause objects from the parsed document.
        claims: List of (claim_index, claim_text, cited_clause_id) tuples.

    Returns:
        List of message dicts for Gateway.chat().
    """
    # Format clauses for the prompt
    clauses_lines: list[str] = []
    for clause in source_clauses:
        text = clause.text[:500]
        clauses_lines.append(f"[{clause.id}]: {text}")

    clauses_text = "\n\n".join(clauses_lines) if clauses_lines else "(no clauses provided)"

    # Format claims for the prompt
    claims_lines: list[str] = []
    for idx, claim_text, cited_clause_id in claims:
        truncated = claim_text[:300] if len(claim_text) > 300 else claim_text
        claims_lines.append(f'{idx}. "{truncated}" (cites clause {cited_clause_id})')

    claims_text = "\n".join(claims_lines)

    user_content = GROUNDING_PROMPT_TEMPLATE.format(
        clauses_text=clauses_text,
        claims_text=claims_text,
    )

    return [{"role": "user", "content": user_content}]


def parse_grounding_response(
    response: str,
) -> list[tuple[int, GroundingVerdict, list[CitationProvenance], float]]:
    """Parse LLM response into structured grounding results.

    Args:
        response: Raw response string from the LLM.

    Returns:
        List of (claim_index, verdict, provenances, confidence) tuples.
    """
    from openreview_cli.grounding.models import (
        CitationProvenance,
        GroundingVerdict,
    )

    results: list[tuple[int, GroundingVerdict, list[CitationProvenance], float]] = []

    # Try to extract JSON array from response
    json_str = _extract_json_array(response)
    if json_str is None:
        logger.warning("No JSON array found in grounding response")
        return results

    try:
        data: list[dict[str, Any]] = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse grounding JSON: %s", e)
        return results

    for item in data:
        if not isinstance(item, dict):
            continue
        claim_index = item.get("claim_index")
        verdict_str = item.get("verdict", "")
        confidence = float(item.get("confidence", 0.0))
        raw_provenances: list[dict[str, Any]] = item.get("provenances", [])

        if claim_index is None or not isinstance(claim_index, int):
            continue

        # Parse verdict
        try:
            verdict = GroundingVerdict(verdict_str)
        except ValueError:
            logger.warning("Unknown verdict '%s' for claim %d", verdict_str, claim_index)
            continue

        # Parse provenances
        provenances: list[CitationProvenance] = []
        for p in raw_provenances:
            if not isinstance(p, dict):
                continue
            clause_id = p.get("clause_id", "")
            paragraph_index = int(p.get("paragraph_index", 0))
            prov_confidence = float(p.get("confidence", 0.0))
            provenances.append(
                CitationProvenance(
                    clause_id=clause_id,
                    paragraph_index=paragraph_index,
                    confidence=prov_confidence,
                )
            )

        results.append((claim_index, verdict, provenances, confidence))

    return results


def _extract_json_array(text: str) -> str | None:
    """Extract the first JSON array from a text response.

    Handles cases where the LLM wraps JSON in markdown code blocks
    or includes explanatory text before/after the JSON.
    """
    # First try to find a JSON array in a code block
    code_block_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text, re.IGNORECASE)
    if code_block_match:
        return code_block_match.group(1)

    # Next try to find a bare JSON array
    array_match = re.search(r"(\[[\s\S]*\])", text, re.DOTALL)
    if array_match:
        return array_match.group(1)

    return None
