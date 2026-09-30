"""Index lifecycle helpers and document ingestion pipeline."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openreview_cli.retrieval.errors import IndexCorruptError, MalformedChunkError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from openreview_cli.retrieval.storage import RetrievalStorage

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


def _require_keys(chunk: dict[str, Any], keys: tuple[str, ...], index: int | None) -> None:
    """Raise MalformedChunkError if any required key is absent from ``chunk``."""
    for key in keys:
        if key not in chunk:
            where = f"chunk {index}" if index is not None else "chunk"
            raise MalformedChunkError(f"{where} is missing required key '{key}'")


def _normalize_chunk(
    chunk: dict[str, Any], document_id: str, index: int | None = None
) -> dict[str, Any]:
    """Normalize a chunk dict to the retrieval storage schema.

    Accepts both the chunk-output shape (``id``, ``source_clause_title``,
    ``char_offset_start``, ...) and the already-normalized fixture shape
    (``chunk_id``, ``clause_heading``, ``char_start``, ...).

    Returns a new dict — never mutates the input.

    Raises:
        MalformedChunkError: If the chunk is not an object or a required key is missing.
    """
    if not isinstance(chunk, dict):
        where = f"chunk {index}" if index is not None else "chunk"
        raise MalformedChunkError(f"{where} is not a JSON object")
    if "chunk_id" in chunk:
        _require_keys(chunk, ("text",), index)
        normalized = dict(chunk)
    else:
        _require_keys(chunk, ("id", "text"), index)
        structural = chunk.get("structural_location") or chunk.get("source_clause_title") or ""
        normalized = {
            "chunk_id": chunk["id"],
            "text": chunk["text"],
            "clause_heading": chunk.get("source_clause_title") or "",
            "clause_level": chunk.get("source_clause_level", 0),
            "parent_chunk_id": chunk.get("parent_chunk_id"),
            "heading_chain": [structural] if structural else [],
            "char_start": chunk.get("char_offset_start", 0),
            "char_end": chunk.get("char_offset_end", 0),
        }
    normalized["document_id"] = document_id
    return normalized


def _index_meta_or_none(storage: RetrievalStorage) -> dict[str, Any] | None:
    """Read the index metadata just written; a read failure must not fail ingest.

    An ingest that has just written the index must not fail on a read of itself,
    so ``IndexCorruptError`` falls back to the synthesised metadata built by the
    caller (issue #118).
    """
    try:
        return storage.get_index_meta()
    except IndexCorruptError:
        return None


def ingest_document(
    chunks: list[dict[str, Any]] | Iterator[dict[str, Any]],
    db_path: str | Path,
    progress_callback: Callable[[int, int], None] | None = None,
    document_id: str | None = None,
) -> dict[str, Any]:
    """Ingest parsed chunks into a keyword-search (BM25) index.

    Args:
        chunks: Iterable of chunk dicts (as loaded from .ndax format).
        db_path: Path to the SQLite database file.
        progress_callback: Called with (current, total) after each chunk.
        document_id: Override document id (defaults to per-chunk value).

    Returns:
        dict with index metadata (matching IndexMeta fields).

    Raises:
        MalformedChunkError: If a chunk is not an object or a required key is missing.
    """
    from openreview_cli.retrieval.storage import RetrievalStorage

    db_path = Path(db_path)

    # Clear existing DB if present
    if db_path.exists():
        clear_index(db_path)

    with RetrievalStorage(db_path) as storage:
        storage.create_schema()

        # ponytail: stream-and-discard — convert to list only for counting,
        # then process each chunk individually (store → discard)
        chunk_list = list(chunks) if not isinstance(chunks, list) else chunks
        total = len(chunk_list)

        # Normalize both chunk-output schema (id/source_*) and already-
        # normalized fixture schema (chunk_id/clause_heading) to storage keys.
        head = chunk_list[0] if chunk_list else None
        resolved_doc_id = document_id or (
            head.get("document_id", "unknown") if isinstance(head, dict) else "unknown"
        )
        chunk_list = [_normalize_chunk(c, resolved_doc_id, i) for i, c in enumerate(chunk_list)]

        # T064: Large document warning
        if total > 5000:
            logger.warning(
                "Large document (%d chunks). BM25-only recommended for best performance.",
                total,
            )
        storage.conn.execute(
            "INSERT OR REPLACE INTO index_meta "
            "(document_id, document_path, index_version, index_status, chunk_count, method, "
            "db_size_bytes, index_timestamp) "
            "VALUES (?, ?, 1, 'ingesting', ?, 'sparse', 0, ?)",
            (
                resolved_doc_id,
                str(db_path),
                total,
                datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
        )
        storage.conn.commit()

        # ponytail: stream-and-discard — one chunk at a time, no accumulation
        for idx, chunk in enumerate(chunk_list):
            # Write chunk to SQLite (triggers FTS5 auto-insert)
            storage.insert_chunk(chunk)

            if progress_callback is not None:
                progress_callback(idx + 1, total)

        # Update index status to indexed
        db_size = db_path.stat().st_size if db_path.exists() else 0
        storage.conn.execute(
            "UPDATE index_meta SET index_status='indexed', method='sparse', db_size_bytes=?, "
            "index_timestamp=?",
            (db_size, datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")),
        )
        storage.conn.commit()

        # T062: Record as most recently indexed document
        doc_id = resolved_doc_id
        _save_last_indexed(db_path.parent, str(db_path), doc_id)

        meta = _index_meta_or_none(storage)
        if meta is None:
            return {
                "document_id": resolved_doc_id,
                "document_path": str(db_path),
                "chunk_count": total,
                "method": "sparse",
                "index_status": "indexed",
                "db_size_bytes": db_size,
                "index_timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

        return dict(meta)


def ingest_from_file(
    file_path: str | Path,
    db_path: str | Path,
    progress_callback: Callable[[int, int], None] | None = None,
    document_id: str | None = None,
) -> dict[str, Any]:
    """Load chunks from an ndax/JSON file and ingest them.

    Args:
        file_path: Path to a .ndax JSON file with chunk data.
        db_path: Path to the SQLite database file.
        progress_callback: Progress callback.
        document_id: Override document id (defaults to per-chunk value).

    Returns:
        dict with index metadata.
    """
    file_path = Path(file_path)
    with open(file_path) as f:
        chunks: list[dict[str, Any]] = json.load(f)

    return ingest_document(
        chunks,
        db_path,
        progress_callback=progress_callback,
        document_id=document_id,
    )
