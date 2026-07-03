from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Method = Literal["sparse", "dense", "hybrid"]

VALID_METHODS: frozenset[str] = frozenset({"sparse", "dense", "hybrid"})


@dataclass
class RetrievalQuery:
    """Input parameters for a retrieval invocation.

    Fields:
        query_text: Natural-language query (required, non-empty).
        method: Retrieval method: "sparse", "dense", or "hybrid".
        top_k: Number of results (1-50).
        rerank: Enable cross-encoder reranker.
        rerank_depth: Number of hybrid results to rerank (>= top_k).
        force_rerank: Override reranker validation warning.
    """

    query_text: str
    method: str = "hybrid"
    top_k: int = 5
    rerank: bool = False
    rerank_depth: int = 20
    force_rerank: bool = False

    def __post_init__(self) -> None:
        if not self.query_text or not self.query_text.strip():
            raise ValueError("query_text must be non-empty")
        if self.method not in VALID_METHODS:
            raise ValueError(
                f"method must be one of {', '.join(sorted(VALID_METHODS))}, got {self.method!r}"
            )
        if not 1 <= self.top_k <= 50:
            raise ValueError(f"top_k must be between 1 and 50, got {self.top_k}")
        if self.rerank_depth < self.top_k:
            raise ValueError(f"rerank_depth ({self.rerank_depth}) must be >= top_k ({self.top_k})")


@dataclass
class RetrievalResult:
    """A single retrieved chunk with its relevance information.

    Fields:
        chunk_id: Unique identifier for the chunk.
        text: Chunk text content.
        clause_heading: The clause heading.
        clause_level: Depth in clause hierarchy (0 = article, etc.).
        hierarchy_chain: Ordered ancestor headings (root first).
        parent_chunk_id: Chunk ID of the parent clause chunk, if any.
        score: Final relevance score (0.0-1.0).
        method: Retrieval method used.
        rank_sparse: Rank in BM25 results (None if not in top-K).
        rank_dense: Rank in dense results (None if not in top-K).
        rrf_score: RRF fusion score (None if not hybrid mode).
        rerank_score: Cross-encoder score (None if reranker not used).
        char_start: Character offset (start) in the original document.
        char_end: Character offset (end) in the original document.
    """

    chunk_id: str
    text: str
    clause_heading: str
    clause_level: int
    hierarchy_chain: list[str]
    parent_chunk_id: str | None
    score: float
    method: str
    rank_sparse: int | None = None
    rank_dense: int | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None
    char_start: int = 0
    char_end: int = 0


@dataclass
class IndexMeta:
    """Metadata about a document's retrieval index.

    Fields:
        document_id: SHA-256 hex hash of the original document.
        document_path: Original file path at ingest time.
        chunk_count: Number of chunks in the index.
        method: Retrieval method used ("sparse" or "hybrid").
        embedding_model: Embedding model identifier, None if sparse-only.
        embedding_dimension: Vector dimension, None if sparse-only.
        index_timestamp: ISO 8601 timestamp of indexing.
        index_status: One of "empty", "ingesting", "indexed", "corrupt".
        db_size_bytes: Size of the database file in bytes.
    """

    document_id: str
    document_path: str
    chunk_count: int
    method: str
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    index_timestamp: str = ""
    index_status: str = "empty"
    db_size_bytes: int = 0
