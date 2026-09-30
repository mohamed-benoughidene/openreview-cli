"""RetrievalEngine — orchestrates keyword (BM25) retrieval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openreview_cli.retrieval.bm25 import normalize_bm25_scores, search_bm25
from openreview_cli.retrieval.errors import (
    IndexCorruptError,
    IndexNotFoundError,
)

if TYPE_CHECKING:
    from openreview_cli.gateway.router import Gateway
    from openreview_cli.retrieval.models import RetrievalQuery, RetrievalResult


def _result_limit(query: RetrievalQuery) -> int:
    """Number of candidates to materialize (the rerank pool when reranking)."""
    return query.rerank_depth if query.rerank else query.top_k


class RetrievalEngine:
    """Orchestrates keyword retrieval over the BM25 index."""

    def __init__(
        self,
        db_path: str | Path,
        gateway: Gateway | None = None,
    ) -> None:
        """Initialize the retrieval engine.

        Args:
            db_path: Path to the SQLite index database.
            gateway: Retained for callers that inject one (``RetrieveStage``); the
                keyword path never calls the gateway.
        """
        self.db_path = Path(db_path)
        self.gateway = gateway
        self.notices: list[str] = []

    def get_index_meta(self) -> dict[str, Any] | None:
        """Return metadata about the current index."""
        from openreview_cli.retrieval.storage import RetrievalStorage

        with RetrievalStorage(self.db_path) as storage:
            return storage.get_index_meta()

    def retrieve(
        self,
        query: RetrievalQuery,
    ) -> list[RetrievalResult]:
        """Execute a retrieval query.

        Args:
            query: The retrieval query parameters.

        Returns:
            Ranked list of RetrievalResult (length = top_k, or rerank_depth when the
            query reranks).

        Raises:
            IndexNotFoundError: If the index database doesn't exist or status is wrong.
            IndexCorruptError: If the index database is corrupted.
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

            return self._retrieve_sparse(storage, query)

    def _retrieve_sparse(
        self,
        storage: Any,
        query: RetrievalQuery,
    ) -> list[RetrievalResult]:
        """Run BM25-only retrieval."""
        from openreview_cli.retrieval.models import RetrievalResult

        limit = _result_limit(query)
        raw_results = search_bm25(storage, query.query_text, limit)
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
                    rerank_score=None,
                    char_start=chunk.get("char_start", 0),
                    char_end=chunk.get("char_end", 0),
                )
            )

        return results[:limit]
