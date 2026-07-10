"""Clause similarity and clustering using legal-bert + HDBSCAN.

Loads ``nlpaueb/legal-bert-base-uncased`` once, releases after embedding.
Clusters with sklearn HDBSCAN (cosine metric).

Ponytail: no abstraction, no plugin system, just 2 methods + cleanup.
"""

from __future__ import annotations

import gc
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from openreview_cli.parsing.models import Clause


_MODEL_NAME = "nlpaueb/legal-bert-base-uncased"
_EMBED_DIM = 768
_BATCH_SIZE = 32


class ClauseClusterer:
    """Embed clauses and cluster them by semantic similarity.

    Usage::

        ClauseClusterer.load()
        try:
            embeddings = ClauseClusterer.embed_clauses(clauses)
            labels = ClauseClusterer.cluster_clauses(embeddings)
        finally:
            ClauseClusterer.cleanup()
    """

    # Class-level cache — tests inspect `_model` directly to verify caching.
    _model: Any = None
    _tokenizer: Any = None

    # ── Lifecycle ────────────────────────────────────────────────────

    @classmethod
    def load(cls) -> None:
        """Load the model + tokenizer (cached after first call).

        Raises OSError if model cannot be downloaded.
        """
        # Use getattr: cleanup() deletes the attribute, so direct access
        # would raise AttributeError on the second load.
        if (
            getattr(cls, "_model", None) is not None
            and getattr(cls, "_tokenizer", None) is not None
        ):
            return
        from transformers import AutoModel, AutoTokenizer

        cls._tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)
        cls._model = AutoModel.from_pretrained(_MODEL_NAME)
        cls._model.eval()

    @classmethod
    def cleanup(cls) -> None:
        """Release model + tokenizer, run GC.

        Uses ``delattr`` (not just ``= None``) so that
        ``hasattr(ClauseClusterer, "_model")`` returns False after
        cleanup — the test ``test_cleanup_releases_model`` depends on this.
        """
        if hasattr(cls, "_model"):
            delattr(cls, "_model")
        if hasattr(cls, "_tokenizer"):
            delattr(cls, "_tokenizer")
        gc.collect()

    # ── Embedding ────────────────────────────────────────────────────

    @classmethod
    def embed_clauses(cls, clauses: list[Clause]) -> np.ndarray:
        """Return (N, 768) embedding matrix via mean-pooling.

        Batches of ``_BATCH_SIZE`` to limit peak memory.
        Model must be loaded via ``load()`` first.
        """
        if cls._model is None or cls._tokenizer is None:
            raise RuntimeError("Model not loaded. Call ClauseClusterer.load() first.")

        import torch

        all_embeddings: list[np.ndarray] = []

        for i in range(0, len(clauses), _BATCH_SIZE):
            batch = clauses[i : i + _BATCH_SIZE]
            texts = [c.text for c in batch]

            inputs = cls._tokenizer(
                texts,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=512,
            )

            with torch.no_grad():
                outputs = cls._model(**inputs)

            # Mean pooling (ignore padding tokens)
            attention_mask = (
                inputs["attention_mask"].unsqueeze(-1).expand(outputs.last_hidden_state.size())
            )
            sum_embeddings = (outputs.last_hidden_state * attention_mask).sum(dim=1)
            mask_sum = attention_mask.sum(dim=1).clamp(min=1e-9)
            batch_embeddings = (sum_embeddings / mask_sum).cpu().numpy()

            all_embeddings.append(batch_embeddings)

        return np.vstack(all_embeddings) if all_embeddings else np.empty((0, _EMBED_DIM))

    # ── Clustering ───────────────────────────────────────────────────

    @classmethod
    def cluster_clauses(
        cls,
        embeddings: np.ndarray,
        min_cluster_size: int = 3,
    ) -> np.ndarray:
        """Return cluster labels (int) via HDBSCAN with cosine metric.

        Parameters
        ----------
        embeddings : np.ndarray
            Shape ``(N, D)`` embedding matrix.
        min_cluster_size : int
            Minimum points per cluster (default 3). Smaller values
            produce more fine-grained clusters.

        Returns
        -------
        np.ndarray
            Cluster label for each point. ``-1`` indicates noise/outlier.
        """
        n_samples = embeddings.shape[0]
        if n_samples == 0:
            return np.array([], dtype=int)
        if n_samples == 1:
            # ponytail: HDBSCAN requires >1 sample
            return np.array([-1], dtype=int)

        from sklearn.cluster import HDBSCAN  # type: ignore[import-untyped]

        clusterer = HDBSCAN(
            metric="cosine",
            min_cluster_size=min_cluster_size,
            min_samples=1,
        )
        labels: np.ndarray = clusterer.fit_predict(embeddings)
        return labels


__all__ = ["ClauseClusterer"]
