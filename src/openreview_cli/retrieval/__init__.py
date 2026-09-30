"""Retrieval pipeline — keyword (BM25) search over SQLite FTS5."""

from openreview_cli.retrieval.engine import RetrievalEngine
from openreview_cli.retrieval.errors import (
    IndexCorruptError,
    IndexNotFoundError,
    RetrievalError,
)
from openreview_cli.retrieval.ingest import (
    clear_index,
    get_index_for_document,
    get_last_indexed_doc,
    get_last_indexed_doc_id,
    index_exists,
    ingest_document,
    ingest_from_file,
)
from openreview_cli.retrieval.models import IndexMeta, RetrievalQuery, RetrievalResult
from openreview_cli.retrieval.storage import RetrievalStorage

__all__ = [
    "IndexCorruptError",
    "IndexMeta",
    "IndexNotFoundError",
    "RetrievalEngine",
    "RetrievalError",
    "RetrievalQuery",
    "RetrievalResult",
    "RetrievalStorage",
    "clear_index",
    "get_index_for_document",
    "get_last_indexed_doc",
    "get_last_indexed_doc_id",
    "index_exists",
    "ingest_document",
    "ingest_from_file",
]
