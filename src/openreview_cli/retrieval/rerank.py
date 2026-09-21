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

DEFAULT_RERANK_MODEL = "qwen3-reranker-0.6b"


class Reranker:
    """Cross-encoder reranker wrapper via AI Gateway.

    The reranker is DISABLED by default (reported to degrade legal text; not yet measured).
    Enable it with the --rerank flag or ``retrieval.rerank_enabled``.

    Attributes:
        gateway: AI Gateway instance for cross-encoder calls.
        model_id: Model identifier for the cross-encoder.
    """

    def __init__(
        self,
        gateway: Any | None,
        model_id: str = DEFAULT_RERANK_MODEL,
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
                score_map[int(item["index"])] = float(item["relevance_score"])

        # Assign rerank scores and method
        for i, r in enumerate(candidates):
            r.rerank_score = score_map.get(i, 0.0)
            r.method = f"{r.method}+rerank"

        # Sort by reranker score descending, then return top_k
        reranked = sorted(candidates, key=lambda x: -(x.rerank_score or 0.0))
        return reranked[:top_k]
