"""Cross-encoder reranker wrapper via AI Gateway (T030)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openreview_cli.retrieval.models import RetrievalResult

from openreview_cli.gateway.models import CapabilityRequirement

logger = logging.getLogger(__name__)

# AI Gateway slot that serves cross-encoder reranking. The gateway resolves the
# actual provider/model from this slot's config (see Gateway.rerank).
RERANK_SLOT = "reranking"


class Reranker:
    """Cross-encoder reranker wrapper via AI Gateway.

    The reranker is DISABLED by default per P-9 warning (degrades legal text).
    Users must opt in via --rerank flag.

    Attributes:
        gateway: AI Gateway instance for cross-encoder calls.
        model_id: Model identifier for the cross-encoder.
    """

    def __init__(
        self,
        gateway: Any | None,
        model_id: str = "qwen3-reranker-0.6b",
    ) -> None:
        """Initialize the reranker.

        Args:
            gateway: AI Gateway instance. If None, rerank() returns candidates unchanged.
            model_id: Cross-encoder model identifier used for validation bookkeeping
                (default: a bundled reranker model id).
        """
        self.gateway = gateway
        self.model_id = model_id

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        """Rerank candidate chunks using cross-encoder.

        Args:
            query: The original query text.
            candidates: List of RetrievalResult objects to rerank.
            top_k: Number of results to return after reranking.

        Returns:
            Reranked list of RetrievalResult objects with rerank_score populated.
            If gateway is None, returns candidates sorted by original score.
        """
        if not candidates:
            return []

        if self.gateway is None:
            logger.warning("No gateway configured; skipping reranker.")
            for r in candidates:
                r.rerank_score = None
            return candidates[:top_k]

        try:
            # Prepare query-chunk pairs for the cross-encoder
            texts = [c.text for c in candidates]
            scores = self.gateway.rerank(
                RERANK_SLOT,
                query,
                texts,
                top_n=top_k,
                requirement=CapabilityRequirement(capability="rerank"),
            )
        except Exception as exc:
            logger.warning("Reranker unavailable (%s); returning original order.", exc)
            for r in candidates:
                r.rerank_score = None
            return candidates[:top_k]

        # Build a mapping from original index to reranker score
        score_map: dict[int, float] = {}
        for item in scores:
            if isinstance(item, dict):
                idx = item.get("index", 0)
                score_map[idx] = item.get("score", 0.0)

        # Assign rerank scores and method
        for i, r in enumerate(candidates):
            r.rerank_score = score_map.get(i, 0.0)
            r.method = "hybrid+rerank"

        # Sort by reranker score descending, then return top_k
        reranked = sorted(candidates, key=lambda x: -(x.rerank_score or 0.0))
        return reranked[:top_k]

    def validate(
        self,
        storage: Any,
    ) -> dict[str, float | bool | int]:
        """Run the reranker validation benchmark.

        Compares Precision@5 with and without reranker on the document.
        Updates the rerank_validation table.
        Tracks consecutive degradation runs (3 strikes → degraded flag).

        Args:
            storage: RetrievalStorage instance for the document.

        Returns:
            dict with keys: with_reranker, without_reranker, degradation_pp,
            consecutive_degradations, degraded
        """
        from openreview_cli.retrieval.bm25 import normalize_bm25_scores, search_bm25
        from openreview_cli.retrieval.models import RetrievalQuery

        # Use BM25 results as baseline (no-reranker)
        meta = storage.get_index_meta()
        if meta is None:
            return {
                "with_reranker": 0.0,
                "without_reranker": 0.0,
                "degradation_pp": 0.0,
                "consecutive_degradations": 0,
                "degraded": False,
            }

        doc_id = meta.get("document_id", "unknown")
        query = RetrievalQuery(
            query_text="confidentiality indemnification liability",
            method="sparse",
            top_k=5,
        )

        # Precision without reranker: use BM25 top-5
        raw = search_bm25(storage, query.query_text, 5)
        ranks = normalize_bm25_scores(raw)
        without_precision = self._compute_precision(storage, list(ranks.keys())[:5], doc_id)

        # Precision with reranker: use reranker on BM25 top-10 candidates
        raw_10 = search_bm25(storage, query.query_text, 10)
        ranks_10 = normalize_bm25_scores(raw_10)
        top_10_ids = list(ranks_10.keys())[:10]

        # Build candidate results for reranker
        import json

        from openreview_cli.retrieval.models import RetrievalResult

        candidates: list[RetrievalResult] = []
        for cid in top_10_ids:
            chunk = storage.load_chunk(cid)
            if chunk is not None:
                heading_chain = json.loads(chunk.get("heading_chain", "[]"))
                candidates.append(
                    RetrievalResult(
                        chunk_id=cid,
                        text=chunk["text"],
                        clause_heading=chunk.get("clause_heading", ""),
                        clause_level=chunk.get("clause_level", 0),
                        hierarchy_chain=heading_chain,
                        parent_chunk_id=chunk.get("parent_chunk_id"),
                        score=0.0,
                        method="hybrid",
                    )
                )

        reranked = self.rerank(query.query_text, candidates, 5)
        reranked_ids = [r.chunk_id for r in reranked]
        with_precision = self._compute_precision(storage, reranked_ids, doc_id)

        degradation_pp = round((with_precision - without_precision) * 100, 2)

        # Write to rerank_validation table; get consecutive degradation count
        consecutive = 0
        try:
            consecutive = storage.insert_rerank_validation(
                model_id=self.model_id,
                document_type="legal-nda",
                precision_with=with_precision,
                precision_without=without_precision,
                degradation_pp=degradation_pp,
            )
        except Exception as exc:
            logger.warning("Failed to write rerank validation: %s", exc)

        degraded = consecutive >= 3
        if degraded:
            logger.warning(
                "Reranker degraded for %d consecutive runs — marked degraded. "
                "The retrieve path warns about it; --force-rerank overrides.",
                consecutive,
            )

        return {
            "with_reranker": with_precision,
            "without_reranker": without_precision,
            "degradation_pp": degradation_pp,
            "consecutive_degradations": consecutive,
            "degraded": degraded,
        }

    def _compute_precision(
        self,
        storage: Any,
        chunk_ids: list[str],
        doc_id: str,
    ) -> float:
        """Compute Precision@K using ground-truth relevant chunks.

        Uses heading-based heuristic: chunks with headings containing
        'confidential', 'indemnif', or 'liability' are considered relevant.
        """
        if not chunk_ids:
            return 0.0

        relevant_terms = {"confidential", "indemnif", "liability"}
        relevant_count = 0

        for cid in chunk_ids:
            chunk = storage.load_chunk(cid)
            if chunk is None:
                continue
            heading = (chunk.get("clause_heading", "") or "").lower()
            text = (chunk.get("text", "") or "").lower()
            if any(term in heading or term in text for term in relevant_terms):
                relevant_count += 1

        return relevant_count / len(chunk_ids)
