"""Prompt templates for the extraction and QA agents.

Each template is a function that returns the system + user message list
for the AI Gateway's ``chat()`` method. Templates are kept in one file
for auditability — prompt changes here directly affect model behaviour.
"""

from __future__ import annotations

import json
from typing import Any


def _parse_json(raw: str, fallback: dict[str, Any]) -> dict[str, Any]:
    """Shared JSON parser with fallback for extraction and QA responses."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return fallback
    return data  # type: ignore[no-any-return]


def build_extraction_messages(
    clause_text: str,
    category_id: str,
    category_name: str,
    category_description: str,
    preferred_desc: str,
    preferred_exemplars: list[str],
    acceptable_desc: str,
    acceptable_exemplars: list[str],
    walkaway_desc: str,
    walkaway_exemplars: list[str],
    default_position: str,
) -> list[dict[str, str]]:
    """Build messages for the extraction agent.

    Returns a list of ``{"role": ..., "content": ...}`` dicts ready for
    ``Gateway.chat(extraction_slot, messages)``.
    """
    system = (
        "You are a legal contract analyst. Your task is to classify a single "
        "clause from a Non-Disclosure Agreement against a 3-position playbook. "
        "Respond ONLY with valid JSON — no preamble, no explanation."
    )

    pref_ex = "\n".join(f'  - "{e}"' for e in preferred_exemplars)
    acc_ex = "\n".join(f'  - "{e}"' for e in acceptable_exemplars)
    walk_ex = "\n".join(f'  - "{e}"' for e in walkaway_exemplars)

    user = (
        f"## Category: {category_name}\n"
        f"{category_description}\n\n"
        f"### Preferred\n"
        f"{preferred_desc}\n"
        f"Exemplars:\n{pref_ex}\n\n"
        f"### Acceptable\n"
        f"{acceptable_desc}\n"
        f"Exemplars:\n{acc_ex}\n\n"
        f"### Walkaway\n"
        f"{walkaway_desc}\n"
        f"Exemplars:\n{walk_ex}\n\n"
        f"### Default position (if no specific indicators match)\n"
        f"{default_position}\n\n"
        f"## Clause to classify\n"
        f"```\n{clause_text}\n```\n\n"
        "Return JSON:\n"
        "{\n"
        '  "position": "preferred" | "acceptable" | "walkaway" | "no-match",\n'
        '  "confidence": 0.0-1.0,\n'
        '  "citation": "exact quoted text from the clause supporting your assessment",\n'
        '  "category_match": true | false\n'
        "}"
    )

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_qa_messages(
    clause_text: str,
    extracted_position: str,
    confidence: float,
    citation: str,
    category_id: str,
    category_name: str,
    preferred_desc: str,
    preferred_exemplars: list[str],
    acceptable_desc: str,
    acceptable_exemplars: list[str],
    walkaway_desc: str,
    walkaway_exemplars: list[str],
) -> list[dict[str, str]]:
    """Build messages for the QA verification agent.

    The QA agent receives the extraction output and verifies each dimension:
    position correctness, category match, citation accuracy, confidence
    appropriateness.
    """
    system = (
        "You are a senior legal review QA analyst. Your job is to verify "
        "an extraction agent's clause assessment. Check for errors in "
        "position assignment, category matching, citation accuracy, and "
        "confidence calibration. Respond ONLY with valid JSON."
    )

    pref_ex = "\n".join(f'  - "{e}"' for e in preferred_exemplars)
    acc_ex = "\n".join(f'  - "{e}"' for e in acceptable_exemplars)
    walk_ex = "\n".join(f'  - "{e}"' for e in walkaway_exemplars)

    user = (
        f"## Category: {category_name}\n"
        f"### Preferred\n{preferred_desc}\nExemplars:\n{pref_ex}\n\n"
        f"### Acceptable\n{acceptable_desc}\nExemplars:\n{acc_ex}\n\n"
        f"### Walkaway\n{walkaway_desc}\nExemplars:\n{walk_ex}\n\n"
        f"## Extraction agent's assessment\n"
        f"- Position: {extracted_position}\n"
        f"- Confidence: {confidence}\n"
        f'- Citation: "{citation}"\n'
        f"- Category: {category_id}\n\n"
        f"## Clause text\n```\n{clause_text}\n```\n\n"
        "Verify each check:\n"
        "1. Citation check: does the cited text appear verbatim in the clause?\n"
        "2. Position check: does the clause text support the assigned position?\n"
        "3. Category check: does the clause belong to this category?\n"
        "4. Confidence check: is the confidence score appropriate?\n\n"
        "Return JSON:\n"
        "{\n"
        '  "verdict": "agree" | "disagree" | "uncertain",\n'
        '  "revised_position": "preferred" | "acceptable" | "walkaway" | null,\n'
        '  "rationale": "brief explanation of disagreement or uncertainty",\n'
        '  "citation_valid": true | false,\n'
        '  "position_valid": true | false,\n'
        '  "category_valid": true | false,\n'
        '  "confidence_valid": true | false\n'
        "}"
    )

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_extraction_response(raw: str) -> dict[str, Any]:
    """Parse the extraction agent's JSON response.

    Returns a dict with keys: position, confidence, citation, category_match.
    On parse failure, returns a default uncertain response.
    """
    fallback: dict[str, Any] = {
        "position": "no-match",
        "confidence": 0.0,
        "citation": "",
        "category_match": False,
    }
    data = _parse_json(raw, fallback)
    if data is fallback:
        return fallback

    for key in ("position", "confidence", "citation"):
        if key not in data:
            return fallback

    return {
        "position": str(data["position"]),
        "confidence": float(data["confidence"]),
        "citation": str(data["citation"]),
        "category_match": bool(data.get("category_match", False)),
    }


def parse_qa_response(raw: str) -> dict[str, Any]:
    """Parse the QA agent's JSON response.

    Returns a dict with keys: verdict, revised_position, rationale,
    citation_valid, position_valid, category_valid, confidence_valid.
    On parse failure, returns an uncertain/default response.
    """
    fallback: dict[str, Any] = {
        "verdict": "uncertain",
        "revised_position": None,
        "rationale": "Could not parse QA response",
        "citation_valid": False,
        "position_valid": False,
        "category_valid": False,
        "confidence_valid": False,
    }
    data = _parse_json(raw, fallback)
    if data is fallback:
        return fallback

    if "verdict" not in data:
        return {
            "verdict": "uncertain",
            "revised_position": None,
            "rationale": "Missing verdict in QA response",
            "citation_valid": False,
            "position_valid": False,
            "category_valid": False,
            "confidence_valid": False,
        }

    return {
        "verdict": str(data.get("verdict", "uncertain")),
        "revised_position": data.get("revised_position"),
        "rationale": str(data.get("rationale", "")),
        "citation_valid": bool(data.get("citation_valid", False)),
        "position_valid": bool(data.get("position_valid", False)),
        "category_valid": bool(data.get("category_valid", False)),
        "confidence_valid": bool(data.get("confidence_valid", False)),
    }
