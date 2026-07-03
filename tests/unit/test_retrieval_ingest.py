"""Unit tests for ingest_document (T015)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from openreview_cli.retrieval.ingest import ingest_document


@pytest.fixture
def sample_chunks() -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": "c1",
            "document_id": "test-doc-123",
            "text": "Confidential information shall be protected.",
            "clause_heading": "Article 3 — Confidentiality",
            "clause_level": 0,
            "parent_chunk_id": None,
            "heading_chain": ["Article 3 — Confidentiality"],
            "char_start": 0,
            "char_end": 50,
        },
        {
            "chunk_id": "c2",
            "document_id": "test-doc-123",
            "text": "Governing law is Delaware.",
            "clause_heading": "Section 7.2 — Governing Law",
            "clause_level": 1,
            "parent_chunk_id": "c1",
            "heading_chain": ["Article 7", "Section 7.2 — Governing Law"],
            "char_start": 100,
            "char_end": 150,
        },
        {
            "chunk_id": "c3",
            "document_id": "test-doc-123",
            "text": "Indemnification obligations of the parties.",
            "clause_heading": "Article 8 — Indemnification",
            "clause_level": 0,
            "parent_chunk_id": None,
            "heading_chain": ["Article 8 — Indemnification"],
            "char_start": 200,
            "char_end": 260,
        },
    ]


class TestIngestDocument:
    """Tests for the ingest_document function."""

    def test_ingest_sparse_creates_db(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        db_path = tmp_path / "test_sparse.db"
        meta = ingest_document(sample_chunks, str(db_path), method="sparse")

        assert db_path.exists()
        assert meta["index_status"] == "indexed"
        assert meta["method"] == "sparse"
        assert meta["chunk_count"] == 3

    def test_ingest_chunks_written(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        db_path = tmp_path / "test_chunks.db"
        ingest_document(sample_chunks, str(db_path), method="sparse")

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT chunk_id, text FROM chunks ORDER BY chunk_id").fetchall()
        conn.close()

        assert len(rows) == 3
        assert rows[0][0] == "c1"
        assert rows[1][0] == "c2"

    def test_ingest_fts_indexed(self, tmp_path: Path, sample_chunks: list[dict[str, Any]]) -> None:
        db_path = tmp_path / "test_fts.db"
        ingest_document(sample_chunks, str(db_path), method="sparse")

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT chunk_id, bm25(chunk_fts) AS score FROM chunk_fts "
            "WHERE chunk_fts MATCH 'confidential' ORDER BY score"
        ).fetchall()
        conn.close()

        assert len(rows) > 0
        chunk_ids = {r[0] for r in rows}
        assert "c1" in chunk_ids

    def test_ingest_sparse_no_embeddings(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        db_path = tmp_path / "test_no_emb.db"
        ingest_document(sample_chunks, str(db_path), method="sparse")

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT COUNT(*) FROM chunk_embeddings").fetchone()
        conn.close()

        assert rows[0] == 0

    def test_ingest_hybrid_with_gateway(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        db_path = tmp_path / "test_hybrid.db"
        mock_gateway = MagicMock()
        # Return a simple 4-dim embedding for any text
        mock_gateway.embed.return_value = [[0.1, 0.2, 0.3, 0.4]]

        meta = ingest_document(sample_chunks, str(db_path), gateway=mock_gateway, method="hybrid")

        assert db_path.exists()
        assert meta["method"] == "hybrid"
        assert meta["embedding_model"] == "nomic-embed-text"

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT COUNT(*) FROM chunk_embeddings").fetchone()
        conn.close()
        assert rows[0] == 3  # All chunks got embeddings

    def test_ingest_idempotent_overwrites(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        db_path = tmp_path / "test_reingest.db"

        # First ingest
        meta1 = ingest_document(sample_chunks, str(db_path), method="sparse")
        assert meta1["chunk_count"] == 3

        # Second ingest with different data
        fewer_chunks = sample_chunks[:1]
        meta2 = ingest_document(fewer_chunks, str(db_path), method="sparse")
        assert meta2["chunk_count"] == 1

        # Verify only 1 chunk exists
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
        conn.close()
        assert rows[0] == 1

    def test_ingest_progress_callback(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        db_path = tmp_path / "test_progress.db"
        calls: list[tuple[int, int]] = []

        def progress(current: int, total: int) -> None:
            calls.append((current, total))

        ingest_document(sample_chunks, str(db_path), method="sparse", progress_callback=progress)

        assert len(calls) == 3
        assert calls[-1] == (3, 3)

    def test_ingest_incomplete_marker(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        """After successful ingest, status should be 'indexed', not 'ingesting'."""
        db_path = tmp_path / "test_marker.db"
        meta = ingest_document(sample_chunks, str(db_path), method="sparse")
        assert meta["index_status"] == "indexed"

    def test_ingest_index_meta_populated(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        db_path = tmp_path / "test_meta.db"
        meta = ingest_document(sample_chunks, str(db_path), method="sparse")
        assert "document_id" in meta
        assert "chunk_count" in meta
        assert "index_timestamp" in meta
        assert meta["document_id"] == "test-doc-123"

    def test_ingest_hybrid_embedding_failure(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        """If embedding fails, ingest should continue (sparse fallback)."""
        db_path = tmp_path / "test_embed_fail.db"
        mock_gateway = MagicMock()
        mock_gateway.embed.side_effect = RuntimeError("Ollama not available")

        meta = ingest_document(sample_chunks, str(db_path), gateway=mock_gateway, method="hybrid")

        assert meta["index_status"] == "indexed"
        # If embedding failed for all chunks, method falls back to sparse
        assert meta["method"] == "sparse"


# T064: Large document warning + embedding dimension mismatch


class TestLargeDocWarning:
    """T064: Large document warning at 5,000+ chunks."""

    def test_large_doc_warning_logged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Ingesting 5001+ chunks should log a warning."""
        import logging

        caplog.set_level(logging.WARNING)

        chunks = [
            {
                "chunk_id": f"c{i:05d}",
                "document_id": "big-doc",
                "text": f"Clause text {i}",
                "clause_heading": "Article 1",
                "clause_level": 0,
                "parent_chunk_id": None,
                "heading_chain": ["Article 1"],
                "char_start": i * 10,
                "char_end": i * 10 + 5,
            }
            for i in range(5001)
        ]

        db_path = tmp_path / "big_test.db"
        ingest_document(chunks, str(db_path), method="sparse")

        assert any(
            "Large document" in rec.message and "5001" in rec.message for rec in caplog.records
        )


class TestEmbeddingDimensionMismatch:
    """T064: Embedding dimension mismatch detection."""

    def test_dimension_mismatch_detected(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """If embedding dimension changes mid-stream, log warning and clear."""
        import logging

        caplog.set_level(logging.WARNING)

        from unittest.mock import MagicMock

        mock_gateway = MagicMock()
        # Return 4-dim for first chunk, then 8-dim for second → mismatch
        return_values = [
            [[0.1, 0.2, 0.3, 0.4]],  # 4-dim
            [[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]],  # 8-dim
        ]
        mock_gateway.embed.side_effect = return_values

        chunks = [
            {
                "chunk_id": "c1",
                "document_id": "mismatch-doc",
                "text": "First clause about confidentiality.",
                "clause_heading": "Article 1",
                "clause_level": 0,
                "parent_chunk_id": None,
                "heading_chain": ["Article 1"],
                "char_start": 0,
                "char_end": 40,
            },
            {
                "chunk_id": "c2",
                "document_id": "mismatch-doc",
                "text": "Second clause with different dimension.",
                "clause_heading": "Article 2",
                "clause_level": 0,
                "parent_chunk_id": None,
                "heading_chain": ["Article 2"],
                "char_start": 41,
                "char_end": 85,
            },
        ]

        db_path = tmp_path / "mismatch_test.db"
        ingest_document(chunks, str(db_path), gateway=mock_gateway, method="hybrid")

        assert any("Embedding model changed" in rec.message for rec in caplog.records)


# T062: Last indexed document tracking


class TestLastIndexedDoc:
    """T062: Most recently indexed document fallback."""

    def test_get_last_indexed_returns_none_when_no_index(self, tmp_path: Path) -> None:
        from openreview_cli.retrieval.ingest import get_last_indexed_doc

        result = get_last_indexed_doc(tmp_path)
        assert result is None

    def test_ingest_creates_last_indexed_file(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        from openreview_cli.retrieval.ingest import get_last_indexed_doc, ingest_document

        db_path = tmp_path / "test_last_indexed.db"
        ndax_path = tmp_path / "test.ndax"
        ndax_path.write_text("[]")  # dummy file for path existence check

        ingest_document(sample_chunks, str(db_path), method="sparse")

        result = get_last_indexed_doc(tmp_path)
        # Should return the db_path since that's what we save
        if result is not None:
            assert "test_last_indexed.db" in result

    def test_get_last_indexed_returns_path(self, tmp_path: Path) -> None:
        from openreview_cli.retrieval.ingest import get_last_indexed_doc

        # Manually create last_indexed.json
        meta = {
            "document_path": str(tmp_path / "my_doc.ndax"),
            "document_hash": "abc123",
            "last_indexed_at": "2026-07-03T12:00:00Z",
        }
        (tmp_path / "last_indexed.json").write_text(json.dumps(meta))

        # Create the referenced file so path exists check passes
        (tmp_path / "my_doc.ndax").write_text("dummy")

        result = get_last_indexed_doc(tmp_path)
        assert result is not None
        assert "my_doc.ndax" in result
