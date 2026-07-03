"""Unit tests for corruption strategy generators (T021)."""

from __future__ import annotations

from openreview_cli.grounding.corruption import (
    anachronism,
    category_swap,
    clause_swap,
    hallucination,
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
