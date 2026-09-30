"""Unit tests for RetrievalEngine (T014)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from openreview_cli.retrieval.engine import RetrievalEngine
from openreview_cli.retrieval.errors import IndexCorruptError, IndexNotFoundError
from openreview_cli.retrieval.models import RetrievalQuery


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test_index.db")


@pytest.fixture
def populated_db(db_path: str) -> str:
    """Create a SQLite DB with a few chunks and an FTS5 index."""
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
            method TEXT NOT NULL DEFAULT 'sparse',
            db_size_bytes INTEGER DEFAULT 0
        );

        INSERT INTO index_meta (document_id, index_status, chunk_count, method)
        VALUES ('test-doc', 'indexed', 4, 'sparse');

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
            tokenize='porter unicode61', prefix='2 3'
        );

        INSERT INTO chunk_fts (rowid, chunk_id, text, clause_heading)
        SELECT rowid, chunk_id, text, clause_heading FROM chunks;
    """)

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def nl_query_db(tmp_path: Path) -> str:
    """Sparse-only index of natural-language contract clauses (no embeddings)."""
    db_path = str(tmp_path / "nl_query.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE index_meta (
            document_id TEXT PRIMARY KEY, document_path TEXT NOT NULL DEFAULT '',
            index_version INTEGER NOT NULL DEFAULT 1,
            index_status TEXT NOT NULL DEFAULT 'indexed',
            index_timestamp TEXT, chunk_count INTEGER NOT NULL DEFAULT 0,
            method TEXT NOT NULL DEFAULT 'sparse', db_size_bytes INTEGER DEFAULT 0
        );
        INSERT INTO index_meta (document_id, index_status, chunk_count, method)
        VALUES ('nl-doc', 'indexed', 4, 'sparse');
        CREATE TABLE chunks (
            chunk_id TEXT PRIMARY KEY, document_id TEXT NOT NULL DEFAULT 'nl-doc',
            text TEXT NOT NULL, clause_heading TEXT NOT NULL,
            clause_level INTEGER NOT NULL DEFAULT 0, parent_chunk_id TEXT,
            heading_chain TEXT NOT NULL DEFAULT '[]',
            char_start INTEGER NOT NULL DEFAULT 0, char_end INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO chunks VALUES
            ('n1','nl-doc','the expiration date of this contract is twelve months from the effective date','Section 9.1',0,NULL,'["Section 9.1"]',0,100),
            ('n2','nl-doc','either party may terminate this agreement for material breach','Section 12',0,NULL,'["Section 12"]',200,300),
            ('n3','nl-doc','governing law is the state of delaware','Section 7',0,NULL,'["Section 7"]',400,500),
            ('n4','nl-doc','confidential information shall be protected by the receiving party','Section 3',0,NULL,'["Section 3"]',600,700);
        CREATE VIRTUAL TABLE chunk_fts USING fts5(
            chunk_id UNINDEXED, text, clause_heading, content='chunks', content_rowid='rowid',
            tokenize='porter unicode61', prefix='2 3'
        );
        INSERT INTO chunk_fts (rowid, chunk_id, text, clause_heading)
        SELECT rowid, chunk_id, text, clause_heading FROM chunks;
    """)
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
        query = RetrievalQuery(
            query_text="confidential OR governing OR indemnification", method="sparse", top_k=2
        )

        results = engine.retrieve(query)

        assert [r.chunk_id for r in results] == ["c3", "c1"]
        assert all(r.method == "sparse" for r in results)

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
                db_size_bytes INTEGER DEFAULT 0
            )
        """)
        conn.execute(
            "INSERT INTO index_meta (document_id, index_status) VALUES ('corrupt-doc', 'corrupt')"
        )
        conn.commit()
        conn.close()

        engine = RetrievalEngine(db_path)
        query = RetrievalQuery(query_text="test")
        with pytest.raises(IndexCorruptError):
            engine.retrieve(query)

    def test_result_ordering_by_score(self, populated_db: str) -> None:
        engine = RetrievalEngine(populated_db)
        query = RetrievalQuery(
            query_text="confidential OR indemnification OR limitation", method="sparse", top_k=5
        )
        results = engine.retrieve(query)
        if len(results) >= 2:
            for i in range(len(results) - 1):
                assert results[i].score >= results[i + 1].score

    # ── T024: Method routing ──

    def test_sparse_calls_bm25_only(self, populated_db: str) -> None:
        """sparse method only returns BM25 results, no dense/embedding calls."""
        engine = RetrievalEngine(populated_db)
        query = RetrievalQuery(query_text="confidential", method="sparse", top_k=3)
        results = engine.retrieve(query)
        assert len(results) <= 3
        assert all(r.method == "sparse" for r in results)
        assert all(r.rank_sparse is not None for r in results)

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


class TestSparseNaturalLanguageQueries:
    """The sparse leg must match real questions, not just single keywords."""

    def test_natural_language_question_returns_rows(self, nl_query_db: str) -> None:
        engine = RetrievalEngine(nl_query_db)
        query = RetrievalQuery(
            query_text="What is the expiration date of this contract?",
            method="sparse",
            top_k=3,
        )

        results = engine.retrieve(query)

        assert [r.chunk_id for r in results] == ["n1", "n3", "n2"]

    def test_cuad_style_question_with_hyphenated_name_returns_rows(self, nl_query_db: str) -> None:
        engine = RetrievalEngine(nl_query_db)
        query = RetrievalQuery(
            query_text=(
                "Consider [PARTY_C] between I-Escrow, Inc. and [PARTY_A]; "
                "What is the expiration date of this contract?"
            ),
            method="sparse",
            top_k=3,
        )

        results = engine.retrieve(query)

        assert [r.chunk_id for r in results] == ["n1", "n3", "n2"]

    def test_lowercase_or_does_not_empty_the_result_set(self, nl_query_db: str) -> None:
        engine = RetrievalEngine(nl_query_db)
        query = RetrievalQuery(query_text="expiration or terminate", method="sparse", top_k=5)

        results = engine.retrieve(query)

        assert {r.chunk_id for r in results} == {"n1", "n2"}

    def test_uppercase_or_query_returns_rows(self, nl_query_db: str) -> None:
        engine = RetrievalEngine(nl_query_db)
        query = RetrievalQuery(query_text="expiration OR terminate", method="sparse", top_k=5)

        results = engine.retrieve(query)

        assert {r.chunk_id for r in results} == {"n1", "n2"}

    def test_realistic_multi_word_query_returns_matching_clause(self, nl_query_db: str) -> None:
        engine = RetrievalEngine(nl_query_db)
        query = RetrievalQuery(
            query_text="return or destroy confidential information", method="sparse", top_k=5
        )

        results = engine.retrieve(query)

        assert results[0].chunk_id == "n4"

    @pytest.mark.parametrize(
        "query_text",
        [
            '"',
            "*",
            "NEAR",
            "-",
            "data-processing",
            "-confidential",
            'he said "confidential"',
            "confid* -term",
            "a NEAR/3 b",
            "text:confidential",
            ":",
        ],
    )
    def test_fts_metacharacters_do_not_raise(self, nl_query_db: str, query_text: str) -> None:
        engine = RetrievalEngine(nl_query_db)

        results = engine.retrieve(RetrievalQuery(query_text=query_text, method="sparse", top_k=3))

        assert isinstance(results, list)


class TestOperatorSemantics:
    """Uppercase FTS5 operators must narrow, not be OR-ified away."""

    def test_uppercase_and_matches_only_chunks_with_both_terms(self, nl_query_db: str) -> None:
        engine = RetrievalEngine(nl_query_db)
        query = RetrievalQuery(query_text="expiration AND contract", method="sparse", top_k=5)

        results = engine.retrieve(query)

        assert [r.chunk_id for r in results] == ["n1"]

    def test_uppercase_and_excludes_chunks_without_both_terms(self, nl_query_db: str) -> None:
        engine = RetrievalEngine(nl_query_db)
        query = RetrievalQuery(query_text="expiration AND breach", method="sparse", top_k=5)

        results = engine.retrieve(query)

        assert results == []


class TestSparseOnlyEngine:
    """T1.2: the engine offers keyword search only — no dense/hybrid paths."""

    def test_default_query_returns_sparse_results(self, populated_db: str) -> None:
        engine = RetrievalEngine(populated_db)

        results = engine.retrieve(RetrievalQuery(query_text="confidential"))

        assert results
        assert all(r.method == "sparse" for r in results)

    def test_engine_has_no_dense_or_hybrid_helpers(self, populated_db: str) -> None:
        engine = RetrievalEngine(populated_db)

        assert not hasattr(engine, "_retrieve_dense")
        assert not hasattr(engine, "_retrieve_hybrid")
        assert not hasattr(engine, "_search_dense_candidates")

    @pytest.mark.parametrize("method", ["dense", "hybrid"])
    def test_engine_is_not_offered_a_dense_or_hybrid_method(
        self, populated_db: str, method: str
    ) -> None:
        engine = RetrievalEngine(populated_db)

        with pytest.raises(ValueError, match="method"):
            RetrievalQuery(query_text="confidential", method=method)

        # the engine still answers a sparse query
        assert engine.retrieve(RetrievalQuery(query_text="confidential"))
