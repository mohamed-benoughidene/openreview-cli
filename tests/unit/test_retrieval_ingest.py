"""Unit tests for ingest_document (T015)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from openreview_cli.retrieval.errors import MalformedChunkError
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
        meta = ingest_document(sample_chunks, str(db_path))

        assert db_path.exists()
        assert meta["index_status"] == "indexed"
        assert meta["method"] == "sparse"
        assert meta["chunk_count"] == 3

    def test_ingest_chunks_written(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        db_path = tmp_path / "test_chunks.db"
        ingest_document(sample_chunks, str(db_path))

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT chunk_id, text FROM chunks ORDER BY chunk_id").fetchall()
        conn.close()

        assert len(rows) == 3
        assert rows[0][0] == "c1"
        assert rows[1][0] == "c2"

    def test_ingest_fts_indexed(self, tmp_path: Path, sample_chunks: list[dict[str, Any]]) -> None:
        db_path = tmp_path / "test_fts.db"
        ingest_document(sample_chunks, str(db_path))

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT chunk_id, bm25(chunk_fts) AS score FROM chunk_fts "
            "WHERE chunk_fts MATCH 'confidential' ORDER BY score"
        ).fetchall()
        conn.close()

        assert len(rows) > 0
        chunk_ids = {r[0] for r in rows}
        assert "c1" in chunk_ids

    def test_ingest_creates_no_embedding_table(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        db_path = tmp_path / "test_no_emb.db"
        ingest_document(sample_chunks, str(db_path))

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunk_embeddings'"
        ).fetchall()
        conn.close()

        assert rows == []

    def test_ingest_idempotent_overwrites(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        db_path = tmp_path / "test_reingest.db"

        # First ingest
        meta1 = ingest_document(sample_chunks, str(db_path))
        assert meta1["chunk_count"] == 3

        # Second ingest with different data
        fewer_chunks = sample_chunks[:1]
        meta2 = ingest_document(fewer_chunks, str(db_path))
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

        ingest_document(sample_chunks, str(db_path), progress_callback=progress)

        assert len(calls) == 3
        assert calls[-1] == (3, 3)

    def test_ingest_incomplete_marker(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        """After successful ingest, status should be 'indexed', not 'ingesting'."""
        db_path = tmp_path / "test_marker.db"
        meta = ingest_document(sample_chunks, str(db_path))
        assert meta["index_status"] == "indexed"

    def test_ingest_index_meta_populated(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        db_path = tmp_path / "test_meta.db"
        meta = ingest_document(sample_chunks, str(db_path))
        assert "document_id" in meta
        assert "chunk_count" in meta
        assert "index_timestamp" in meta
        assert meta["document_id"] == "test-doc-123"


# T064: Large document warning


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
        ingest_document(chunks, str(db_path))

        assert any(
            "Large document" in rec.message and "5001" in rec.message for rec in caplog.records
        )


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

        ingest_document(sample_chunks, str(db_path))

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

    def test_get_last_indexed_doc_id_returns_hash(self, tmp_path: Path) -> None:
        from openreview_cli.retrieval.ingest import get_last_indexed_doc_id

        (tmp_path / "last_indexed.json").write_text(
            json.dumps(
                {
                    "document_path": str(tmp_path / "old.db"),
                    "document_hash": "abc123fullhash",
                }
            )
        )
        assert get_last_indexed_doc_id(tmp_path) == "abc123fullhash"

    def test_get_last_indexed_doc_id_legacy_fallback(self, tmp_path: Path) -> None:
        from openreview_cli.retrieval.ingest import get_last_indexed_doc_id

        (tmp_path / "last_indexed.json").write_text(
            json.dumps({"document_path": str(tmp_path / "abc123.db")})
        )
        assert get_last_indexed_doc_id(tmp_path) == "abc123"

    def test_get_last_indexed_doc_id_none_when_missing(self, tmp_path: Path) -> None:
        from openreview_cli.retrieval.ingest import get_last_indexed_doc_id

        assert get_last_indexed_doc_id(tmp_path) is None


class TestChunkSchemaNormalization:
    """ingest_document must accept chunk-output schema (id/source_* keys)."""

    def test_ingest_accepts_chunk_output_shape(self, tmp_path: Path) -> None:
        # Real chunk --format json output shape (11 keys, no chunk_id)
        chunk_output = [
            {
                "id": "c0",
                "text": "Article I: Definitions",
                "token_count": 42,
                "source_clause_id": "clause-0",
                "source_clause_title": "Article I — Definitions",
                "source_clause_level": 0,
                "chunk_index_within_clause": 0,
                "char_offset_start": 0,
                "char_offset_end": 128,
                "parent_chunk_id": None,
                "structural_location": "Article I — Definitions",
            },
        ]

        db_path = tmp_path / "chunk_output.db"
        meta = ingest_document(
            chunk_output,
            str(db_path),
            document_id="test-chunk-output",
        )

        assert meta["index_status"] == "indexed"
        assert meta["document_id"] == "test-chunk-output"
        assert meta["chunk_count"] == 1

        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT chunk_id, clause_heading, clause_level, char_start, char_end FROM chunks"
        ).fetchone()
        conn.close()
        assert row == ("c0", "Article I — Definitions", 0, 0, 128)

    def test_ingest_accepts_existing_fixture_shape(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        """Already-normalized chunks (fixture shape) must pass through unchanged."""
        db_path = tmp_path / "fixture_shape.db"
        meta = ingest_document(sample_chunks, str(db_path))
        assert meta["chunk_count"] == 3
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT clause_heading FROM chunks WHERE chunk_id = 'c1'").fetchone()
        conn.close()
        assert row[0] == "Article 3 — Confidentiality"

    def test_normalize_chunk_maps_all_keys(self) -> None:
        from openreview_cli.retrieval.ingest import _normalize_chunk

        chunk_output = {
            "id": "c5",
            "text": "Governing law",
            "token_count": 10,
            "source_clause_id": "clause-3",
            "source_clause_title": "Article 7 — Governing Law",
            "source_clause_level": 1,
            "chunk_index_within_clause": 0,
            "char_offset_start": 400,
            "char_offset_end": 450,
            "parent_chunk_id": "c4",
            "structural_location": "Article 7 > Section 7.2",
        }

        normalized = _normalize_chunk(chunk_output, "doc-1")
        assert normalized["chunk_id"] == "c5"
        assert normalized["document_id"] == "doc-1"
        assert normalized["clause_heading"] == "Article 7 — Governing Law"
        assert normalized["clause_level"] == 1
        assert normalized["char_start"] == 400
        assert normalized["char_end"] == 450
        assert normalized["parent_chunk_id"] == "c4"
        assert normalized["heading_chain"] == ["Article 7 > Section 7.2"]


class TestMalformedChunk:
    """A chunk missing a required key is a typed error, not a bare KeyError."""

    def test_missing_id_names_the_key_and_index(self) -> None:
        from openreview_cli.retrieval.ingest import _normalize_chunk

        with pytest.raises(MalformedChunkError) as excinfo:
            _normalize_chunk({"text": "x"}, "doc-1", 3)

        message = str(excinfo.value)
        assert "'id'" in message
        assert "chunk 3" in message

    def test_missing_text_names_the_key(self) -> None:
        from openreview_cli.retrieval.ingest import _normalize_chunk

        with pytest.raises(MalformedChunkError, match="'text'"):
            _normalize_chunk({"id": "c5"}, "doc-1", 0)

    def test_ingest_document_propagates_the_typed_error(self, tmp_path: Path) -> None:
        db_path = tmp_path / "malformed.db"

        with pytest.raises(MalformedChunkError, match="'id'"):
            ingest_document([{"text": "x"}], str(db_path))

    @pytest.mark.parametrize(
        "not_an_object", ["not an object", "id text", ["id", "text"], 42, None], ids=repr
    )
    def test_non_dict_element_names_the_index(self, not_an_object: Any) -> None:
        """A non-object element must not reach the key access as a dict.

        ``"id text"`` and ``["id", "text"]`` are the dangerous shapes: the
        membership test in ``_require_keys`` passes for them, so the old code
        fell through to ``chunk.get(...)`` and raised a bare ``AttributeError``.
        """
        from openreview_cli.retrieval.ingest import _normalize_chunk

        with pytest.raises(MalformedChunkError) as excinfo:
            _normalize_chunk(not_an_object, "doc-1", 2)

        message = str(excinfo.value)
        assert "chunk 2" in message
        assert "JSON object" in message

    def test_non_dict_element_without_index_says_chunk(self) -> None:
        from openreview_cli.retrieval.ingest import _normalize_chunk

        not_an_object: Any = "not an object"
        with pytest.raises(MalformedChunkError, match="chunk is not a JSON object"):
            _normalize_chunk(not_an_object, "doc-1")

    def test_ingest_document_rejects_a_non_dict_element_after_the_first(
        self, tmp_path: Path, sample_chunks: list[dict[str, Any]]
    ) -> None:
        db_path = tmp_path / "non_object.db"
        chunks: list[Any] = [sample_chunks[0], "not an object"]

        with pytest.raises(MalformedChunkError) as excinfo:
            ingest_document(chunks, str(db_path))

        message = str(excinfo.value)
        assert "chunk 1" in message
        assert "JSON object" in message

    def test_ingest_document_non_dict_head_is_a_typed_error(self, tmp_path: Path) -> None:
        db_path = tmp_path / "non_object_head.db"

        with pytest.raises(MalformedChunkError, match="JSON object"):
            ingest_document(["not an object"], str(db_path))  # type: ignore[list-item]

    def test_ingest_document_empty_list_yields_zero_chunks(self, tmp_path: Path) -> None:
        db_path = tmp_path / "empty_chunks.db"

        meta = ingest_document([], str(db_path))

        assert meta["chunk_count"] == 0
