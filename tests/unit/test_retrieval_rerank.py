"""Unit tests for Reranker class (T029)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from openreview_cli.retrieval.models import RetrievalResult
from openreview_cli.retrieval.rerank import Reranker


def _candidate(chunk_id: str, score: float) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        text=f"text {chunk_id}",
        clause_heading=f"Article {chunk_id}",
        clause_level=0,
        hierarchy_chain=[f"Article {chunk_id}"],
        parent_chunk_id=None,
        score=score,
        method="hybrid",
    )


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
        assert reranker.model_id == "qwen3-reranker-0.6b"

    def test_init_without_gateway(self) -> None:
        reranker = Reranker(None)
        assert reranker.gateway is None


class TestRerankerRerank:
    """Tests for Reranker.rerank."""

    def test_rerank_returns_sorted_results(self) -> None:
        mock_gateway = MagicMock()
        # Simulate gateway.rerank returning scores for each pair
        mock_gateway.rerank.return_value = [
            {"index": 0, "relevance_score": 0.9},
            {"index": 1, "relevance_score": 0.7},
            {"index": 2, "relevance_score": 0.5},
        ]

        reranker = Reranker(mock_gateway, model_id="test-cross-encoder")
        candidates = [
            RetrievalResult(
                chunk_id="c1",
                text="text one",
                clause_heading="H1",
                clause_level=0,
                hierarchy_chain=["H1"],
                parent_chunk_id=None,
                score=0.3,
                method="hybrid",
            ),
            RetrievalResult(
                chunk_id="c2",
                text="text two",
                clause_heading="H2",
                clause_level=0,
                hierarchy_chain=["H2"],
                parent_chunk_id=None,
                score=0.6,
                method="hybrid",
            ),
            RetrievalResult(
                chunk_id="c3",
                text="text three",
                clause_heading="H3",
                clause_level=0,
                hierarchy_chain=["H3"],
                parent_chunk_id=None,
                score=0.1,
                method="hybrid",
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

    def test_rerank_labels_rows_with_the_candidate_method(self) -> None:
        mock_gateway = MagicMock()
        mock_gateway.rerank.return_value = [{"index": 0, "relevance_score": 0.9}]
        reranker = Reranker(mock_gateway, model_id="test-cross-encoder")
        candidates = [
            RetrievalResult(
                chunk_id="c1",
                text="t",
                clause_heading="H1",
                clause_level=0,
                hierarchy_chain=["H1"],
                parent_chunk_id=None,
                score=0.5,
                method="sparse",
            )
        ]

        results = reranker.rerank("q", candidates, top_k=1)

        assert results[0].method == "sparse+rerank"

    def test_rerank_uses_reranking_slot(self) -> None:
        """The gateway must be called with the 'reranking' slot, not the model id (B3)."""
        mock_gateway = MagicMock()
        mock_gateway.rerank.return_value = [
            {"index": 0, "relevance_score": 0.9},
            {"index": 1, "relevance_score": 0.7},
        ]

        reranker = Reranker(mock_gateway, model_id="test-cross-encoder")
        candidates = [
            RetrievalResult(
                chunk_id="c1",
                text="text one",
                clause_heading="H1",
                clause_level=0,
                hierarchy_chain=["H1"],
                parent_chunk_id=None,
                score=0.3,
                method="hybrid",
            ),
            RetrievalResult(
                chunk_id="c2",
                text="text two",
                clause_heading="H2",
                clause_level=0,
                hierarchy_chain=["H2"],
                parent_chunk_id=None,
                score=0.6,
                method="hybrid",
            ),
        ]

        reranker.rerank("test query", candidates, top_k=2)

        mock_gateway.rerank.assert_called_once()
        args = mock_gateway.rerank.call_args[0]
        assert args[0] == "reranking"
        assert args[0] != "test-cross-encoder"

    def test_rerank_empty_candidates(self) -> None:
        mock_gateway = MagicMock()
        reranker = Reranker(mock_gateway)
        results = reranker.rerank("test query", [], top_k=5)
        assert results == []

    def test_rerank_without_gateway_returns_original(self) -> None:
        reranker = Reranker(None)
        candidates = [
            RetrievalResult(
                chunk_id="c1",
                text="text",
                clause_heading="H1",
                clause_level=0,
                hierarchy_chain=["H1"],
                parent_chunk_id=None,
                score=0.5,
                method="hybrid",
            ),
        ]
        results = reranker.rerank("test query", candidates, top_k=5)
        assert len(results) == 1
        assert results[0].chunk_id == "c1"
        assert results[0].rerank_score is None

    def test_rerank_top_k_respected(self) -> None:
        mock_gateway = MagicMock()
        mock_gateway.rerank.return_value = [
            {"index": 0, "relevance_score": 0.9},
            {"index": 1, "relevance_score": 0.8},
            {"index": 2, "relevance_score": 0.7},
        ]

        reranker = Reranker(mock_gateway, model_id="test-cross-encoder")
        candidates = [
            RetrievalResult(
                chunk_id=f"c{i}",
                text=f"text {i}",
                clause_heading=f"H{i}",
                clause_level=0,
                hierarchy_chain=[f"H{i}"],
                parent_chunk_id=None,
                score=0.1 * i,
                method="hybrid",
            )
            for i in range(3)
        ]

        results = reranker.rerank("test query", candidates, top_k=1)
        assert len(results) == 1

    def test_rerank_reorders_from_gateway_relevance_score(self) -> None:
        """Regression guard for B1: gateway scores must change the order, not just annotate it."""
        mock_gateway = MagicMock()
        mock_gateway.rerank.return_value = [
            {"index": 2, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.5},
            {"index": 1, "relevance_score": 0.1},
        ]
        reranker = Reranker(mock_gateway, model_id="test-cross-encoder")
        candidates = [_candidate("c1", 0.9), _candidate("c2", 0.6), _candidate("c3", 0.1)]

        results = reranker.rerank("test query", candidates, top_k=3)

        assert [r.chunk_id for r in results] == ["c3", "c1", "c2"]
        assert [r.rerank_score for r in results] == [0.9, 0.5, 0.1]

    def test_rerank_raises_when_payload_lacks_relevance_score(self) -> None:
        """A payload the code cannot parse must fail loudly, not silently keep the input order."""
        mock_gateway = MagicMock()
        mock_gateway.rerank.return_value = [{"index": 0, "score": 0.9}]
        reranker = Reranker(mock_gateway, model_id="test-cross-encoder")

        with pytest.raises(KeyError):
            reranker.rerank("test query", [_candidate("c1", 0.5)], top_k=1)


class TestConsecutiveDegradation:
    """T063: 3-consecutive-run counter for reranker degradation."""

    def test_consecutive_degradation_counter_via_storage(self, tmp_path: Path) -> None:
        """Insert rerank validation records and verify consecutive counter."""
        from openreview_cli.retrieval.storage import RetrievalStorage

        db_path = tmp_path / "test_degradation.db"
        storage = RetrievalStorage(db_path)
        storage.create_schema()

        model_id = "test-cross-encoder"
        doc_type = "legal-nda"

        # First run: degradation (with < without => degradation_pp < 0)
        c1 = storage.insert_rerank_validation(
            model_id,
            doc_type,
            precision_with=0.2,
            precision_without=0.8,
            degradation_pp=-60.0,
        )
        assert c1 == 1, f"Expected 1, got {c1}"

        # Second consecutive degradation
        c2 = storage.insert_rerank_validation(
            model_id,
            doc_type,
            precision_with=0.3,
            precision_without=0.8,
            degradation_pp=-50.0,
        )
        assert c2 == 2, f"Expected 2, got {c2}"

        # Only 2 degradations → not yet flagged
        assert c2 < 3

        # Third consecutive degradation → should be >= 3
        c3 = storage.insert_rerank_validation(
            model_id,
            doc_type,
            precision_with=0.1,
            precision_without=0.8,
            degradation_pp=-70.0,
        )
        assert c3 == 3, f"Expected 3, got {c3}"

    def test_degradation_resets_after_improvement(self, tmp_path: Path) -> None:
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
