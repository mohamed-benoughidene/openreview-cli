"""Index lifecycle helpers and document ingestion pipeline."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from openreview_cli.gateway.router import Gateway

logger = logging.getLogger(__name__)


def index_exists(db_path: str | Path) -> bool:
    """Check if an index database file exists on disk.

    A ``True`` return means the file exists; it does not validate the
    schema or check for corruption. Use ``RetrievalStorage.get_index_meta()``
    for deeper validation.
    """
    return Path(db_path).exists()


def clear_index(db_path: str | Path) -> None:
    """Delete an index database file.

    Silently succeeds if the file does not exist.
    """
    path = Path(db_path)
    if path.exists():
        path.unlink()


def get_index_for_document(
    doc_hash: str,
    db_dir: str | Path | None = None,
) -> Path | None:
    """Resolve the SQLite database path for a document hash.

    Arguments:
        doc_hash: SHA-256 hex string identifying the document.
        db_dir: Override directory for index databases.
                Defaults to ``{platformdirs user_data_dir}/openreview/indexes/``.

    Returns:
        Path if the database file exists, otherwise None.
    """
    if db_dir is None:
        from openreview_cli.config.paths import get_data_dir

        db_dir = get_data_dir() / "indexes"

    db_path = Path(db_dir) / f"{doc_hash}.db"
    return db_path if db_path.exists() else None


def _ensure_db_dir(db_dir: str | Path | None) -> Path:
    """Resolve and create the index database directory."""
    from openreview_cli.config.paths import get_data_dir

    resolved = Path(db_dir) if db_dir is not None else get_data_dir() / "indexes"
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


# ponytail: last_indexed.json is a small JSON file in the db_dir
# that tracks the most recently indexed document. When <file> is omitted
# from the retrieve command, this file provides the fallback document path.
# Upgrade to SQLite meta-DB if cross-document queries ever land.
_LAST_INDEXED_FILE = "last_indexed.json"


def get_last_indexed_doc(db_dir: str | Path) -> str | None:
    """Return the document path of the most recently indexed document.

    Reads the ``last_indexed.json`` file in the index database directory.
    Returns None if no document has been indexed yet.
    """
    path = Path(db_dir) / _LAST_INDEXED_FILE
    if not path.exists():
        return None
    try:
        data: dict[str, object] = json.loads(path.read_text())
        doc_path = data.get("document_path")
        if isinstance(doc_path, str) and Path(doc_path).exists():
            return doc_path
    except (json.JSONDecodeError, OSError):
        logger.debug("Could not read last_indexed.json", exc_info=True)
    return None


def get_last_indexed_doc_id(db_dir: str | Path) -> str | None:
    """Return the document_id of the most recently indexed document.

    Reads the ``document_hash`` field from ``last_indexed.json``. Falls back
    to the ``document_path`` DB filename stem for legacy files that predate
    this helper.
    """
    path = Path(db_dir) / _LAST_INDEXED_FILE
    if not path.exists():
        return None
    try:
        data: dict[str, object] = json.loads(path.read_text())
        doc_id = data.get("document_hash")
        if isinstance(doc_id, str) and doc_id:
            return doc_id
        doc_path = data.get("document_path")
        if isinstance(doc_path, str):
            return Path(doc_path).stem
    except (json.JSONDecodeError, OSError):
        logger.debug("Could not read last_indexed.json", exc_info=True)
    return None


def _save_last_indexed(db_dir: str | Path, doc_path: str, doc_hash: str) -> None:
    """Record the document as the most recently indexed."""
    path = Path(db_dir) / _LAST_INDEXED_FILE
    try:
        path.write_text(
            json.dumps(
                {
                    "document_path": doc_path,
                    "document_hash": doc_hash,
                    "last_indexed_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            )
        )
    except OSError:
        logger.debug("Could not write last_indexed.json", exc_info=True)


def ingest_document(
    chunks: list[dict[str, Any]] | Iterator[dict[str, Any]],
    db_path: str | Path,
    gateway: Gateway | None = None,
    method: str = "hybrid",
    model_id: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Ingest parsed chunks into a retrieval index.

    Args:
        chunks: Iterable of chunk dicts (as loaded from .ndax format).
        db_path: Path to the SQLite database file.
        gateway: AI Gateway instance for embedding computation.
        method: "sparse" (BM25 only) or "hybrid" (BM25 + dense embeddings).
        model_id: Embedding model to use (None = use default "nomic-embed-text").
        progress_callback: Called with (current, total) after each chunk.

    Returns:
        dict with index metadata (matching IndexMeta fields).

    Raises:
        EmbeddingError: If embedding computation fails for a chunk.
    """
    from openreview_cli.retrieval.dense import (
        compute_embedding,
        compute_l2_norm,
        serialize_embedding,
    )
    from openreview_cli.retrieval.storage import RetrievalStorage

    db_path = Path(db_path)
    resolved_model = model_id or "nomic-embed-text"

    # Clear existing DB if present
    if db_path.exists():
        clear_index(db_path)

    with RetrievalStorage(db_path) as storage:
        storage.create_schema()

        # ponytail: stream-and-discard — convert to list only for counting,
        # then process each chunk individually (embed → store → discard)
        chunk_list = list(chunks) if not isinstance(chunks, list) else chunks
        total = len(chunk_list)

        # T064: Large document warning
        if total > 5000:
            logger.warning(
                "Large document (%d chunks). BM25-only recommended for best performance. "
                "Embedding similarity may take several seconds.",
                total,
            )
        storage.conn.execute(
            "INSERT OR REPLACE INTO index_meta "
            "(document_id, document_path, index_version, index_status, chunk_count, method, "
            "embedding_model, embedding_dim, db_size_bytes, index_timestamp) "
            "VALUES (?, ?, 1, 'ingesting', ?, ?, ?, NULL, 0, ?)",
            (
                chunk_list[0].get("document_id", "unknown"),
                str(db_path),
                total,
                method,
                resolved_model,
                datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
        )
        storage.conn.commit()

        embedding_dim: int | None = None
        any_embedding_succeeded = False

        # ponytail: stream-and-discard — one chunk at a time, no accumulation
        for idx, chunk in enumerate(chunk_list):
            # Write chunk to SQLite (triggers FTS5 auto-insert)
            storage.insert_chunk(chunk)

            # Compute and store embedding for hybrid mode
            if method == "hybrid" and gateway is not None:
                try:
                    vector, dim = compute_embedding(chunk["text"], gateway, resolved_model)

                    # T064: Embedding dimension mismatch check
                    if embedding_dim is not None and dim != embedding_dim:
                        logger.warning(
                            "Embedding model changed; re-indexing document. "
                            "(old dim=%d, new dim=%d)",
                            embedding_dim,
                            dim,
                        )
                        # Re-ingest will happen on next call — clear and retry
                        storage.conn.execute("DELETE FROM chunk_embeddings")
                        storage.conn.commit()
                        break

                    embedding_dim = dim
                    norm = compute_l2_norm(vector)
                    blob = serialize_embedding(vector)
                    storage.insert_embedding(chunk["chunk_id"], blob, resolved_model, dim, norm)
                    any_embedding_succeeded = True
                except Exception as exc:
                    logger.warning("Embedding failed for chunk %s: %s", chunk["chunk_id"], exc)
                    # Continue with sparse-only for this chunk

            if progress_callback is not None:
                progress_callback(idx + 1, total)

        # Update index status to indexed
        final_method = (
            "hybrid"
            if (method == "hybrid" and gateway is not None and any_embedding_succeeded)
            else "sparse"
        )
        db_size = db_path.stat().st_size if db_path.exists() else 0

        if embedding_dim is None:
            storage.conn.execute(
                "UPDATE index_meta SET index_status='indexed', method=?, embedding_model=NULL, "
                "embedding_dim=NULL, db_size_bytes=?, "
                "index_timestamp=?",
                (final_method, db_size, datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")),
            )
        else:
            storage.conn.execute(
                "UPDATE index_meta SET index_status='indexed', method=?, embedding_model=?, "
                "embedding_dim=?, db_size_bytes=?, "
                "index_timestamp=?",
                (
                    final_method,
                    resolved_model,
                    embedding_dim,
                    db_size,
                    datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ),
            )
        storage.conn.commit()

        # T062: Record as most recently indexed document
        doc_id = chunk_list[0].get("document_id", "unknown")
        _save_last_indexed(db_path.parent, str(db_path), doc_id)

        meta = storage.get_index_meta()
        if meta is None:
            return {
                "document_id": chunk_list[0].get("document_id", "unknown"),
                "document_path": str(db_path),
                "chunk_count": total,
                "method": final_method,
                "embedding_model": resolved_model if embedding_dim else None,
                "embedding_dimension": embedding_dim,
                "index_status": "indexed",
                "db_size_bytes": db_size,
                "index_timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

        return dict(meta)


def ingest_from_file(
    file_path: str | Path,
    db_path: str | Path,
    gateway: Gateway | None = None,
    method: str = "hybrid",
    model_id: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Load chunks from an ndax/JSON file and ingest them.

    Args:
        file_path: Path to a .ndax JSON file with chunk data.
        db_path: Path to the SQLite database file.
        gateway: AI Gateway instance for embedding computation.
        method: "sparse" or "hybrid".
        model_id: Embedding model override.
        progress_callback: Progress callback.

    Returns:
        dict with index metadata.
    """
    file_path = Path(file_path)
    with open(file_path) as f:
        chunks: list[dict[str, Any]] = json.load(f)

    return ingest_document(
        chunks,
        db_path,
        gateway=gateway,
        method=method,
        model_id=model_id,
        progress_callback=progress_callback,
    )
