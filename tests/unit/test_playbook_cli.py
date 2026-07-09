"""Unit tests for playbook CLI command logic (D-46, D-47, D-48).

Tests storage backend behavior for undelete, JSON diff output, bulk ops.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openreview_cli.storage.database import (
    delete_playbook,
    import_playbook_yaml,
    init_database,
    list_playbooks,
    list_playbooks_with_meta,
    set_current_version,
)


def _seed_playbook(db_path: Path, playbook_id: str) -> None:
    init_database(db_path)
    content = '{"id": "' + playbook_id + '", "categories": []}'
    import_playbook_yaml(db_path, playbook_id, content)


class TestUndelete:
    """D-46: Undelete via set_current_version (clears deleted_at)."""

    def test_undelete_restores_to_active_list(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1")
        delete_playbook(db, "pb1")

        # Verify deleted
        active = list_playbooks_with_meta(db, include_deleted=False)
        assert len(active) == 0

        # Undelete by re-setting current version
        set_current_version(db, "pb1", 1)

        # Verify back in active list
        active = list_playbooks_with_meta(db, include_deleted=False)
        assert len(active) == 1
        assert active[0][0] == "pb1"

    def test_undelete_clears_deleted_flag(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1")
        delete_playbook(db, "pb1")

        meta = list_playbooks_with_meta(db, include_deleted=True)
        assert meta[0][3] is True

        set_current_version(db, "pb1", 1)

        meta = list_playbooks_with_meta(db, include_deleted=True)
        assert meta[0][3] is False

    def test_undelete_nonexistent(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        init_database(db)
        with pytest.raises(ValueError, match="not found"):
            set_current_version(db, "no-such-pb", 1)

    def test_undelete_already_active(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb1")

        # Already active — no change expected
        changed, msg = set_current_version(db, "pb1", 1)
        assert changed is False
        assert "already current" in msg


class TestDiffJson:
    """D-47: compute_playbook_diff produces JSON-serialisable output."""

    def test_diff_json_has_expected_keys(self) -> None:
        from openreview_cli.review.playbook import compute_playbook_diff

        v1_data = {"id": "pb", "categories": [{"id": "cat1", "name": "First"}]}
        v2_data = {
            "id": "pb",
            "categories": [
                {"id": "cat1", "name": "First Updated"},
                {"id": "cat2", "name": "Second"},
            ],
        }

        diff = compute_playbook_diff(v1_data, v2_data)
        import dataclasses

        d = dataclasses.asdict(diff)

        assert "added_categories" in d
        assert "removed_categories" in d
        assert "changed_categories" in d
        assert "v1" in d
        assert "v2" in d
        assert "cat2" in d["added_categories"]
        assert len(d["removed_categories"]) == 0

    def test_diff_json_serializable(self) -> None:
        from openreview_cli.review.playbook import compute_playbook_diff

        v1_data = {"id": "pb", "categories": [{"id": "cat1"}]}
        v2_data = {"id": "pb", "categories": [{"id": "cat1"}, {"id": "cat2"}]}

        diff = compute_playbook_diff(v1_data, v2_data)
        import dataclasses

        d = dataclasses.asdict(diff)
        dumped = json.dumps(d, indent=2)
        loaded = json.loads(dumped)

        assert "added_categories" in loaded
        assert loaded["added_categories"] == ["cat2"]

    def test_diff_json_removed_categories(self) -> None:
        from openreview_cli.review.playbook import compute_playbook_diff

        v1_data = {"id": "pb", "categories": [{"id": "cat1"}, {"id": "cat2"}]}
        v2_data = {"id": "pb", "categories": [{"id": "cat1"}]}

        diff = compute_playbook_diff(v1_data, v2_data)
        import dataclasses

        d = dataclasses.asdict(diff)

        assert d["removed_categories"] == ["cat2"]
        assert len(d["added_categories"]) == 0


class TestBulkExport:
    """D-48: Bulk export iterates all playbooks."""

    def test_export_all_playbooks(self, tmp_path: Path) -> None:
        from openreview_cli.storage.database import export_playbook_version

        db = tmp_path / "test.db"
        _seed_playbook(db, "pb-x1")
        _seed_playbook(db, "pb-x2")

        all_pbs = list_playbooks(db)
        assert len(all_pbs) == 2

        out_dir = tmp_path / "exports"
        out_dir.mkdir()

        for pb_id, _ver, _created in all_pbs:
            content = export_playbook_version(db, pb_id)
            assert content is not None
            (out_dir / f"{pb_id}.yaml").write_text(content, encoding="utf-8")

        assert (out_dir / "pb-x1.yaml").exists()
        assert (out_dir / "pb-x2.yaml").exists()

    def test_bulk_export_empty(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        init_database(db)

        all_pbs = list_playbooks(db)
        assert len(all_pbs) == 0


class TestBulkDelete:
    """D-48: Bulk delete soft-deletes all playbooks."""

    def test_delete_all_playbooks(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb-d1")
        _seed_playbook(db, "pb-d2")

        delete_playbook(db, "pb-d1")
        delete_playbook(db, "pb-d2")

        active = list_playbooks_with_meta(db, include_deleted=False)
        assert len(active) == 0

        all_pbs = list_playbooks_with_meta(db, include_deleted=True)
        assert len(all_pbs) == 2

    def test_bulk_delete_idempotent(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _seed_playbook(db, "pb-d3")
        delete_playbook(db, "pb-d3")
        # Second delete is idempotent
        changed, msg = delete_playbook(db, "pb-d3")
        assert changed is False
        assert "already deleted" in msg

    def test_bulk_delete_mixed(self, tmp_path: Path) -> None:
        """Verify only undeleted playbooks are affected by delete."""
        db = tmp_path / "test.db"
        _seed_playbook(db, "keep")
        _seed_playbook(db, "remove")

        delete_playbook(db, "remove")

        keep_active = [
            p for p in list_playbooks_with_meta(db, include_deleted=False) if p[0] == "keep"
        ]
        remove_active = [
            p for p in list_playbooks_with_meta(db, include_deleted=False) if p[0] == "remove"
        ]

        assert len(keep_active) == 1
        assert len(remove_active) == 0
