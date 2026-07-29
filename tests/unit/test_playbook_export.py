"""Unit tests for Playbook Export (T015).

Covers export_playbook_version() contract: specific version export,
current version fallback, non-existent version, non-existent playbook.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openreview_cli.storage.database import (
    get_connection,
    init_database,
)
from openreview_cli.storage.playbooks import (
    export_playbook_version,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_playbook_export.db"


@pytest.fixture
def seeded_db(db_path: Path) -> Path:
    """Init database, seed playbook_versions with one playbook, return db_path."""
    init_database(db_path)
    _seed_playbook(db_path, "pb-a", {"name": "a1", "metadata": {"version": 1}})
    _seed_playbook(db_path, "pb-a", {"name": "a2", "metadata": {"version": 2}})
    return db_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ===================================================================
# T015: export_playbook_version (contract)
# ===================================================================


class TestExportPlaybookVersion:
    """export_playbook_version returns content string for a version."""

    def test_exports_specific_version(self, seeded_db: Path) -> None:
        content = export_playbook_version(seeded_db, "pb-a", version=1)
        assert content is not None
        parsed = json.loads(content)
        assert parsed["name"] == "a1"

    def test_exports_current_version_when_no_arg(self, seeded_db: Path) -> None:
        """No version arg: uses current version (max)."""
        content = export_playbook_version(seeded_db, "pb-a")
        assert content is not None
        parsed = json.loads(content)
        assert parsed["name"] == "a2"

    def test_returns_none_for_nonexistent_version(self, seeded_db: Path) -> None:
        content = export_playbook_version(seeded_db, "pb-a", version=99)
        assert content is None

    def test_raises_for_nonexistent_playbook(self, db_path: Path) -> None:
        init_database(db_path)
        with pytest.raises(ValueError, match="not found"):
            export_playbook_version(db_path, "ghost")
