import json
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import cast

import pytest

from openreview_cli.retrieval.ingest import clear_index, index_exists
from openreview_cli.retrieval.storage import RetrievalStorage

SAMPLE_CHUNK = {
    "chunk_id": "chunk-001",
    "document_id": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
    "text": "This is a sample clause text for testing.",
    "clause_heading": "Article 1 — Test",
    "clause_level": 0,
    "parent_chunk_id": None,
    "heading_chain": ["Article 1 — Test"],
    "char_start": 0,
    "char_end": 42,
}


@pytest.fixture
def db_path() -> Generator[Path, None, None]:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink()


@pytest.fixture
def storage(db_path: Path) -> RetrievalStorage:
    s = RetrievalStorage(db_path)
    s.create_schema()
    return s


class TestSchemaCreation:
    def test_creates_all_tables(self, storage: RetrievalStorage) -> None:
        cursor = storage.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        assert "index_meta" in tables
        assert "chunks" in tables
        assert "chunk_embeddings" in tables
        assert "rerank_validation" in tables

    def test_creates_fts_virtual_table(self, storage: RetrievalStorage) -> None:
        cursor = storage.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunk_fts'"
        )
        assert cursor.fetchone() is not None

    def test_creates_triggers(self, storage: RetrievalStorage) -> None:
        cursor = storage.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name"
        )
        triggers = {row["name"] for row in cursor.fetchall()}
        assert "chunks_ai" in triggers
        assert "chunks_ad" in triggers
        assert "chunks_au" in triggers

    def test_creates_indexes(self, storage: RetrievalStorage) -> None:
        cursor = storage.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        )
        indexes = {row["name"] for row in cursor.fetchall()}
        assert "idx_chunks_document_id" in indexes
        assert "idx_chunks_parent" in indexes
        assert "idx_chunks_clause_level" in indexes
        assert "idx_embeddings_model_id" in indexes

    def test_schema_is_idempotent(self, storage: RetrievalStorage) -> None:
        # Calling create_schema twice should not raise
        storage.create_schema()


class TestInsertChunk:
    def test_inserts_chunk(self, storage: RetrievalStorage) -> None:
        # First insert index_meta row (FK dependency)
        storage.conn.execute(
            "INSERT INTO index_meta (document_id, document_path) VALUES (?, ?)",
            (SAMPLE_CHUNK["document_id"], "/tmp/test.ndax"),
        )
        storage.conn.commit()

        storage.insert_chunk(SAMPLE_CHUNK)
        chunk = storage.load_chunk("chunk-001")
        assert chunk is not None
        assert chunk["text"] == "This is a sample clause text for testing."
        assert chunk["clause_heading"] == "Article 1 — Test"

    def test_inserts_with_parent(self, storage: RetrievalStorage) -> None:
        storage.conn.execute(
            "INSERT INTO index_meta (document_id, document_path) VALUES (?, ?)",
            (SAMPLE_CHUNK["document_id"], "/tmp/test.ndax"),
        )
        storage.conn.commit()
        storage.insert_chunk(SAMPLE_CHUNK)

        child = dict(SAMPLE_CHUNK)
        child["chunk_id"] = "chunk-002"
        child["parent_chunk_id"] = "chunk-001"
        child["text"] = "Child clause"
        child["heading_chain"] = ["Article 1 — Test", "Section 1.1"]
        child["char_start"] = 43
        child["char_end"] = 60
        storage.insert_chunk(child)

        loaded = storage.load_chunk("chunk-002")
        assert loaded is not None
        assert loaded["parent_chunk_id"] == "chunk-001"

    def test_heading_chain_serialized(self, storage: RetrievalStorage) -> None:
        storage.conn.execute(
            "INSERT INTO index_meta (document_id, document_path) VALUES (?, ?)",
            (SAMPLE_CHUNK["document_id"], "/tmp/test.ndax"),
        )
        storage.conn.commit()
        storage.insert_chunk(SAMPLE_CHUNK)
        chunk = storage.load_chunk("chunk-001")
        assert chunk is not None
        chain = json.loads(chunk["heading_chain"])
        assert chain == ["Article 1 — Test"]


class TestFtsSync:
    """Tests that the FTS5 virtual table is kept in sync via triggers."""

    def test_fts_populated_on_insert(self, storage: RetrievalStorage) -> None:
        storage.conn.execute(
            "INSERT INTO index_meta (document_id, document_path) VALUES (?, ?)",
            (SAMPLE_CHUNK["document_id"], "/tmp/test.ndax"),
        )
        storage.conn.commit()
        storage.insert_chunk(SAMPLE_CHUNK)

        results = storage.search_fts("sample clause", 5)
        assert len(results) >= 1
        assert results[0][0] == "chunk-001"

    def test_fts_returns_bm25_scores(self, storage: RetrievalStorage) -> None:
        storage.conn.execute(
            "INSERT INTO index_meta (document_id, document_path) VALUES (?, ?)",
            (SAMPLE_CHUNK["document_id"], "/tmp/test.ndax"),
        )
        storage.conn.commit()
        storage.insert_chunk(SAMPLE_CHUNK)

        results = storage.search_fts("sample clause", 5)
        # bm25() returns negative scores where more negative = better
        assert len(results) > 0
        chunk_id, score = results[0]
        assert chunk_id == "chunk-001"
        assert score < 0  # BM25 returns negative values

    def test_fts_multiple_chunks_ranked(self, storage: RetrievalStorage) -> None:
        storage.conn.execute(
            "INSERT INTO index_meta (document_id, document_path) VALUES (?, ?)",
            (SAMPLE_CHUNK["document_id"], "/tmp/test.ndax"),
        )
        storage.conn.commit()

        texts = [
            "This clause contains the word indemnification.",
            "This clause is about something else.",
        ]
        chunks = [
            {
                **SAMPLE_CHUNK,
                "chunk_id": f"chunk-{i:03d}",
                "text": texts[i % 2],
            }
            for i in range(10)
        ]
        for c in chunks:
            storage.insert_chunk(c)

        results = storage.search_fts("indemnification", 5)
        assert len(results) > 0
        # All results should contain "indemnification"
        for chunk_id, _score in results:
            match = cast("str", next(c["text"] for c in chunks if c["chunk_id"] == chunk_id))
            assert "indemnification" in match


class TestEmbeddings:
    def test_insert_and_load_embedding(self, storage: RetrievalStorage) -> None:
        storage.conn.execute(
            "INSERT INTO index_meta (document_id, document_path) VALUES (?, ?)",
            (SAMPLE_CHUNK["document_id"], "/tmp/test.ndax"),
        )
        storage.conn.commit()
        storage.insert_chunk(SAMPLE_CHUNK)

        embedding = b"\x00\x00\x80?\x00\x00\x00@"  # 2 floats: 1.0, 2.0
        storage.insert_embedding("chunk-001", embedding, "nomic-embed-text", 2, 2.236)

        loaded = storage.load_embedding("chunk-001")
        assert loaded is not None
        assert loaded[0] == embedding
        assert loaded[1] == pytest.approx(2.236)

    def test_load_embedding_not_found(self, storage: RetrievalStorage) -> None:
        result = storage.load_embedding("nonexistent")
        assert result is None

    def test_load_embeddings_streams_all(self, storage: RetrievalStorage) -> None:
        storage.conn.execute(
            "INSERT INTO index_meta (document_id, document_path) VALUES (?, ?)",
            (SAMPLE_CHUNK["document_id"], "/tmp/test.ndax"),
        )
        storage.conn.commit()

        for i in range(3):
            chunk = {**SAMPLE_CHUNK, "chunk_id": f"chunk-{i:03d}"}
            storage.insert_chunk(chunk)
            storage.insert_embedding(
                f"chunk-{i:03d}",
                b"\x00\x00\x80?",
                "nomic-embed-text",
                1,
                1.0,
            )

        embeddings = list(storage.load_embeddings())
        assert len(embeddings) == 3
        chunk_ids = {e[0] for e in embeddings}
        assert chunk_ids == {"chunk-000", "chunk-001", "chunk-002"}

    def test_embedding_on_delete_cascade(self, storage: RetrievalStorage) -> None:
        storage.conn.execute(
            "INSERT INTO index_meta (document_id, document_path) VALUES (?, ?)",
            (SAMPLE_CHUNK["document_id"], "/tmp/test.ndax"),
        )
        storage.conn.commit()
        storage.insert_chunk(SAMPLE_CHUNK)
        storage.insert_embedding("chunk-001", b"\x00\x00\x80?", "test", 1, 1.0)

        storage.conn.execute("DELETE FROM chunks WHERE chunk_id = 'chunk-001'")
        storage.conn.commit()

        assert storage.load_embedding("chunk-001") is None


class TestIndexMeta:
    def test_set_and_get_index_status(self, storage: RetrievalStorage) -> None:
        storage.conn.execute(
            "INSERT INTO index_meta (document_id, document_path, method) VALUES (?, ?, ?)",
            (SAMPLE_CHUNK["document_id"], "/tmp/test.ndax", "hybrid"),
        )
        storage.conn.commit()

        storage.set_index_status("indexed")
        meta = storage.get_index_meta()
        assert meta is not None
        assert meta["index_status"] == "indexed"

    def test_get_index_meta_returns_none_when_empty(self, storage: RetrievalStorage) -> None:
        meta = storage.get_index_meta()
        assert meta is None

    def test_get_index_meta_returns_fields(self, storage: RetrievalStorage) -> None:
        storage.conn.execute(
            "INSERT INTO index_meta (document_id, document_path, method, embedding_model, embedding_dim) "
            "VALUES (?, ?, ?, ?, ?)",
            ("doc-hash", "/tmp/test.ndax", "hybrid", "nomic-embed-text", 1024),
        )
        storage.conn.commit()

        meta = storage.get_index_meta()
        assert meta is not None
        assert meta["document_id"] == "doc-hash"
        assert meta["method"] == "hybrid"
        assert meta["embedding_model"] == "nomic-embed-text"


class TestClearIndex:
    def test_clear_index_removes_db_file(self, db_path: Path) -> None:
        storage = RetrievalStorage(db_path)
        storage.create_schema()
        storage.conn.execute(
            "INSERT INTO index_meta (document_id, document_path) VALUES (?, ?)",
            ("hash", "/tmp/test.ndax"),
        )
        storage.conn.commit()
        storage.close()

        assert index_exists(db_path) is True
        clear_index(db_path)
        assert index_exists(db_path) is False

    def test_clear_index_silent_if_missing(self) -> None:
        path = Path("/tmp/nonexistent-test-db-12345.db")
        clear_index(path)  # should not raise
