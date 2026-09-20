"""Unit tests for BM25 sparse retrieval (T011)."""

from __future__ import annotations

from openreview_cli.retrieval.bm25 import normalize_bm25_scores, preprocess_query


class TestPreprocessQuery:
    """Tests for query preprocessing."""

    def test_lowercase(self) -> None:
        assert preprocess_query("CONFIDENTIALITY") == '"confidentiality"'

    def test_strip_punctuation(self) -> None:
        result = preprocess_query("confidentiality, obligations!")
        assert result == '"confidentiality" OR "obligations"'

    def test_preserve_hyphens(self) -> None:
        result = preprocess_query("data-processing agreement")
        assert result == '"data-processing" OR "agreement"'

    def test_mixed_punctuation_and_hyphens(self) -> None:
        result = preprocess_query("Return of Confidential Information? (Section 5.1)")
        assert (
            result
            == '"return" OR "of" OR "confidential" OR "information" OR "section" OR "5" OR "1"'
        )

    def test_whitespace_collapse(self) -> None:
        result = preprocess_query("  wide   spaces  ")
        assert result == '"wide" OR "spaces"'

    def test_empty_query_returns_empty(self) -> None:
        result = preprocess_query("")
        assert result == ""

    def test_query_with_only_punctuation(self) -> None:
        result = preprocess_query("?!,.;:")
        assert result == ""

    def test_terms_are_quoted_so_metacharacters_are_inert(self) -> None:
        result = preprocess_query('he said "confidential"')
        assert result == '"he" OR "said" OR "confidential"'

    def test_multi_term_query_is_or_joined(self) -> None:
        result = preprocess_query("governing law delaware")
        assert result == '"governing" OR "law" OR "delaware"'

    def test_lowercase_or_is_a_term_not_an_operator(self) -> None:
        result = preprocess_query("confidential or governing")
        assert result == '"confidential" OR "or" OR "governing"'

    def test_uppercase_or_is_preserved_as_an_operator(self) -> None:
        result = preprocess_query("confidential OR governing")
        assert result == '"confidential" OR "governing"'

    def test_uppercase_and_is_preserved_as_an_operator(self) -> None:
        result = preprocess_query("confidential AND governing")
        assert result == '"confidential" AND "governing"'

    def test_uppercase_not_is_preserved_as_an_operator(self) -> None:
        result = preprocess_query("a NOT b NOT c")
        assert result == '"a" NOT "b" NOT "c"'

    def test_operator_without_a_left_term_is_dropped(self) -> None:
        assert preprocess_query("OR confidential") == '"confidential"'
        assert preprocess_query("NOT confidential") == '"confidential"'

    def test_operator_without_a_right_term_is_dropped(self) -> None:
        assert preprocess_query("confidential OR") == '"confidential"'

    def test_operator_only_query_returns_empty(self) -> None:
        assert preprocess_query("AND") == ""
        assert preprocess_query("OR OR") == ""

    def test_repeated_operators_collapse(self) -> None:
        assert preprocess_query("a OR OR b") == '"a" OR "b"'

    def test_implicit_or_applies_around_an_explicit_operator(self) -> None:
        assert preprocess_query("a b AND c") == '"a" OR "b" AND "c"'


class TestNormalizeBm25Scores:
    """Tests for BM25 score normalization."""

    def test_basic_normalization(self) -> None:
        raw = [("chunk-a", -5.0), ("chunk-b", -3.0), ("chunk-c", -1.0)]
        result = normalize_bm25_scores(raw)
        assert result == {"chunk-a": 1, "chunk-b": 2, "chunk-c": 3}

    def test_ties_use_next_rank(self) -> None:
        # FTS5 doesn't typically return ties, but handle gracefully
        raw = [("chunk-a", -5.0), ("chunk-b", -5.0)]
        result = normalize_bm25_scores(raw)
        # Both have same score, order within tie is preserved
        assert set(result.keys()) == {"chunk-a", "chunk-b"}
        assert result["chunk-a"] == 1
        assert result["chunk-b"] == 2

    def test_single_result(self) -> None:
        raw = [("chunk-sole", -10.0)]
        result = normalize_bm25_scores(raw)
        assert result == {"chunk-sole": 1}

    def test_empty_input(self) -> None:
        result = normalize_bm25_scores([])
        assert result == {}

    def test_negative_scores_sorted_correctly(self) -> None:
        # More negative = better score (FTS5 convention)
        raw = [("worst", -1.0), ("best", -10.0), ("mid", -5.0)]
        result = normalize_bm25_scores(raw)
        assert result["best"] == 1
        assert result["mid"] == 2
        assert result["worst"] == 3

    def test_positive_scores(self) -> None:
        # Edge case: all positive scores (score format might vary)
        raw = [("a", -3.0), ("b", -6.0)]
        result = normalize_bm25_scores(raw)
        assert result["b"] == 1  # Most negative = best
        assert result["a"] == 2
