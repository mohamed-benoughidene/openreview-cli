"""Unit tests for corruption strategy generators (T021) and the grounding guard (T032).

The generator tests at the top cover the legacy helpers and their documented scope.
The tests at the bottom cover the honest negative generator (``unsupported_claim``),
the mandatory guard (``is_genuine_negative``) that every generated negative passes
through, and the sentence rule both share (``first_qualifying_sentence``).
"""

from __future__ import annotations

import inspect

from openreview_cli.grounding.corruption import (
    GROUNDING_VALID_NEGATIVES,
    ClauseUnit,
    anachronism,
    category_swap,
    clause_swap,
    first_qualifying_sentence,
    hallucination,
    is_genuine_negative,
    unsupported_claim,
)
from openreview_cli.parsing.models import Clause


def _make_clause(id_: str, text: str = "Some clause text") -> Clause:
    return Clause(
        id=id_,
        title=None,
        text=text,
        level=1,
        parent_id=None,
        source_page=None,
        source_paragraph=None,
        source_span=None,
    )


class TestClauseSwap:
    def test_replaces_with_different_clause(self) -> None:
        clauses = [_make_clause("4.3"), _make_clause("7.1"), _make_clause("10.2")]
        claim = "The receiving party shall not disclose (citing clause 4.3)"
        result = clause_swap(claim, clauses, "4.3")
        assert result != claim
        assert "4.3" not in result
        assert "citing clause" in result

    def test_single_clause_returns_unchanged(self) -> None:
        clauses = [_make_clause("4.3")]
        claim = "Claim citing clause 4.3"
        result = clause_swap(claim, clauses, "4.3")
        assert result == claim

    def test_empty_clauses_returns_unchanged(self) -> None:
        clauses: list[Clause] = []
        claim = "Claim citing clause 4.3"
        result = clause_swap(claim, clauses, "4.3")
        assert result == claim

    def test_deterministic_with_same_inputs(self) -> None:
        clauses = [_make_clause("4.3"), _make_clause("7.1"), _make_clause("10.2")]
        claim = "Claim citing clause 4.3"
        r1 = clause_swap(claim, clauses, "4.3")
        r2 = clause_swap(claim, clauses, "4.3")
        assert r1 == r2


class TestCategorySwap:
    def test_replaces_with_different_category(self) -> None:
        claim = "The clause falls under confidentiality obligations"
        categories = ["confidentiality", "indemnification", "termination"]
        result = category_swap(claim, "confidentiality", categories)
        assert result != claim
        assert "confidentiality" not in result

    def test_single_category_returns_unchanged(self) -> None:
        claim = "Category: confidentiality"
        result = category_swap(claim, "confidentiality", ["confidentiality"])
        assert result == claim

    def test_empty_categories_returns_unchanged(self) -> None:
        claim = "Category: confidentiality"
        result = category_swap(claim, "confidentiality", [])
        assert result == claim

    def test_deterministic_with_same_inputs(self) -> None:
        categories = ["confidentiality", "indemnification", "termination"]
        claim = "confidentiality obligations"
        r1 = category_swap(claim, "confidentiality", categories)
        r2 = category_swap(claim, "confidentiality", categories)
        assert r1 == r2


class TestHallucination:
    def test_returns_fabricated_text(self) -> None:
        claim = "The receiving party shall not disclose confidential information"
        result = hallucination(claim)
        assert result != claim
        assert len(result) > 10

    def test_deterministic_for_same_input(self) -> None:
        claim = "Test claim for hallucination"
        r1 = hallucination(claim)
        r2 = hallucination(claim)
        assert r1 == r2

    def test_different_inputs_produce_possibly_different_outputs(self) -> None:
        r1 = hallucination("First claim about confidentiality")
        r2 = hallucination("Second claim about indemnification")
        # These are derived from different seeds so should differ
        # (collision probability is 1/10 with 10 fabrications)
        # We just check that at least one differs across many pairings
        texts = {hallucination(f"claim {i}") for i in range(20)}
        assert len(texts) > 1

    def test_return_type_is_string(self) -> None:
        result = hallucination("any claim")
        assert isinstance(result, str)


class TestAnachronism:
    def test_replaces_clause_id_with_fake(self) -> None:
        claim = "The receiving party shall not disclose (citing clause 4.3)"
        result = anachronism(claim, "4.3")
        assert result != claim
        assert "4.3" not in result

    def test_fake_id_does_not_match_original(self) -> None:
        result = anachronism("citing clause 4.3", "4.3")
        # Should not contain the original clause_id
        assert "4.3" not in result

    def test_deterministic_for_same_input(self) -> None:
        claim = "citing clause 4.3"
        r1 = anachronism(claim, "4.3")
        r2 = anachronism(claim, "4.3")
        assert r1 == r2

    def test_different_clause_ids_produce_different_fakes(self) -> None:
        r1 = anachronism("citing clause 4.3", "4.3")
        r2 = anachronism("citing clause 7.1", "7.1")
        assert r1 != r2


# ---------------------------------------------------------------------------
# The honest negative generator, the mandatory guard, and the shared sentence
# rule (plan T3.1 / design 2026-09-30-grounding-accuracy-harness-design.md §2, §3).
# ---------------------------------------------------------------------------

# Two real-shaped source units. Each starts with a short heading sentence (under
# the selection bar) so the "first *qualifying* sentence" rule is exercised.
CLAUSE_A_TEXT = (
    "4.1 Confidentiality. The receiving party shall not disclose any Confidential Information "
    "to any third party without the prior written consent of the disclosing party."
)
CLAUSE_B_TEXT = (
    "9.3 Indemnity. The receiving party shall indemnify and hold harmless the disclosing party "
    "against all third-party claims."
)
# A sentence that is asserted against CLAUSE_A but is not part of it.
FOREIGN_CLAIM = (
    "The receiving party shall indemnify and hold harmless the disclosing party "
    "against all third-party claims."
)

UNIT_A = ClauseUnit(id="c000", text=CLAUSE_A_TEXT)
UNIT_B = ClauseUnit(id="c001", text=CLAUSE_B_TEXT)


class TestFirstQualifyingSentence:
    """The §2.1/§2.2 selection rule, shared by positives and cross-clause negatives."""

    def test_skips_short_sentences_and_returns_the_first_that_qualifies(self) -> None:
        assert first_qualifying_sentence(CLAUSE_A_TEXT) == (
            "The receiving party shall not disclose any Confidential Information to any third "
            "party without the prior written consent of the disclosing party."
        )

    def test_returns_none_when_no_sentence_qualifies(self) -> None:
        assert first_qualifying_sentence("Short one. Also short.") is None

    def test_returns_none_for_empty_text(self) -> None:
        assert first_qualifying_sentence("") is None

    def test_returns_verbatim_clause_text(self) -> None:
        sentence = first_qualifying_sentence(CLAUSE_B_TEXT)
        assert sentence is not None
        assert sentence in CLAUSE_B_TEXT


class TestUnsupportedClaim:
    """`unsupported_claim(a, b)` — a genuine negative with no string surgery."""

    def test_claim_is_drawn_from_the_other_clause(self) -> None:
        claim = unsupported_claim(UNIT_A, UNIT_B)
        assert claim is not None
        assert claim in CLAUSE_B_TEXT, "the negative must be verbatim text from clause_b"
        assert claim not in CLAUSE_A_TEXT

    def test_claim_is_a_genuine_negative_against_the_cited_clause(self) -> None:
        claim = unsupported_claim(UNIT_A, UNIT_B)
        assert claim is not None
        assert is_genuine_negative(claim, CLAUSE_A_TEXT) is True

    def test_skips_the_short_heading_sentence(self) -> None:
        assert unsupported_claim(UNIT_A, UNIT_B) == FOREIGN_CLAIM

    def test_same_clause_twice_returns_none(self) -> None:
        # Nothing here can be a genuine negative: a sentence from the clause is
        # supported by the very clause it is asserted against.
        assert unsupported_claim(UNIT_A, UNIT_A) is None

    def test_clause_without_a_qualifying_sentence_returns_none(self) -> None:
        tiny = ClauseUnit(id="c002", text="Tiny clause. Too short to qualify.")
        assert unsupported_claim(UNIT_A, tiny) is None

    def test_accepts_units_built_from_plain_id_text_pairs(self) -> None:
        # A harness keeps plain (id, text) pairs; it constructs a ClauseUnit at the call.
        claim = unsupported_claim(
            ClauseUnit("c000", CLAUSE_A_TEXT), ClauseUnit("c001", CLAUSE_B_TEXT)
        )
        assert claim == FOREIGN_CLAIM

    def test_deterministic_with_same_inputs(self) -> None:
        assert unsupported_claim(UNIT_A, UNIT_B) == unsupported_claim(UNIT_A, UNIT_B)


class TestGenuineNegativeGuard:
    """The mandatory guard: a negative whose claim appears verbatim in the cited
    clause is a mislabel and must be dropped (and counted) by the harness."""

    def test_accepts_a_cross_clause_claim(self) -> None:
        assert is_genuine_negative(FOREIGN_CLAIM, CLAUSE_A_TEXT) is True

    def test_rejects_the_no_op_corruption_verbatim_clause_text(self) -> None:
        assert is_genuine_negative(CLAUSE_A_TEXT, CLAUSE_A_TEXT) is False

    def test_rejects_a_claim_that_appears_inside_the_clause(self) -> None:
        assert is_genuine_negative(FOREIGN_CLAIM, CLAUSE_B_TEXT) is False

    def test_normalisation_ignores_case(self) -> None:
        clause = "The receiving party shall not disclose Confidential Information."
        claim = "the receiving party SHALL NOT disclose confidential information."
        assert is_genuine_negative(claim, clause) is False

    def test_normalisation_ignores_whitespace(self) -> None:
        clause = "The receiving party shall not disclose Confidential Information."
        claim = "  The receiving    party shall not\ndisclose Confidential Information.  "
        assert is_genuine_negative(claim, clause) is False

    def test_accepts_a_near_miss_claim(self) -> None:
        # The guard is a substring test on the exact claim, not a semantic check.
        clause = "The receiving party shall not disclose Confidential Information."
        claim = "The receiving party shall promptly disclose Confidential Information."
        assert is_genuine_negative(claim, clause) is True

    def test_empty_claim_is_rejected(self) -> None:
        assert is_genuine_negative("", CLAUSE_A_TEXT) is False

    def test_no_op_clause_swap_is_caught_by_the_guard(self) -> None:
        # W12: clause_swap edits the claim *text*, which no-ops on prose. The guard
        # catches the resulting mislabel for free: the "negative" is the clause text.
        clauses = [_make_clause("4.1", CLAUSE_A_TEXT), _make_clause("9.3", CLAUSE_B_TEXT)]
        claim = (
            "The receiving party shall not disclose any Confidential Information to any third "
            "party without the prior written consent of the disclosing party."
        )
        swapped = clause_swap(claim, clauses, "4.1")
        assert swapped == claim, "clause_swap no-ops on prose (no clause id in the text)"
        assert is_genuine_negative(swapped, CLAUSE_A_TEXT) is False

    def test_no_op_anachronism_is_caught_by_the_guard(self) -> None:
        claim = "The receiving party shall not disclose Confidential Information."
        assert anachronism(claim, "4.1") == claim
        assert is_genuine_negative(anachronism(claim, "4.1"), claim) is False

    def test_indemnity_fabrication_is_dropped_against_an_indemnity_clause(self) -> None:
        # hallucination's index-4 fabrication is *supported* by an indemnity clause
        # (design §1.5). Found by scanning seeds so the test does not hardcode the index.
        fabricated: str | None = None
        for i in range(1000):
            candidate = hallucination(f"seed claim {i}")
            if "indemnify and hold harmless" in candidate:
                fabricated = candidate
                break
        assert fabricated is not None, "hallucination never produced the indemnity fabrication"
        assert is_genuine_negative(fabricated, CLAUSE_B_TEXT) is False
        assert is_genuine_negative(fabricated, CLAUSE_A_TEXT) is True


class TestDocumentedScope:
    """Which helpers may produce grounding negatives, and why the others may not."""

    def test_only_unsupported_claim_and_hallucination_are_grounding_negatives(self) -> None:
        assert GROUNDING_VALID_NEGATIVES == ("unsupported_claim", "hallucination")
        assert "category_swap" not in GROUNDING_VALID_NEGATIVES
        assert "anachronism" not in GROUNDING_VALID_NEGATIVES
        assert "clause_swap" not in GROUNDING_VALID_NEGATIVES

    def test_category_swap_cannot_change_support(self) -> None:
        # category_swap never receives the clause text (classification case, not a
        # support case): the evidence the claim is asserted against is untouched.
        assert set(inspect.signature(category_swap).parameters) == {
            "claim",
            "original_category",
            "categories",
        }
        claim = (
            "This clause imposes confidentiality obligations: the receiving party shall keep "
            "the disclosing party's Confidential Information confidential."
        )
        swapped = category_swap(claim, "confidentiality", ["indemnification"])
        assert "indemnification" in swapped
        assert swapped.replace("indemnification", "confidentiality") == claim
