"""Retention: expiry cleanup + on-demand PII deletion."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from openreview_cli.pii.cache import PiiCache
from openreview_cli.pii.models import PiiResult
from openreview_cli.pii.persist import write_audit_trail_row
from openreview_cli.pii.retention import cleanup_expired, delete_pii_data
from openreview_cli.storage import init_database


@pytest.fixture
def db(tmp_path: Path) -> Path:
    p = tmp_path / "t.db"
    init_database(p)
    return p


def _seed(db: Path, doc_hash: str, tmp_path: Path, expired: bool) -> tuple[Path, Path]:
    mapping = tmp_path / f"{doc_hash[:8]}-mapping.json"
    review = tmp_path / f"{doc_hash[:8]}-review.json"
    mapping.write_text("{}")
    review.write_text("{}")
    PiiCache(db).put(doc_hash, "cfg", str(review), str(mapping))
    if expired:
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        conn = sqlite3.connect(str(db))
        conn.execute("UPDATE pii_cache SET expiry_at = ? WHERE document_hash = ?", (past, doc_hash))
        conn.commit()
        conn.close()
    return mapping, review


def _seed_review_dir(db: Path, doc_hash: str, tmp_path: Path, expired: bool = False) -> Path:
    """Seed a row whose mapping+result live inside a real review directory.

    Mirrors what ``strip_and_persist`` leaves on disk: the encrypted mapping,
    the stripped text, and the legacy ``pii_audit.json`` all in
    ``<data_dir>/reviews/<hash[:12]>/``.
    """
    review_dir = tmp_path / "reviews" / doc_hash[:12]
    review_dir.mkdir(parents=True)
    (review_dir / "pii_map.enc").write_bytes(b"encrypted")
    (review_dir / "stripped.txt").write_text("stripped")
    (review_dir / "pii_audit.json").write_text("{}")
    PiiCache(db).put(
        doc_hash,
        "cfg",
        str(review_dir / "stripped.txt"),
        str(review_dir / "pii_map.enc"),
    )
    if expired:
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        conn = sqlite3.connect(str(db))
        conn.execute("UPDATE pii_cache SET expiry_at = ? WHERE document_hash = ?", (past, doc_hash))
        conn.commit()
        conn.close()
    return review_dir


def _clean_result() -> PiiResult:
    return PiiResult(
        stripped_text="Hello world",
        mapping={},
        entities=[],
        page_count=1,
        duration_seconds=0.0,
        warnings=[],
        failed_pages=None,
    )


def _audit_count(db: Path, document_hash: str) -> int:
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM pii_audit_trail WHERE document_hash = ?",
            (document_hash,),
        ).fetchone()
    finally:
        conn.close()
    return int(row[0])


def test_cleanup_deletes_only_expired(db: Path, tmp_path: Path) -> None:
    old_m, old_r = _seed(db, "a" * 64, tmp_path, expired=True)
    new_m, new_r = _seed(db, "b" * 64, tmp_path, expired=False)
    write_audit_trail_row(
        db,
        document_hash="a" * 64,
        config_hash="cfg",
        pii_result=_clean_result(),
        status="success",
    )
    assert cleanup_expired(db) == 1
    assert not old_m.exists() and not old_r.exists()
    assert new_m.exists() and new_r.exists()
    assert PiiCache(db).get("a" * 64) is None
    assert PiiCache(db).get("b" * 64) is not None
    assert _audit_count(db, "a" * 64) == 0


def test_delete_pii_data_requires_8_char_prefix(db: Path) -> None:
    with pytest.raises(ValueError):
        delete_pii_data(db, "short")


def test_delete_pii_data_removes_files_and_rows(db: Path, tmp_path: Path) -> None:
    m, r = _seed(db, "c" * 64, tmp_path, expired=False)
    write_audit_trail_row(
        db,
        document_hash="c" * 64,
        config_hash="cfg",
        pii_result=_clean_result(),
        status="success",
    )
    out = delete_pii_data(db, "c" * 8)
    assert out["mapping_removed"] is True
    assert out["audit_records"] == 1
    assert out["cache_removed"] is True
    assert not m.exists() and not r.exists()


def test_delete_pii_data_no_match_returns_zeros(db: Path) -> None:
    assert delete_pii_data(db, "deadbeef") == {
        "mapping_removed": False,
        "audit_records": 0,
        "cache_removed": False,
    }


def test_delete_pii_data_removes_a_clean_document_audit_row(db: Path) -> None:
    write_audit_trail_row(
        db,
        document_hash="d" * 64,
        config_hash="cfg",
        pii_result=_clean_result(),
        status="success",
    )
    out = delete_pii_data(db, "d" * 8)
    assert out == {"mapping_removed": False, "audit_records": 1, "cache_removed": False}
    assert _audit_count(db, "d" * 64) == 0


def test_cleanup_expired_removes_old_audit_rows_but_keeps_fresh(db: Path) -> None:
    for doc_hash in ("e" * 64, "f" * 64):
        write_audit_trail_row(
            db,
            document_hash=doc_hash,
            config_hash="cfg",
            pii_result=_clean_result(),
            status="success",
        )
    past = (datetime.now(UTC) - timedelta(days=31)).isoformat()
    conn = sqlite3.connect(str(db))
    conn.execute(
        "UPDATE pii_audit_trail SET timestamp = ? WHERE document_hash = ?",
        (past, "e" * 64),
    )
    conn.commit()
    conn.close()
    assert cleanup_expired(db) == 0
    assert _audit_count(db, "e" * 64) == 0
    assert _audit_count(db, "f" * 64) == 1


def test_cli_pii_delete_removes_a_clean_document_audit_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from openreview_cli.app import app
    from openreview_cli.config.paths import get_data_dir

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    db_path = get_data_dir() / "openreview.db"
    init_database(db_path)
    write_audit_trail_row(
        db_path,
        document_hash="d" * 64,
        config_hash="cfg",
        pii_result=_clean_result(),
        status="success",
    )
    result = CliRunner().invoke(app, ["pii", "delete", "d" * 8])
    assert result.exit_code == 0, result.output
    assert "Audit trail: removed (1 records)" in result.output
    assert "No PII data found" not in result.output
    assert _audit_count(db_path, "d" * 64) == 0


def test_delete_pii_data_removes_legacy_review_dir_leftovers(db: Path, tmp_path: Path) -> None:
    review_dir = _seed_review_dir(db, "1" * 64, tmp_path)
    out = delete_pii_data(db, "1" * 64)
    assert out["mapping_removed"] is True
    assert not (review_dir / "pii_map.enc").exists()
    assert not (review_dir / "stripped.txt").exists()
    assert not (review_dir / "pii_audit.json").exists()
    assert not review_dir.exists()


def test_delete_pii_data_keeps_unrelated_files_in_review_dir(db: Path, tmp_path: Path) -> None:
    review_dir = _seed_review_dir(db, "2" * 64, tmp_path)
    memo = review_dir / "memo.md"
    memo.write_text("keep me")
    out = delete_pii_data(db, "2" * 64)
    assert out["mapping_removed"] is True
    assert not (review_dir / "pii_map.enc").exists()
    assert not (review_dir / "pii_audit.json").exists()
    assert memo.read_text() == "keep me"
    assert review_dir.is_dir()


def test_cleanup_expired_removes_legacy_review_dir_leftovers(db: Path, tmp_path: Path) -> None:
    review_dir = _seed_review_dir(db, "3" * 64, tmp_path, expired=True)
    assert cleanup_expired(db) == 1
    assert not (review_dir / "pii_map.enc").exists()
    assert not (review_dir / "stripped.txt").exists()
    assert not (review_dir / "pii_audit.json").exists()
    assert not review_dir.exists()
    assert PiiCache(db).get("3" * 64) is None
