"""Grounding prompt templates for the Citation Grounding Discriminator.

Sends batched claims (5-10 per call) to the AI Gateway for grounding
discrimination. Prompt instructs the LLM to respond with structured JSON
per claim.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from openreview_cli.llm_json import strip_fences

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

For each claim, respond with one JSON object. If there is a single claim, you may return that object on its own; if there are several, return a JSON array of the objects, one per claim, in the same order as the input claims. Return the JSON only — no text before or after it."""


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

    data = _first_json_value(response)
    items = _answer_items(data)

    for position, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        claim_index = _claim_index(item.get("claim_index"), position)
        verdict_str = item.get("verdict", "")
        confidence = float(item.get("confidence", 0.0))
        raw_provenances: list[dict[str, Any]] = item.get("provenances", [])

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

    if not results:
        # TEMPORARY DIAGNOSTIC — REMOVE ONCE THE ANSWER SHAPE IS KNOWN. A CI run
        # measured every grounding answer as unreadable, and the raw reply can
        # never be logged (privacy), so the shape alone is recorded here: the
        # reader returns nothing, and this line is the only way to see why.
        logger.warning("Unreadable grounding answer: %s", _shape_note(response, data))

    return results


def _answer_items(value: Any) -> list[Any]:
    """Return the candidate answer items inside a decoded grounding answer.

    The prompt promises a bare object for one claim and a JSON array for a
    batch, but a model may still wrap the batch in a key of its own — a CI run
    measured ``{"claims": [...]}`` on every answer. Such a wrapper is unwrapped
    here so the per-item validation below can decide, rather than the whole
    reply being discarded for lacking a ``verdict`` of its own.
    """
    if isinstance(value, list):
        return value
    if not isinstance(value, dict):
        return [value]
    if "verdict" in value:
        return [value]

    wrapper_keys = [
        key
        for key, nested in value.items()
        if isinstance(nested, list) and all(isinstance(item, dict) for item in nested)
    ]
    if wrapper_keys:
        key = "claims" if "claims" in wrapper_keys else wrapper_keys[0]
        return list(value[key])
    if value and all(isinstance(nested, dict) for nested in value.values()):
        return list(value.values())
    return [value]


def _shape_note(response: str, value: Any) -> str:
    """Describe the SHAPE of a value that could not be read — never its content.

    TEMPORARY DIAGNOSTIC, remove with the warning in ``parse_grounding_response``.
    Only structure is reported: a length, one single character, the decoded type,
    and key names. Key names and counts are structure, not contract text, so no
    source document or claim text can leak through this line.
    """
    first_char = response.lstrip()[:1] or "(empty)"

    if value is None:
        decoded = "none"
    elif isinstance(value, bool):
        decoded = "bool"
    elif isinstance(value, str):
        decoded = "str"
    elif isinstance(value, int):
        decoded = "int"
    elif isinstance(value, float):
        decoded = "float"
    elif isinstance(value, list):
        decoded = f"list(n={len(value)})"
    elif isinstance(value, dict):
        decoded = f"dict(keys={sorted(value)})"
    else:
        decoded = type(value).__name__

    parts = [f"len={len(response)}", f"first={first_char!r}", f"decoded={decoded}"]

    if isinstance(value, list):
        if not value:
            parts.append("first_item=none")
        elif isinstance(value[0], dict):
            parts.append(f"first_item=dict(keys={sorted(value[0])})")
        else:
            parts.append(f"first_item={type(value[0]).__name__}")

    return ", ".join(parts)


def _claim_index(raw: Any, position: int) -> int:
    """Return an item's claim index, falling back to its position in the answer.

    The prompt only promises that a batch comes back "in the same order as the
    input claims", so the model may well leave the index out — most obviously
    for a single claim, where the answer is one bare object. An index the model
    did supply is honoured, a numeric string is coerced, and anything else is
    ignored in favour of the position rather than discarding the answer.
    """
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        try:
            return int(raw.strip())
        except ValueError:
            return position
    return position


def _first_json_value(text: str) -> Any | None:
    """Return the first JSON value in ``text``, or None when there is none.

    The payload is unwrapped through the project-wide fence helper first, then
    candidate start positions are offered to the standard library decoder. That
    decoder understands quoted strings and escapes, so a bracket or brace inside
    a reason string cannot unbalance the scan, and it stops at the end of the
    first valid value, so trailing prose is ignored. An answer too deeply nested
    to decode is treated as unreadable rather than allowed to escape.
    """
    candidate_text = strip_fences(text)
    decoder = json.JSONDecoder()
    for index, char in enumerate(candidate_text):
        if char not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(candidate_text, index)
        except json.JSONDecodeError:
            continue
        except RecursionError:
            # A payload this deep is treated as unreadable rather than decoded:
            # stop here instead of walking the remaining offsets, which would
            # spend unbounded time on an answer already this malformed.
            break
        return value
    return None
