"""Unit tests for the bilateral clause alignment engine.

Covers exact heading match, fuzzy match, positional fallback,
unmatched detection, mixed scenarios, and edge cases.
"""

from __future__ import annotations

import pytest

from openreview_cli.bilateral.align import align_clauses
from openreview_cli.bilateral.models import MatchingMethod
from openreview_cli.parsing.models import Clause


def make_clause(
    clause_id: str = "c1",
    title: str | None = "Confidentiality",
    text: str = "Confidentiality clause text",
    level: int = 1,
) -> Clause:
    """Create a minimal Clause for testing."""
    return Clause(
        id=clause_id,
        title=title,
        text=text,
        level=level,
        parent_id=None,
        source_page=1,
        source_paragraph=None,
        source_span=(0, len(text)),
    )


class TestAlignmentExact:
    """Tests for exact heading match (case-insensitive equality)."""

    def test_exact_heading_match(self) -> None:
        a = [make_clause("a1", "Confidentiality"), make_clause("a2", "Term")]
        b = [make_clause("b1", "Confidentiality"), make_clause("b2", "Term")]
        table = align_clauses(a, b)

        assert table.matched_count == 2
        assert all(p.method == MatchingMethod.exact for p in table.matched_pairs)
        assert all(p.score == 1.0 for p in table.matched_pairs)

    def test_case_insensitive_match(self) -> None:
        a = [make_clause("a1", "Confidentiality")]
        b = [make_clause("b1", "confidentiality")]
        table = align_clauses(a, b)

        assert table.matched_count == 1
        assert table.matched_pairs[0].method == MatchingMethod.exact
        assert table.matched_pairs[0].score == 1.0

    def test_exact_no_match(self) -> None:
        a = [make_clause("a1", "Confidentiality")]
        b = [make_clause("b1", "Governing Law")]
        table = align_clauses(a, b)

        # Falls through to positional fallback, not exact
        assert table.matched_count == 1
        assert table.matched_pairs[0].method == MatchingMethod.positional

    def test_exact_with_extra_spaces(self) -> None:
        a = [make_clause("a1", "  Confidential Information  ")]
        b = [make_clause("b1", "confidential information")]
        table = align_clauses(a, b)

        assert table.matched_count == 1
        assert table.matched_pairs[0].method == MatchingMethod.exact


class TestAlignmentFuzzy:
    """Tests for fuzzy heading match using difflib."""

    def test_fuzzy_match_above_threshold(self) -> None:
        a = [make_clause("a1", "Confidentiality")]
        b = [make_clause("b1", "Confidentiality Obligations")]
        table = align_clauses(a, b)

        assert table.matched_count == 1
        assert table.matched_pairs[0].method == MatchingMethod.fuzzy
        assert table.matched_pairs[0].score >= 0.7

    def test_fuzzy_match_below_threshold(self) -> None:
        a = [make_clause("a1", "Term")]
        b = [make_clause("b1", "Termination")]
        table = align_clauses(a, b)

        # Falls through to positional
        assert table.matched_count == 1
        assert table.matched_pairs[0].method == MatchingMethod.positional

    def test_fuzzy_prefers_best_match(self) -> None:
        a = [make_clause("a1", "Confidential Information")]
        b = [
            make_clause("b1", "Governing Law"),
            make_clause("b2", "Confidentiality Obligations"),
        ]
        table = align_clauses(a, b)

        # "Confidential Information" should fuzzy-match "Confidentiality Obligations"
        assert table.matched_count == 1
        assert table.matched_pairs[0].method in (MatchingMethod.exact, MatchingMethod.fuzzy)

    def test_fuzzy_no_second_match(self) -> None:
        # Party A has two clauses sharing "Confidential" prefix
        a = [
            make_clause("a1", "Confidential Information"),
            make_clause("a2", "Confidential Treatment"),
        ]
        # Party B has only one clause that could match
        b = [make_clause("b1", "Confidentiality")]
        table = align_clauses(a, b)

        # One matched (fuzzy), one unmatched
        assert table.matched_count == 1
        assert len(table.unmatched_a) == 1


class TestAlignmentPositional:
    """Tests for positional fallback matching."""

    def test_positional_fallback_no_heading_overlap(self) -> None:
        a = [make_clause("a1", "Section 1"), make_clause("a2", "Section 2")]
        b = [make_clause("b1", "Article 1"), make_clause("b2", "Article 2")]
        table = align_clauses(a, b)

        assert table.matched_count == 2
        assert all(p.method == MatchingMethod.positional for p in table.matched_pairs)
        assert all(p.score == 0.5 for p in table.matched_pairs)

    def test_positional_different_lengths(self) -> None:
        a = [make_clause("a1", "A"), make_clause("a2", "B"), make_clause("a3", "C")]
        b = [make_clause("b1", "X"), make_clause("b2", "Y")]
        table = align_clauses(a, b)

        # Two matched by position, one unmatched
        assert table.matched_count == 2
        assert all(p.method == MatchingMethod.positional for p in table.matched_pairs)
        assert len(table.unmatched_a) == 1
        assert table.unmatched_a[0].id == "a3"

    def test_positional_correct_index_tracking(self) -> None:
        a = [make_clause("a1", "A"), make_clause("a2", "B")]
        b = [make_clause("b1", "X"), make_clause("b2", "Y")]
        table = align_clauses(a, b)

        assert table.matched_pairs[0].pair_id == "A0-B0"
        assert table.matched_pairs[1].pair_id == "A1-B1"


class TestAlignmentUnmatched:
    """Tests for unmatched clause detection."""

    def test_unmatched_a_only(self) -> None:
        a = [make_clause("a1", "Confidentiality"), make_clause("a2", "Extra Clause")]
        b = [make_clause("b1", "Confidentiality")]
        table = align_clauses(a, b)

        assert table.matched_count == 1
        assert len(table.unmatched_a) == 1
        assert table.unmatched_a[0].id == "a2"
        assert len(table.unmatched_b) == 0

    def test_unmatched_b_only(self) -> None:
        a = [make_clause("a1", "Confidentiality")]
        b = [make_clause("b1", "Confidentiality"), make_clause("b2", "Extra Clause")]
        table = align_clauses(a, b)

        assert table.matched_count == 1
        assert len(table.unmatched_a) == 0
        assert len(table.unmatched_b) == 1
        assert table.unmatched_b[0].id == "b2"

    def test_both_unmatched_via_fallback(self) -> None:
        # Use headings with low similarity so they don't fuzzy-match
        # (ratio will be below threshold, falling through to positional)
        a = [make_clause("a1", "AAA"), make_clause("a2", "BBB")]
        b = [make_clause("b1", "XXX"), make_clause("b2", "YYY")]
        table = align_clauses(a, b)

        # Two positional matches (same indices)
        assert table.matched_count == 2
        assert all(p.method == MatchingMethod.positional for p in table.matched_pairs)


class TestAlignmentMixed:
    """Tests for mixed scenarios with exact, fuzzy, positional, and unmatched."""

    def test_mixed_scenario(self) -> None:
        a = [
            make_clause("a1", "Confidentiality"),
            make_clause("a2", "Term"),
            make_clause("a3", "Unique Clause A"),
        ]
        b = [
            make_clause("b1", "Confidentiality"),
            make_clause("b2", "Termination Period"),
            make_clause("b3", "Unique Clause B"),
        ]
        table = align_clauses(a, b)

        # a1-b1: exact match
        # a2-b2: "Term" vs "Termination Period" — fuzzy if >= 0.8, else positional
        # a3-b3: no match → positional (same index)
        assert table.matched_count == 3

        # Verify exact match
        assert any(
            p.method == MatchingMethod.exact and p.clause_a.id == "a1" for p in table.matched_pairs
        )

    def test_no_heading_clauses_fall_back_to_text(self) -> None:
        a = [make_clause("a1", title=None, text="Confidentiality clause")]
        b = [make_clause("b1", title=None, text="Confidentiality clause too")]
        table = align_clauses(a, b)

        # Title is None for both, fallback to text prefix
        assert table.matched_count == 1


class TestAlignmentEdgeCases:
    """Tests for edge cases like empty docs, identical docs, etc."""

    def test_empty_documents(self) -> None:
        table = align_clauses([], [])
        assert table.matched_count == 0
        assert table.alignment_rate == 0.0
        assert len(table.unmatched_a) == 0
        assert len(table.unmatched_b) == 0

    def test_one_empty_document(self) -> None:
        a = [make_clause("a1", "Confidentiality")]
        b: list[Clause] = []
        table = align_clauses(a, b)

        assert table.matched_count == 0
        assert len(table.unmatched_a) == 1

    def test_identical_documents_all_matched(self) -> None:
        a = [
            make_clause("a1", "Confidentiality"),
            make_clause("a2", "Term"),
            make_clause("a3", "Governing Law"),
        ]
        b = [
            make_clause("b1", "Confidentiality"),
            make_clause("b2", "Term"),
            make_clause("b3", "Governing Law"),
        ]
        table = align_clauses(a, b)

        assert table.matched_count == 3
        assert table.alignment_rate == 1.0
        assert len(table.unmatched_a) == 0
        assert len(table.unmatched_b) == 0
        assert all(p.method == MatchingMethod.exact for p in table.matched_pairs)

    def test_completely_different_headings(self) -> None:
        a = [make_clause("a1", "AAA"), make_clause("a2", "BBB")]
        b = [make_clause("b1", "XXX"), make_clause("b2", "YYY")]
        table = align_clauses(a, b)

        # Should fall through to positional for all
        assert table.matched_count == 2
        assert all(p.method == MatchingMethod.positional for p in table.matched_pairs)

    def test_single_clause_each(self) -> None:
        a = [make_clause("a1", "Confidentiality")]
        b = [make_clause("b1", "Confidentiality")]
        table = align_clauses(a, b)

        assert table.matched_count == 1
        assert table.matched_pairs[0].method == MatchingMethod.exact
        assert table.matched_pairs[0].score == 1.0

    def test_alignment_rate_calculation(self) -> None:
        a = [make_clause("a1", "A"), make_clause("a2", "B"), make_clause("a3", "C")]
        b = [make_clause("b1", "A"), make_clause("b2", "B")]
        table = align_clauses(a, b)

        # 2 matched pairs (4 clauses) + 1 unmatched = 5 total, 4/5 = 0.8
        assert table.alignment_rate == pytest.approx(4 / 5)
