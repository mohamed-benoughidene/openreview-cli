"""Shared PII inventory read — backs both `pii list` and the TUI stored-PII screen.

The reader is the single source of truth for "what PII data is stored", so these
tests pin both query branches and the CLI's JSON contract.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.pii.cache import PiiCache
from openreview_cli.pii.inventory import list_pii_documents
from openreview_cli.pii.models import PiiResult
from openreview_cli.pii.persist import write_audit_trail_row
from openreview_cli.storage import init_database

JSON_KEYS = {"document_hash", "created_at", "expiry_at", "entity_count", "mapping_path"}


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "t.db"
    init_database(path)
    return path


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


def _seed_mapping(db: Path, doc_hash: str, tmp_path: Path) -> tuple[Path, Path]:
    """Write the encrypted-mapping artifacts + cache row for one document."""
    mapping = tmp_path / f"{doc_hash[:8]}-mapping.enc"
    stripped = tmp_path / f"{doc_hash[:8]}-stripped.txt"
    mapping.write_text("{}", encoding="utf-8")
    stripped.write_text("hello", encoding="utf-8")
    PiiCache(db).put(doc_hash, "cfg", str(stripped), str(mapping))
    return mapping, stripped


def _seed_audit(db: Path, doc_hash: str, entity_count: int, age_days: int = 0) -> None:
    """Insert one audit row directly (the aggregate reads these columns only)."""
    stamp = (datetime.now(UTC) - timedelta(days=age_days)).isoformat()
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT INTO pii_audit_trail "
            "(document_hash, timestamp, entity_count, entity_type_distribution, "
            " processing_time_ms, config_hash, status, failed_pages) "
            "VALUES (?, ?, ?, '{}', 0, 'cfg', 'success', '[]')",
            (doc_hash, stamp, entity_count),
        )
        conn.commit()
    finally:
        conn.close()


def test_empty_db_returns_empty_list(db: Path) -> None:
    assert list_pii_documents(db) == []


def test_returns_mapped_document_with_artifact_paths(db: Path, tmp_path: Path) -> None:
    mapping, stripped = _seed_mapping(db, "a" * 64, tmp_path)
    write_audit_trail_row(
        db,
        document_hash="a" * 64,
        config_hash="cfg",
        pii_result=_clean_result(),
        status="success",
    )

    rows = list_pii_documents(db)

    assert len(rows) == 1
    assert rows[0]["document_hash"] == "a" * 64
    assert rows[0]["mapping_path"] == str(mapping)
    assert rows[0]["created_at"] and rows[0]["expiry_at"]
    assert set(rows[0]) == JSON_KEYS
    assert mapping.exists() and stripped.exists()


def test_mapped_document_without_audit_row_still_counts_zero(db: Path, tmp_path: Path) -> None:
    """The COALESCE keeps a cache row visible before/without its audit record."""
    _seed_mapping(db, "b" * 64, tmp_path)

    rows = list_pii_documents(db)

    assert len(rows) == 1
    assert rows[0]["entity_count"] == 0


def test_audit_only_document_is_opt_in(db: Path) -> None:
    """A strip with no stored mapping is invisible unless explicitly requested."""
    _seed_audit(db, "c" * 64, 0)

    assert list_pii_documents(db) == []

    rows = list_pii_documents(db, include_audit_only=True)
    assert len(rows) == 1
    assert rows[0]["document_hash"] == "c" * 64
    assert rows[0]["mapping_path"] is None
    assert rows[0]["expiry_at"] is None
    assert rows[0]["created_at"] is not None


def test_latest_audit_row_wins_the_entity_count(db: Path, tmp_path: Path) -> None:
    """SQLite's bare-column rule must stay in force: the newest audit row counts."""
    _seed_mapping(db, "d" * 64, tmp_path)
    _seed_audit(db, "d" * 64, 7, age_days=2)
    _seed_audit(db, "d" * 64, 11)

    rows = list_pii_documents(db)

    assert rows[0]["entity_count"] == 11


def test_ordered_newest_cache_row_first(db: Path, tmp_path: Path) -> None:
    _seed_mapping(db, "e" * 64, tmp_path)
    _seed_mapping(db, "f" * 64, tmp_path)
    conn = sqlite3.connect(str(db))
    conn.execute(
        "UPDATE pii_cache SET created_at = ? WHERE document_hash = ?",
        ((datetime.now(UTC) - timedelta(days=5)).isoformat(), "e" * 64),
    )
    conn.commit()
    conn.close()

    rows = list_pii_documents(db)

    assert [row["document_hash"] for row in rows] == ["f" * 64, "e" * 64]


def test_reader_is_a_pure_query_and_needs_the_schema(tmp_path: Path) -> None:
    """The shared reader must not hide a missing schema.

    Callers (the TUI wrapper) run init_database first; keeping the reader a pure
    query is what keeps the CLI path byte-identical.
    """
    bare = tmp_path / "bare.db"
    sqlite3.connect(str(bare)).close()

    with pytest.raises(sqlite3.OperationalError):
        list_pii_documents(bare)


def test_cli_pii_list_json_contract_default_vs_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`pii list` keeps its JSON key set, and `--all` stays the only way to see
    an audit-only document."""
    from openreview_cli.app import app
    from openreview_cli.config.paths import get_data_dir

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    database = get_data_dir() / "openreview.db"
    init_database(database)
    _seed_mapping(database, "1" * 64, tmp_path)
    _seed_audit(database, "2" * 64, 0)

    default = CliRunner().invoke(app, ["pii", "list", "--format", "json"])
    assert default.exit_code == 0, default.output
    payload = json.loads(default.output.strip())
    assert len(payload) == 1
    assert payload[0]["document_hash"] == "1" * 64
    assert set(payload[0]) == JSON_KEYS

    every = CliRunner().invoke(app, ["pii", "list", "--all", "--format", "json"])
    assert every.exit_code == 0, every.output
    all_payload = json.loads(every.output.strip())
    assert {row["document_hash"] for row in all_payload} == {"1" * 64, "2" * 64}
    assert set(all_payload[0]) == JSON_KEYS
