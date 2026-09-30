from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Method = Literal["sparse"]

VALID_METHODS: frozenset[str] = frozenset({"sparse"})


@dataclass
class RetrievalQuery:
    """Input parameters for a retrieval invocation.

    Fields:
        query_text: Natural-language query (required, non-empty).
        method: Retrieval method. Keyword search ("sparse") is the only method;
            anything else is rejected.
        top_k: Number of results (1-50).
    """

    query_text: str
    method: str = "sparse"
    top_k: int = 5

    def __post_init__(self) -> None:
        if not self.query_text or not self.query_text.strip():
            raise ValueError("query_text must be non-empty")
        if self.method not in VALID_METHODS:
            raise ValueError(
                f"method must be one of {', '.join(sorted(VALID_METHODS))}, got {self.method!r}"
            )
        if not 1 <= self.top_k <= 50:
            raise ValueError(f"top_k must be between 1 and 50, got {self.top_k}")


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
    char_start: int = 0
    char_end: int = 0


@dataclass
class IndexMeta:
    """Metadata about a document's retrieval index.

    Fields:
        document_id: SHA-256 hex hash of the original document.
        document_path: Original file path at ingest time.
        chunk_count: Number of chunks in the index.
        method: Retrieval method used (always "sparse").
        index_timestamp: ISO 8601 timestamp of indexing.
        index_status: One of "empty", "ingesting", "indexed", "corrupt".
        db_size_bytes: Size of the database file in bytes.
    """

    document_id: str
    document_path: str
    chunk_count: int
    method: str
    index_timestamp: str = ""
    index_status: str = "empty"
    db_size_bytes: int = 0
