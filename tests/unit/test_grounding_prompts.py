"""Unit tests for the grounding answer reader."""

from __future__ import annotations

import json

from openreview_cli.grounding.models import GroundingVerdict
from openreview_cli.grounding.prompts import GROUNDING_PROMPT_TEMPLATE, parse_grounding_response

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

    `raw_decode` raises `RecursionError` on such input and the scan stops there,
    so the payload is treated as unreadable — no verdicts — rather than raising
    out of the parser in the real pipeline.
    """
    response = ("[" * 30_000) + json.dumps([GROUNDED])

    assert parse_grounding_response(response) == []


def test_trailing_prose_containing_brackets_still_parses() -> None:
    """Regression guard: the old greedy regex returned empty when prose after
    the answer itself contained a bracket pair."""
    response = f"{json.dumps([GROUNDED])}\nNote: [see the clause above]"

    assert [row[1] for row in parse_grounding_response(response)] == [GroundingVerdict.GROUNDED]


NEW_TAIL = (
    "For each claim, respond with one JSON object. If there is a single claim, you may return that "
    "object on its own; if there are several, return a JSON array of the objects, one per claim, in the "
    "same order as the input claims. Return the JSON only"
)


def test_prompt_permits_a_single_object_and_keeps_the_array_for_batches() -> None:
    normalised = " ".join(GROUNDING_PROMPT_TEMPLATE.split())
    assert NEW_TAIL in normalised


def test_prompt_no_longer_demands_an_array_unconditionally() -> None:
    assert "Respond with a JSON array of these objects" not in GROUNDING_PROMPT_TEMPLATE


# ── answers that omit the index: the prompt only promises an order ────────────


def _unindexed(verdict: str = "grounded") -> dict[str, object]:
    """The same answer minus ``claim_index`` — legal when the call has one claim."""
    answer = {**GROUNDED, "verdict": verdict}
    del answer["claim_index"]
    return answer


def test_object_without_claim_index_is_read_as_the_answer_for_position_zero() -> None:
    rows = parse_grounding_response(json.dumps(_unindexed()))

    assert len(rows) == 1
    claim_index, verdict, provenances, confidence = rows[0]
    assert claim_index == 0
    assert verdict is GroundingVerdict.GROUNDED
    assert [(p.clause_id, p.paragraph_index, p.confidence) for p in provenances] == [
        ("4.3", 2, 0.95)
    ]
    assert confidence == 0.95


def test_array_without_claim_indices_is_read_in_input_order() -> None:
    response = json.dumps([_unindexed(), _unindexed("ungrounded"), _unindexed("uncertain")])

    assert _indices(response) == [0, 1, 2]
    assert _verdicts(response) == [
        GroundingVerdict.GROUNDED,
        GroundingVerdict.UNGROUNDED,
        GroundingVerdict.UNCERTAIN,
    ]


def test_numeric_string_claim_index_is_coerced_to_an_int() -> None:
    response = json.dumps([{**_unindexed(), "claim_index": "0"}])

    assert _indices(response) == [0]


def test_non_numeric_string_claim_index_falls_back_to_the_position() -> None:
    response = json.dumps([{**_unindexed(), "claim_index": "n/a"}, _unindexed("ungrounded")])

    assert _indices(response) == [0, 1]


def test_an_integer_claim_index_still_wins_over_the_position() -> None:
    response = json.dumps([_obj(5), _unindexed("ungrounded")])

    assert _indices(response) == [5, 1]


def test_an_unknown_verdict_is_still_skipped_with_or_without_an_index() -> None:
    response = json.dumps(
        [_unindexed("nope"), {**_unindexed("nope"), "claim_index": 1}, _unindexed("grounded")]
    )

    assert _indices(response) == [2]
