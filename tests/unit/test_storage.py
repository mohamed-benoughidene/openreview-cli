"""Unit tests for storage layer CRUD operations."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def db_path() -> Path:
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    from openreview_cli.storage.database import init_database

    init_database(path)
    return path


class TestPlaybookVersionCRUD:
    def test_ensure_playbook_record_inserts(self, db_path: Path) -> None:
        from openreview_cli.storage.database import ensure_playbook_record, transaction

        ensure_playbook_record(
            db_path, "test-playbook", mode="precheck", description="Test playbook", author="test"
        )
        with transaction(db_path) as conn:
            row = conn.execute(
                "SELECT id, mode, description, author FROM playbook WHERE id = ?",
                ("test-playbook",),
            ).fetchone()
        assert row is not None
        assert row[0] == "test-playbook"
        assert row[1] == "precheck"
        assert row[2] == "Test playbook"
        assert row[3] == "test"

    def test_ensure_playbook_record_idempotent(self, db_path: Path) -> None:
        from openreview_cli.storage.database import ensure_playbook_record, transaction

        ensure_playbook_record(db_path, "test-playbook", mode="precheck")
        ensure_playbook_record(db_path, "test-playbook", mode="precheck")
        with transaction(db_path) as conn:
            rows = conn.execute(
                "SELECT COUNT(*) FROM playbook WHERE id = ?", ("test-playbook",)
            ).fetchone()
        assert rows[0] == 1

    def test_insert_and_find_version(self, db_path: Path) -> None:
        from openreview_cli.storage.database import (
            ensure_playbook_record,
            find_version,
            insert_version,
        )

        ensure_playbook_record(db_path, "test-playbook")
        insert_version(db_path, "test-playbook", "1.0.0", "abc123", "content here")

        found = find_version(db_path, "test-playbook", "1.0.0")
        assert found is not None
        assert found["id"] == "test-playbook"
        assert found["version"] == "1.0.0"
        assert found["content_hash"] == "abc123"
        assert found["content"] == "content here"

    def test_find_nonexistent_version(self, db_path: Path) -> None:
        from openreview_cli.storage.database import find_version

        found = find_version(db_path, "nonexistent", "1.0.0")
        assert found is None

    def test_insert_version_idempotent(self, db_path: Path) -> None:
        from openreview_cli.storage.database import (
            ensure_playbook_record,
            insert_version,
            transaction,
        )

        ensure_playbook_record(db_path, "test-playbook")
        insert_version(db_path, "test-playbook", "1.0.0", "abc123", "content")
        insert_version(db_path, "test-playbook", "1.0.0", "abc123", "content")

        with transaction(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM playbook_version WHERE id = ? AND version = ?",
                ("test-playbook", "1.0.0"),
            ).fetchone()[0]
        assert count == 1

    def test_get_max_plus_suffix(self, db_path: Path) -> None:
        from openreview_cli.storage.database import (
            ensure_playbook_record,
            get_max_plus_suffix,
            insert_version,
        )

        ensure_playbook_record(db_path, "test-playbook")
        insert_version(db_path, "test-playbook", "1.0.0", "h1", "content")
        insert_version(db_path, "test-playbook", "1.0.0+1", "h2", "content v2")
        insert_version(db_path, "test-playbook", "1.0.0+2", "h3", "content v3")

        assert get_max_plus_suffix(db_path, "test-playbook", "1.0.0") == 2

    def test_get_max_plus_suffix_no_suffixes(self, db_path: Path) -> None:
        from openreview_cli.storage.database import (
            ensure_playbook_record,
            get_max_plus_suffix,
        )

        ensure_playbook_record(db_path, "test-playbook")
        assert get_max_plus_suffix(db_path, "test-playbook", "1.0.0") == 0
