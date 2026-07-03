"""Unit tests for RetrievalEngine (T014)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from openreview_cli.retrieval.engine import RetrievalEngine
from openreview_cli.retrieval.errors import IndexCorruptError, IndexNotFoundError
from openreview_cli.retrieval.models import RetrievalQuery


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test_index.db")


@pytest.fixture
def populated_db(db_path: str) -> str:
    """Create a SQLite DB with a few chunks, FTS5, and embeddings."""
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
            method TEXT NOT NULL DEFAULT 'hybrid',
            embedding_model TEXT,
            embedding_dim INTEGER,
            db_size_bytes INTEGER DEFAULT 0
        );

        INSERT INTO index_meta (document_id, index_status, chunk_count, method, embedding_dim)
        VALUES ('test-doc', 'indexed', 4, 'hybrid', 4);

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

        CREATE TABLE IF NOT EXISTS chunk_embeddings (
            chunk_id TEXT PRIMARY KEY,
            embedding BLOB NOT NULL,
            model_id TEXT NOT NULL,
            dimension INTEGER NOT NULL,
            chunk_norm REAL NOT NULL
        );
    """)

    # Insert embeddings (4-dim vectors for simplicity)
    import struct

    vecs = {
        "c1": [0.5, 0.3, 0.1, 0.8],
        "c2": [0.1, 0.9, 0.2, 0.1],
        "c3": [0.8, 0.1, 0.3, 0.5],
        "c4": [0.2, 0.4, 0.7, 0.2],
    }
    for cid, vec in vecs.items():
        blob = struct.pack("<4f", *vec)
        norm = (sum(v * v for v in vec)) ** 0.5
        conn.execute(
            "INSERT INTO chunk_embeddings VALUES (?, ?, ?, ?, ?)",
            (cid, blob, "test-model", 4, norm),
        )

    conn.commit()
    conn.close()
    return db_path


class TestRetrievalEngine:
    """Tests for RetrievalEngine."""

    def test_init(self, db_path: str) -> None:
        engine = RetrievalEngine(db_path)
        assert str(engine.db_path) == db_path
        assert engine.gateway is None

    def test_get_index_meta_returns_none_when_no_db(self, tmp_path: Path) -> None:
        missing_db = str(tmp_path / "nonexistent.db")
        engine = RetrievalEngine(missing_db)
        meta = engine.get_index_meta()
        assert meta is None

    def test_get_index_meta_returns_meta(self, populated_db: str) -> None:
        engine = RetrievalEngine(populated_db)
        meta = engine.get_index_meta()
        assert meta is not None
        assert meta["document_id"] == "test-doc"
        assert meta["index_status"] == "indexed"

    def test_retrieve_no_db_raises(self, tmp_path: Path) -> None:
        missing_db = str(tmp_path / "nonexistent.db")
        engine = RetrievalEngine(missing_db)
        query = RetrievalQuery(query_text="confidentiality")
        with pytest.raises(IndexNotFoundError):
            engine.retrieve(query)

    def test_retrieve_sparse_returns_results(self, populated_db: str) -> None:
        engine = RetrievalEngine(populated_db)
        query = RetrievalQuery(query_text="confidential", method="sparse", top_k=3)
        results = engine.retrieve(query)
        assert len(results) <= 3
        assert all(r.method == "sparse" for r in results)
        if results:
            assert results[0].score >= 0

    def test_retrieve_sparse_top_k_respected(self, populated_db: str) -> None:
        engine = RetrievalEngine(populated_db)
        query = RetrievalQuery(query_text="confidential OR governing OR indemnification", method="sparse", top_k=2)
        results = engine.retrieve(query)
        assert len(results) <= 2

    def test_retrieve_dense_with_gateway(self, populated_db: str) -> None:
        mock_gateway = MagicMock()
        # Return a 4-dim embedding
        mock_gateway.embed.return_value = [[0.3, 0.5, 0.2, 0.7]]

        engine = RetrievalEngine(populated_db, gateway=mock_gateway)
        query = RetrievalQuery(query_text="confidential information", method="dense", top_k=2)
        results = engine.retrieve(query)
        assert len(results) <= 2
        assert all(r.method == "dense" for r in results)

    def test_retrieve_dense_fallback_no_gateway(self, populated_db: str) -> None:
        engine = RetrievalEngine(populated_db, gateway=None)
        query = RetrievalQuery(query_text="confidential", method="dense", top_k=2)
        results = engine.retrieve(query)
        # Falls back to sparse
        assert all(r.method == "sparse" for r in results)

    def test_retrieve_hybrid_returns_results(self, populated_db: str) -> None:
        mock_gateway = MagicMock()
        mock_gateway.embed.return_value = [[0.3, 0.5, 0.2, 0.7]]

        engine = RetrievalEngine(populated_db, gateway=mock_gateway)
        query = RetrievalQuery(query_text="confidential information", method="hybrid", top_k=3)
        results = engine.retrieve(query)
        assert len(results) <= 3
        assert all(r.method == "hybrid" for r in results)
        # Check we have rrf_score populated
        if results:
            assert results[0].rrf_score is not None

    def test_retrieve_hybrid_fallback_no_gateway(self, populated_db: str) -> None:
        """Hybrid without gateway falls back to BM25-only."""
        engine = RetrievalEngine(populated_db, gateway=None)
        query = RetrievalQuery(query_text="confidential", method="hybrid", top_k=2)
        results = engine.retrieve(query)
        # Should still return results using BM25 only
        assert len(results) <= 2

    def test_corrupt_db_raises(self, db_path: str) -> None:
        """A DB with status 'corrupt' raises IndexCorruptError."""
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS index_meta (
                document_id TEXT PRIMARY KEY,
                document_path TEXT NOT NULL DEFAULT '',
                index_version INTEGER NOT NULL DEFAULT 1,
                index_status TEXT NOT NULL DEFAULT 'corrupt',
                index_timestamp TEXT,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                method TEXT NOT NULL DEFAULT 'sparse',
                embedding_model TEXT,
                embedding_dim INTEGER,
                db_size_bytes INTEGER DEFAULT 0
            )
        """)
        conn.execute("INSERT INTO index_meta (document_id, index_status) VALUES ('corrupt-doc', 'corrupt')")
        conn.commit()
        conn.close()

        engine = RetrievalEngine(db_path)
        query = RetrievalQuery(query_text="test")
        with pytest.raises(IndexCorruptError):
            engine.retrieve(query)

    def test_result_ordering_by_score(self, populated_db: str) -> None:
        engine = RetrievalEngine(populated_db)
        query = RetrievalQuery(query_text="confidential OR indemnification OR limitation", method="sparse", top_k=5)
        results = engine.retrieve(query)
        if len(results) >= 2:
            for i in range(len(results) - 1):
                assert results[i].score >= results[i + 1].score

    # ── T024: Method routing ──

    def test_sparse_calls_bm25_only(self, populated_db: str) -> None:
        """sparse method only returns BM25 results, no dense/embedding calls."""
        engine = RetrievalEngine(populated_db, gateway=None)
        query = RetrievalQuery(query_text="confidential", method="sparse", top_k=3)
        results = engine.retrieve(query)
        assert len(results) <= 3
        assert all(r.method == "sparse" for r in results)
        assert all(r.rank_sparse is not None for r in results)
        assert all(r.rank_dense is None for r in results)
        assert all(r.rrf_score is None for r in results)
        assert all(r.rerank_score is None for r in results)

    def test_dense_calls_embedding_only_with_gateway(self, populated_db: str) -> None:
        """dense method returns embedding-similarity results when gateway is available."""
        mock_gateway = MagicMock()
        mock_gateway.embed.return_value = [[0.3, 0.5, 0.2, 0.7]]

        engine = RetrievalEngine(populated_db, gateway=mock_gateway)
        query = RetrievalQuery(query_text="confidential", method="dense", top_k=2)
        results = engine.retrieve(query)
        assert len(results) <= 2
        assert all(r.method == "dense" for r in results)
        assert all(r.rank_dense is not None for r in results)
        assert all(r.rank_sparse is None for r in results)

    def test_hybrid_calls_both_sparse_and_dense(self, populated_db: str) -> None:
        """hybrid method returns fused results with both ranks populated."""
        mock_gateway = MagicMock()
        mock_gateway.embed.return_value = [[0.3, 0.5, 0.2, 0.7]]

        engine = RetrievalEngine(populated_db, gateway=mock_gateway)
        query = RetrievalQuery(query_text="confidential", method="hybrid", top_k=3)
        results = engine.retrieve(query)
        assert len(results) <= 3
        assert all(r.method == "hybrid" for r in results)
        assert all(r.rrf_score is not None for r in results)
        # At least one result should have a sparse rank
        assert any(r.rank_sparse is not None for r in results)

    def test_dense_fallback_to_sparse_when_gateway_fails(self, populated_db: str) -> None:
        """dense method falls back to BM25 when embedding computation fails."""
        mock_gateway = MagicMock()
        mock_gateway.embed.side_effect = RuntimeError("model unavailable")

        engine = RetrievalEngine(populated_db, gateway=mock_gateway)
        query = RetrievalQuery(query_text="confidential", method="dense", top_k=2)
        results = engine.retrieve(query)
        assert len(results) <= 2
        assert all(r.method == "sparse" for r in results), (
            "Should fall back to sparse when embedding fails"
        )

    # ── T035: Hierarchy preservation ──

    def test_hierarchy_chain_populated_sparse(self, populated_db: str) -> None:
        """Sparse retrieval populates hierarchy_chain from stored heading_chain."""
        engine = RetrievalEngine(populated_db)
        query = RetrievalQuery(query_text="governing", method="sparse", top_k=5)
        results = engine.retrieve(query)
        assert len(results) > 0
        # c2 has 2-level hierarchy: ["Article 7", "Section 7.2"]
        c2 = next((r for r in results if r.chunk_id == "c2"), None)
        if c2 is not None:
            assert c2.hierarchy_chain == ["Article 7", "Section 7.2"]
            assert c2.parent_chunk_id == "c1"

    def test_hierarchy_chain_single_level(self, populated_db: str) -> None:
        """Single-level chunks have hierarchy_chain with just their own heading."""
        engine = RetrievalEngine(populated_db)
        query = RetrievalQuery(query_text="confidential", method="sparse", top_k=5)
        results = engine.retrieve(query)
        c1 = next((r for r in results if r.chunk_id == "c1"), None)
        if c1 is not None:
            assert c1.hierarchy_chain == ["Article 3"]
            assert c1.parent_chunk_id is None

    def test_hierarchy_chain_two_level(self, populated_db: str) -> None:
        """Two-level chunk has hierarchy chain with root and child heading."""
        engine = RetrievalEngine(populated_db)
        query = RetrievalQuery(query_text="governing", method="sparse", top_k=5)
        results = engine.retrieve(query)
        c2 = next((r for r in results if r.chunk_id == "c2"), None)
        if c2 is not None:
            assert len(c2.hierarchy_chain) == 2
            assert c2.hierarchy_chain[0] == "Article 7"
            assert c2.hierarchy_chain[1] == "Section 7.2"

    def test_hierarchy_chain_dense(self, populated_db: str) -> None:
        """Dense retrieval populates hierarchy_chain."""
        mock_gateway = MagicMock()
        mock_gateway.embed.return_value = [[0.3, 0.5, 0.2, 0.7]]

        engine = RetrievalEngine(populated_db, gateway=mock_gateway)
        query = RetrievalQuery(query_text="confidential", method="dense", top_k=5)
        results = engine.retrieve(query)
        assert len(results) > 0
        for r in results:
            assert isinstance(r.hierarchy_chain, list)
            assert len(r.hierarchy_chain) > 0

    def test_hierarchy_chain_hybrid(self, populated_db: str) -> None:
        """Hybrid retrieval populates hierarchy_chain."""
        mock_gateway = MagicMock()
        mock_gateway.embed.return_value = [[0.3, 0.5, 0.2, 0.7]]

        engine = RetrievalEngine(populated_db, gateway=mock_gateway)
        query = RetrievalQuery(query_text="confidential", method="hybrid", top_k=5)
        results = engine.retrieve(query)
        assert len(results) > 0
        for r in results:
            assert isinstance(r.hierarchy_chain, list)
            assert len(r.hierarchy_chain) > 0
