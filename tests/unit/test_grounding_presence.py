"""Unit tests for the presence primitive: coverage and the wording-absent guard.

``presence`` is a product-owned measurement primitive (plan Task 1). It records how much of
a claim's wording appears in the clause it cites, plus one boolean for the model to read.
Nothing here sets a verdict, and no test asks it to: the number and the boolean are
measurements only (design §1 rejects a coverage veto).
"""

from __future__ import annotations

from openreview_cli.grounding.presence import coverage, measure, normalise

# A real-shaped clause with a numbered heading and one long sentence.
CLAUSE_TEXT = (
    "4.1 Confidentiality. The receiving party shall not disclose any Confidential "
    "Information to any third party without the prior written consent of the disclosing party."
)
# A verbatim quote of that sentence: every claim token must occur in the clause.
VERBATIM_QUOTE = (
    "The receiving party shall not disclose any Confidential Information to any third party "
    "without the prior written consent of the disclosing party."
)
# A short quote (six tokens) from the same clause.
SHORT_QUOTE = "The receiving party shall not disclose"
# A sentence from another kind of clause, asserted against CLAUSE_TEXT.
FOREIGN_SENTENCE = (
    "This agreement shall remain in effect for a term of 99 years from the effective date."
)
# The same clause with a second, unrelated sentence appended: it must not change anything.
LONG_CLAUSE_TEXT = CLAUSE_TEXT + (
    " Nothing in this section limits any other remedy available to the disclosing party, "
    "whether at law or in equity, and each remedy is cumulative and not exclusive."
)


class TestNormalise:
    """`normalise` is the shared case-fold/whitespace-collapse step."""

    def test_case_folds_and_collapses_whitespace(self) -> None:
        assert normalise("  The   Receiving\tParty\nShall  ") == "the receiving party shall"

    def test_leaves_already_normalised_text_alone(self) -> None:
        assert normalise("the receiving party shall not disclose") == (
            "the receiving party shall not disclose"
        )


class TestCoverage:
    """`coverage` is the share of the claim's tokens that also occur in the clause."""

    def test_verbatim_quote_scores_one(self) -> None:
        assert coverage(VERBATIM_QUOTE, CLAUSE_TEXT) == 1.0

    def test_a_sentence_from_another_clause_scores_below_the_bar(self) -> None:
        # Comfortably under the module's internal bar; the exact value is not the point.
        assert coverage(FOREIGN_SENTENCE, CLAUSE_TEXT) < 0.5

    def test_case_and_whitespace_do_not_matter(self) -> None:
        noisy_claim = "  THE receiving\tparty SHALL not   disclose any Confidential INFORMATION  "
        noisy_clause = "\n".join(CLAUSE_TEXT.split(" ")).upper()
        assert coverage(noisy_claim, noisy_clause) == coverage(
            "the receiving party shall not disclose any confidential information", CLAUSE_TEXT
        )

    def test_long_clause_does_not_dilute_a_short_quote(self) -> None:
        assert coverage(SHORT_QUOTE, CLAUSE_TEXT) == 1.0
        assert coverage(SHORT_QUOTE, LONG_CLAUSE_TEXT) == 1.0

    def test_extra_claim_wording_lowers_the_score(self) -> None:
        # The denominator is the claim, so unproven extra wording cannot score 1.0.
        padded = SHORT_QUOTE + " and also liquidated damages are payable on demand"
        assert coverage(padded, CLAUSE_TEXT) < 1.0

    def test_empty_claim_scores_zero(self) -> None:
        assert coverage("", CLAUSE_TEXT) == 0.0


class TestMeasure:
    """`measure` returns the number beside the wording-absent guard."""

    def test_verbatim_quote_is_not_absent(self) -> None:
        score, wording_absent = measure(VERBATIM_QUOTE, CLAUSE_TEXT)
        assert score == 1.0
        assert wording_absent is False

    def test_a_sentence_from_another_clause_is_absent(self) -> None:
        score, wording_absent = measure(FOREIGN_SENTENCE, CLAUSE_TEXT)
        assert score < 0.5
        assert wording_absent is True

    def test_empty_clause_is_never_absent(self) -> None:
        score, wording_absent = measure(VERBATIM_QUOTE, "")
        assert score == 0.0
        assert wording_absent is False

    def test_whitespace_only_clause_is_never_absent(self) -> None:
        _, wording_absent = measure(VERBATIM_QUOTE, "   \n\t ")
        assert wording_absent is False

    def test_claim_under_five_tokens_is_never_absent(self) -> None:
        # Four tokens, none of them in the clause: the measurement is not trusted this small.
        _, wording_absent = measure("liquidated damages are payable", CLAUSE_TEXT)
        assert wording_absent is False

    def test_reference_like_claim_is_never_absent(self) -> None:
        for reference in ("4.3", "v12.4", "1.2.3.4.5"):
            _, wording_absent = measure(reference, CLAUSE_TEXT)
            assert wording_absent is False, reference

    def test_long_clause_does_not_dilute_a_short_quote(self) -> None:
        score, wording_absent = measure(SHORT_QUOTE, LONG_CLAUSE_TEXT)
        assert score == 1.0
        assert wording_absent is False

    def test_number_matches_coverage_for_every_guard(self) -> None:
        pairs = [
            (VERBATIM_QUOTE, CLAUSE_TEXT),
            (VERBATIM_QUOTE, ""),
            (FOREIGN_SENTENCE, CLAUSE_TEXT),
            (SHORT_QUOTE, LONG_CLAUSE_TEXT),
            ("liquidated damages are payable", CLAUSE_TEXT),
            ("4.3", CLAUSE_TEXT),
            ("", CLAUSE_TEXT),
        ]
        for claim_text, clause_text in pairs:
            assert measure(claim_text, clause_text)[0] == coverage(claim_text, clause_text)
