"""Unit tests for playbook delete command (T033)."""

from __future__ import annotations

from pathlib import Path

import pytest

from openreview_cli.storage.database import (
    init_database,
)
from openreview_cli.storage.playbooks import (
    delete_playbook,
    import_playbook_yaml,
)


def _seed_playbook(db_path: Path, playbook_id: str) -> None:
    init_database(db_path)
    content = '{"id": "' + playbook_id + '", "categories": []}'
    import_playbook_yaml(db_path, playbook_id, content)


class TestDeletePlaybook:
    """T033 unit tests for delete_playbook storage function."""

    def test_soft_delete_active(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1")

        changed, msg = delete_playbook(db, "pb1")
        assert changed is True
        assert "Deleted playbook 'pb1'" in msg

    def test_delete_nonexistent(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        init_database(db)

        with pytest.raises(ValueError, match="not found"):
            delete_playbook(db, "no-such-pb")

    def test_delete_already_deleted(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1")

        delete_playbook(db, "pb1")
        changed, msg = delete_playbook(db, "pb1")
        assert changed is False
        assert "already deleted" in msg

    def test_delete_idempotent(self, tmp_path: Path) -> None:
        """Multiple deletes after first are all idempotent."""
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1")

        delete_playbook(db, "pb1")
        for _ in range(3):
            changed, msg = delete_playbook(db, "pb1")
            assert changed is False
            assert "already deleted" in msg

    def test_delete_preserves_versions(self, tmp_path: Path) -> None:
        """Soft-delete does not remove version data."""
        db = tmp_path / "test.db"
        init_database(db)
        import_playbook_yaml(db, "pb1", '{"v": 1, "categories": []}')
        import_playbook_yaml(db, "pb1", '{"v": 2, "categories": []}')

        delete_playbook(db, "pb1")

        from openreview_cli.storage.playbooks import get_playbook_version

        v1 = get_playbook_version(db, "pb1", 1)
        v2 = get_playbook_version(db, "pb1", 2)
        assert v1 is not None
        assert v2 is not None
