"""Integration tests for playbook versioning."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from openreview_cli.review.playbook import load_playbook


@pytest.fixture
def db_path() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    from openreview_cli.storage.database import init_database

    init_database(path)
    return path


def _make_playbook_yaml(
    path: Path,
    playbook_id: str = "test-pb",
    version: str = "1.0.0",
    extra_cat: bool = False,
) -> None:
    cats = [
        {
            "id": "test-cat",
            "name": "Test",
            "description": "Test",
            "favorable": {"description": "Fav", "exemplars": ["e1"]},
            "neutral": {"description": "Neu", "exemplars": ["e2"]},
            "unfavorable": {"description": "Unf", "exemplars": ["e3"]},
            "default_position": "neutral",
        }
    ]
    if extra_cat:
        cats.append(
            {
                "id": "extra-cat",
                "name": "Extra",
                "description": "Extra",
                "favorable": {"description": "Fav", "exemplars": ["e1"]},
                "neutral": {"description": "Neu", "exemplars": ["e2"]},
                "unfavorable": {"description": "Unf", "exemplars": ["e3"]},
                "default_position": "favorable",
            }
        )
    data = {
        "id": playbook_id,
        "mode": "precheck",
        "metadata": {
            "version": version,
            "description": "Test",
            "author": "test",
        },
        "categories": cats,
    }
    path.write_text(yaml.dump(data), encoding="utf-8")


class TestFirstReviewBundled:
    def test_creates_playbook_version_row(self, db_path: Path) -> None:
        from openreview_cli.review.playbook import BUNDLED_PLAYBOOK_PATH
        from openreview_cli.storage.database import find_version

        playbook = load_playbook(BUNDLED_PLAYBOOK_PATH, db_path=db_path)
        assert playbook.version_id == "precheck-nda-v1@1.0.0"
        found = find_version(db_path, "precheck-nda-v1", "1.0.0")
        assert found is not None

    def test_duplicate_run_reuses_row(self, db_path: Path) -> None:
        from openreview_cli.review.playbook import BUNDLED_PLAYBOOK_PATH
        from openreview_cli.storage.database import find_version, transaction

        load_playbook(BUNDLED_PLAYBOOK_PATH, db_path=db_path)
        load_playbook(BUNDLED_PLAYBOOK_PATH, db_path=db_path)

        with transaction(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM playbook_version WHERE id = ? AND version = ?",
                ("precheck-nda-v1", "1.0.0"),
            ).fetchone()[0]
        assert count == 1
        found = find_version(db_path, "precheck-nda-v1", "1.0.0")
        assert found is not None


class TestAutoVersioning:
    def test_version_less_stores_as_0_1_0(self, db_path: Path) -> None:
        from openreview_cli.storage.database import find_version

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            fpath = Path(f.name)
        try:
            _make_playbook_yaml(fpath, version="")
            playbook = load_playbook(fpath, db_path=db_path)
            assert playbook.metadata.version == "0.1.0"
            found = find_version(db_path, "test-pb", "0.1.0")
            assert found is not None
        finally:
            fpath.unlink()

    def test_no_duplicate_on_second_load(self, db_path: Path) -> None:
        from openreview_cli.storage.database import transaction

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            fpath = Path(f.name)
        try:
            _make_playbook_yaml(fpath, version="")
            load_playbook(fpath, db_path=db_path)
            load_playbook(fpath, db_path=db_path)
            with transaction(db_path) as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM playbook_version WHERE id = ?",
                    ("test-pb",),
                ).fetchone()[0]
            assert count == 1
        finally:
            fpath.unlink()


class TestContentChangeDetection:
    def test_modified_content_creates_plus_one(self, db_path: Path) -> None:
        from openreview_cli.storage.database import find_version

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            fpath = Path(f.name)
        try:
            _make_playbook_yaml(fpath, playbook_id="test-pb", version="1.0.0")
            playbook1 = load_playbook(fpath, db_path=db_path)
            assert playbook1.version_id == "test-pb@1.0.0"

            # Modify the playbook content (same version)
            _make_playbook_yaml(fpath, playbook_id="test-pb", version="1.0.0", extra_cat=True)
            playbook2 = load_playbook(fpath, db_path=db_path)
            assert playbook2.version_id is not None
            assert "test-pb@1.0.0+" in playbook2.version_id

            # Old version still exists
            old = find_version(db_path, "test-pb", "1.0.0")
            assert old is not None
        finally:
            fpath.unlink()

    def test_old_report_still_referenced(self, db_path: Path) -> None:
        from openreview_cli.storage.database import find_version

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            fpath = Path(f.name)
        try:
            _make_playbook_yaml(fpath, playbook_id="test-pb", version="1.0.0")
            playbook1 = load_playbook(fpath, db_path=db_path)
            v1_id = playbook1.version_id

            _make_playbook_yaml(fpath, playbook_id="test-pb", version="1.0.0", extra_cat=True)
            playbook2 = load_playbook(fpath, db_path=db_path)

            assert v1_id != playbook2.version_id
            old = find_version(db_path, "test-pb", "1.0.0")
            assert old is not None
        finally:
            fpath.unlink()


class TestThreeModes:
    def test_three_playbooks_store_independently(self, db_path: Path) -> None:
        from openreview_cli.review.playbook import BUNDLED_PLAYBOOK_PATH
        from openreview_cli.storage.database import transaction

        precheck_path = BUNDLED_PLAYBOOK_PATH
        dealcheck_path = BUNDLED_PLAYBOOK_PATH.parent / "dealcheck-nda-v1.yaml"
        hirecheck_path = BUNDLED_PLAYBOOK_PATH.parent / "hirecheck-terms-v1.yaml"

        load_playbook(precheck_path, db_path=db_path)
        load_playbook(dealcheck_path, db_path=db_path)
        load_playbook(hirecheck_path, db_path=db_path)

        with transaction(db_path) as conn:
            rows = conn.execute("SELECT id, version FROM playbook_version ORDER BY id").fetchall()
        ids = [(r[0], r[1]) for r in rows]
        assert ("precheck-nda-v1", "1.0.0") in ids
        assert ("dealcheck-nda-v1", "1.0.0") in ids
        assert ("hirecheck-terms-v1", "1.0.0") in ids


class TestVersionPin:
    def test_pinned_version_reuse(self, db_path: Path) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            fpath = Path(f.name)
        try:
            _make_playbook_yaml(fpath, playbook_id="test-pb", version="1.0.0")
            load_playbook(fpath, db_path=db_path)

            playbook = load_playbook(fpath, db_path=db_path, pin_version="1.0.0")
            assert playbook.version_id == "test-pb@1.0.0"
        finally:
            fpath.unlink()

    def test_version_mismatch_error(self, db_path: Path) -> None:
        from openreview_cli.review.playbook import PlaybookLoadError

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            fpath = Path(f.name)
        try:
            _make_playbook_yaml(fpath, playbook_id="test-pb", version="1.0.0")
            with pytest.raises(PlaybookLoadError, match="Requested version"):
                load_playbook(fpath, db_path=db_path, pin_version="2.0.0")
        finally:
            fpath.unlink()
