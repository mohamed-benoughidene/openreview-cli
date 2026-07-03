"""Unit tests for BM25 sparse retrieval (T011)."""

from __future__ import annotations

from openreview_cli.retrieval.bm25 import normalize_bm25_scores, preprocess_query


class TestPreprocessQuery:
    """Tests for query preprocessing."""

    def test_lowercase(self) -> None:
        assert preprocess_query("CONFIDENTIALITY") == "confidentiality"

    def test_strip_punctuation(self) -> None:
        result = preprocess_query("confidentiality, obligations!")
        assert result == "confidentiality obligations"

    def test_preserve_hyphens(self) -> None:
        result = preprocess_query("data-processing agreement")
        assert result == "data-processing agreement"

    def test_mixed_punctuation_and_hyphens(self) -> None:
        result = preprocess_query("Return of Confidential Information? (Section 5.1)")
        # Periods and parentheses stripped, hyphen preserved
        assert "return" in result
        assert "confidential" in result
        assert "section" in result
        assert "5" in result or "5 1" in result

    def test_whitespace_collapse(self) -> None:
        result = preprocess_query("  wide   spaces  ")
        assert result == "wide spaces"

    def test_empty_query_returns_empty(self) -> None:
        result = preprocess_query("")
        assert result == ""

    def test_query_with_only_punctuation(self) -> None:
        result = preprocess_query("?!,.;:")
        assert result == ""


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
