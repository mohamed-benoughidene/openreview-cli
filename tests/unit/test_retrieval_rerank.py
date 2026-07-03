"""Unit tests for Reranker class (T029)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from openreview_cli.retrieval.models import RetrievalResult
from openreview_cli.retrieval.rerank import Reranker


class TestRerankerInit:
    """Tests for Reranker.__init__."""

    def test_init_with_gateway(self) -> None:
        mock_gateway = MagicMock()
        reranker = Reranker(mock_gateway, model_id="test-cross-encoder")
        assert reranker.gateway is mock_gateway
        assert reranker.model_id == "test-cross-encoder"

    def test_init_default_model(self) -> None:
        mock_gateway = MagicMock()
        reranker = Reranker(mock_gateway)
        assert reranker.model_id == "lightrag-cross-encoder"

    def test_init_without_gateway(self) -> None:
        reranker = Reranker(None)  # type: ignore[arg-type]
        assert reranker.gateway is None


class TestRerankerRerank:
    """Tests for Reranker.rerank."""

    def test_rerank_returns_sorted_results(self) -> None:
        mock_gateway = MagicMock()
        # Simulate gateway.rerank returning scores for each pair
        mock_gateway.rerank.return_value = [
            {"score": 0.9, "index": 0},
            {"score": 0.7, "index": 1},
            {"score": 0.5, "index": 2},
        ]

        reranker = Reranker(mock_gateway, model_id="test-cross-encoder")
        candidates = [
            RetrievalResult(
                chunk_id="c1", text="text one", clause_heading="H1", clause_level=0,
                hierarchy_chain=["H1"], parent_chunk_id=None, score=0.3, method="hybrid",
            ),
            RetrievalResult(
                chunk_id="c2", text="text two", clause_heading="H2", clause_level=0,
                hierarchy_chain=["H2"], parent_chunk_id=None, score=0.6, method="hybrid",
            ),
            RetrievalResult(
                chunk_id="c3", text="text three", clause_heading="H3", clause_level=0,
                hierarchy_chain=["H3"], parent_chunk_id=None, score=0.1, method="hybrid",
            ),
        ]

        results = reranker.rerank("test query", candidates, top_k=2)

        assert len(results) == 2
        # Should be sorted by rerank_score descending
        assert results[0].rerank_score is not None
        assert results[1].rerank_score is not None
        assert results[0].rerank_score >= results[1].rerank_score
        # Method should indicate reranker was used
        assert all(r.method == "hybrid+rerank" for r in results)

    def test_rerank_empty_candidates(self) -> None:
        mock_gateway = MagicMock()
        reranker = Reranker(mock_gateway)
        results = reranker.rerank("test query", [], top_k=5)
        assert results == []

    def test_rerank_without_gateway_returns_original(self) -> None:
        reranker = Reranker(None)  # type: ignore[arg-type]
        candidates = [
            RetrievalResult(
                chunk_id="c1", text="text", clause_heading="H1", clause_level=0,
                hierarchy_chain=["H1"], parent_chunk_id=None, score=0.5, method="hybrid",
            ),
        ]
        results = reranker.rerank("test query", candidates, top_k=5)
        assert len(results) == 1
        assert results[0].chunk_id == "c1"
        assert results[0].rerank_score is None

    def test_rerank_top_k_respected(self) -> None:
        mock_gateway = MagicMock()
        mock_gateway.rerank.return_value = [
            {"score": 0.9, "index": 0},
            {"score": 0.8, "index": 1},
            {"score": 0.7, "index": 2},
        ]

        reranker = Reranker(mock_gateway, model_id="test-cross-encoder")
        candidates = [
            RetrievalResult(
                chunk_id=f"c{i}", text=f"text {i}", clause_heading=f"H{i}",
                clause_level=0, hierarchy_chain=[f"H{i}"], parent_chunk_id=None,
                score=0.1 * i, method="hybrid",
            )
            for i in range(3)
        ]

        results = reranker.rerank("test query", candidates, top_k=1)
        assert len(results) == 1


class TestRerankerValidate:
    """Tests for Reranker.validate."""

    def test_compute_precision_returns_zero_for_empty(self) -> None:
        mock_storage = MagicMock()
        reranker = Reranker(MagicMock(), model_id="test-cross-encoder")
        precision = reranker._compute_precision(mock_storage, [], "doc1")
        assert precision == 0.0

    def test_compute_precision_counts_relevant_headings(self) -> None:
        mock_storage = MagicMock()
        mock_storage.load_chunk.side_effect = [
            {"chunk_id": "c1", "text": "text", "clause_heading": "Confidentiality",
             "clause_level": 0, "heading_chain": '["Confidentiality"]',
             "parent_chunk_id": None, "char_start": 0, "char_end": 10},
            {"chunk_id": "c2", "text": "text", "clause_heading": "Governing Law",
             "clause_level": 0, "heading_chain": '["Governing Law"]',
             "parent_chunk_id": None, "char_start": 10, "char_end": 20},
            {"chunk_id": "c3", "text": "text", "clause_heading": "Indemnification",
             "clause_level": 0, "heading_chain": '["Indemnification"]',
             "parent_chunk_id": None, "char_start": 20, "char_end": 30},
        ]

        reranker = Reranker(MagicMock(), model_id="test-cross-encoder")
        # c1 (confidential) and c3 (indemnification) are relevant → 2/3
        precision = reranker._compute_precision(mock_storage, ["c1", "c2", "c3"], "doc1")
        assert precision == 2.0 / 3.0

    def test_validate_returns_comparison_structure(self) -> None:
        """validate() returns dict with expected keys."""
        mock_gateway = MagicMock()
        mock_gateway.rerank.return_value = [
            {"score": 0.9, "index": 0},
            {"score": 0.8, "index": 1},
        ]
        mock_storage = MagicMock()

        chunk_data = {
            "c1": {"chunk_id": "c1", "text": "confidential text",
                   "clause_heading": "Article 3 — Confidentiality", "clause_level": 0,
                   "heading_chain": '["Article 3"]', "parent_chunk_id": None,
                   "char_start": 0, "char_end": 100},
            "c2": {"chunk_id": "c2", "text": "indemnification text",
                   "clause_heading": "Article 8", "clause_level": 0,
                   "heading_chain": '["Article 8"]', "parent_chunk_id": None,
                   "char_start": 200, "char_end": 300},
            "c3": {"chunk_id": "c3", "text": "liability text",
                   "clause_heading": "Article 9", "clause_level": 0,
                   "heading_chain": '["Article 9"]', "parent_chunk_id": None,
                   "char_start": 400, "char_end": 500},
        }

        def _load_chunk(cid: str) -> dict | None:
            return chunk_data.get(cid)

        mock_storage.load_chunk.side_effect = _load_chunk
        mock_storage.search_fts.return_value = [
            ("c1", -2.0), ("c2", -1.5), ("c3", -1.0),
        ]
        mock_storage.insert_rerank_validation.return_value = 0  # T063: consecutive counter
        mock_storage.get_index_meta.return_value = {
            "document_id": "test-doc",
            "document_path": "/path/to/doc",
            "chunk_count": 3,
            "method": "sparse",
            "embedding_model": None,
            "embedding_dim": None,
            "index_timestamp": "2026-07-03T12:00:00Z",
            "index_status": "indexed",
            "db_size_bytes": 4096,
        }
        mock_storage.db_path = "/tmp/test.db"  # Doesn't need to exist for validate

        reranker = Reranker(mock_gateway, model_id="test-cross-encoder")
        result = reranker.validate(mock_storage)

        assert "with_reranker" in result
        assert "without_reranker" in result
        assert "degradation_pp" in result
        assert isinstance(result["with_reranker"], float)
        assert isinstance(result["without_reranker"], float)
        assert isinstance(result["degradation_pp"], float)
        assert 0.0 <= result["with_reranker"] <= 1.0
        assert 0.0 <= result["without_reranker"] <= 1.0


class TestConsecutiveDegradation:
    """T063: 3-consecutive-run counter for reranker degradation."""

    def test_consecutive_degradation_counter_via_storage(
        self, tmp_path: Path
    ) -> None:
        """Insert rerank validation records and verify consecutive counter."""
        from openreview_cli.retrieval.storage import RetrievalStorage

        db_path = tmp_path / "test_degradation.db"
        storage = RetrievalStorage(db_path)
        storage.create_schema()

        model_id = "test-cross-encoder"
        doc_type = "legal-nda"

        # First run: degradation (with < without => degradation_pp < 0)
        c1 = storage.insert_rerank_validation(
            model_id, doc_type, precision_with=0.2, precision_without=0.8, degradation_pp=-60.0,
        )
        assert c1 == 1, f"Expected 1, got {c1}"

        # Second consecutive degradation
        c2 = storage.insert_rerank_validation(
            model_id, doc_type, precision_with=0.3, precision_without=0.8, degradation_pp=-50.0,
        )
        assert c2 == 2, f"Expected 2, got {c2}"

        # Only 2 degradations → not yet flagged
        assert c2 < 3

        # Third consecutive degradation → should be >= 3
        c3 = storage.insert_rerank_validation(
            model_id, doc_type, precision_with=0.1, precision_without=0.8, degradation_pp=-70.0,
        )
        assert c3 == 3, f"Expected 3, got {c3}"

    def test_degradation_resets_after_improvement(
        self, tmp_path: Path
    ) -> None:
        """Consecutive counter resets to 0 after a non-degraded run."""
        from openreview_cli.retrieval.storage import RetrievalStorage

        db_path = tmp_path / "test_reset.db"
        storage = RetrievalStorage(db_path)
        storage.create_schema()

        model_id = "test-cross-encoder"
        doc_type = "legal-nda"

        # Two degradations
        storage.insert_rerank_validation(model_id, doc_type, 0.2, 0.8, -60.0)
        c2 = storage.insert_rerank_validation(model_id, doc_type, 0.1, 0.8, -70.0)
        assert c2 == 2

        # Improvement (with > without → degradation_pp > 0)
        c3 = storage.insert_rerank_validation(model_id, doc_type, 0.9, 0.8, 10.0)
        assert c3 == 0, f"Expected 0 (reset), got {c3}"

    def test_validate_returns_degraded_flag_after_three(
        self, tmp_path: Path
    ) -> None:
        """Reranker.validate() should set degraded=True after 3 consecutive degradations."""
        from unittest.mock import MagicMock

        from openreview_cli.retrieval.rerank import Reranker

        db_path = tmp_path / "test_degraded_flag.db"
        from openreview_cli.retrieval.storage import RetrievalStorage

        storage = RetrievalStorage(db_path)
        storage.create_schema()

        # Seed minimal index_meta and chunks
        storage.conn.execute(
            "INSERT INTO index_meta (document_id, document_path, chunk_count, method) "
            "VALUES ('test-doc', '/tmp/test.ndax', 2, 'sparse')"
        )
        storage.conn.execute(
            "INSERT INTO chunks (chunk_id, document_id, text, clause_heading, "
            "clause_level, heading_chain, char_start, char_end) "
            "VALUES ('c1', 'test-doc', 'confidential information text', "
            "'Confidentiality', 0, '[\"Confidentiality\"]', 0, 30)"
        )
        storage.conn.execute(
            "INSERT INTO chunks (chunk_id, document_id, text, clause_heading, "
            "clause_level, heading_chain, char_start, char_end) "
            "VALUES ('c2', 'test-doc', 'indemnification liability text', "
            "'Indemnification', 0, '[\"Indemnification\"]', 31, 70)"
        )
        storage.conn.commit()

        mock_gateway = MagicMock()
        # Reranker returns worse results each time (degradation)
        mock_gateway.rerank.return_value = [
            {"score": 0.1, "index": 0},
            {"score": 0.05, "index": 1},
        ]
        mock_storage = MagicMock(wraps=storage)
        mock_storage.search_fts.return_value = [
            ("c1", -2.0), ("c2", -1.5),
        ]
        mock_storage.load_chunk.side_effect = lambda cid: storage.load_chunk(cid)

        reranker = Reranker(mock_gateway, model_id="test-cross-encoder")

        # 3 consecutive runs with degradation
        result: dict[str, float | bool | int] = {"degraded": False, "consecutive_degradations": 0}
        for _i in range(3):
            result = reranker.validate(mock_storage)

        assert result["degraded"] is True
        assert result["consecutive_degradations"] >= 3
