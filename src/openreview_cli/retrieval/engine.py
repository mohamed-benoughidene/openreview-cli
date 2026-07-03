"""RetrievalEngine — orchestrates BM25 + dense + RRF hybrid retrieval."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openreview_cli.retrieval.bm25 import normalize_bm25_scores, search_bm25
from openreview_cli.retrieval.dense import (
    compute_embedding,
    compute_l2_norm,
    cosine_similarity,
    deserialize_embedding,
)
from openreview_cli.retrieval.errors import (
    IndexCorruptError,
    IndexNotFoundError,
)
from openreview_cli.retrieval.rrf import rrf_fuse

if TYPE_CHECKING:
    from openreview_cli.gateway.router import Gateway
    from openreview_cli.retrieval.models import RetrievalQuery, RetrievalResult

logger = logging.getLogger(__name__)


class RetrievalEngine:
    """Orchestrates hybrid retrieval across BM25 + Dense + RRF fusion."""

    def __init__(
        self,
        db_path: str | Path,
        gateway: Gateway | None = None,
    ) -> None:
        """Initialize the retrieval engine.

        Args:
            db_path: Path to the SQLite index database.
            gateway: AI Gateway instance for embedding calls.
        """
        self.db_path = Path(db_path)
        self.gateway = gateway
        self.notices: list[str] = []

    def get_index_meta(self) -> dict[str, Any] | None:
        """Return metadata about the current index."""
        from openreview_cli.retrieval.storage import RetrievalStorage

        with RetrievalStorage(self.db_path) as storage:
            return storage.get_index_meta()

    def _search_dense_candidates(
        self,
        storage: Any,
        gateway: Gateway,
        query_text: str,
    ) -> list[tuple[str, float]]:
        """Compute query embedding and score all stored vectors via cosine similarity.

        Returns list of (chunk_id, similarity) sorted descending.
        """
        query_vec, dim = compute_embedding(query_text, gateway)
        query_norm = compute_l2_norm(query_vec)

        scored: list[tuple[str, float]] = []
        for chunk_id, embedding_blob, chunk_norm in storage.load_embeddings():
            chunk_vec = deserialize_embedding(embedding_blob, dim)
            sim = cosine_similarity(query_vec, chunk_vec, query_norm, chunk_norm)
            scored.append((chunk_id, sim))

        scored.sort(key=lambda x: -x[1])
        return scored

    def retrieve(
        self,
        query: RetrievalQuery,
    ) -> list[RetrievalResult]:
        """Execute a retrieval query.

        Args:
            query: The retrieval query parameters.

        Returns:
            Ranked list of RetrievalResult (length = top_k).

        Raises:
            IndexNotFoundError: If the index database doesn't exist or status is wrong.
            IndexCorruptError: If the index database is corrupted.
            ModelUnavailableError: If embedding model is not available for dense/hybrid.
        """
        from openreview_cli.retrieval.storage import RetrievalStorage

        # Reset notices for this invocation
        self.notices = []

        if not self.db_path.exists():
            raise IndexNotFoundError("Document not indexed. Run `openreview ingest <file>` first.")

        with RetrievalStorage(self.db_path) as storage:
            meta = storage.get_index_meta()
            if meta is None:
                raise IndexNotFoundError(
                    "Document not indexed. Run `openreview ingest <file>` first."
                )

            status = meta.get("index_status", "")
            if status == "corrupt":
                raise IndexCorruptError(
                    "Index database is corrupt. Re-run `openreview ingest <file>` to rebuild."
                )
            if status == "ingesting":
                raise IndexNotFoundError(
                    "Index was being built but the process was interrupted. "
                    "Run `openreview ingest <file>` to rebuild."
                )

            method = query.method

            # ── Sparse path ──
            if method == "sparse":
                return self._retrieve_sparse(storage, query)

            # ── Dense path ──
            if method == "dense":
                return self._retrieve_dense(storage, query)

            # ── Hybrid path ──
            if method == "hybrid":
                return self._retrieve_hybrid(storage, query)

            msg = f"Unknown retrieval method: {method}"
            raise ValueError(msg)

    def _retrieve_sparse(
        self,
        storage: Any,
        query: RetrievalQuery,
    ) -> list[RetrievalResult]:
        """Run BM25-only retrieval."""
        from openreview_cli.retrieval.models import RetrievalResult

        raw_results = search_bm25(storage, query.query_text, query.top_k)
        ranks = normalize_bm25_scores(raw_results)

        results: list[RetrievalResult] = []
        for cid, rank in sorted(ranks.items(), key=lambda x: x[1]):
            chunk = storage.load_chunk(cid)
            if chunk is None:
                continue
            heading_chain: list[str] = json.loads(chunk.get("heading_chain", "[]"))
            results.append(
                RetrievalResult(
                    chunk_id=cid,
                    text=chunk["text"],
                    clause_heading=chunk["clause_heading"],
                    clause_level=chunk["clause_level"],
                    hierarchy_chain=heading_chain,
                    parent_chunk_id=chunk.get("parent_chunk_id"),
                    score=1.0 / rank if rank > 0 else 0.0,  # Simple score: inverse rank
                    method="sparse",
                    rank_sparse=rank,
                    rank_dense=None,
                    rrf_score=None,
                    rerank_score=None,
                    char_start=chunk.get("char_start", 0),
                    char_end=chunk.get("char_end", 0),
                )
            )

        return results[: query.top_k]

    def _retrieve_dense(
        self,
        storage: Any,
        query: RetrievalQuery,
    ) -> list[RetrievalResult]:
        """Run dense embedding-only retrieval."""
        from openreview_cli.retrieval.models import RetrievalResult

        if self.gateway is None:
            # Fallback to sparse if no gateway available
            logger.warning("No gateway configured; falling back to BM25-only.")
            self.notices.append("Dense retrieval unavailable, using BM25 only")
            return self._retrieve_sparse(storage, query)

        try:
            scored = self._search_dense_candidates(storage, self.gateway, query.query_text)
        except Exception as exc:
            logger.warning("Embedding unavailable (%s); falling back to BM25-only.", exc)
            self.notices.append("Dense retrieval unavailable, using BM25 only")
            return self._retrieve_sparse(storage, query)

        dense_ranks: dict[str, int] = {
            cid: rank for rank, (cid, _) in enumerate(scored[: query.top_k], start=1)
        }

        results: list[RetrievalResult] = []
        for cid, sim in scored[: query.top_k]:
            chunk = storage.load_chunk(cid)
            if chunk is None:
                continue
            heading_chain = json.loads(chunk.get("heading_chain", "[]"))
            rank = dense_ranks.get(cid)
            results.append(
                RetrievalResult(
                    chunk_id=cid,
                    text=chunk["text"],
                    clause_heading=chunk["clause_heading"],
                    clause_level=chunk["clause_level"],
                    hierarchy_chain=heading_chain,
                    parent_chunk_id=chunk.get("parent_chunk_id"),
                    score=sim,
                    method="dense",
                    rank_sparse=None,
                    rank_dense=rank,
                    rrf_score=None,
                    rerank_score=None,
                    char_start=chunk.get("char_start", 0),
                    char_end=chunk.get("char_end", 0),
                )
            )

        return results

    def _retrieve_hybrid(
        self,
        storage: Any,
        query: RetrievalQuery,
    ) -> list[RetrievalResult]:
        """Run BM25 + dense hybrid retrieval with RRF fusion."""
        from openreview_cli.retrieval.models import RetrievalResult

        # Step 1: BM25 search
        bm25_depth = max(query.top_k * 3, 30)  # Get more candidates for fusion
        raw_sparse = search_bm25(storage, query.query_text, bm25_depth)
        sparse_ranks = normalize_bm25_scores(raw_sparse)
        # Keep only top_k from BM25 for the ranking dict
        sparse_ranks = dict(list(sparse_ranks.items())[:bm25_depth])

        # Step 2: Dense search (if gateway available)
        dense_ranks: dict[str, int] = {}
        if self.gateway is not None:
            try:
                dense_depth = max(query.top_k * 3, 30)
                scored = self._search_dense_candidates(storage, self.gateway, query.query_text)
                dense_ranks = {
                    cid: rank for rank, (cid, _) in enumerate(scored[:dense_depth], start=1)
                }
            except Exception as exc:
                logger.warning("Dense retrieval unavailable (%s); using BM25 only.", exc)
                self.notices.append("Dense retrieval unavailable, using BM25 only")

        # Step 3: RRF fusion
        fused = rrf_fuse(sparse_ranks, dense_ranks)

        # Step 4: Build results for top_k
        results: list[RetrievalResult] = []
        for _rank, (cid, rrf_score) in enumerate(fused[: query.top_k], start=1):
            chunk = storage.load_chunk(cid)
            if chunk is None:
                continue
            heading_chain = json.loads(chunk.get("heading_chain", "[]"))
            results.append(
                RetrievalResult(
                    chunk_id=cid,
                    text=chunk["text"],
                    clause_heading=chunk["clause_heading"],
                    clause_level=chunk["clause_level"],
                    hierarchy_chain=heading_chain,
                    parent_chunk_id=chunk.get("parent_chunk_id"),
                    score=rrf_score,
                    method="hybrid",
                    rank_sparse=sparse_ranks.get(cid),
                    rank_dense=dense_ranks.get(cid),
                    rrf_score=rrf_score,
                    rerank_score=None,
                    char_start=chunk.get("char_start", 0),
                    char_end=chunk.get("char_end", 0),
                )
            )

        return results
