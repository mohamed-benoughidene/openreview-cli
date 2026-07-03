"""Retrieval pipeline — BM25 + Dense + RRF hybrid retrieval."""

from openreview_cli.retrieval.engine import RetrievalEngine
from openreview_cli.retrieval.errors import (
    EmbeddingError,
    IndexCorruptError,
    IndexNotFoundError,
    RetrievalError,
)
from openreview_cli.retrieval.ingest import (
    clear_index,
    get_index_for_document,
    get_last_indexed_doc,
    index_exists,
    ingest_document,
    ingest_from_file,
)
from openreview_cli.retrieval.models import IndexMeta, RetrievalQuery, RetrievalResult
from openreview_cli.retrieval.rerank import Reranker
from openreview_cli.retrieval.storage import RetrievalStorage

__all__ = [
    "EmbeddingError",
    "IndexCorruptError",
    "IndexMeta",
    "IndexNotFoundError",

    "Reranker",
    "RetrievalEngine",
    "RetrievalError",
    "RetrievalQuery",
    "RetrievalResult",
    "RetrievalStorage",
    "clear_index",
    "get_index_for_document",
    "get_last_indexed_doc",
    "index_exists",
    "ingest_document",
    "ingest_from_file",
]
