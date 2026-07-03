"""Memory and streaming integration tests for retrieval pipeline (T040, T043, T044)."""

from __future__ import annotations

import time
import tracemalloc
from pathlib import Path
from typing import Any

import pytest

from openreview_cli.retrieval.engine import RetrievalEngine
from openreview_cli.retrieval.ingest import ingest_document
from openreview_cli.retrieval.models import RetrievalQuery

PEAK_MEMORY_LIMIT_BYTES = 100 * 1024 * 1024  # 100 MB


def _generate_chunks(count: int, doc_id: str = "test-doc") -> list[dict[str, Any]]:
    """Generate synthetic chunks for memory/performance testing."""
    chunks: list[dict[str, Any]] = []
    for i in range(count):
        # Alternate heading structures to simulate real documents
        article_num = i // 100 + 1
        section_num = (i % 100) // 10 + 1
        subsection_num = i % 10 + 1
        if i % 3 == 0:
            # Single-level (article only)
            heading_chain = [f"Article {article_num}"]
        elif i % 3 == 1:
            # Two-level (article > section)
            heading_chain = [
                f"Article {article_num}",
                f"Section {article_num}.{section_num}",
            ]
        else:
            # Three-level (article > section > subsection)
            heading_chain = [
                f"Article {article_num}",
                f"Section {article_num}.{section_num}",
                f"Subsection {article_num}.{section_num}.{subsection_num}",
            ]

        chunks.append(
            {
                "chunk_id": f"c{i:05d}",
                "document_id": doc_id,
                "text": (
                    f"This is chunk {i} containing legal text about confidentiality, "
                    f"governing law, indemnification, and limitation of liability."
                ),
                "clause_heading": heading_chain[-1],
                "clause_level": i % 3,
                "heading_chain": heading_chain,
                "parent_chunk_id": f"c{i:05d}" if i > 0 else None,
                "char_start": i * 200,
                "char_end": (i + 1) * 200,
            }
        )
    return chunks


class TestIngestMemory:
    """T040, T043: Memory and timing benchmarks for ingestion."""

    @pytest.mark.memory
    def test_ingest_500_chunks_peak_memory(self, tmp_path: Path) -> None:
        """Ingesting 500 chunks should peak <100 MB (ex-model)."""
        chunks = _generate_chunks(500)
        db_path = tmp_path / "test_500.db"

        tracemalloc.start()
        try:
            ingest_document(
                chunks,
                db_path,
                gateway=None,
                method="sparse",
            )
        finally:
            _current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

        assert peak < PEAK_MEMORY_LIMIT_BYTES, (
            f"Peak memory {peak / 1024 / 1024:.1f} MB exceeds 100 MB"
        )

    def test_ingest_200_chunks_under_10s(self, tmp_path: Path) -> None:
        """Ingesting 200 chunks (sparse) should complete in <10s."""
        chunks = _generate_chunks(200)
        db_path = tmp_path / "test_200.db"

        start = time.time()
        ingest_document(
            chunks,
            db_path,
            gateway=None,
            method="sparse",
        )
        elapsed = time.time() - start

        assert elapsed < 10.0, f"Ingest took {elapsed:.2f}s (limit: 10s)"


class TestRetrieveMemory:
    """T044: Memory benchmarks for retrieval."""

    @pytest.mark.memory
    def test_retrieve_500_chunks_peak_memory(self, tmp_path: Path) -> None:
        """Retrieving across 500 chunks should peak <100 MB."""
        chunks = _generate_chunks(500)
        db_path = tmp_path / "retrieve_500.db"

        ingest_document(chunks, db_path, gateway=None, method="sparse")

        engine = RetrievalEngine(db_path)
        query = RetrievalQuery(
            query_text="confidentiality governing law",
            method="sparse",
            top_k=5,
        )

        tracemalloc.start()
        try:
            results = engine.retrieve(query)
        finally:
            _current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

        assert peak < PEAK_MEMORY_LIMIT_BYTES, (
            f"Peak memory {peak / 1024 / 1024:.1f} MB exceeds 100 MB"
        )
        assert len(results) <= 5
