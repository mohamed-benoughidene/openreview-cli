"""Unit tests for playbook set-current command (T028)."""

from __future__ import annotations

from pathlib import Path

import pytest

from openreview_cli.storage.database import (
    init_database,
)
from openreview_cli.storage.playbooks import (
    delete_playbook,
    import_playbook_yaml,
    set_current_version,
)


def _seed_playbook(db_path: Path, playbook_id: str, versions: int = 2) -> None:
    """Seed a playbook with N versions."""
    init_database(db_path)
    for v in range(1, versions + 1):
        content = f'{{"id": "{playbook_id}", "version": {v}, "categories": []}}'
        import_playbook_yaml(db_path, playbook_id, content)


class TestSetCurrentVersion:
    """T028 unit tests for set_current_version storage function."""

    def test_set_valid_version(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1", 3)

        changed, msg = set_current_version(db, "pb1", 2)
        assert changed is True
        assert "Set current version of 'pb1' to 2" in msg

    def test_set_already_current(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1", 2)

        # First call sets it
        set_current_version(db, "pb1", 1)
        # Second call should be idempotent
        changed, msg = set_current_version(db, "pb1", 1)
        assert changed is False
        assert "already current" in msg

    def test_set_nonexistent_version(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1", 1)

        with pytest.raises(ValueError, match="not found"):
            set_current_version(db, "pb1", 99)

    def test_set_nonexistent_playbook(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        init_database(db)

        with pytest.raises(ValueError, match="not found"):
            set_current_version(db, "no-such-pb", 1)

    def test_set_reactivates_deleted_playbook(self, tmp_path: Path) -> None:
        """set-current re-activates a deleted playbook (sets deleted_at = NULL)."""
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1", 2)

        delete_playbook(db, "pb1")
        changed, msg = set_current_version(db, "pb1", 1)
        assert changed is True
        assert "Set current version" in msg

    def test_set_after_delete_idempotent(self, tmp_path: Path) -> None:
        """Setting current after reactivation reports changed correctly."""
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1", 2)

        delete_playbook(db, "pb1")
        set_current_version(db, "pb1", 2)
        # Set same version again — should already be current
        changed, msg = set_current_version(db, "pb1", 2)
        assert changed is False
        assert "already current" in msg
