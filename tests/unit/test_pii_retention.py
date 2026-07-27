"""Retention: expiry cleanup + on-demand PII deletion."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from openreview_cli.pii.cache import PiiCache
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


def test_cleanup_deletes_only_expired(db: Path, tmp_path: Path) -> None:
    old_m, old_r = _seed(db, "a" * 64, tmp_path, expired=True)
    new_m, new_r = _seed(db, "b" * 64, tmp_path, expired=False)
    assert cleanup_expired(db) == 1
    assert not old_m.exists() and not old_r.exists()
    assert new_m.exists() and new_r.exists()
    assert PiiCache(db).get("a" * 64) is None
    assert PiiCache(db).get("b" * 64) is not None


def test_delete_pii_data_requires_8_char_prefix(db: Path) -> None:
    with pytest.raises(ValueError):
        delete_pii_data(db, "short")


def test_delete_pii_data_removes_files_and_rows(db: Path, tmp_path: Path) -> None:
    m, r = _seed(db, "c" * 64, tmp_path, expired=False)
    out = delete_pii_data(db, "c" * 8)
    assert out["mapping_removed"] is True
    assert out["cache_removed"] is True
    assert not m.exists() and not r.exists()


def test_delete_pii_data_no_match_returns_zeros(db: Path) -> None:
    assert delete_pii_data(db, "deadbeef") == {
        "mapping_removed": False,
        "audit_records": 0,
        "cache_removed": False,
    }
