"""Reciprocal Rank Fusion (RRF) for merging sparse and dense rankings."""

from __future__ import annotations


def rrf_fuse(
    sparse_ranks: dict[str, int],
    dense_ranks: dict[str, int],
    k: int = 60,
) -> list[tuple[str, float]]:
    """Fuse sparse and dense ranked results via Reciprocal Rank Fusion.

    Args:
        sparse_ranks: dict[chunk_id, rank] from BM25 (1 = best).
        dense_ranks: dict[chunk_id, rank] from cosine similarity (1 = best).
        k: RRF constant (default 60).

    Returns:
        List of (chunk_id, rrf_score) sorted by descending score.

    Formula:
        score(c) = 1/(k + rank_sparse(c)) + 1/(k + rank_dense(c))

    A chunk appearing in only one set gets contribution only from that set.
    """
    if k <= 0:
        msg = "RRF constant k must be positive"
        raise ValueError(msg)

    all_chunk_ids = set(sparse_ranks) | set(dense_ranks)
    scores: dict[str, float] = {}

    for cid in all_chunk_ids:
        score = 0.0
        if cid in sparse_ranks:
            score += 1.0 / (k + sparse_ranks[cid])
        if cid in dense_ranks:
            score += 1.0 / (k + dense_ranks[cid])
        scores[cid] = score

    return sorted(scores.items(), key=lambda x: -x[1])
