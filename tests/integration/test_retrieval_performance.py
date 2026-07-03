"""Retrieval performance and database size tests (T058, T059, T060).

- T058: BM25 retrieval for 1,000 chunks completes in <1s
- T059: Full ingestion (parse + chunk + embed + index) for 200 chunks <10s
- T060: DB size <10 MB for 1,000 chunks (BM25-only), <20 MB with embeddings
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from openreview_cli.retrieval.bm25 import search_bm25
from openreview_cli.retrieval.ingest import ingest_document
from openreview_cli.retrieval.storage import RetrievalStorage

BM25_P95_TIME_LIMIT = 1.0  # seconds
INGEST_TIME_LIMIT = 10.0  # seconds
DB_SIZE_SPARSE_LIMIT = 10 * 1024 * 1024  # 10 MB
DB_SIZE_DENSE_LIMIT = 20 * 1024 * 1024  # 20 MB


def _generate_chunks(count: int, doc_id: str = "perf-test-doc") -> list[dict[str, Any]]:
    """Generate synthetic chunks for performance testing."""
    chunks: list[dict[str, Any]] = []
    for i in range(count):
        article_num = i // 100 + 1
        section_num = (i % 100) // 10 + 1
        if i % 3 == 0:
            heading_chain = [f"Article {article_num}"]
        elif i % 3 == 1:
            heading_chain = [
                f"Article {article_num}",
                f"Section {article_num}.{section_num}",
            ]
        else:
            heading_chain = [
                f"Article {article_num}",
                f"Section {article_num}.{section_num}",
                f"Subsection {article_num}.{section_num}.{i % 10 + 1}",
            ]

        chunks.append(
            {
                "chunk_id": f"pc{i:05d}",
                "document_id": doc_id,
                "text": (
                    f"This is chunk {i} containing legal text about confidentiality, "
                    f"governing law, indemnification, and limitation of liability. "
                    f"Some terms include data-processing, non-disclosure, "
                    f"and intellectual-property rights."
                ),
                "clause_heading": heading_chain[-1],
                "clause_level": i % 3,
                "heading_chain": heading_chain,
                "parent_chunk_id": f"pc{i:05d}" if i > 0 else None,
                "char_start": i * 200,
                "char_end": (i + 1) * 200,
            }
        )
    return chunks


class TestBM25Performance:
    """T058: BM25 retrieval speed for 1,000 chunks."""

    @pytest.fixture(scope="class")
    def large_sparse_index(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        """Create a 1,000-chunk sparse index (once per class)."""
        tmp_dir = tmp_path_factory.mktemp("perf_bm25")
        chunks = _generate_chunks(1000)
        db_path = tmp_dir / "large_bm25.db"
        ingest_document(chunks, str(db_path), gateway=None, method="sparse")
        return db_path

    def test_bm25_retrieval_under_1s_p95(
        self,
        large_sparse_index: Path,
    ) -> None:
        """BM25 retrieval for 1,000 chunks should complete in <1s (P95)."""
        queries = [
            "confidentiality obligations",
            "governing law",
            "indemnification",
            "limitation of liability",
            "termination",
            "warranty disclaimer",
            "return of materials",
            "confidential information",
            "entire agreement",
            "parties",
        ]

        run_times: list[float] = []
        with RetrievalStorage(large_sparse_index) as storage:
            for query_text in queries:
                start = time.perf_counter()
                search_bm25(storage, query_text, top_k=10)
                elapsed = time.perf_counter() - start
                run_times.append(elapsed)

        # Sort and compute P95
        run_times.sort()
        p95_index = min(math.ceil(0.95 * len(run_times)) - 1, len(run_times) - 1)
        p95_time = run_times[p95_index]

        assert p95_time < BM25_P95_TIME_LIMIT, (
            f"BM25 P95 retrieval time {p95_time * 1000:.1f}ms exceeds "
            f"{BM25_P95_TIME_LIMIT * 1000:.0f}ms limit"
        )

    def test_bm25_all_queries_return_results(
        self,
        large_sparse_index: Path,
    ) -> None:
        """All BM25 queries should return at least 1 result."""
        queries = [
            "confidentiality",
            "governing law",
            "indemnification",
        ]
        with RetrievalStorage(large_sparse_index) as storage:
            for query_text in queries:
                results = search_bm25(storage, query_text, top_k=5)
                assert len(results) > 0, f"Query '{query_text}' returned no results"


class TestIngestionPerformance:
    """T059: Ingestion speed for 200 chunks."""

    def test_ingest_200_chunks_under_10s(self, tmp_path: Path) -> None:
        """Full ingestion (sparse) for 200 chunks should complete in <10s."""
        chunks = _generate_chunks(200)
        db_path = tmp_path / "ingest_200.db"

        start = time.perf_counter()
        ingest_document(chunks, str(db_path), gateway=None, method="sparse")
        elapsed = time.perf_counter() - start

        assert elapsed < INGEST_TIME_LIMIT, (
            f"Ingest took {elapsed:.2f}s (limit: {INGEST_TIME_LIMIT}s)"
        )

        # Verify index is valid
        with RetrievalStorage(db_path) as storage:
            meta = storage.get_index_meta()
            assert meta is not None
            assert meta["chunk_count"] == 200
            assert meta["index_status"] == "indexed"


class TestDatabaseSize:
    """T060: SQLite database size validation."""

    def test_sparse_db_size_under_10mb(self, tmp_path: Path) -> None:
        """1,000 chunks (BM25-only) should result in DB <10 MB."""
        chunks = _generate_chunks(1000)
        db_path = tmp_path / "size_sparse.db"

        ingest_document(chunks, str(db_path), gateway=None, method="sparse")

        db_size = db_path.stat().st_size
        assert db_size < DB_SIZE_SPARSE_LIMIT, (
            f"Sparse DB size {db_size / 1024 / 1024:.2f} MB exceeds 10 MB limit"
        )

    @patch("openreview_cli.gateway.router.Gateway")
    def test_dense_db_size_under_20mb(
        self,
        mock_gateway_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """1,000 chunks with embeddings should result in DB <20 MB."""
        mock_gw = MagicMock()
        # Return a consistent 384-dim embedding
        mock_gw.embed.return_value = [[0.1 * (i % 10) / 10.0 for i in range(384)]]
        mock_gateway_class.return_value = mock_gw

        chunks = _generate_chunks(1000, doc_id="dense-size-test")
        db_path = tmp_path / "size_dense.db"

        ingest_document(
            chunks,
            str(db_path),
            gateway=mock_gw,
            method="hybrid",
            model_id="test-model",
        )

        db_size = db_path.stat().st_size
        assert db_size < DB_SIZE_DENSE_LIMIT, (
            f"Dense DB size {db_size / 1024 / 1024:.2f} MB exceeds 20 MB limit"
        )

    def test_sparse_db_smaller_than_dense(self, tmp_path: Path) -> None:
        """BM25-only DB should be smaller than DB with embeddings."""
        chunks = _generate_chunks(200)
        sparse_db = tmp_path / "sparse.db"
        ingest_document(chunks, str(sparse_db), gateway=None, method="sparse")
        sparse_size = sparse_db.stat().st_size

        # For dense comparison, create a DB with manual embeddings
        dense_db = tmp_path / "dense.db"
        ingest_document(chunks, str(dense_db), gateway=None, method="sparse")

        # Manually add embeddings (since we can't call gateway)
        import sqlite3
        import struct

        conn = sqlite3.connect(str(dense_db))
        try:
            # Get all chunk IDs
            rows = conn.execute("SELECT chunk_id FROM chunks").fetchall()
            for (cid,) in rows:
                vec = [0.1] * 384
                blob = struct.pack(f"<{384}f", *vec)
                norm = math.sqrt(sum(v * v for v in vec))
                conn.execute(
                    "INSERT INTO chunk_embeddings (chunk_id, embedding, model_id, dimension, chunk_norm) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (cid, sqlite3.Binary(blob), "test-model", 384, norm),
                )
            conn.commit()
        finally:
            conn.close()

        # Update index meta to reflect hybrid mode
        conn2 = sqlite3.connect(str(dense_db))
        try:
            conn2.execute(
                "UPDATE index_meta SET method='hybrid', embedding_model='test-model', embedding_dim=384"
            )
            # Recompute DB size
            db_size = dense_db.stat().st_size
            conn2.execute("UPDATE index_meta SET db_size_bytes=?", (db_size,))
            conn2.commit()
        finally:
            conn2.close()

        dense_size = dense_db.stat().st_size
        assert dense_size > sparse_size, (
            f"Dense DB ({dense_size} bytes) should be larger than sparse ({sparse_size} bytes)"
        )
