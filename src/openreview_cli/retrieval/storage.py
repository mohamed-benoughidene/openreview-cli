from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from openreview_cli.retrieval.errors import IndexCorruptError


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
                                 CHECK(method IN ('sparse')),
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
                tokenize='porter unicode61',
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

    def load_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        """Load a single chunk by ID, or None if not found."""
        cursor = self.conn.execute("SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def set_index_status(self, status: str) -> None:
        """Set the index status in the index_meta table."""
        self.conn.execute("UPDATE index_meta SET index_status = ?", (status,))
        self.conn.commit()

    def get_index_meta(self) -> dict[str, Any] | None:
        """Read index metadata row, or None if not yet populated.

        Raises:
            IndexCorruptError: the file exists but SQLite cannot read it as a database.
        """
        try:
            cursor = self.conn.execute("SELECT * FROM index_meta")
            row = cursor.fetchone()
            if row is None:
                return None
            return dict(row)
        except sqlite3.OperationalError:
            return None
        except sqlite3.DatabaseError as exc:
            raise IndexCorruptError(
                f"Index database at {self.db_path} is damaged and cannot be read: {exc}. "
                "Re-run `openreview ingest <file>` to rebuild."
            ) from exc

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> RetrievalStorage:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
