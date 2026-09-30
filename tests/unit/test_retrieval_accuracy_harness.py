"""Unit tests for ``scripts/measure_retrieval_accuracy.py``.

The harness's public helpers are exercised against a tiny synthetic corpus and
a tiny benchmark JSON so the real CUAD run never executes. Everything is
offline: chunking is the product's own deterministic chunker and retrieval is
SQLite FTS5, both local.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.benchmark_scripts import load_benchmark_script

SCRIPT = load_benchmark_script("measure_retrieval_accuracy")

# Four paragraphs. ``confidential`` appears three times in P3 and once in P4,
# so a query for that single term must rank the P3 chunk above the P4 chunk.
DOC_A = (
    "The termination notice period is thirty days.\n"
    "\n"
    "Payment shall be made within ten business days of invoice receipt.\n"
    "\n"
    "confidential confidential confidential boilerplate text.\n"
    "\n"
    "confidential information means proprietary data."
)
DOC_B = (
    "This Agreement is governed by the laws of Delaware.\n"
    "\n"
    "No waiver shall be effective unless in writing."
)


def _span_of(text: str, needle: str) -> list[int]:
    start = text.index(needle)
    return [start, start + len(needle)]


A_TERMINATION_SPAN = _span_of(DOC_A, "The termination notice period is thirty days.")
A_CONFIDENTIAL_SPAN = _span_of(DOC_A, "confidential information means proprietary data.")
B_GOVERNING_SPAN = _span_of(DOC_B, "This Agreement is governed by the laws of Delaware.")


def _write_tiny_corpus(corpus_root: Path, benchmark_path: Path) -> None:
    corpus_root.mkdir(parents=True, exist_ok=True)
    (corpus_root / "doc_a.txt").write_text(DOC_A, encoding="utf-8")
    (corpus_root / "doc_b.txt").write_text(DOC_B, encoding="utf-8")
    payload = {
        "tests": [
            {
                "query": "What is the termination notice period?",
                "snippets": [
                    {"file_path": "doc_a.txt", "span": A_TERMINATION_SPAN, "answer": "thirty days"}
                ],
            },
            {
                # No term in this query appears in either document.
                "query": "xyzzyplugh frobnicate",
                "snippets": [
                    {"file_path": "doc_a.txt", "span": A_TERMINATION_SPAN, "answer": "thirty days"}
                ],
            },
            {
                # Ranked second: the P3 chunk has three occurrences to P4's one.
                "query": "confidential",
                "snippets": [
                    {
                        "file_path": "doc_a.txt",
                        "span": A_CONFIDENTIAL_SPAN,
                        "answer": "proprietary data",
                    }
                ],
            },
            {
                "query": "What is the governing law jurisdiction?",
                "snippets": [
                    {"file_path": "doc_b.txt", "span": B_GOVERNING_SPAN, "answer": "Delaware"}
                ],
            },
        ]
    }
    benchmark_path.write_text(json.dumps(payload), encoding="utf-8")


def _build_index(tmp_path: Path, text: str, document_id: str) -> Path:
    db_path = tmp_path / f"{document_id}.db"
    SCRIPT.index_contract(text, db_path, document_id)
    return db_path


# ── score_query: exact metric arithmetic per rank ───────────────────────────


def test_score_query_relevant_ranked_first(tmp_path: Path) -> None:
    db_path = _build_index(tmp_path, DOC_A, "doc-a")
    score = SCRIPT.score_query(
        db_path, "What is the termination notice period?", [tuple(A_TERMINATION_SPAN)], 20
    )
    assert score["first_rank"] == 1
    assert score["hit_at_1"] == 1.0
    assert score["hit_at_5"] == 1.0
    assert score["reciprocal_rank_at_5"] == 1.0


def test_score_query_nothing_matches(tmp_path: Path) -> None:
    db_path = _build_index(tmp_path, DOC_A, "doc-a")
    score = SCRIPT.score_query(db_path, "xyzzyplugh frobnicate", [tuple(A_TERMINATION_SPAN)], 20)
    assert score["first_rank"] is None
    assert score["hit_at_1"] == 0.0
    assert score["hit_at_5"] == 0.0
    assert score["reciprocal_rank_at_5"] == 0.0


def test_score_query_relevant_ranked_second(tmp_path: Path) -> None:
    db_path = _build_index(tmp_path, DOC_A, "doc-a")
    score = SCRIPT.score_query(db_path, "confidential", [tuple(A_CONFIDENTIAL_SPAN)], 20)
    assert score["first_rank"] == 2
    assert score["hit_at_1"] == 0.0
    assert score["hit_at_5"] == 1.0
    assert score["reciprocal_rank_at_5"] == 0.5


# ── evaluate: averages over the sample ──────────────────────────────────────


def test_evaluate_reports_exact_average_metrics(tmp_path: Path) -> None:
    corpus_root = tmp_path / "corpus"
    benchmark = tmp_path / "cuad.json"
    _write_tiny_corpus(corpus_root, benchmark)

    receipt: dict[str, Any] = SCRIPT.evaluate(benchmark, corpus_root, limit=None, depth=20)

    assert receipt["skipped"] is False
    # Ranks 1, none, 2, 1 -> hit@1 = 2/4, hit@5 = 3/4, MRR@5 = 2.5/4.
    assert receipt["metrics"]["hit_at_1"] == 2 / 4
    assert receipt["metrics"]["hit_at_5"] == 3 / 4
    assert receipt["metrics"]["mrr_at_5"] == 2.5 / 4
    assert receipt["sample"]["queries_scored"] == 4
    assert receipt["sample"]["contracts_used"] == 2
    assert receipt["retrieval_depth"] == 20
    assert receipt["product_default_top_k"] == 5
    # The rules the number depends on must be recorded in the receipt.
    assert "overlap" in receipt["ground_truth_rule"]
    assert "paragraph" in receipt["chunking_rule"].lower()
    assert receipt["fts"]["tokenize"] == "porter unicode61"
    assert receipt["fts"]["prefix"] == "2 3"


def test_evaluate_limit_bounds_scored_queries(tmp_path: Path) -> None:
    corpus_root = tmp_path / "corpus"
    benchmark = tmp_path / "cuad.json"
    _write_tiny_corpus(corpus_root, benchmark)

    receipt = SCRIPT.evaluate(benchmark, corpus_root, limit=2, depth=20)
    assert receipt["sample"]["queries_scored"] == 2
    assert receipt["sample"]["queries_total"] == 4
    # First two queries: rank 1 and a miss -> hit@1 = 0.5, hit@5 = 0.5, MRR = 0.5.
    assert receipt["metrics"]["hit_at_1"] == 0.5
    assert receipt["metrics"]["hit_at_5"] == 0.5
    assert receipt["metrics"]["mrr_at_5"] == 0.5


# ── graceful skips ──────────────────────────────────────────────────────────


def test_evaluate_skips_when_corpus_missing(tmp_path: Path) -> None:
    benchmark = tmp_path / "cuad.json"
    _write_tiny_corpus(tmp_path / "corpus", benchmark)
    missing_root = tmp_path / "does-not-exist"

    receipt = SCRIPT.evaluate(benchmark, missing_root, limit=None, depth=20)

    assert receipt["skipped"] is True
    assert receipt["reason"]
    assert receipt["metrics"]["hit_at_1"] == 0.0


def test_evaluate_skips_when_benchmark_missing(tmp_path: Path) -> None:
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir(parents=True)
    (corpus_root / "doc_a.txt").write_text(DOC_A, encoding="utf-8")

    receipt = SCRIPT.evaluate(tmp_path / "nope.json", corpus_root, limit=None, depth=20)

    assert receipt["skipped"] is True
    assert receipt["reason"]


def test_main_writes_skip_receipt_and_exits_zero(tmp_path: Path) -> None:
    out = tmp_path / "receipt.json"
    exit_code = SCRIPT.main(
        [
            "--benchmark",
            str(tmp_path / "missing.json"),
            "--corpus-root",
            str(tmp_path / "missing-corpus"),
            "--out",
            str(out),
        ]
    )
    assert exit_code == 0
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["skipped"] is True


# ── tokenizer arm ───────────────────────────────────────────────────────────


def _fts_ddl(db_path: Path) -> str:
    """Return the ``CREATE ...`` SQL of the ``chunk_fts`` virtual table."""
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'chunk_fts'").fetchone()
    finally:
        conn.close()
    assert row is not None, "chunk_fts was never created"
    return str(row[0])


def test_parse_args_defaults_to_the_shipped_tokenizer() -> None:
    """The default arm must stay the shipped one: ``porter unicode61``."""
    assert SCRIPT.parse_args([]).tokenizer == "porter"


def test_index_contract_creates_the_fts_table_with_the_chosen_tokenizer(tmp_path: Path) -> None:
    porter_db = _build_index(tmp_path, DOC_A, "doc-porter")
    assert "tokenize='porter unicode61'" in _fts_ddl(porter_db)

    unicode_db = tmp_path / "doc-unicode.db"
    SCRIPT.index_contract(DOC_A, unicode_db, "doc-unicode", tokenizer="unicode61")
    ddl = _fts_ddl(unicode_db)
    assert "tokenize='unicode61'" in ddl
    assert "porter" not in ddl
    # The recreated table keeps the shipped shape, not just the tokenizer.
    assert "chunk_id UNINDEXED" in ddl
    assert "content='chunks'" in ddl
    assert "content_rowid='rowid'" in ddl
    assert "prefix='2 3'" in ddl


def test_unicode61_arm_indexes_the_content_it_was_rebuilt_from(tmp_path: Path) -> None:
    """The rebuilt index is live and unstemmed (the point of the comparison)."""
    db_path = tmp_path / "doc-unicode.db"
    SCRIPT.index_contract(DOC_A, db_path, "doc-unicode", tokenizer="unicode61")

    literal = SCRIPT.score_query(db_path, "confidential", [tuple(A_CONFIDENTIAL_SPAN)], 20)
    assert literal["first_rank"] == 2

    porter_db = _build_index(tmp_path, DOC_A, "doc-porter")
    stemmed = SCRIPT.score_query(porter_db, "notices", [tuple(A_TERMINATION_SPAN)], 20)
    unicode_score = SCRIPT.score_query(db_path, "notices", [tuple(A_TERMINATION_SPAN)], 20)
    assert stemmed["first_rank"] is not None, "porter should stem 'notices' onto 'notice'"
    assert unicode_score["first_rank"] is None, "unicode61 must not stem"


def test_evaluate_records_the_tokenizer_arm_in_the_receipt(tmp_path: Path) -> None:
    corpus_root = tmp_path / "corpus"
    benchmark = tmp_path / "cuad.json"
    _write_tiny_corpus(corpus_root, benchmark)

    shipped = SCRIPT.evaluate(benchmark, corpus_root, depth=20)
    assert shipped["fts"]["tokenizer"] == "porter"
    assert shipped["fts"]["tokenize"] == "porter unicode61"
    assert shipped["fts"]["default_tokenizer"] == "porter"

    comparison = SCRIPT.evaluate(benchmark, corpus_root, depth=20, tokenizer="unicode61")
    assert comparison["fts"]["tokenizer"] == "unicode61"
    assert comparison["fts"]["tokenize"] == "unicode61"


def test_evaluate_rejects_an_unknown_tokenizer(tmp_path: Path) -> None:
    corpus_root = tmp_path / "corpus"
    benchmark = tmp_path / "cuad.json"
    _write_tiny_corpus(corpus_root, benchmark)
    with pytest.raises(ValueError, match="tokenizer"):
        SCRIPT.evaluate(benchmark, corpus_root, depth=20, tokenizer="snowball")
