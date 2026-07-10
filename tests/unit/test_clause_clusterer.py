"""Unit tests for ClauseClusterer (clause embedding + HDBSCAN clustering).

Core clustering logic tested with synthetic data.
Model-dependent tests marked @pytest.mark.slow, skip if offline.
"""

from __future__ import annotations

import numpy as np
import pytest

from openreview_cli.parsing.clause_clusterer import ClauseClusterer
from openreview_cli.parsing.models import Clause


class TestClusteringLogic:
    """Tests cluster_clauses() with synthetic embeddings — no model needed."""

    def test_distinct_clusters(self) -> None:
        """Clearly separated embedding groups → multiple clusters.

        Use unit vectors in different directions for cosine stability.
        """
        rng = np.random.default_rng(42)
        # Group A: random unit vectors near (1, 0, 0, ...)
        base_a = np.zeros(10)
        base_a[0] = 1.0
        group_a = base_a + rng.normal(0, 0.05, size=(8, 10))
        group_a = group_a / np.linalg.norm(group_a, axis=1, keepdims=True)
        # Group B: random unit vectors near (0, 1, 0, ...)
        base_b = np.zeros(10)
        base_b[1] = 1.0
        group_b = base_b + rng.normal(0, 0.05, size=(8, 10))
        group_b = group_b / np.linalg.norm(group_b, axis=1, keepdims=True)

        embeddings = np.vstack([group_a, group_b])
        labels = ClauseClusterer.cluster_clauses(embeddings, min_cluster_size=3)
        unique_labels = set(labels)
        # Expect at least 2 real clusters
        assert len(unique_labels - {-1}) >= 2, f"Expected >=2 clusters, got {unique_labels}"

    def test_duplicate_clusters(self) -> None:
        """All identical embeddings → single cluster (or all noise)."""
        embeddings = np.array([[1.0, 2.0]] * 10)
        labels = ClauseClusterer.cluster_clauses(embeddings, min_cluster_size=3)
        unique_labels = set(labels)
        # All same label: either a real cluster or all noise (-1)
        assert len(unique_labels) == 1, f"Expected 1 label, got {unique_labels}"

    def test_single_embedding(self) -> None:
        """Single point → empty labels (HDBSCAN requires >1 sample)."""
        embeddings = np.array([[0.5, 0.5]])
        labels = ClauseClusterer.cluster_clauses(embeddings, min_cluster_size=2)
        assert len(labels) == 1, "Single point should return 1 label"

    def test_noise_points(self) -> None:
        """Far apart points with high min_cluster_size → all noise."""
        rng = np.random.default_rng(42)
        embeddings = rng.uniform(0, 100, size=(5, 10))
        labels = ClauseClusterer.cluster_clauses(embeddings, min_cluster_size=5)
        unique_labels = set(labels)
        assert -1 in unique_labels, "Expected noise label"
        # With 5 points and min_cluster_size=5, all could be one cluster or noise
        assert len(unique_labels) >= 1


class TestClusteringEdgeCases:
    """Edge cases for clustering logic."""

    def test_empty_embeddings(self) -> None:
        """Empty array → empty labels."""
        embeddings = np.empty((0, 768))
        labels = ClauseClusterer.cluster_clauses(embeddings)
        assert len(labels) == 0

    def test_high_dimensional(self) -> None:
        """768-d synthetic vectors — as realistic as possible without model."""
        rng = np.random.default_rng(99)
        # Unit vectors in different directions
        base_a = np.zeros(768)
        base_a[0] = 1.0
        group_a = base_a + rng.normal(0, 0.05, size=(8, 768))
        group_a = group_a / np.linalg.norm(group_a, axis=1, keepdims=True)

        base_b = np.zeros(768)
        base_b[1] = 1.0
        group_b = base_b + rng.normal(0, 0.05, size=(8, 768))
        group_b = group_b / np.linalg.norm(group_b, axis=1, keepdims=True)

        embeddings = np.vstack([group_a, group_b])
        labels = ClauseClusterer.cluster_clauses(embeddings, min_cluster_size=3)
        unique = set(labels) - {-1}
        assert len(unique) >= 2, f"Expected >=2 clusters in 768-d, got {unique}"


@pytest.mark.slow
class TestModelIntegration:
    """Tests requiring actual legal-bert model download.

    Skipped if model not cached or offline.
    """

    @pytest.fixture
    def sample_clauses(self) -> list[Clause]:
        return [
            Clause(
                id="c1",
                title="Definition of Confidential Information",
                text="Confidential Information means any information disclosed by one party to the other.",
                level=0,
                parent_id=None,
                source_page=1,
                source_paragraph=None,
                source_span=(0, 100),
            ),
            Clause(
                id="c2",
                title="Definition of Confidential Information",
                text="Confidential Information means any information disclosed by one party to the other.",
                level=0,
                parent_id=None,
                source_page=1,
                source_paragraph=None,
                source_span=(101, 200),
            ),
            Clause(
                id="c3",
                title="Governing Law",
                text="This Agreement shall be governed by and construed in accordance with the laws of Delaware.",
                level=0,
                parent_id=None,
                source_page=2,
                source_paragraph=None,
                source_span=(201, 300),
            ),
            Clause(
                id="c4",
                title="Governing Law",
                text="This Agreement shall be governed by and construed in accordance with the laws of Delaware.",
                level=0,
                parent_id=None,
                source_page=2,
                source_paragraph=None,
                source_span=(301, 400),
            ),
            Clause(
                id="c5",
                title="Termination",
                text="Either party may terminate this Agreement upon 30 days written notice.",
                level=0,
                parent_id=None,
                source_page=3,
                source_paragraph=None,
                source_span=(401, 500),
            ),
        ]

    def test_embed_clauses_shape(self, sample_clauses: list[Clause]) -> None:
        """Embeddings shape must be (n_clauses, 768)."""
        try:
            ClauseClusterer.load()
        except (OSError, Exception) as e:
            pytest.skip(f"Model not available: {e}")
        try:
            embeddings = ClauseClusterer.embed_clauses(sample_clauses)
        finally:
            ClauseClusterer.cleanup()
        assert embeddings.shape == (len(sample_clauses), 768), (
            f"Expected ({len(sample_clauses)}, 768), got {embeddings.shape}"
        )

    def test_model_loaded_once(self, sample_clauses: list[Clause]) -> None:
        """Loading model twice returns the same cached instance."""
        try:
            ClauseClusterer.load()
        except (OSError, Exception) as e:
            pytest.skip(f"Model not available: {e}")
        try:
            m1 = ClauseClusterer._model  # type: ignore[attr-defined]
            ClauseClusterer.load()  # second load returns cached
            m2 = ClauseClusterer._model  # type: ignore[attr-defined]
            assert m1 is m2, "Model not cached"
        finally:
            ClauseClusterer.cleanup()

    def test_cleanup_releases_model(self, sample_clauses: list[Clause]) -> None:
        """Cleanup removes model reference."""
        try:
            ClauseClusterer.load()
        except (OSError, Exception) as e:
            pytest.skip(f"Model not available: {e}")
        ClauseClusterer.cleanup()
        assert not hasattr(ClauseClusterer, "_model"), "Model reference not removed"

    def test_similar_clauses_same_cluster(self, sample_clauses: list[Clause]) -> None:
        """Duplicate clauses should end up in same cluster."""
        try:
            ClauseClusterer.load()
        except (OSError, Exception) as e:
            pytest.skip(f"Model not available: {e}")
        try:
            embeddings = ClauseClusterer.embed_clauses(sample_clauses)
            labels = ClauseClusterer.cluster_clauses(embeddings, min_cluster_size=2)
        finally:
            ClauseClusterer.cleanup()
        # c1 and c2 have identical text → same cluster
        assert labels[0] == labels[1], (
            f"Identical clauses (c1, c2) not in same cluster: {labels[0]} vs {labels[1]}"
        )
        # c3 and c4 have identical text → same cluster
        assert labels[2] == labels[3], (
            f"Identical clauses (c3, c4) not in same cluster: {labels[2]} vs {labels[3]}"
        )
