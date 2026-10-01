"""Unit tests for the grounding answer reader."""

from __future__ import annotations

import json

from openreview_cli.config.loader import DEFAULT_CONFIG
from openreview_cli.grounding.discriminator import _BATCH_SIZE
from openreview_cli.grounding.models import GroundingVerdict
from openreview_cli.grounding.prompts import (
    _CLAUSE_WINDOW_CHARS,
    _MAX_PROMPT_CLAUSES,
    _TRUNCATION_MARKER,
    GROUNDING_PROMPT_TEMPLATE,
    _clause_window,
    build_grounding_messages,
    build_second_pass_messages,
    parse_grounding_response,
    parse_miscited_ids,
)
from openreview_cli.parsing.models import Clause

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


# ── answers the model wrapped in a key: the shape a CI run measured ───────────


def test_one_answer_wrapped_in_claims_parses() -> None:
    response = json.dumps({"claims": [_obj(0)]})

    assert _indices(response) == [0]
    assert _verdicts(response) == [GroundingVerdict.GROUNDED]


def test_three_answers_wrapped_in_claims_parse_in_order() -> None:
    response = json.dumps({"claims": [_obj(0), _obj(1, "ungrounded"), _obj(2, "uncertain")]})

    assert _indices(response) == [0, 1, 2]
    assert _verdicts(response) == [
        GroundingVerdict.GROUNDED,
        GroundingVerdict.UNGROUNDED,
        GroundingVerdict.UNCERTAIN,
    ]


def test_a_wrapped_answer_without_claim_index_falls_back_to_position_zero() -> None:
    rows = parse_grounding_response(json.dumps({"claims": [_unindexed()]}))

    assert len(rows) == 1
    assert rows[0][0] == 0
    assert rows[0][1] is GroundingVerdict.GROUNDED


def test_a_dict_of_answers_keyed_by_index_parses_in_insertion_order() -> None:
    response = json.dumps({"0": _obj(0), "1": _obj(1, "ungrounded")})

    assert _indices(response) == [0, 1]
    assert _verdicts(response) == [GroundingVerdict.GROUNDED, GroundingVerdict.UNGROUNDED]


def test_claims_is_preferred_when_several_wrapper_keys_hold_answer_lists() -> None:
    response = json.dumps({"notes": [_obj(9)], "claims": [_obj(0)]})

    assert _indices(response) == [0]


def test_a_bare_array_and_a_bare_object_are_still_read() -> None:
    """Regression guards: unwrapping must not disturb the shapes that already worked."""
    assert _verdicts(json.dumps([GROUNDED])) == [GroundingVerdict.GROUNDED]
    assert _verdicts(json.dumps(GROUNDED)) == [GroundingVerdict.GROUNDED]


# ── the per-claim hint: absent wording is named on that claim's own line ──────

# Pinned verbatim: the model reads this exact sentence, so a test that imported it
# from the implementation would only prove the implementation equals itself.
_HINT = (
    "[the claim's wording does not appear in the cited clause; "
    "answer grounded only if the clause still entails it]"
)

_CLAUSES = [
    Clause(
        id="4.3",
        title=None,
        text="The receiving party shall not disclose confidential information.",
        level=1,
        parent_id=None,
        source_page=1,
        source_paragraph=None,
        source_span=None,
    )
]

# Two claims on one clause: the first is quoted from it, the second is not.
_CLAIMS = [
    (0, "The receiving party shall not disclose", "4.3"),
    (1, "The term is twelve months from the effective date", "4.3"),
]


def _user_content(messages: list[dict[str, str]]) -> str:
    return next(m["content"] for m in messages if m["role"] == "user")


def _claim_line(content: str, index: int) -> str:
    # Anchored on the opening quote so the template's own numbered list ("1. Is the
    # claim supported…") is never mistaken for a claim line.
    return next(line for line in content.splitlines() if line.startswith(f'{index}. "'))


def _built(*args: object) -> str:
    return _user_content(build_grounding_messages(_CLAUSES, _CLAIMS, *args))  # type: ignore[arg-type]


def test_a_flagged_claim_line_carries_the_hint_and_an_unflagged_one_does_not() -> None:
    content = _built({1})

    assert _HINT in _claim_line(content, 1)
    assert _HINT not in _claim_line(content, 0)


def test_the_hint_is_appended_after_the_existing_citation_text() -> None:
    line = _claim_line(_built({1}), 1)

    assert line.startswith(
        '1. "The term is twelve months from the effective date" (cites clause 4.3) '
    )
    assert line.endswith(_HINT)


def test_an_empty_set_adds_no_hint() -> None:
    assert _HINT not in _built(set())


def test_none_is_byte_identical_to_omitting_the_argument() -> None:
    without = build_grounding_messages(_CLAUSES, _CLAIMS)
    with_none = build_grounding_messages(_CLAUSES, _CLAIMS, None)

    assert with_none == without
    assert with_none[0]["content"].encode() == without[0]["content"].encode()


def test_an_unflagged_claim_line_is_byte_identical_with_or_without_the_set() -> None:
    assert _claim_line(_built({1}), 0) == _claim_line(_built(), 0)


def test_the_hint_carries_no_claim_or_clause_text_of_its_own() -> None:
    # The line's shape — the hint appended last — is pinned by the test above.
    assert _CLAUSES[0].text not in _HINT
    assert _CLAIMS[1][1] not in _HINT


# ── item 7: the clause window is measured in sentences, not characters ────────


class TestClauseWindow:
    """Item 7: ~2000 characters, whole sentences while they fit, a marker when text was left out."""

    def test_a_long_clause_is_cut_on_a_sentence_boundary_and_marked(self) -> None:
        text = "The receiving party shall not disclose Confidential Information to anyone. " * 80
        window = _clause_window(text)
        assert len(window) <= _CLAUSE_WINDOW_CHARS + len(_TRUNCATION_MARKER)
        assert window.endswith(_TRUNCATION_MARKER)
        body = window[: -len(_TRUNCATION_MARKER)]
        assert text.startswith(body) and body.rstrip().endswith(".")

    def test_a_long_clause_window_fills_the_bound(self) -> None:
        """The window is only a window if it actually approaches the bound.

        ``test_a_long_clause_is_cut_on_a_sentence_boundary_and_marked`` pins the upper bound
        and the marker, so an implementation that stopped at the *first* sentence boundary
        passes it while keeping ~100 characters of a ~6000-character clause (5% of the
        bound) and dropping the rest. This pins the fill ratio so that wrong cut fails.
        """
        sentence = "The receiving party shall not disclose Confidential Information to anyone. "
        text = sentence * 80  # 6000 characters, all sentence-boundaried
        window = _clause_window(text)
        body = window[: -len(_TRUNCATION_MARKER)]

        assert len(window) <= _CLAUSE_WINDOW_CHARS + len(_TRUNCATION_MARKER)
        # Measured: 1949 of 2000 characters (97.5%). A first-sentence-only cut would keep 75
        # (3.8%), so this fails loudly against it.
        assert len(body) >= 0.90 * _CLAUSE_WINDOW_CHARS, (
            f"window filled only {len(body)} of {_CLAUSE_WINDOW_CHARS} characters"
        )

    def test_a_single_oversized_first_sentence_is_hard_clipped(self) -> None:
        # The bound in the sentence-boundary test must hold for every input, so a first
        # sentence longer than the window is clamped at the window, not kept whole.
        text = "x" * (_CLAUSE_WINDOW_CHARS + 500)
        assert _clause_window(text) == text[:_CLAUSE_WINDOW_CHARS] + _TRUNCATION_MARKER

    def test_the_built_message_carries_the_window_and_not_the_text_beyond_it(self) -> None:
        """The call site, not the helper: assert on the message the model receives.

        Every test above exercises ``_clause_window`` directly, so a call site that went
        back to slicing the raw clause text would still pass them. This builds the real
        messages and pins what the model is sent: the window's truncation marker is
        present and the clause text past the window never reaches it.
        """
        filler = (
            "The receiving party shall not disclose Confidential Information to any third "
            "party without prior written consent. "
        )
        beyond = "SENTINEL past the window shall indemnify the other party for all losses."
        clause = Clause(
            id="4.3",
            title=None,
            text=filler * 60 + beyond,
            level=1,
            parent_id=None,
            source_page=1,
            source_paragraph=None,
            source_span=None,
        )

        content = _user_content(build_grounding_messages([clause], [(0, "a claim", "4.3")]))

        assert len(clause.text) > _CLAUSE_WINDOW_CHARS  # the clause really is cut
        assert _TRUNCATION_MARKER in content
        assert "SENTINEL past the window" not in content


# ── item 3: sibling clauses, bounded; the fourth answer is a field ────────────


def test_the_prompt_shows_at_most_the_cap_of_clauses() -> None:
    clauses = [
        Clause(
            id=f"c{i}",
            title=None,
            text="Sentence one is here. " * 20,
            level=1,
            parent_id=None,
            source_page=1,
            source_paragraph=None,
            source_span=None,
        )
        for i in range(_MAX_PROMPT_CLAUSES + 5)
    ]
    content = _user_content(build_grounding_messages(clauses, [(0, "a claim", "c0")]))
    clause_lines = [line for line in content.splitlines() if line.startswith("[")]
    assert len(clause_lines) == _MAX_PROMPT_CLAUSES
    assert all(
        len(line) <= _CLAUSE_WINDOW_CHARS + len(_TRUNCATION_MARKER) + 8 for line in clause_lines
    )


def _configured_grounding_budget() -> tuple[int, int]:
    """The grounding slot's ``(num_ctx, max_tokens)`` as the gateway builds its request.

    Both come from the config the gateway reads (``config/loader.py`` ``DEFAULT_CONFIG``):
    the context the model runs with, and the output the request reserves inside it.
    """
    from typing import Any, cast

    gateway = cast("dict[str, Any]", DEFAULT_CONFIG["gateway"])
    grounding = gateway["models"]["grounding"]
    return int(grounding["extra_params"]["num_ctx"]), int(grounding["params"]["max_tokens"])


def test_the_worst_case_prompt_stays_inside_the_configured_context() -> None:
    """The built prompt must fit the context the grounding model actually runs with.

    Ollama truncates silently at its default 4096, so a prompt that overflows does not
    error — the model just never sees the tail. This pins the worst case: the clause cap
    of sections each windowed to the full bound, one full batch of the longest claim lines
    (each carrying the wording-absent hint), and the fixed instruction text between them.
    The numbers below are stated so a future widening of the cap or the window fails here
    instead of silently truncating in production.
    """
    # Longer than the window, so every section is windowed to (at most) the bound plus the marker.
    sentence = (
        "The receiving party shall not disclose Confidential Information to any third party. "
    )
    oversized = sentence * 40
    clauses = [
        Clause(
            id=f"c{i}",
            title=None,
            text=oversized,
            level=1,
            parent_id=None,
            source_page=1,
            source_paragraph=None,
            source_span=None,
        )
        for i in range(_MAX_PROMPT_CLAUSES)
    ]
    # A full batch of the longest possible claim lines, every one hinted.
    claims = [(i, "x" * 300, f"c{i}") for i in range(_BATCH_SIZE)]
    content = _user_content(build_grounding_messages(clauses, claims, set(range(_BATCH_SIZE))))

    num_ctx, output_reservation = _configured_grounding_budget()
    # English runs about 3.5 characters per token; 3.5 is the conservative end of the usual
    # 3-4 range, i.e. it over-counts tokens rather than under-counting them. Measured here:
    #   sections: 8 x (1956-char window + marker + id prefix) = 15,710 chars
    #   fixed instruction text (GROUNDING_PROMPT_TEMPLATE)    =  1,389 chars
    #   10 max-length claim lines + the wording-absent hint   =  4,320 chars
    #   total                                                 = 21,419 chars ~ 6,120 tokens
    chars_per_token = 3.5
    estimated_tokens = len(content) / chars_per_token

    assert _MAX_PROMPT_CLAUSES == 8 and _CLAUSE_WINDOW_CHARS == 2000
    # The bound must cover the input AND the output the request reserves: the slot's context
    # has to hold the worst-case prompt plus ``max_tokens``, with margin, or Ollama truncates
    # the tail silently — the exact failure the context size was added to prevent.
    assert estimated_tokens + output_reservation <= num_ctx * 0.85, (
        f"worst-case prompt ~{estimated_tokens:.0f} tokens plus a {output_reservation}-token "
        f"output reservation exceeds num_ctx {num_ctx}"
    )


def test_the_prompt_offers_the_fourth_answer_as_a_field() -> None:
    assert "miscited_to_clause_id" in GROUNDING_PROMPT_TEMPLATE
    # The three verdicts are unchanged: the fourth answer is a field, never a verdict.
    assert '"grounded" | "ungrounded" | "uncertain"' in GROUNDING_PROMPT_TEMPLATE


def test_the_verdict_enum_has_no_fourth_member() -> None:
    assert set(GroundingVerdict.__members__) == {"GROUNDED", "UNGROUNDED", "UNCERTAIN"}


def test_miscited_ids_are_keyed_by_the_claimed_index_not_the_array_position() -> None:
    """A batch's answer may not come back in index order, and the pointers must follow the
    finding each one names — not the slot it happened to occupy in the array.

    Keying by array position instead of ``claim_index`` returns ``{0: ..., 1: ...}`` for
    this answer and misattributes every pointer, while every batch-path test (which uses
    in-order indices) stays green.
    """
    response = json.dumps(
        [
            {"claim_index": 7, "miscited_to_clause_id": "4.7"},
            {"claim_index": 3, "miscited_to_clause_id": "9.2"},
        ]
    )

    assert parse_miscited_ids(response) == {7: "4.7", 3: "9.2"}


# ── item 4: the second narrow question, closed, sharing the same machinery ────


def test_the_second_pass_question_is_closed_and_never_asks_for_reasoning() -> None:
    content = _user_content(build_second_pass_messages(_CLAUSES, _CLAIMS))
    assert "leaves out" in content
    for banned in ("step by step", "chain of thought", "think through", "explain your reasoning"):
        assert banned not in content.lower()


def test_the_second_pass_uses_the_same_clause_window() -> None:
    # FIX 8: 100 sentences (~2200 chars) actually exceeds the 2000-char window, so it truncates.
    long_clause = Clause(
        id="4.3",
        title=None,
        text="Sentence one is here. " * 100,
        level=1,
        parent_id=None,
        source_page=1,
        source_paragraph=None,
        source_span=None,
    )
    assert _TRUNCATION_MARKER in _user_content(
        build_second_pass_messages([long_clause], [(0, "a claim", "4.3")])
    )


def test_the_second_pass_names_the_keys_it_expects() -> None:
    """The shared reader drops any item without a ``verdict`` key, so a prompt that names no
    keys lets a well-behaved model answer ``{"supported": "yes"}`` — which parses to nothing —
    and the whole second pass becomes a silent no-op while looking enabled."""
    content = _user_content(build_second_pass_messages(_CLAUSES, _CLAIMS))

    assert "claim_index" in content
    for verdict in ('"grounded"', '"ungrounded"', '"uncertain"'):
        assert verdict in content


def test_a_key_named_second_pass_answer_parses() -> None:
    """The shape the second-pass template now names must be readable by the shared reader."""
    answer = json.dumps(
        [
            {"claim_index": 3, "verdict": "ungrounded"},
            {"claim_index": 7, "verdict": "grounded"},
        ]
    )

    assert [(index, verdict) for index, verdict, _p, _c in parse_grounding_response(answer)] == [
        (3, GroundingVerdict.UNGROUNDED),
        (7, GroundingVerdict.GROUNDED),
    ]
