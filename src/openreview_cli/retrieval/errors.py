"""Custom exception classes for the retrieval pipeline.

All retrieval exceptions inherit from ``RetrievalError``.
"""

from __future__ import annotations


class RetrievalError(Exception):
    """Base error for the retrieval pipeline."""


class IndexCorruptError(RetrievalError):
    """Index database is missing, corrupt, or from incompatible schema.

    Message: "Index database is corrupt. Re-run `openreview ingest <file>` to rebuild."
    """


class IndexNotFoundError(RetrievalError):
    """Document has not been indexed.

    Message: "Document not indexed. Run `openreview ingest <file>` first."
    """


class EmbeddingError(RetrievalError):
    """Embedding computation failed for a chunk.

    Message: "Embedding computation failed for chunk '{chunk_id}': {reason}"
    """


