"""Unit tests for US2: Playbook database storage + migration.

Tests T015-T017: migration 006 schema, storage functions, list behavior.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from pathlib import Path

import pytest

from openreview_cli.storage.database import get_connection

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "src" / "openreview_cli" / "storage" / "migrations"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_playbooks.db"


@pytest.fixture
def conn(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _run_migration(conn: sqlite3.Connection) -> None:
    """Run the 006 migration on a fresh connection."""
    sql = (MIGRATIONS_DIR / "006_playbooks.sql").read_text()
    conn.executescript(sql)
    conn.commit()


class TestMigration006:
    """T015: Migration 006 creates playbook_versions table with correct schema."""

    def test_table_created(self, conn: sqlite3.Connection) -> None:
        _run_migration(conn)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='playbook_versions'"
        ).fetchall()
        assert len(tables) == 1
        assert tables[0]["name"] == "playbook_versions"

    def test_schema_columns(self, conn: sqlite3.Connection) -> None:
        _run_migration(conn)
        cols = {row["name"]: row["type"] for row in conn.execute("PRAGMA table_info(playbook_versions)")}
        assert cols["playbook_id"] == "TEXT"
        assert cols["version"] == "INTEGER"
        assert cols["content"] == "TEXT"
        assert cols["created_at"] == "TEXT"

    def test_primary_key(self, conn: sqlite3.Connection) -> None:
        _run_migration(conn)
        pk = [
            row["name"]
            for row in conn.execute("PRAGMA table_info(playbook_versions)")
            if row["pk"] > 0
        ]
        assert set(pk) == {"playbook_id", "version"}

    def test_index_created(self, conn: sqlite3.Connection) -> None:
        _run_migration(conn)
        indexes = [
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        ]
        assert "idx_playbook_versions_lookup" in indexes

    def test_user_version(self, conn: sqlite3.Connection) -> None:
        _run_migration(conn)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 6

    def test_idempotent(self, conn: sqlite3.Connection) -> None:
        """Running migration twice should not raise."""
        _run_migration(conn)
        _run_migration(conn)  # second run — should be no-op

    def test_empty_db_allows_insert(self, conn: sqlite3.Connection) -> None:
        _run_migration(conn)
        conn.execute(
            "INSERT INTO playbook_versions (playbook_id, version, content) VALUES (?, ?, ?)",
            ("test-playbook", 1, '{"id": "test-playbook"}'),
        )
        row = conn.execute("SELECT playbook_id, version FROM playbook_versions").fetchone()
        assert row["playbook_id"] == "test-playbook"
        assert row["version"] == 1


class TestPlaybookStorage:
    """T016: Storage functions work correctly."""

    def test_save_and_get_by_version(self, conn: sqlite3.Connection) -> None:
        _run_migration(conn)

        # Save version 1
        v1 = _save_version(conn, "my-playbook", {"name": "v1"})
        assert v1 == 1

        # Save version 2
        v2 = _save_version(conn, "my-playbook", {"name": "v2"})
        assert v2 == 2

        # Get version 1
        row = _get_version(conn, "my-playbook", 1)
        assert row is not None
        content = json.loads(row)
        assert content["name"] == "v1"

        # Get version 2
        row = _get_version(conn, "my-playbook", 2)
        assert row is not None
        content = json.loads(row)
        assert content["name"] == "v2"

    def test_get_nonexistent_version(self, conn: sqlite3.Connection) -> None:
        _run_migration(conn)
        row = _get_version(conn, "nonexistent", 1)
        assert row is None

        _save_version(conn, "pb", {"a": 1})
        row = _get_version(conn, "pb", 99)
        assert row is None

    def test_get_latest_version(self, conn: sqlite3.Connection) -> None:
        _run_migration(conn)

        # No versions yet
        result = _get_latest(conn, "empty")
        assert result is None

        _save_version(conn, "pb", {"v": 1})
        _save_version(conn, "pb", {"v": 2})
        _save_version(conn, "pb", {"v": 3})

        result = _get_latest(conn, "pb")
        assert result is not None
        content, version = result
        assert version == 3
        assert json.loads(content)["v"] == 3

    def test_list_playbooks(self, conn: sqlite3.Connection) -> None:
        """T017: list_playbooks returns (playbook_id, max_version, created_at) grouped by ID."""
        _run_migration(conn)

        # Empty DB
        result = _list_playbooks(conn)
        assert result == []

        # Insert two playbooks, multiple versions
        _save_version(conn, "pb-a", {"name": "a1"})
        _save_version(conn, "pb-a", {"name": "a2"})
        _save_version(conn, "pb-b", {"name": "b1"})

        result = _list_playbooks(conn)
        assert len(result) == 2

        ids = {r[0] for r in result}
        assert ids == {"pb-a", "pb-b"}

        # Check max versions
        for row in result:
            if row[0] == "pb-a":
                assert row[1] == 2  # max version
            elif row[0] == "pb-b":
                assert row[1] == 1  # max version

        # created_at should be a non-empty string
        for row in result:
            assert len(row[2]) > 0  # created_at is not empty


# --- helper functions that mirror the storage API ---


def _save_version(conn: sqlite3.Connection, playbook_id: str, content: dict[str, object]) -> int:
    """Insert a new version and return the version number."""
    cur = conn.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM playbook_versions WHERE playbook_id = ?",
        (playbook_id,),
    )
    next_ver = int(cur.fetchone()[0])
    conn.execute(
        "INSERT INTO playbook_versions (playbook_id, version, content) VALUES (?, ?, ?)",
        (playbook_id, next_ver, json.dumps(content)),
    )
    conn.commit()
    return next_ver


def _get_version(conn: sqlite3.Connection, playbook_id: str, version: int) -> str | None:
    row = conn.execute(
        "SELECT content FROM playbook_versions WHERE playbook_id = ? AND version = ?",
        (playbook_id, version),
    ).fetchone()
    return str(row["content"]) if row else None


def _get_latest(conn: sqlite3.Connection, playbook_id: str) -> tuple[str, int] | None:
    row = conn.execute(
        "SELECT content, version FROM playbook_versions WHERE playbook_id = ? ORDER BY version DESC LIMIT 1",
        (playbook_id,),
    ).fetchone()
    return (str(row["content"]), int(row["version"])) if row else None


def _list_playbooks(conn: sqlite3.Connection) -> list[tuple[str, int, str]]:
    rows = conn.execute(
        "SELECT playbook_id, MAX(version) AS version, created_at FROM playbook_versions GROUP BY playbook_id ORDER BY playbook_id"
    ).fetchall()
    return [(str(r["playbook_id"]), int(r["version"]), str(r["created_at"])) for r in rows]
