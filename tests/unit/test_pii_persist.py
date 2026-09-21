"""PII persistence — audit trail rows + cache rows written by the review pipeline.

Regression coverage for D-8: the supported review pipeline (StripStage) persists
the result of every PII strip to the PII governance lifecycle (pii_audit_trail
table / pii_cache rows), so ``pii list`` reports the recorded entity_count. Every
strip records one ``pii_audit_trail`` row; a clean document records
``entity_count=0`` and still gets no ``pii_cache`` row.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from openreview_cli.pii.cache import PiiCache
from openreview_cli.pii.models import PiiEntity, PiiResult
from openreview_cli.pii.persist import persist_pii_result, write_audit_trail_row
from openreview_cli.storage import init_database


def _entity(
    entity_type: str,
    placeholder: str,
    original: str = "value",
    score: float = 0.9,
) -> PiiEntity:
    return PiiEntity(
        entity_type=entity_type,
        original_value=original,
        start=0,
        end=len(original),
        score=score,
        placeholder=placeholder,
        source="nlp",
    )


def _result_with_mapping(
    failed_pages: list[int] | None = None,
    duration_seconds: float = 1.5,
) -> PiiResult:
    return PiiResult(
        stripped_text="Hello [PARTY_A] and [PERSON_1]",
        mapping={"PARTY_A": "Acme", "PERSON_1": "Jane"},
        entities=[
            _entity("ORGANIZATION", "[PARTY_A]", original="Acme"),
            _entity("PERSON", "[PERSON_1]", original="Jane"),
        ],
        page_count=2,
        duration_seconds=duration_seconds,
        warnings=[],
        failed_pages=failed_pages,
    )


def _result_no_mapping() -> PiiResult:
    return PiiResult(
        stripped_text="Hello world",
        mapping={},
        entities=[],
        page_count=1,
        duration_seconds=0.5,
        warnings=[],
        failed_pages=None,
    )


# ── write_audit_trail_row ────────────────────────────────────────────────


def test_write_audit_trail_row_writes_correct_columns(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    init_database(db)

    pii_result = _result_with_mapping()
    write_audit_trail_row(
        db,
        document_hash="h" * 64,
        config_hash="cfg-hash",
        pii_result=pii_result,
        status="success",
    )

    conn = sqlite3.connect(str(db))
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM pii_audit_trail").fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    row = dict(rows[0])
    assert row["document_hash"] == "h" * 64
    assert row["config_hash"] == "cfg-hash"
    assert row["entity_count"] == 2
    assert json.loads(row["entity_type_distribution"]) == {
        "ORGANIZATION": 1,
        "PERSON": 1,
    }
    assert row["processing_time_ms"] == 1500
    assert row["status"] == "success"
    assert json.loads(row["failed_pages"]) == []
    assert row["timestamp"]


def test_write_audit_trail_row_partial_status_and_failed_pages(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    init_database(db)

    write_audit_trail_row(
        db,
        document_hash="a" * 64,
        config_hash="cfg-hash",
        pii_result=_result_with_mapping(failed_pages=[2, 3]),
        status="partial",
    )

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM pii_audit_trail").fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["document_hash"] == "a" * 64
    assert row["processing_time_ms"] == 1500
    assert row["status"] == "partial"
    assert json.loads(row["failed_pages"]) == [2, 3]


# ── persist_pii_result ───────────────────────────────────────────────────


def test_persist_pii_result_writes_cache_and_audit_rows(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    init_database(db)
    review_dir = tmp_path / "reviews" / ("h" * 12)

    persist_pii_result(
        db,
        document_hash="h" * 64,
        config_hash="cfg-hash",
        pii_result=_result_with_mapping(),
        review_dir=review_dir,
        encryption_key="test-key-1234567890123456",
    )

    # pii_cache row exists with paths pointing at the written files
    cache_row = PiiCache(db).get("h" * 64)
    assert cache_row is not None
    assert cache_row["config_hash"] == "cfg-hash"
    assert Path(cache_row["review_result_path"]).exists()
    assert Path(cache_row["mapping_path"]).exists()
    assert Path(cache_row["review_result_path"]).read_text(encoding="utf-8") == (
        "Hello [PARTY_A] and [PERSON_1]"
    )

    # audit trail row exists with correct entity_count
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM pii_audit_trail").fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["entity_count"] == 2
    assert row["status"] == "success"


def test_persist_pii_result_records_an_audit_row_for_a_clean_document(
    tmp_path: Path,
) -> None:
    db = tmp_path / "t.db"
    init_database(db)
    review_dir = tmp_path / "reviews" / ("n" * 12)

    persist_pii_result(
        db,
        document_hash="n" * 64,
        config_hash="cfg-hash",
        pii_result=_result_no_mapping(),
        review_dir=review_dir,
        encryption_key="test-key-1234567890123456",
    )

    assert PiiCache(db).get("n" * 64) is None
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM pii_audit_trail").fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["entity_count"] == 0
    assert row["status"] == "success"
    assert not (review_dir / "stripped.txt").exists()
    assert not (review_dir / "pii_map.enc").exists()


# ── StripStage integration ───────────────────────────────────────────────


def test_strip_stage_persists_pii_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """StripStage.run persists a real PiiResult to pii_cache + pii_audit_trail."""
    import hashlib

    from openreview_cli.config.loader import load_config
    from openreview_cli.pipeline.adapters.strip import StripStage

    doc_path = tmp_path / "contract.txt"
    doc_path.write_text("Confidential NDA between Acme and Jane", encoding="utf-8")

    clauses = [type("Clause", (), {"id": "1", "text": "Hello [PARTY_A] and [PERSON_1]"})()]
    pii_result = _result_with_mapping()

    monkeypatch.setattr(
        "openreview_cli.pii.strip_pii_clauses",
        lambda *args, **kwargs: (clauses, pii_result),
    )

    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    config_path = config_dir / "config.yml"
    load_config(config_path)  # materialise a valid config.yml for the tmp config dir

    monkeypatch.setattr("openreview_cli.config.paths.get_data_dir", lambda: data_dir)
    monkeypatch.setattr("openreview_cli.config.paths.get_config_dir", lambda: config_dir)

    db = data_dir / "openreview.db"
    init_database(db)  # mirrors app startup (app.py:211) before a review runs

    stage = StripStage()
    ctx = {"clauses": clauses, "document_path": str(doc_path), "document": None}
    result = asyncio.run(stage.run(ctx))

    assert result == {"stripped_clauses": clauses}

    document_hash = hashlib.sha256(doc_path.read_bytes()).hexdigest()
    db = data_dir / "openreview.db"

    cache_row = PiiCache(db).get(document_hash)
    assert cache_row is not None
    assert len(cache_row["config_hash"]) == 64
    assert Path(cache_row["review_result_path"]).read_text(encoding="utf-8") == (
        "Hello [PARTY_A] and [PERSON_1]"
    )
    assert Path(cache_row["mapping_path"]).exists()

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT entity_count, status, config_hash FROM pii_audit_trail WHERE document_hash = ?",
            (document_hash,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["entity_count"] == 2
    assert row["status"] == "success"
    assert row["config_hash"] == cache_row["config_hash"]
