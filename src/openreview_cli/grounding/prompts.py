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
- miscited_to_clause_id: str | None — set this only when the claim is genuinely true but the clause it cites does not support it while a different clause in the list does; name that clause's id. Leave it null in every other case. Keep verdict "grounded" when you set it.

For each claim, respond with one JSON object. If there is a single claim, you may return that object on its own; if there are several, return a JSON array of the objects, one per claim, in the same order as the input claims. Return the JSON only — no text before or after it."""


# Appended, on that claim's own line, when the claim's wording was measured absent from
# the clause it cites. It names no claim or clause text and states no verdict: it tells
# the model what was measured and leaves the grounded/ungrounded call to the model.
_WORDING_ABSENT_HINT = (
    "[the claim's wording does not appear in the cited clause; "
    "answer grounded only if the clause still entails it]"
)


# Item 7: 59% of CUAD clauses exceed 500 characters and 99.6% of those were cut mid-word; a
# sentence-aware window of about 2000 characters covers 9 in 10. Whole sentences while they
# fit; a single sentence longer than the window is hard-clipped.
_CLAUSE_WINDOW_CHARS = 2000
_TRUNCATION_MARKER = " …[clause text truncated]"

# Item 3: the prompt shows the finding's own clause plus sibling clauses, so the checker can
# name a section that supports a finding the cited clause does not. The list is bounded — a
# hard cap on how many clauses are shown — so the built prompt cannot grow without limit.
_MAX_PROMPT_CLAUSES = 20


def _clause_window(text: str, limit: int = _CLAUSE_WINDOW_CHARS) -> str:
    """At most ``limit`` characters of ``text``, cut on a sentence boundary when one fits.
    A single first sentence longer than ``limit`` is hard-clipped at ``limit``."""
    if len(text) <= limit:
        return text
    from openreview_cli.parsing.clause_detector import nupunkt_detect_boundaries

    end = 0
    for _start, stop in nupunkt_detect_boundaries(text):
        if stop <= limit and text[end:stop].strip():
            end = stop
    if end == 0:  # the first sentence alone exceeds the window: hard-clip it
        end = limit
    return text[:end].rstrip() + _TRUNCATION_MARKER


def _format_clauses(source_clauses: list[Clause]) -> str:
    """The clause list the model is shown, bounded.

    At most ``_MAX_PROMPT_CLAUSES`` clauses, each windowed to whole sentences inside
    ``_CLAUSE_WINDOW_CHARS``. The list carries only clause ids and windowed text — no
    finding text — so the prompt gains surrounding sections without growing past the cap.
    """
    lines = [
        f"[{clause.id}]: {_clause_window(clause.text)}"
        for clause in source_clauses[:_MAX_PROMPT_CLAUSES]
    ]
    return "\n\n".join(lines) if lines else "(no clauses provided)"


def build_grounding_messages(
    source_clauses: list[Clause],
    claims: list[tuple[int, str, str]],
    wording_absent_indices: set[int] | None = None,
) -> list[dict[str, str]]:
    """Build system+user messages for the grounding gateway call.

    Args:
        source_clauses: List of Clause objects from the parsed document.
        claims: List of (claim_index, claim_text, cited_clause_id) tuples.
        wording_absent_indices: Claim indices whose wording was measured absent from the
            clause they cite (Task 2's ``presence.measure``). Each such claim's line gains
            one bracketed hint. ``None`` — the default — adds no hint.

    Returns:
        List of message dicts for Gateway.chat().
    """
    # Format clauses for the prompt: bounded, each windowed to whole sentences.
    clauses_text = _format_clauses(source_clauses)

    # Format claims for the prompt
    claims_lines: list[str] = []
    for idx, claim_text, cited_clause_id in claims:
        truncated = claim_text[:300] if len(claim_text) > 300 else claim_text
        line = f'{idx}. "{truncated}" (cites clause {cited_clause_id})'
        if wording_absent_indices and idx in wording_absent_indices:
            line = f"{line} {_WORDING_ABSENT_HINT}"
        claims_lines.append(line)

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

    return results


def parse_miscited_ids(response: str) -> dict[int, str]:
    """The fourth answer, per claim: the clause id the checker named, if any.

    Tolerant by construction: an answer with no pointer, an empty or non-string value, or
    an unreadable reply all yield an empty (or partial) mapping and nothing else. Only the
    named clause id is returned — no claim or clause text is read out or recorded.
    """
    ids: dict[int, str] = {}
    for position, item in enumerate(_answer_items(_first_json_value(response))):
        if isinstance(item, dict):
            named = item.get("miscited_to_clause_id")
            if isinstance(named, str) and named.strip():
                ids[_claim_index(item.get("claim_index"), position)] = named.strip()
    return ids


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
