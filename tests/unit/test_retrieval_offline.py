"""Unit tests for offline fallback (T045)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from openreview_cli.retrieval.engine import RetrievalEngine
from openreview_cli.retrieval.models import RetrievalQuery


@pytest.fixture
def populated_db(tmp_path: Path) -> str:
    """Create a minimal populated index DB (no embeddings needed for offline tests)."""
    db_path = str(tmp_path / "test_index.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS index_meta (
            document_id TEXT PRIMARY KEY,
            document_path TEXT NOT NULL DEFAULT '',
            index_version INTEGER NOT NULL DEFAULT 1,
            index_status TEXT NOT NULL DEFAULT 'indexed',
            index_timestamp TEXT,
            chunk_count INTEGER NOT NULL DEFAULT 0,
            method TEXT NOT NULL DEFAULT 'sparse',
            embedding_model TEXT,
            embedding_dim INTEGER,
            db_size_bytes INTEGER DEFAULT 0
        );
        INSERT INTO index_meta (document_id, index_status, chunk_count, method)
        VALUES ('test-doc', 'indexed', 4, 'sparse');

        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL DEFAULT 'test-doc',
            text TEXT NOT NULL,
            clause_heading TEXT NOT NULL,
            clause_level INTEGER NOT NULL DEFAULT 0,
            parent_chunk_id TEXT,
            heading_chain TEXT NOT NULL DEFAULT '[]',
            char_start INTEGER NOT NULL DEFAULT 0,
            char_end INTEGER NOT NULL DEFAULT 0
        );
        INSERT INTO chunks VALUES
            ('c1', 'test-doc', 'confidential information shall be protected', 'Article 3', 0, NULL, '["Article 3"]', 0, 100),
            ('c2', 'test-doc', 'governing law is delaware', 'Section 7.2', 1, 'c1', '["Article 7","Section 7.2"]', 200, 300),
            ('c3', 'test-doc', 'indemnification obligations', 'Article 8', 0, NULL, '["Article 8"]', 400, 500),
            ('c4', 'test-doc', 'limitation of liability', 'Article 9', 0, NULL, '["Article 9"]', 600, 700);

        CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
            chunk_id UNINDEXED, text, clause_heading,
            content='chunks', content_rowid='rowid',
            tokenize='unicode61', prefix='2 3'
        );
        INSERT INTO chunk_fts (rowid, chunk_id, text, clause_heading)
        SELECT rowid, chunk_id, text, clause_heading FROM chunks;
    """)
    conn.commit()
    conn.close()
    return db_path


class TestOfflineFallback:
    """T045: Offline fallback behavior."""

    def test_dense_fallback_when_gateway_none(self, populated_db: str) -> None:
        """Dense retrieval with no gateway falls back to BM25."""
        engine = RetrievalEngine(populated_db, gateway=None)
        query = RetrievalQuery(query_text="confidential", method="dense", top_k=2)
        results = engine.retrieve(query)
        assert len(results) <= 2
        assert all(r.method == "sparse" for r in results)

    def test_dense_fallback_when_gateway_offline(self, populated_db: str) -> None:
        """Dense retrieval with offline gateway falls back to BM25."""
        mock_gateway = MagicMock()
        mock_gateway.embed.side_effect = ConnectionError("Connection refused")

        engine = RetrievalEngine(populated_db, gateway=mock_gateway)
        query = RetrievalQuery(query_text="confidential", method="dense", top_k=2)
        results = engine.retrieve(query)
        assert len(results) <= 2
        assert all(r.method == "sparse" for r in results)

    def test_hybrid_fallback_when_gateway_offline(self, populated_db: str) -> None:
        """Hybrid retrieval with offline gateway falls back to BM25."""
        mock_gateway = MagicMock()
        mock_gateway.embed.side_effect = ConnectionError("Connection refused")

        engine = RetrievalEngine(populated_db, gateway=mock_gateway)
        query = RetrievalQuery(query_text="confidential", method="hybrid", top_k=2)
        results = engine.retrieve(query)
        # Hybrid still returns results (sparse-only contribution)
        assert len(results) <= 2
        assert all(r.method == "hybrid" for r in results)

    def test_sparse_works_without_network(self, populated_db: str) -> None:
        """Sparse retrieval works with no gateway (pure SQLite FTS5)."""
        engine = RetrievalEngine(populated_db, gateway=None)
        query = RetrievalQuery(query_text="confidential", method="sparse", top_k=3)
        results = engine.retrieve(query)
        assert len(results) > 0
        assert all(r.method == "sparse" for r in results)

    def test_notice_on_dense_fallback(self, populated_db: str) -> None:
        """Engine captures notice when falling back from dense to sparse."""
        engine = RetrievalEngine(populated_db, gateway=None)
        query = RetrievalQuery(query_text="confidential", method="dense", top_k=2)
        _ = engine.retrieve(query)
        assert len(engine.notices) > 0
        assert any("Dense" in n or "unavailable" in n for n in engine.notices)

    def test_notice_on_hybrid_fallback(self, populated_db: str) -> None:
        """Engine captures notice when dense part of hybrid fails."""
        mock_gateway = MagicMock()
        mock_gateway.embed.side_effect = ConnectionError("Connection refused")

        engine = RetrievalEngine(populated_db, gateway=mock_gateway)
        query = RetrievalQuery(query_text="confidential", method="hybrid", top_k=2)
        _ = engine.retrieve(query)
        assert len(engine.notices) > 0
        assert any("Dense" in n or "unavailable" in n for n in engine.notices)

    def test_no_notice_on_sparse(self, populated_db: str) -> None:
        """Sparse retrieval produces no notices (no dense path attempted)."""
        engine = RetrievalEngine(populated_db, gateway=None)
        query = RetrievalQuery(query_text="confidential", method="sparse", top_k=2)
        _ = engine.retrieve(query)
        assert len(engine.notices) == 0
