from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator


class RetrievalStorage:
    """Low-level SQLite operations for the retrieval index.

    Each indexed document gets its own SQLite database file.
    Operates in WAL mode with foreign keys enabled.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def create_schema(self) -> None:
        """Create all tables, FTS5 virtual table, indexes, and triggers.

        Idempotent — safe to call multiple times.
        """
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS index_meta (
                document_id      TEXT PRIMARY KEY,
                document_path    TEXT NOT NULL,
                index_version    INTEGER NOT NULL DEFAULT 1,
                index_status     TEXT NOT NULL DEFAULT 'empty'
                                 CHECK(index_status IN ('empty','ingesting','indexed','corrupt')),
                index_timestamp  TEXT,
                chunk_count      INTEGER NOT NULL DEFAULT 0,
                method           TEXT NOT NULL DEFAULT 'sparse'
                                 CHECK(method IN ('sparse','hybrid')),
                embedding_model  TEXT,
                embedding_dim    INTEGER,
                db_size_bytes    INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id         TEXT PRIMARY KEY,
                document_id      TEXT NOT NULL REFERENCES index_meta(document_id),
                text             TEXT NOT NULL,
                clause_heading   TEXT NOT NULL,
                clause_level     INTEGER NOT NULL CHECK(clause_level >= 0),
                parent_chunk_id  TEXT REFERENCES chunks(chunk_id),
                heading_chain    TEXT NOT NULL,
                char_start       INTEGER NOT NULL CHECK(char_start >= 0),
                char_end         INTEGER NOT NULL CHECK(char_end > char_start),
                created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_chunks_parent ON chunks(parent_chunk_id);
            CREATE INDEX IF NOT EXISTS idx_chunks_clause_level ON chunks(clause_level);

            CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
                chunk_id UNINDEXED,
                text,
                clause_heading,
                content='chunks',
                content_rowid='rowid',
                tokenize='unicode61',
                prefix='2 3'
            );

            CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                INSERT INTO chunk_fts(rowid, chunk_id, text, clause_heading)
                VALUES (new.rowid, new.chunk_id, new.text, new.clause_heading);
            END;

            CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                INSERT INTO chunk_fts(chunk_fts, rowid, chunk_id, text, clause_heading)
                VALUES ('delete', old.rowid, old.chunk_id, old.text, old.clause_heading);
            END;

            CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
                INSERT INTO chunk_fts(chunk_fts, rowid, chunk_id, text, clause_heading)
                VALUES ('delete', old.rowid, old.chunk_id, old.text, old.clause_heading);
                INSERT INTO chunk_fts(rowid, chunk_id, text, clause_heading)
                VALUES (new.rowid, new.chunk_id, new.text, new.clause_heading);
            END;

            CREATE TABLE IF NOT EXISTS chunk_embeddings (
                chunk_id    TEXT PRIMARY KEY REFERENCES chunks(chunk_id) ON DELETE CASCADE,
                embedding   BLOB NOT NULL,
                model_id    TEXT NOT NULL,
                dimension   INTEGER NOT NULL CHECK(dimension > 0),
                chunk_norm  REAL NOT NULL CHECK(chunk_norm > 0.0)
            );

            CREATE INDEX IF NOT EXISTS idx_embeddings_model_id ON chunk_embeddings(model_id);

            CREATE TABLE IF NOT EXISTS rerank_validation (
                model_id              TEXT NOT NULL,
                document_type         TEXT NOT NULL,
                precision_with        REAL CHECK(precision_with BETWEEN 0.0 AND 1.0),
                precision_without     REAL CHECK(precision_without BETWEEN 0.0 AND 1.0),
                degradation_pp        REAL,
                benchmark_timestamp   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                PRIMARY KEY (model_id, document_type)
            );

            CREATE TABLE IF NOT EXISTS rerank_validation_log (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id              TEXT NOT NULL,
                document_type         TEXT NOT NULL,
                precision_with        REAL CHECK(precision_with BETWEEN 0.0 AND 1.0),
                precision_without     REAL CHECK(precision_without BETWEEN 0.0 AND 1.0),
                degradation_pp        REAL,
                consecutive           INTEGER NOT NULL DEFAULT 0,
                run_timestamp         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            );

            CREATE INDEX IF NOT EXISTS idx_val_log_lookup
                ON rerank_validation_log(model_id, document_type, run_timestamp DESC);
        """)

    def insert_chunk(self, chunk: dict[str, Any]) -> None:
        """Insert a single chunk row.

        The chunk dict must include at minimum:
            chunk_id, document_id, text, clause_heading, clause_level,
            heading_chain (list[str]), char_start, char_end.
        Optional: parent_chunk_id.
        """
        heading_chain = json.dumps(chunk.get("heading_chain", [chunk.get("clause_heading", "")]))
        self.conn.execute(
            """INSERT INTO chunks
                 (chunk_id, document_id, text, clause_heading, clause_level,
                  parent_chunk_id, heading_chain, char_start, char_end)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                chunk["chunk_id"],
                chunk["document_id"],
                chunk["text"],
                chunk.get("clause_heading", ""),
                chunk.get("clause_level", 0),
                chunk.get("parent_chunk_id"),
                heading_chain,
                chunk.get("char_start", 0),
                chunk.get("char_end", 0),
            ),
        )
        self.conn.commit()

    def insert_embedding(
        self,
        chunk_id: str,
        embedding: bytes,
        model_id: str,
        dimension: int,
        norm: float,
    ) -> None:
        """Insert a single embedding row."""
        self.conn.execute(
            "INSERT INTO chunk_embeddings (chunk_id, embedding, model_id, dimension, chunk_norm) "
            "VALUES (?, ?, ?, ?, ?)",
            (chunk_id, embedding, model_id, dimension, norm),
        )
        self.conn.commit()

    def search_fts(self, query_text: str, top_k: int) -> list[tuple[str, float]]:
        """BM25 search via FTS5.

        Returns list of (chunk_id, bm25_score).
        bm25_score is from SQLite's bm25() ranking function (negative = better).
        """
        cursor = self.conn.execute(
            "SELECT chunk_id, bm25(chunk_fts) AS score "
            "FROM chunk_fts WHERE chunk_fts MATCH ? ORDER BY score LIMIT ?",
            (query_text, top_k),
        )
        return [(row["chunk_id"], row["score"]) for row in cursor.fetchall()]

    def load_embeddings(self) -> Iterator[tuple[str, bytes, float]]:
        """Stream all (chunk_id, embedding_blob, chunk_norm) tuples.

        Yields one row at a time — does not load all embeddings into memory.
        """
        # ponytail: streaming iterator — cursor.fetchone() implicit via ``for row``
        cursor = self.conn.execute("SELECT chunk_id, embedding, chunk_norm FROM chunk_embeddings")
        for row in cursor:
            yield (row["chunk_id"], row["embedding"], row["chunk_norm"])

    def load_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        """Load a single chunk by ID, or None if not found."""
        cursor = self.conn.execute("SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def load_embedding(self, chunk_id: str) -> tuple[bytes, float] | None:
        """Load a single embedding by chunk ID, or None if not found."""
        cursor = self.conn.execute(
            "SELECT embedding, chunk_norm FROM chunk_embeddings WHERE chunk_id = ?",
            (chunk_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return (row["embedding"], row["chunk_norm"])

    def set_index_status(self, status: str) -> None:
        """Set the index status in the index_meta table."""
        self.conn.execute("UPDATE index_meta SET index_status = ?", (status,))
        self.conn.commit()

    def get_index_meta(self) -> dict[str, Any] | None:
        """Read index metadata row, or None if not yet populated."""
        try:
            cursor = self.conn.execute("SELECT * FROM index_meta")
            row = cursor.fetchone()
            if row is None:
                return None
            return dict(row)
        except sqlite3.OperationalError:
            return None

    def insert_rerank_validation(
        self,
        model_id: str,
        document_type: str,
        precision_with: float,
        precision_without: float,
        degradation_pp: float,
    ) -> int:
        """Insert or update a reranker validation record.

        Returns the consecutive degradation count (how many recent runs all
        showed degradation_pp > 0). Uses the validation log to track history.

        Uses INSERT OR REPLACE to handle the PRIMARY KEY (model_id, document_type).
        """
        # Write consolidated record
        self.conn.execute(
            """INSERT OR REPLACE INTO rerank_validation
               (model_id, document_type, precision_with, precision_without, degradation_pp)
               VALUES (?, ?, ?, ?, ?)""",
            (model_id, document_type, precision_with, precision_without, degradation_pp),
        )

        # Compute consecutive degradation count from previous log entries.
        # FR-5: degradation = Precision@5 with reranker <= without reranker,
        # i.e. degradation_pp <= 0 (where degradation_pp = (with - without) * 100).
        is_degraded = degradation_pp <= 0
        prev = self.get_rerank_validation_log(model_id, document_type, limit=3)
        consecutive = 0
        if is_degraded:
            # Count how many consecutive recent entries also showed degradation
            for entry in prev:
                prev_pp = entry.get("degradation_pp", 0)
                if prev_pp is not None and float(prev_pp) <= 0:  # type: ignore[arg-type]
                    consecutive += 1
                else:
                    break
            consecutive += 1  # count the current run

        # Write log entry
        self.conn.execute(
            """INSERT INTO rerank_validation_log
               (model_id, document_type, precision_with, precision_without, degradation_pp, consecutive)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                model_id,
                document_type,
                precision_with,
                precision_without,
                degradation_pp,
                consecutive,
            ),
        )

        self.conn.commit()
        return consecutive

    def get_rerank_validation(
        self,
        model_id: str,
        document_type: str,
    ) -> dict[str, object] | None:
        """Read a reranker validation record, or None if not found."""
        cursor = self.conn.execute(
            "SELECT * FROM rerank_validation WHERE model_id = ? AND document_type = ?",
            (model_id, document_type),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def get_rerank_validation_log(
        self,
        model_id: str,
        document_type: str,
        limit: int = 3,
    ) -> list[dict[str, object]]:
        """Read the last N reranker validation log entries for a (model, doc_type).

        Returns entries ordered by run_timestamp DESC (newest first).
        """
        cursor = self.conn.execute(
            "SELECT * FROM rerank_validation_log "
            "WHERE model_id = ? AND document_type = ? "
            "ORDER BY run_timestamp DESC LIMIT ?",
            (model_id, document_type, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> RetrievalStorage:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
