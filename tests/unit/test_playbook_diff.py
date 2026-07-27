"""Unit tests for Playbook Diff (T021).

Covers diff_playbook_versions() + compute_playbook_diff() contract:
equal versions, category added/removed, description changed,
exemplar added/removed, version normalisation, non-existent version error.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openreview_cli.review.playbook import compute_playbook_diff
from openreview_cli.storage.database import (
    get_connection,
    init_database,
)
from openreview_cli.storage.playbooks import (
    diff_playbook_versions,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_playbook_diff.db"


@pytest.fixture
def seeded_db(db_path: Path) -> Path:
    """Init database, seed playbook_versions with one playbook, return db_path."""
    init_database(db_path)
    _seed_playbook(db_path, "pb-a", {"name": "a1", "metadata": {"version": 1}})
    _seed_playbook(db_path, "pb-a", {"name": "a2", "metadata": {"version": 2}})
    _seed_playbook(db_path, "pb-b", {"name": "b1", "metadata": {"version": 1}})
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
# T021: diff_playbook_versions + compute_playbook_diff
# ===================================================================


class TestDiffPlaybookVersions:
    """diff_playbook_versions fetches raw data; compute_playbook_diff computes diff."""

    def test_equal_versions(self, seeded_db: Path) -> None:
        """Same version twice returns unchanged."""
        d1, d2, v1, v2 = diff_playbook_versions(seeded_db, "pb-a", 1, 1)
        assert v1 == 1
        assert v2 == 1
        diff = compute_playbook_diff(d1, d2)
        assert diff.status == "unchanged"

    def test_category_added(self, db_path: Path) -> None:
        init_database(db_path)
        _seed_playbook(
            db_path,
            "pb",
            {
                "categories": [
                    {
                        "id": "c1",
                        "name": "C1",
                        "description": "",
                        "preferred": {"description": "d", "exemplars": ["e"]},
                        "acceptable": {"description": "d", "exemplars": ["e"]},
                        "walkaway": {"description": "d", "exemplars": ["e"]},
                        "default_position": "preferred",
                    }
                ]
            },
        )
        _seed_playbook(
            db_path,
            "pb",
            {
                "categories": [
                    {
                        "id": "c1",
                        "name": "C1",
                        "description": "",
                        "preferred": {"description": "d", "exemplars": ["e"]},
                        "acceptable": {"description": "d", "exemplars": ["e"]},
                        "walkaway": {"description": "d", "exemplars": ["e"]},
                        "default_position": "preferred",
                    },
                    {
                        "id": "c2",
                        "name": "C2",
                        "description": "",
                        "preferred": {"description": "d", "exemplars": ["e"]},
                        "acceptable": {"description": "d", "exemplars": ["e"]},
                        "walkaway": {"description": "d", "exemplars": ["e"]},
                        "default_position": "acceptable",
                    },
                ]
            },
        )
        d1, d2, _v1, _v2 = diff_playbook_versions(db_path, "pb", 1, 2)
        diff = compute_playbook_diff(d1, d2)
        assert diff.status == "changed"
        assert "c2" in diff.added_categories
        assert diff.removed_categories == []

    def test_category_removed(self, db_path: Path) -> None:
        init_database(db_path)
        _seed_playbook(
            db_path,
            "pb",
            {
                "categories": [
                    {
                        "id": "c1",
                        "name": "C1",
                        "description": "",
                        "preferred": {"description": "d", "exemplars": ["e"]},
                        "acceptable": {"description": "d", "exemplars": ["e"]},
                        "walkaway": {"description": "d", "exemplars": ["e"]},
                        "default_position": "preferred",
                    },
                    {
                        "id": "c2",
                        "name": "C2",
                        "description": "",
                        "preferred": {"description": "d", "exemplars": ["e"]},
                        "acceptable": {"description": "d", "exemplars": ["e"]},
                        "walkaway": {"description": "d", "exemplars": ["e"]},
                        "default_position": "acceptable",
                    },
                ]
            },
        )
        _seed_playbook(
            db_path,
            "pb",
            {
                "categories": [
                    {
                        "id": "c1",
                        "name": "C1",
                        "description": "",
                        "preferred": {"description": "d", "exemplars": ["e"]},
                        "acceptable": {"description": "d", "exemplars": ["e"]},
                        "walkaway": {"description": "d", "exemplars": ["e"]},
                        "default_position": "preferred",
                    }
                ]
            },
        )
        d1, d2, _v1, _v2 = diff_playbook_versions(db_path, "pb", 1, 2)
        diff = compute_playbook_diff(d1, d2)
        assert diff.status == "changed"
        assert diff.removed_categories == ["c2"]

    def test_changed_description(self, db_path: Path) -> None:
        init_database(db_path)
        _seed_playbook(
            db_path,
            "pb",
            {
                "categories": [
                    {
                        "id": "c1",
                        "name": "C1",
                        "description": "old",
                        "preferred": {"description": "d", "exemplars": ["e"]},
                        "acceptable": {"description": "d", "exemplars": ["e"]},
                        "walkaway": {"description": "d", "exemplars": ["e"]},
                        "default_position": "preferred",
                    }
                ]
            },
        )
        _seed_playbook(
            db_path,
            "pb",
            {
                "categories": [
                    {
                        "id": "c1",
                        "name": "C1",
                        "description": "new",
                        "preferred": {"description": "d", "exemplars": ["e"]},
                        "acceptable": {"description": "d", "exemplars": ["e"]},
                        "walkaway": {"description": "d", "exemplars": ["e"]},
                        "default_position": "preferred",
                    }
                ]
            },
        )
        d1, d2, _v1, _v2 = diff_playbook_versions(db_path, "pb", 1, 2)
        diff = compute_playbook_diff(d1, d2)
        assert diff.status == "changed"
        assert diff.changed_categories["c1"]["description"] == {
            "before": "old",
            "after": "new",
        }

    def test_exemplars_added_removed(self, db_path: Path) -> None:
        init_database(db_path)
        _seed_playbook(
            db_path,
            "pb",
            {
                "categories": [
                    {
                        "id": "c1",
                        "name": "C1",
                        "description": "",
                        "preferred": {"description": "d", "exemplars": ["e1"]},
                        "acceptable": {"description": "d", "exemplars": ["e"]},
                        "walkaway": {"description": "d", "exemplars": ["e"]},
                        "default_position": "preferred",
                    }
                ]
            },
        )
        _seed_playbook(
            db_path,
            "pb",
            {
                "categories": [
                    {
                        "id": "c1",
                        "name": "C1",
                        "description": "",
                        "preferred": {"description": "d", "exemplars": ["e1", "e2"]},
                        "acceptable": {"description": "d", "exemplars": ["e"]},
                        "walkaway": {"description": "d", "exemplars": ["e"]},
                        "default_position": "preferred",
                    }
                ]
            },
        )
        d1, d2, _v1, _v2 = diff_playbook_versions(db_path, "pb", 1, 2)
        diff = compute_playbook_diff(d1, d2)
        assert diff.status == "changed"
        assert "e2" in diff.changed_categories["c1"]["exemplars_added"]
        assert "exemplars_removed" not in diff.changed_categories["c1"]

    def test_normalises_v1_greater_than_v2(self, db_path: Path) -> None:
        init_database(db_path)
        _seed_playbook(
            db_path,
            "pb",
            {
                "categories": [
                    {
                        "id": "c1",
                        "name": "C1",
                        "description": "old",
                        "preferred": {"description": "d", "exemplars": ["e"]},
                        "acceptable": {"description": "d", "exemplars": ["e"]},
                        "walkaway": {"description": "d", "exemplars": ["e"]},
                        "default_position": "preferred",
                    }
                ]
            },
        )
        _seed_playbook(
            db_path,
            "pb",
            {
                "categories": [
                    {
                        "id": "c1",
                        "name": "C1",
                        "description": "new",
                        "preferred": {"description": "d", "exemplars": ["e"]},
                        "acceptable": {"description": "d", "exemplars": ["e"]},
                        "walkaway": {"description": "d", "exemplars": ["e"]},
                        "default_position": "preferred",
                    }
                ]
            },
        )
        d1, d2, v1, v2 = diff_playbook_versions(db_path, "pb", 2, 1)
        assert v1 == 1
        assert v2 == 2
        diff = compute_playbook_diff(d1, d2)
        assert diff.status == "changed"

    def test_raises_for_nonexistent_version(self, seeded_db: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            diff_playbook_versions(seeded_db, "pb-a", 1, 99)
