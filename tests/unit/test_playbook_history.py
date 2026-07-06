"""Unit tests for playbook history command (T039)."""

from __future__ import annotations

from pathlib import Path

import pytest

from openreview_cli.storage.database import (
    delete_playbook,
    get_playbook_history,
    import_playbook_yaml,
    init_database,
    set_current_version,
)


def _seed_playbook(db_path: Path, playbook_id: str, versions: int = 3) -> None:
    init_database(db_path)
    for v in range(1, versions + 1):
        content = '{"id": "' + playbook_id + '", "version": ' + str(v) + ', "categories": []}'
        import_playbook_yaml(db_path, playbook_id, content)


class TestGetPlaybookHistory:
    """T039 unit tests for get_playbook_history storage function."""

    def test_multi_version_history(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1", 3)

        rows, current_version, is_deleted = get_playbook_history(db, "pb1")
        assert len(rows) == 3
        assert rows[0]["version"] == 1
        assert rows[1]["version"] == 2
        assert rows[2]["version"] == 3

    def test_current_version_marker(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1", 3)
        set_current_version(db, "pb1", 2)

        rows, current_version, is_deleted = get_playbook_history(db, "pb1")
        assert current_version == 2
        assert rows[1]["is_current"] is True  # version 2
        assert rows[0]["is_current"] is False  # version 1
        assert rows[2]["is_current"] is False  # version 3

    def test_latest_version_marker(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1", 3)

        rows, _, _ = get_playbook_history(db, "pb1")
        assert rows[0]["is_latest"] is False
        assert rows[1]["is_latest"] is False
        assert rows[2]["is_latest"] is True  # version 3 is latest

    def test_deleted_flag(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1", 2)

        delete_playbook(db, "pb1")
        _, _, is_deleted = get_playbook_history(db, "pb1")
        assert is_deleted is True

    def test_not_deleted_flag(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1", 1)

        _, _, is_deleted = get_playbook_history(db, "pb1")
        assert is_deleted is False

    def test_nonexistent_playbook(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        init_database(db)

        with pytest.raises(ValueError, match="not found"):
            get_playbook_history(db, "no-such-pb")
