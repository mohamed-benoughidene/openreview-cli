import pytest

from openreview_cli.retrieval.models import IndexMeta, RetrievalQuery, RetrievalResult


class TestRetrievalQuery:
    def test_creates_with_defaults(self) -> None:
        q = RetrievalQuery(query_text="confidentiality clause")
        assert q.query_text == "confidentiality clause"
        assert q.method == "hybrid"
        assert q.top_k == 5
        assert q.rerank is False
        assert q.rerank_depth == 20
        assert q.force_rerank is False

    def test_creates_with_all_fields(self) -> None:
        q = RetrievalQuery(
            query_text="limitation of liability",
            method="sparse",
            top_k=10,
            rerank=True,
            rerank_depth=15,
            force_rerank=True,
        )
        assert q.query_text == "limitation of liability"
        assert q.method == "sparse"
        assert q.top_k == 10
        assert q.rerank is True
        assert q.rerank_depth == 15
        assert q.force_rerank is True

    def test_accepts_dense_method(self) -> None:
        q = RetrievalQuery(query_text="test", method="dense")
        assert q.method == "dense"

    def test_rejects_empty_query(self) -> None:
        with pytest.raises(ValueError) as exc:
            RetrievalQuery(query_text="")
        assert "non-empty" in str(exc.value).lower()

    def test_rejects_blank_query(self) -> None:
        with pytest.raises(ValueError) as exc:
            RetrievalQuery(query_text="   ")
        assert "non-empty" in str(exc.value).lower()

    def test_rejects_invalid_method(self) -> None:
        with pytest.raises(ValueError) as exc:
            RetrievalQuery(query_text="test", method="vector")
        assert "method" in str(exc.value).lower()

    def test_rejects_top_k_too_low(self) -> None:
        with pytest.raises(ValueError) as exc:
            RetrievalQuery(query_text="test", top_k=0)
        assert "top_k" in str(exc.value).lower()

    def test_rejects_top_k_too_high(self) -> None:
        with pytest.raises(ValueError) as exc:
            RetrievalQuery(query_text="test", top_k=51)
        assert "top_k" in str(exc.value).lower()

    def test_rejects_rerank_depth_less_than_top_k(self) -> None:
        with pytest.raises(ValueError) as exc:
            RetrievalQuery(query_text="test", top_k=10, rerank_depth=5)
        assert "rerank_depth" in str(exc.value).lower()

    def test_accepts_rerank_depth_equal_to_top_k(self) -> None:
        q = RetrievalQuery(query_text="test", top_k=10, rerank_depth=10)
        assert q.rerank_depth == 10

    def test_accepts_boundary_top_k_values(self) -> None:
        q1 = RetrievalQuery(query_text="test", top_k=1)
        assert q1.top_k == 1
        q2 = RetrievalQuery(query_text="test", top_k=50, rerank_depth=50)
        assert q2.top_k == 50


class TestRetrievalResult:
    def test_creates_with_minimal_fields(self) -> None:
        r = RetrievalResult(
            chunk_id="chunk-001",
            text="confidential text",
            clause_heading="Article 3",
            clause_level=0,
            hierarchy_chain=["Article 3"],
            parent_chunk_id=None,
            score=0.95,
            method="hybrid",
        )
        assert r.chunk_id == "chunk-001"
        assert r.score == 0.95
        assert r.rank_sparse is None
        assert r.rank_dense is None
        assert r.rrf_score is None
        assert r.rerank_score is None
        assert r.char_start == 0
        assert r.char_end == 0

    def test_creates_with_all_fields(self) -> None:
        r = RetrievalResult(
            chunk_id="chunk-001",
            text="confidential text",
            clause_heading="Article 3 — Obligations",
            clause_level=0,
            hierarchy_chain=["Article 3 — Obligations", "Section 3.1"],
            parent_chunk_id=None,
            score=0.89,
            method="hybrid+rerank",
            rank_sparse=2,
            rank_dense=1,
            rrf_score=0.0164,
            rerank_score=0.92,
            char_start=100,
            char_end=400,
        )
        assert r.chunk_id == "chunk-001"
        assert r.clause_heading == "Article 3 — Obligations"
        assert r.score == 0.89
        assert r.method == "hybrid+rerank"
        assert r.rank_sparse == 2
        assert r.rank_dense == 1
        assert r.rrf_score == 0.0164
        assert r.rerank_score == 0.92
        assert r.char_start == 100
        assert r.char_end == 400

    def test_hierarchy_chain_order_preserved(self) -> None:
        r = RetrievalResult(
            chunk_id="chunk-005",
            text="text",
            clause_heading="Section 7.3",
            clause_level=2,
            hierarchy_chain=["Article 7", "Section 7.1", "Section 7.3"],
            parent_chunk_id="chunk-004",
            score=0.5,
            method="sparse",
        )
        assert r.hierarchy_chain == ["Article 7", "Section 7.1", "Section 7.3"]
        assert len(r.hierarchy_chain) == 3

    def test_multiple_results_ranked(self) -> None:
        results = [
            RetrievalResult(
                chunk_id=f"chunk-{i}",
                text=f"text {i}",
                clause_heading=f"Heading {i}",
                clause_level=0,
                hierarchy_chain=[f"Heading {i}"],
                parent_chunk_id=None,
                score=1.0 - i * 0.1,
                method="hybrid",
            )
            for i in range(5)
        ]
        for i in range(1, len(results)):
            assert results[i - 1].score >= results[i].score


class TestIndexMeta:
    def test_creates_with_minimal_fields(self) -> None:
        meta = IndexMeta(
            document_id="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            document_path="/tmp/test-contract.ndax",
            chunk_count=12,
            method="hybrid",
        )
        assert (
            meta.document_id == "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        )
        assert meta.chunk_count == 12
        assert meta.method == "hybrid"
        assert meta.embedding_model is None
        assert meta.embedding_dimension is None
        assert meta.index_timestamp == ""
        assert meta.index_status == "empty"
        assert meta.db_size_bytes == 0

    def test_creates_with_all_fields(self) -> None:
        meta = IndexMeta(
            document_id="a1b2c3d4",
            document_path="/tmp/test.ndax",
            chunk_count=47,
            method="hybrid",
            embedding_model="nomic-embed-text",
            embedding_dimension=1024,
            index_timestamp="2026-07-03T14:30:00Z",
            index_status="indexed",
            db_size_bytes=3_200_000,
        )
        assert meta.embedding_model == "nomic-embed-text"
        assert meta.embedding_dimension == 1024
        assert meta.index_timestamp == "2026-07-03T14:30:00Z"
        assert meta.index_status == "indexed"
        assert meta.db_size_bytes == 3_200_000
