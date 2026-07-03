"""Unit tests for RRF fusion (T013)."""

from __future__ import annotations

import pytest

from openreview_cli.retrieval.rrf import rrf_fuse


class TestRrfFuse:
    """Tests for Reciprocal Rank Fusion."""

    def test_both_methods_overlapping(self) -> None:
        sparse = {"A": 1, "B": 2, "C": 3}
        dense = {"A": 2, "B": 1, "D": 3}
        result = rrf_fuse(sparse, dense)
        # Result should be sorted by score descending
        assert len(result) == 4
        scores = dict(result)
        # A = 1/(60+1) + 1/(60+2) = 1/61 + 1/62
        # B = 1/(60+2) + 1/(60+1) = same as A
        # C = 1/(60+3) + 0 = 1/63
        # D = 0 + 1/(60+3) = 1/63
        assert abs(scores["A"] - (1 / 61 + 1 / 62)) < 1e-10
        assert abs(scores["B"] - (1 / 62 + 1 / 61)) < 1e-10
        assert abs(scores["C"] - 1 / 63) < 1e-10
        assert abs(scores["D"] - 1 / 63) < 1e-10
        # C and D should have the same score
        assert scores["C"] == scores["D"]

    def test_disjoint_results(self) -> None:
        sparse = {"A": 1, "B": 2}
        dense = {"C": 1, "D": 2}
        result = rrf_fuse(sparse, dense)
        assert len(result) == 4
        scores = dict(result)
        # Each gets 1/(60 + rank) from only one set
        assert abs(scores["A"] - 1 / 61) < 1e-10
        assert abs(scores["B"] - 1 / 62) < 1e-10
        assert abs(scores["C"] - 1 / 61) < 1e-10
        assert abs(scores["D"] - 1 / 62) < 1e-10

    def test_empty_sparse(self) -> None:
        sparse: dict[str, int] = {}
        dense = {"A": 1, "B": 2}
        result = rrf_fuse(sparse, dense)
        assert len(result) == 2
        scores = dict(result)
        assert abs(scores["A"] - 1 / 61) < 1e-10
        assert abs(scores["B"] - 1 / 62) < 1e-10

    def test_empty_dense(self) -> None:
        sparse = {"A": 1, "B": 2}
        dense: dict[str, int] = {}
        result = rrf_fuse(sparse, dense)
        assert len(result) == 2
        scores = dict(result)
        assert abs(scores["A"] - 1 / 61) < 1e-10

    def test_both_empty(self) -> None:
        sparse: dict[str, int] = {}
        dense: dict[str, int] = {}
        result = rrf_fuse(sparse, dense)
        assert result == []

    def test_default_k_parameter(self) -> None:
        sparse: dict[str, int] = {"A": 1}
        dense: dict[str, int] = {}
        result = rrf_fuse(sparse, dense)
        # With k=60 (default): score = 1/(60+1)
        assert abs(dict(result)["A"] - 1 / 61) < 1e-10

    def test_custom_k_parameter(self) -> None:
        sparse: dict[str, int] = {"A": 1}
        dense: dict[str, int] = {}
        result = rrf_fuse(sparse, dense, k=10)
        assert abs(dict(result)["A"] - 1 / 11) < 1e-10

    def test_k_zero_raises(self) -> None:
        sparse: dict[str, int] = {"A": 1}
        dense: dict[str, int] = {}
        with pytest.raises(ValueError, match="RRF constant k must be positive"):
            rrf_fuse(sparse, dense, k=0)

    def test_k_negative_raises(self) -> None:
        sparse: dict[str, int] = {"A": 1}
        dense: dict[str, int] = {}
        with pytest.raises(ValueError, match="RRF constant k must be positive"):
            rrf_fuse(sparse, dense, k=-1)

    def test_scores_monotonically_decreasing(self) -> None:
        sparse = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}
        dense = {"A": 3, "C": 1, "E": 2, "F": 4}
        result = rrf_fuse(sparse, dense)
        scores = [s for _, s in result]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], f"Score at {i} < score at {i + 1}"

    def test_single_method_only(self) -> None:
        sparse = {"A": 1, "B": 2, "C": 3}
        dense: dict[str, int] = {}
        result = rrf_fuse(sparse, dense)
        assert len(result) == 3
        # Pure sparse: sorted by rank asc (score desc)
        assert result[0][0] == "A"
        assert result[1][0] == "B"
        assert result[2][0] == "C"
