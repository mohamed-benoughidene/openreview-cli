"""Unit tests for Phase 2 Foundational: playbook meta migration + storage helpers.

Covers T007-T014: migration 007, ensure_playbook_meta, get_current_version,
set_current_version, delete_playbook, get_playbook_history, list_playbooks extended.

Note: export and diff unit tests moved to test_playbook_export.py (T015)
and test_playbook_diff.py (T021).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from pathlib import Path

import pytest

from openreview_cli.storage.database import (
    delete_playbook,
    ensure_playbook_meta,
    get_connection,
    get_current_version,
    get_playbook_history,
    init_database,
    list_playbooks,
    list_playbooks_with_meta,
    set_current_version,
)

MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[2] / "src" / "openreview_cli" / "storage" / "migrations"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_playbook_mgmt.db"


@pytest.fixture
def conn(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Raw connection with WAL + FK + Row factory, no migrations run."""
    conn = get_connection(db_path)
    yield conn
    conn.close()


@pytest.fixture
def seeded_db(db_path: Path) -> Path:
    """Init database, seed playbook_versions with two playbooks, return db_path."""
    init_database(db_path)
    _seed_playbook(db_path, "pb-a", {"name": "a1", "metadata": {"version": 1}})
    _seed_playbook(db_path, "pb-a", {"name": "a2", "metadata": {"version": 2}})
    _seed_playbook(db_path, "pb-b", {"name": "b1", "metadata": {"version": 1}})
    return db_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_migration(conn: sqlite3.Connection) -> None:
    sql = (MIGRATIONS_DIR / "007_playbook_meta.sql").read_text()
    conn.executescript(sql)
    conn.commit()


def _run_all_migrations(conn: sqlite3.Connection) -> None:
    """Run all migrations up to 007."""
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(sql_file.read_text())
    conn.commit()


def _seed_playbook(db_path: Path, playbook_id: str, content: dict[str, object]) -> int:
    """Insert a playbook version, return version number."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM playbook_versions WHERE playbook_id = ?",
            (playbook_id,),
        )
        ver = int(cur.fetchone()[0])
        conn.execute(
            "INSERT INTO playbook_versions (playbook_id, version, content) VALUES (?, ?, ?)",
            (playbook_id, ver, json.dumps(content)),
        )
        conn.commit()
        return ver
    finally:
        conn.close()


def _get_version_count(db_path: Path) -> int:
    conn = get_connection(db_path)
    try:
        return int(conn.execute("SELECT COUNT(*) FROM playbook_versions").fetchone()[0])
    finally:
        conn.close()


# ===================================================================
# T007: Migration 007 — playbook_meta table
# ===================================================================


class TestMigration007:
    """T007: Migration 007 creates playbook_meta table with correct schema."""

    def test_table_created(self, conn: sqlite3.Connection) -> None:
        _run_migration(conn)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='playbook_meta'"
        ).fetchall()
        assert len(tables) == 1
        assert tables[0]["name"] == "playbook_meta"

    def test_schema_columns(self, conn: sqlite3.Connection) -> None:
        _run_migration(conn)
        cols = {
            row["name"]: row["type"] for row in conn.execute("PRAGMA table_info(playbook_meta)")
        }
        assert cols["playbook_id"] == "TEXT"
        assert cols["current_version"] == "INTEGER"
        assert cols["deleted_at"] == "TEXT"

    def test_primary_key(self, conn: sqlite3.Connection) -> None:
        _run_migration(conn)
        pk = [
            row["name"] for row in conn.execute("PRAGMA table_info(playbook_meta)") if row["pk"] > 0
        ]
        assert pk == ["playbook_id"]

    def test_user_version(self, conn: sqlite3.Connection) -> None:
        _run_migration(conn)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 7

    def test_idempotent(self, conn: sqlite3.Connection) -> None:
        _run_migration(conn)
        _run_migration(conn)  # second run — must not raise

    def test_insert_and_read(self, conn: sqlite3.Connection) -> None:
        _run_migration(conn)
        # Run 006 first to have playbook_versions table
        _run_all_migrations(conn)
        conn.execute(
            "INSERT INTO playbook_versions (playbook_id, version, content) VALUES (?, ?, ?)",
            ("test-pb", 1, "{}"),
        )
        conn.execute(
            "INSERT INTO playbook_meta (playbook_id, current_version) VALUES (?, ?)",
            ("test-pb", 1),
        )
        row = conn.execute("SELECT * FROM playbook_meta").fetchone()
        assert row["playbook_id"] == "test-pb"
        assert row["current_version"] == 1
        assert row["deleted_at"] is None


# ===================================================================
# T008: Migration 007 registered (verified via init_database)
# ===================================================================


class TestMigration007Registered:
    """T008: init_database runs migration 007."""

    def test_init_database_runs_migration(self, db_path: Path) -> None:
        init_database(db_path)
        conn = get_connection(db_path)
        try:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            assert version >= 7
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='playbook_meta'"
            ).fetchall()
            assert len(tables) == 1
        finally:
            conn.close()


# ===================================================================
# T009 / T013: ensure_playbook_meta + internal version data
# ===================================================================


class TestEnsurePlaybookMeta:
    """T009/T013: ensure_playbook_meta lazy-creates meta rows."""

    def test_creates_meta_with_max_version(self, seeded_db: Path) -> None:
        """Existing playbook with 2 versions: meta.current_version = 2."""
        assert _get_version_count(seeded_db) == 3
        ensure_playbook_meta(seeded_db, "pb-a")
        conn = get_connection(seeded_db)
        try:
            row = conn.execute(
                "SELECT * FROM playbook_meta WHERE playbook_id = ?", ("pb-a",)
            ).fetchone()
            assert row is not None
            assert row["current_version"] == 2
            assert row["deleted_at"] is None
        finally:
            conn.close()

    def test_idempotent(self, seeded_db: Path) -> None:
        ensure_playbook_meta(seeded_db, "pb-a")
        ensure_playbook_meta(seeded_db, "pb-a")  # second call — no error
        conn = get_connection(seeded_db)
        try:
            rows = conn.execute("SELECT COUNT(*) FROM playbook_meta").fetchone()[0]
            assert rows == 1
        finally:
            conn.close()

    def test_raises_for_nonexistent_playbook(self, db_path: Path) -> None:
        init_database(db_path)
        with pytest.raises(ValueError, match="not found"):
            ensure_playbook_meta(db_path, "ghost")


# ===================================================================
# get_current_version (contract)
# ===================================================================


class TestGetCurrentVersion:
    """get_current_version returns effective version."""

    def test_returns_max_version_when_no_meta(self, seeded_db: Path) -> None:
        """No meta row: falls back to MAX(version)."""
        ver = get_current_version(seeded_db, "pb-a")
        assert ver == 2

    def test_returns_meta_current_version(self, seeded_db: Path) -> None:
        """Meta row exists: returns current_version."""
        ensure_playbook_meta(seeded_db, "pb-a")
        ver = get_current_version(seeded_db, "pb-a")
        assert ver == 2

    def test_raises_for_nonexistent(self, db_path: Path) -> None:
        init_database(db_path)
        with pytest.raises(ValueError, match="not found"):
            get_current_version(db_path, "ghost")


# ===================================================================
# export_playbook_version → moved to test_playbook_export.py (T015)
# ===================================================================

# ===================================================================
# diff_playbook_versions → moved to test_playbook_diff.py (T021)
# ===================================================================

# ===================================================================
# T010: set_current_version (contract)
# ===================================================================


class TestSetCurrentVersion:
    """T010: set_current_version updates meta.current_version and re-activates."""

    def test_sets_current_version(self, seeded_db: Path) -> None:
        changed, msg = set_current_version(seeded_db, "pb-a", 1)
        assert changed
        assert "Set current version" in msg
        ver = get_current_version(seeded_db, "pb-a")
        assert ver == 1

    def test_idempotent_when_already_current(self, seeded_db: Path) -> None:
        ensure_playbook_meta(seeded_db, "pb-a")
        changed, msg = set_current_version(seeded_db, "pb-a", 2)
        assert not changed
        assert "already current" in msg

    def test_raises_for_nonexistent_playbook(self, db_path: Path) -> None:
        init_database(db_path)
        with pytest.raises(ValueError, match="not found"):
            set_current_version(db_path, "ghost", 1)

    def test_raises_for_nonexistent_version(self, seeded_db: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            set_current_version(seeded_db, "pb-a", 99)

    def test_reactivates_deleted_playbook(self, seeded_db: Path) -> None:
        """Setting current version on a deleted playbook restores it."""
        ensure_playbook_meta(seeded_db, "pb-a")
        conn = get_connection(seeded_db)
        try:
            conn.execute(
                "UPDATE playbook_meta SET deleted_at = '2026-01-01' WHERE playbook_id = 'pb-a'"
            )
            conn.commit()
        finally:
            conn.close()
        changed, msg = set_current_version(seeded_db, "pb-a", 1)
        assert changed
        conn = get_connection(seeded_db)
        try:
            row = conn.execute(
                "SELECT deleted_at FROM playbook_meta WHERE playbook_id = 'pb-a'"
            ).fetchone()
            assert row["deleted_at"] is None
        finally:
            conn.close()


# ===================================================================
# T011: delete_playbook (contract) / soft_delete_playbook
# ===================================================================


class TestDeletePlaybook:
    """T011: delete_playbook soft-deletes via meta.deleted_at."""

    def test_soft_deletes(self, seeded_db: Path) -> None:
        changed, msg = delete_playbook(seeded_db, "pb-a")
        assert changed
        assert "Deleted" in msg
        conn = get_connection(seeded_db)
        try:
            row = conn.execute(
                "SELECT deleted_at FROM playbook_meta WHERE playbook_id = 'pb-a'"
            ).fetchone()
            assert row["deleted_at"] is not None
        finally:
            conn.close()

    def test_idempotent_when_already_deleted(self, seeded_db: Path) -> None:
        delete_playbook(seeded_db, "pb-a")
        changed, msg = delete_playbook(seeded_db, "pb-a")
        assert not changed
        assert "already deleted" in msg

    def test_raises_for_nonexistent_playbook(self, db_path: Path) -> None:
        init_database(db_path)
        with pytest.raises(ValueError, match="not found"):
            delete_playbook(db_path, "ghost")


# ===================================================================
# T014: get_playbook_history (contract)
# ===================================================================


class TestGetPlaybookHistory:
    """T014: get_playbook_history returns version timeline."""

    def test_returns_full_history(self, seeded_db: Path) -> None:
        rows, current, is_deleted = get_playbook_history(seeded_db, "pb-a")
        assert len(rows) == 2
        assert rows[0]["version"] == 1
        assert rows[1]["version"] == 2
        assert current == 2
        assert not is_deleted

    def test_current_and_latest_flags(self, seeded_db: Path) -> None:
        rows, current, is_deleted = get_playbook_history(seeded_db, "pb-a")
        for r in rows:
            if r["version"] == 2:
                assert r["is_current"]
                assert r["is_latest"]
            else:
                assert not r["is_current"]
                assert not r["is_latest"]

    def test_current_flag_reflects_set_current(self, seeded_db: Path) -> None:
        set_current_version(seeded_db, "pb-a", 1)
        rows, current, is_deleted = get_playbook_history(seeded_db, "pb-a")
        assert current == 1
        for r in rows:
            if r["version"] == 1:
                assert r["is_current"]
            else:
                assert not r["is_current"]

    def test_deleted_flag(self, seeded_db: Path) -> None:
        delete_playbook(seeded_db, "pb-a")
        _, _, is_deleted = get_playbook_history(seeded_db, "pb-a")
        assert is_deleted

    def test_raises_for_nonexistent_playbook(self, db_path: Path) -> None:
        init_database(db_path)
        with pytest.raises(ValueError, match="not found"):
            get_playbook_history(db_path, "ghost")


# ===================================================================
# list_playbooks extended (contract)
# ===================================================================


class TestListPlaybooksExtended:
    """Extended list_playbooks_with_meta with include_deleted and is_deleted flag."""

    def test_lists_all_playbooks(self, seeded_db: Path) -> None:
        pbs = list_playbooks_with_meta(seeded_db)
        ids = {pb[0] for pb in pbs}
        assert ids == {"pb-a", "pb-b"}

    def test_returns_four_tuple(self, seeded_db: Path) -> None:
        """Returns (playbook_id, max_version, created_at, is_deleted)."""
        pbs = list_playbooks_with_meta(seeded_db)
        for pb in pbs:
            assert len(pb) == 4
            assert isinstance(pb[0], str)  # playbook_id
            assert isinstance(pb[1], int)  # max_version
            assert isinstance(pb[2], str)  # created_at
            assert isinstance(pb[3], bool)  # is_deleted

    def test_include_deleted_false_excludes_deleted(self, seeded_db: Path) -> None:
        delete_playbook(seeded_db, "pb-a")
        pbs = list_playbooks_with_meta(seeded_db, include_deleted=False)
        ids = {pb[0] for pb in pbs}
        assert "pb-a" not in ids
        assert "pb-b" in ids

    def test_include_deleted_true_includes_deleted(self, seeded_db: Path) -> None:
        delete_playbook(seeded_db, "pb-a")
        pbs = list_playbooks_with_meta(seeded_db, include_deleted=True)
        ids = {pb[0] for pb in pbs}
        assert ids == {"pb-a", "pb-b"}
        for pb in pbs:
            if pb[0] == "pb-a":
                assert pb[3] is True
            else:
                assert pb[3] is False

    def test_empty_db(self, db_path: Path) -> None:
        init_database(db_path)
        pbs = list_playbooks_with_meta(db_path)
        assert pbs == []


class TestListPlaybooksBackwardCompat:
    """Original list_playbooks remains backward compatible."""

    def test_returns_three_tuple(self, seeded_db: Path) -> None:
        pbs = list_playbooks(seeded_db)
        assert len(pbs) == 2
        for pb in pbs:
            assert len(pb) == 3
            assert isinstance(pb[0], str)
            assert isinstance(pb[1], int)
            assert isinstance(pb[2], str)

    def test_empty_db(self, db_path: Path) -> None:
        init_database(db_path)
        assert list_playbooks(db_path) == []


# ===================================================================
# Edge cases — no playbook data, multiple deletes, etc.
# ===================================================================


class TestEdgeCases:
    """Edge cases for storage helpers."""

    def test_ensure_meta_no_versions(self, db_path: Path) -> None:
        """Fresh database with no playbook_versions raises ValueError."""
        init_database(db_path)
        with pytest.raises(ValueError, match="not found"):
            ensure_playbook_meta(db_path, "nonexistent")

    def test_get_current_version_no_meta_no_versions(self, db_path: Path) -> None:
        init_database(db_path)
        with pytest.raises(ValueError, match="not found"):
            get_current_version(db_path, "nonexistent")

    def test_get_history_no_meta(self, seeded_db: Path) -> None:
        """History should work even without a playbook_meta row."""
        rows, current, is_deleted = get_playbook_history(seeded_db, "pb-b")
        assert len(rows) == 1
        assert current == 1
        assert not is_deleted
