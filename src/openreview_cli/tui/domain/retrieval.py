"""Retrieval domain adapter for the TUI — identity, chunk, ingest, status, search.

A thin wrapper over the existing ``retrieval/ingest.py`` and ``retrieval/engine.py``
entry points. No chunking, indexing, embedding or scoring logic lives here, and
nothing here imports Textual, so the whole surface is unit-testable.

Two deliberate constraints:

* ``openreview_cli.gateway.router`` is never imported (it pulls litellm in,
  measured 3.17 s) and no ``Gateway`` is ever constructed — retrieval is
  sparse-only in v1.
* ``index_meta`` checks that the database file exists *before* touching
  ``RetrievalEngine``. ``sqlite3.connect`` creates the file it is handed, so a
  status read without that guard would fabricate an empty index on disk.
"""

from __future__ import annotations

import dataclasses
import hashlib
import threading
from pathlib import Path
from typing import Any

from openreview_cli.chunking.models import ChunkConfig
from openreview_cli.chunking.stream import stream_chunks
from openreview_cli.config.loader import load_config
from openreview_cli.config.paths import get_config_dir
from openreview_cli.parsing.stream import parse_document
from openreview_cli.retrieval.engine import RetrievalEngine
from openreview_cli.retrieval.ingest import _ensure_db_dir, ingest_document
from openreview_cli.retrieval.ingest import clear_index as _ingest_clear_index
from openreview_cli.retrieval.models import RetrievalQuery, RetrievalResult

#: v1 is sparse-only: no gateway, no Ollama, no network, no API key (D5).
_METHOD = "sparse"
_DEFAULT_TOP_K = 5

#: Serializes the two index-mutating operations. ``ingest_document`` deletes the
#: database before rebuilding it, so two concurrent ingests on one path were
#: measured to leave a malformed image that neither search nor a metadata read
#: can open. The screen's busy flag covers the UI; this lock covers any caller.
_INDEX_LOCK = threading.Lock()


def resolve_document(path: Path, *, db_dir: Path | None = None) -> tuple[str, Path]:
    """Validate *path* and return ``(document_id, db_path)``.

    ``document_id`` is the sha256 of the file's bytes, so one index exists per
    source document and every step of the flow addresses the same one.

    Raises:
        FileNotFoundError: The path does not exist.
        IsADirectoryError: The path is a directory.
        OSError: The file could not be read.
    """
    path = _require_readable_file(path)
    document_id = hashlib.sha256(path.read_bytes()).hexdigest()
    resolved_dir = _ensure_db_dir(db_dir)
    return document_id, resolved_dir / f"{document_id[:32]}.db"


def chunk_document(path: Path) -> list[dict[str, Any]]:
    """Parse and chunk *path* in memory, with no Rich progress bar.

    The returned dicts are the ``dataclasses.asdict(Chunk)`` shape that
    ``ingest_document`` normalizes; no ``.ndax`` file is written or read.

    Raises:
        ParseError: The document could not be parsed.
        OSError: The file could not be read.
    """
    parsed = parse_document(path, allow_password_prompt=False)
    clauses = parsed[1]
    return [
        dataclasses.asdict(chunk)
        for chunk in stream_chunks(clauses, ChunkConfig(), show_progress=False)
    ]


def index_meta(db_path: Path) -> dict[str, Any] | None:
    """Return the index metadata, or ``None`` when no index exists yet.

    The existence check comes first and is load-bearing: it is what stops a
    status read from creating a 4096-byte database as a side effect.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return None
    return RetrievalEngine(db_path).get_index_meta()


def ingest_chunks(
    chunks: list[dict[str, Any]],
    db_path: Path,
    *,
    document_id: str,
) -> dict[str, Any]:
    """Index *chunks* at *db_path* under *document_id*, sparse-only.

    Rebuilds the index from scratch — ``ingest_document`` clears the database
    first — so callers must confirm before rebuilding an indexed document.
    """
    with _INDEX_LOCK:
        return ingest_document(
            chunks,
            db_path,
            method=_METHOD,
            document_id=document_id,
        )


def clear_index(db_path: Path) -> None:
    """Delete the index at *db_path*, serialized against ingest."""
    with _INDEX_LOCK:
        _ingest_clear_index(db_path)


def search(
    db_path: Path,
    query: str,
    *,
    top_k: int | None = None,
) -> list[RetrievalResult]:
    """Search *db_path* sparse-only, using the configured ``retrieval.top_k``.

    Raises:
        IndexNotFoundError: No index at *db_path* (or a status that is not usable).
        IndexCorruptError: The stored index status is ``corrupt``.
    """
    return RetrievalEngine(db_path).retrieve(
        RetrievalQuery(
            query_text=query,
            method=_METHOD,
            top_k=top_k or configured_top_k(),
        )
    )


def configured_top_k() -> int:
    """Read ``retrieval.top_k`` the way the CLI reads it.

    Read from ``load_config()`` directly rather than through
    ``openreview_cli.app``: ``tui/`` has never imported the CLI module, and
    doing so would drag the whole CLI into the TUI's import graph.

    Public so the screen can report the cut it actually applied, from the one
    number it also passes to ``search``.
    """
    section = load_config(get_config_dir() / "config.yml").get("retrieval")
    if not isinstance(section, dict):
        return _DEFAULT_TOP_K
    try:
        return int(section.get("top_k", _DEFAULT_TOP_K))
    except (TypeError, ValueError):
        return _DEFAULT_TOP_K


def _require_readable_file(path: str | Path) -> Path:
    """Return *path* as a ``Path`` once it is known to be an existing file."""
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"No file found at {resolved}.")
    if resolved.is_dir():
        raise IsADirectoryError(f"{resolved} is a directory, not a file.")
    return resolved
