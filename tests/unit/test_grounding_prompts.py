"""Unit tests for the grounding answer reader."""

from __future__ import annotations

import json

from openreview_cli.grounding.models import GroundingVerdict
from openreview_cli.grounding.prompts import parse_grounding_response

GROUNDED = {
    "claim_index": 0,
    "verdict": "grounded",
    "provenances": [{"clause_id": "4.3", "paragraph_index": 2, "confidence": 0.95}],
    "confidence": 0.95,
    "reason": None,
}


def _obj(index: int, verdict: str = "grounded") -> dict[str, object]:
    return {**GROUNDED, "claim_index": index, "verdict": verdict}


def _verdicts(response: str) -> list[GroundingVerdict]:
    return [row[1] for row in parse_grounding_response(response)]


def _indices(response: str) -> list[int]:
    return [row[0] for row in parse_grounding_response(response)]


# ── shapes that already worked: regression guards ─────────────────────────────


def test_bare_array_parses() -> None:
    assert _verdicts(json.dumps([GROUNDED])) == [GroundingVerdict.GROUNDED]


def test_fenced_array_parses() -> None:
    assert _verdicts(f"```json\n{json.dumps([GROUNDED])}\n```") == [GroundingVerdict.GROUNDED]


def test_fenced_array_without_language_tag_parses() -> None:
    assert _verdicts(f"```\n{json.dumps([GROUNDED])}\n```") == [GroundingVerdict.GROUNDED]


def test_prose_before_the_array_parses() -> None:
    assert _verdicts(f"Here is the result:\n{json.dumps([GROUNDED])}") == [
        GroundingVerdict.GROUNDED
    ]


def test_prose_after_the_array_parses() -> None:
    assert _verdicts(f"{json.dumps([GROUNDED])}\nLet me know if you need more.") == [
        GroundingVerdict.GROUNDED
    ]


def test_fenced_array_with_trailing_prose_parses() -> None:
    assert _verdicts(f"```json\n{json.dumps([GROUNDED])}\n```\nThat is my answer.") == [
        GroundingVerdict.GROUNDED
    ]


def test_quoted_reason_containing_brackets_parses() -> None:
    grounded = {**GROUNDED, "reason": "see [section 3] and a stray ] here"}
    assert _verdicts(json.dumps([grounded])) == [GroundingVerdict.GROUNDED]


def test_quoted_reason_containing_a_brace_parses() -> None:
    grounded = {**GROUNDED, "reason": "a closing } brace inside a string"}
    assert _verdicts(json.dumps([grounded])) == [GroundingVerdict.GROUNDED]


def test_batch_of_three_parses_with_indices_in_order() -> None:
    response = json.dumps([_obj(0), _obj(1, "ungrounded"), _obj(2)])
    assert _indices(response) == [0, 1, 2]


def test_truncated_json_returns_empty() -> None:
    assert parse_grounding_response('[{"claim_index": 0, "verdict": "gro') == []


def test_empty_string_returns_empty() -> None:
    assert parse_grounding_response("") == []


def test_text_without_json_returns_empty() -> None:
    assert parse_grounding_response("I cannot help with that.") == []


# ── shapes that failed: the reason this task exists ───────────────────────────


def test_bracketed_preamble_before_the_array_parses() -> None:
    response = f"First, consider [the claim]. Then:\n{json.dumps([GROUNDED])}"
    assert _verdicts(response) == [GroundingVerdict.GROUNDED]


def test_a_single_object_parses_as_one_result() -> None:
    assert _verdicts(json.dumps(GROUNDED)) == [GroundingVerdict.GROUNDED]


def test_two_arrays_back_to_back_take_the_first() -> None:
    response = json.dumps([_obj(0)]) + json.dumps([_obj(1)])
    assert _indices(response) == [0]


def test_a_pathological_answer_is_treated_as_unreadable_not_as_a_crash() -> None:
    """Deeply nested brackets must not abort the run that is measuring a model.

    `raw_decode` raises `RecursionError` on such input, and that error would
    escape the discriminator's try block in the real pipeline.
    """
    response = ("[" * 30_000) + json.dumps([GROUNDED])

    assert parse_grounding_response(response) == []


def test_trailing_prose_containing_brackets_still_parses() -> None:
    """Regression guard: the old greedy regex returned empty when prose after
    the answer itself contained a bracket pair."""
    response = f"{json.dumps([GROUNDED])}\nNote: [see the clause above]"

    assert [row[1] for row in parse_grounding_response(response)] == [GroundingVerdict.GROUNDED]
