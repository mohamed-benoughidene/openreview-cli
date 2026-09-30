import json
import re
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import cast

import pytest

from openreview_cli.retrieval.engine import RetrievalEngine
from openreview_cli.retrieval.errors import IndexCorruptError
from openreview_cli.retrieval.ingest import clear_index, index_exists, ingest_document
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
        assert "chunk_embeddings" not in tables
        # The reranker was removed, so its validation tables are never created.
        assert "rerank_validation" not in tables
        assert "rerank_validation_log" not in tables

    def test_creates_fts_virtual_table(self, storage: RetrievalStorage) -> None:
        cursor = storage.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunk_fts'"
        )
        assert cursor.fetchone() is not None

    def test_fts_tokenizer_is_porter_unicode61(self, storage: RetrievalStorage) -> None:
        """FR-001: the FTS table is created with the ``porter unicode61`` tokenizer.

        Asserts on the DDL SQLite actually recorded, not on a constant in the source.
        """
        cursor = storage.conn.execute("SELECT sql FROM sqlite_master WHERE name='chunk_fts'")
        row = cursor.fetchone()
        assert row is not None, "chunk_fts was not created"
        ddl = cast("str", row["sql"])
        match = re.search(r"tokenize\s*=\s*'([^']+)'", ddl)
        assert match is not None, f"no tokenizer recorded in chunk_fts DDL: {ddl}"
        assert match.group(1) == "porter unicode61"

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
        assert "idx_embeddings_model_id" not in indexes

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


class TestIndexMeta:
    def test_set_and_get_index_status(self, storage: RetrievalStorage) -> None:
        storage.conn.execute(
            "INSERT INTO index_meta (document_id, document_path, method) VALUES (?, ?, ?)",
            (SAMPLE_CHUNK["document_id"], "/tmp/test.ndax", "sparse"),
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
            "INSERT INTO index_meta (document_id, document_path, method) VALUES (?, ?, ?)",
            ("doc-hash", "/tmp/test.ndax", "sparse"),
        )
        storage.conn.commit()

        meta = storage.get_index_meta()
        assert meta is not None
        assert meta["document_id"] == "doc-hash"
        assert meta["method"] == "sparse"


def _truncated_index(path: Path) -> Path:
    """Build a real index, then truncate it to half its length (#118's damage)."""
    ingest_document([dict(SAMPLE_CHUNK)], path)
    raw = path.read_bytes()
    path.write_bytes(raw[: len(raw) // 2])
    return path


class TestIndexMetaCorruption:
    """Issue #118: "not indexed", "empty" and "corrupt" are three separate answers."""

    def test_fresh_empty_database_is_not_indexed(self, db_path: Path) -> None:
        # A zero-byte file is SQLite's empty-database state: no index_meta table.
        assert RetrievalStorage(db_path).get_index_meta() is None

    def test_truncated_index_is_reported_as_corrupt(self, db_path: Path) -> None:
        _truncated_index(db_path)
        with pytest.raises(IndexCorruptError) as exc:
            RetrievalStorage(db_path).get_index_meta()
        assert str(db_path) in str(exc.value)

    def test_truncated_index_through_the_engine_is_corrupt(self, db_path: Path) -> None:
        _truncated_index(db_path)
        with pytest.raises(IndexCorruptError):
            RetrievalEngine(db_path).get_index_meta()


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


class TestSparseOnlySchema:
    """T1.2: the index carries no embedding storage at all."""

    def test_no_chunk_embeddings_table(self, storage: RetrievalStorage) -> None:
        cursor = storage.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row["name"] for row in cursor.fetchall()}
        assert "chunk_embeddings" not in tables

    def test_no_embeddings_index(self, storage: RetrievalStorage) -> None:
        cursor = storage.conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row["name"] for row in cursor.fetchall()}
        assert "idx_embeddings_model_id" not in indexes

    def test_index_meta_has_no_embedding_columns(self, storage: RetrievalStorage) -> None:
        cursor = storage.conn.execute("PRAGMA table_info(index_meta)")
        columns = {row["name"] for row in cursor.fetchall()}
        assert "embedding_model" not in columns
        assert "embedding_dim" not in columns

    def test_storage_exposes_no_embedding_helpers(self, storage: RetrievalStorage) -> None:
        assert not hasattr(storage, "insert_embedding")
        assert not hasattr(storage, "load_embedding")
        assert not hasattr(storage, "load_embeddings")
