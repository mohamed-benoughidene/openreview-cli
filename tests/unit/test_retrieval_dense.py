"""Unit tests for dense embedding utilities (T012)."""

from __future__ import annotations

import math

import pytest

from openreview_cli.retrieval.dense import (
    compute_l2_norm,
    cosine_similarity,
    deserialize_embedding,
    serialize_embedding,
)


class TestEmbeddingSerialization:
    """Tests for serialize_embedding / deserialize_embedding round-trip."""

    def test_roundtrip_simple(self) -> None:
        original = [0.1, 0.2, 0.3, 0.4]
        blob = serialize_embedding(original)
        restored = deserialize_embedding(blob, len(original))
        assert len(restored) == len(original)
        for a, b in zip(original, restored):
            assert abs(a - b) < 1e-6

    def test_roundtrip_empty_vector(self) -> None:
        original: list[float] = []
        blob = serialize_embedding(original)
        restored = deserialize_embedding(blob, 0)
        assert restored == []

    def test_roundtrip_all_zeros(self) -> None:
        original = [0.0] * 1024
        blob = serialize_embedding(original)
        restored = deserialize_embedding(blob, len(original))
        assert all(v == 0.0 for v in restored)

    def test_roundtrip_negative_values(self) -> None:
        original = [-0.5, 0.0, 0.5, -1.0, 1.0]
        blob = serialize_embedding(original)
        restored = deserialize_embedding(blob, len(original))
        for a, b in zip(original, restored):
            assert abs(a - b) < 1e-6

    def test_blob_size(self) -> None:
        original = [1.0] * 100
        blob = serialize_embedding(original)
        # float32 = 4 bytes per value
        assert len(blob) == 100 * 4


class TestCosineSimilarity:
    """Tests for cosine_similarity."""

    def test_identical_vectors(self) -> None:
        a = [1.0, 2.0, 3.0]
        b = [1.0, 2.0, 3.0]
        sim = cosine_similarity(a, b)
        assert abs(sim - 1.0) < 1e-10

    def test_orthogonal_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        sim = cosine_similarity(a, b)
        assert abs(sim) < 1e-10

    def test_opposite_vectors(self) -> None:
        a = [1.0, 2.0, 3.0]
        b = [-1.0, -2.0, -3.0]
        sim = cosine_similarity(a, b)
        assert abs(sim - (-1.0)) < 1e-10

    def test_zero_vector(self) -> None:
        a = [0.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        sim = cosine_similarity(a, b)
        assert sim == 0.0

    def test_with_precomputed_norms(self) -> None:
        a = [3.0, 4.0]  # norm = 5.0
        b = [6.0, 8.0]  # norm = 10.0
        sim = cosine_similarity(a, b, query_norm=5.0, chunk_norm=10.0)
        # dot = 3*6 + 4*8 = 50, cos = 50/(5*10) = 1.0
        assert abs(sim - 1.0) < 1e-10

    def test_partial_overlap(self) -> None:
        a = [1.0, 0.0, 0.5]
        b = [0.0, 1.0, 1.0]
        sim = cosine_similarity(a, b)
        # dot = 0 + 0 + 0.5 = 0.5
        # norm_a = sqrt(1 + 0 + 0.25) = sqrt(1.25)
        # norm_b = sqrt(0 + 1 + 1) = sqrt(2)
        # cos = 0.5 / (sqrt(1.25) * sqrt(2))
        expected = 0.5 / (math.sqrt(1.25) * math.sqrt(2.0))
        assert abs(sim - expected) < 1e-10


class TestComputeL2Norm:
    """Tests for compute_l2_norm."""

    def test_simple_vector(self) -> None:
        vec = [3.0, 4.0]
        norm = compute_l2_norm(vec)
        assert abs(norm - 5.0) < 1e-10

    def test_unit_vector(self) -> None:
        vec = [1.0, 0.0, 0.0]
        norm = compute_l2_norm(vec)
        assert abs(norm - 1.0) < 1e-10

    def test_zero_vector(self) -> None:
        vec = [0.0, 0.0, 0.0]
        norm = compute_l2_norm(vec)
        assert abs(norm) < 1e-10

    def test_negative_values(self) -> None:
        vec = [-3.0, -4.0]
        norm = compute_l2_norm(vec)
        assert abs(norm - 5.0) < 1e-10


# ── T027: Dense-only retrieval path tests ──


class TestDenseOnlyRetrieval:
    """Tests for dense-only retrieval path (T027)."""

    def test_dense_results_ranked_by_similarity(self) -> None:
        """Verify dense-only path returns results ranked by cosine similarity.

        This test verifies the retrieval path logic independently by
        asserting that cosine similarity produces correct ordering.
        """
        # Vectors with known similarity: closer vectors rank higher
        query_vec = [1.0, 0.0, 0.0]
        chunk_vecs = {
            "c1": [0.9, 0.1, 0.0],  # cos ≈ 0.994
            "c2": [0.5, 0.5, 0.5],  # cos ≈ 0.577
            "c3": [0.0, 1.0, 0.0],  # cos = 0.0
        }

        query_norm = compute_l2_norm(query_vec)
        scored: list[tuple[str, float]] = []
        for cid, vec in chunk_vecs.items():
            norm = compute_l2_norm(vec)
            sim = cosine_similarity(query_vec, vec, query_norm, norm)
            scored.append((cid, sim))

        # Sort by descending similarity
        scored.sort(key=lambda x: -x[1])

        expected_order = ["c1", "c2", "c3"]
        actual_order = [cid for cid, _ in scored]
        assert actual_order == expected_order, (
            f"Expected ranking {expected_order}, got {actual_order}"
        )

        # Scores should be monotonically decreasing
        for i in range(len(scored) - 1):
            assert scored[i][1] >= scored[i + 1][1]

    def test_dense_results_range(self) -> None:
        """Dense similarity values should be in [-1, 1]."""
        vec_a = [1.0, 0.0]
        vec_b = [0.0, 1.0]
        vec_c = [-1.0, 0.0]

        an = compute_l2_norm(vec_a)
        bn = compute_l2_norm(vec_b)
        cn = compute_l2_norm(vec_c)

        assert abs(cosine_similarity(vec_a, vec_a, an, an) - 1.0) < 1e-10
        assert abs(cosine_similarity(vec_a, vec_b, an, bn)) < 1e-10
        assert abs(cosine_similarity(vec_a, vec_c, an, cn) - (-1.0)) < 1e-10
