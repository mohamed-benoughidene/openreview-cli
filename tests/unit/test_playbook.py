"""Unit tests for playbook loader (YAML parsing, validation, bundled playbook)."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from openreview_cli.review.models import (
    Playbook,
)
from openreview_cli.review.playbook import (
    PlaybookLoadError,
    content_hash,
    load_bundled,
    load_playbook,
)


def _valid_playbook_dict() -> dict[str, Any]:
    return {
        "id": "test-playbook",
        "mode": "precheck",
        "metadata": {"version": "1.0.0", "description": "Test", "author": "test"},
        "categories": [
            {
                "id": "confidentiality-term",
                "name": "Confidentiality Term",
                "description": "Defines confidentiality term",
                "favorable": {
                    "description": "Short term",
                    "exemplars": ["3 years", "2 years"],
                },
                "neutral": {
                    "description": "Standard term",
                    "exemplars": ["5 years"],
                },
                "unfavorable": {
                    "description": "Indefinite",
                    "exemplars": ["perpetuity", "indefinitely"],
                },
                "default_position": "neutral",
            }
        ],
    }


class TestLoadBundled:
    def test_loads_bundled_playbook(self) -> None:
        """Bundled NDA playbook loads and validates without error."""
        playbook = load_bundled()
        assert isinstance(playbook, Playbook)
        assert playbook.id == "precheck-nda-v1"
        assert playbook.mode == "precheck"
        assert len(playbook.categories) >= 6

    def test_bundled_playbook_has_expected_categories(self) -> None:
        playbook = load_bundled()
        cat_ids = {c.id for c in playbook.categories}
        for expected in (
            "confidentiality-term",
            "permitted-disclosures",
            "non-solicitation",
            "term-and-termination",
            "return-of-materials",
            "boilerplate",
        ):
            assert expected in cat_ids


class TestLoadPlaybook:
    def test_load_valid_yaml(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(_valid_playbook_dict(), f)
            fpath = f.name
        try:
            playbook = load_playbook(Path(fpath))
            assert playbook.id == "test-playbook"
            assert len(playbook.categories) == 1
        finally:
            Path(fpath).unlink()

    def test_file_not_found(self) -> None:
        with pytest.raises(PlaybookLoadError, match="not found"):
            load_playbook(Path("/nonexistent/playbook.yaml"))

    def test_invalid_yaml_syntax(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("{{{invalid: yaml: broken")
            fpath = f.name
        try:
            with pytest.raises(PlaybookLoadError, match="YAML"):
                load_playbook(Path(fpath))
        finally:
            Path(fpath).unlink()

    def test_missing_required_fields(self) -> None:
        d = _valid_playbook_dict()
        del d["id"]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(d, f)
            fpath = f.name
        try:
            with pytest.raises(PlaybookLoadError, match="id"):
                load_playbook(Path(fpath))
        finally:
            Path(fpath).unlink()

    def test_invalid_position_string(self) -> None:
        d = _valid_playbook_dict()
        d["categories"][0]["default_position"] = "invalid_pos"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(d, f)
            fpath = f.name
        try:
            with pytest.raises(PlaybookLoadError):
                load_playbook(Path(fpath))
        finally:
            Path(fpath).unlink()

    def test_empty_categories(self) -> None:
        d = _valid_playbook_dict()
        d["categories"] = []
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(d, f)
            fpath = f.name
        try:
            with pytest.raises(PlaybookLoadError, match="categories"):
                load_playbook(Path(fpath))
        finally:
            Path(fpath).unlink()

    def test_minimal_exemplars_is_empty(self) -> None:
        d = _valid_playbook_dict()
        d["categories"][0]["favorable"]["exemplars"] = []
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(d, f)
            fpath = f.name
        try:
            with pytest.raises(PlaybookLoadError, match="exemplars"):
                load_playbook(Path(fpath))
        finally:
            Path(fpath).unlink()


class TestContentHash:
    def test_sha256_of_bytes(self) -> None:
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        assert content_hash(data) == expected

    def test_different_inputs_different_hashes(self) -> None:
        assert content_hash(b"foo") != content_hash(b"bar")

    def test_same_input_same_hash(self) -> None:
        assert content_hash(b"test") == content_hash(b"test")


class TestVersionDetection:
    def test_bundled_playbook_has_version(self) -> None:
        playbook = load_bundled()
        assert playbook.metadata.version == "1.0.0"

    def test_version_detected_from_yaml(self) -> None:
        d = _valid_playbook_dict()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(d, f)
            fpath = f.name
        try:
            playbook = load_playbook(Path(fpath))
            assert playbook.metadata.version == "1.0.0"
        finally:
            Path(fpath).unlink()

    def test_version_id_attached(self) -> None:
        d = _valid_playbook_dict()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(d, f)
            fpath = f.name
        try:
            playbook = load_playbook(Path(fpath))
            assert playbook.version_id == "test-playbook@1.0.0"
            assert playbook.content_hash is not None
        finally:
            Path(fpath).unlink()


class TestAutoVersioning:
    def test_version_less_playbook_gets_0_1_0(self) -> None:
        d = _valid_playbook_dict()
        d["metadata"] = {"description": "No version", "author": "test"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(d, f)
            fpath = f.name
        try:
            playbook = load_playbook(Path(fpath))
            assert playbook.metadata.version == "0.1.0"
        finally:
            Path(fpath).unlink()

    def test_empty_version_gets_0_1_0(self) -> None:
        d = _valid_playbook_dict()
        d["metadata"]["version"] = ""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(d, f)
            fpath = f.name
        try:
            playbook = load_playbook(Path(fpath))
            assert playbook.metadata.version == "0.1.0"
        finally:
            Path(fpath).unlink()


class TestDbUnavailableFallback:
    def test_loads_without_db_path(self) -> None:
        d = _valid_playbook_dict()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(d, f)
            fpath = f.name
        try:
            playbook = load_playbook(Path(fpath))
            assert playbook.id == "test-playbook"
            assert playbook.metadata.version == "1.0.0"
        finally:
            Path(fpath).unlink()


class TestVersionPin:
    def test_stored_version_reused(self) -> None:
        from openreview_cli.storage.database import init_database

        d = _valid_playbook_dict()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(d, f)
            fpath = f.name
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as dbf:
            db_path = Path(dbf.name)
        try:
            init_database(db_path)
            from openreview_cli.storage.database import (
                ensure_playbook_record,
                insert_version,
            )

            ensure_playbook_record(
                db_path, "test-playbook", mode="precheck", description="Test", author="test"
            )
            raw_bytes = Path(fpath).read_bytes()
            ch = content_hash(raw_bytes)
            insert_version(db_path, "test-playbook", "1.0.0", ch, raw_bytes.decode())
            playbook = load_playbook(Path(fpath), db_path=db_path)
            assert playbook.version_id == "test-playbook@1.0.0"
        finally:
            Path(fpath).unlink()
            db_path.unlink()

    def test_version_mismatch_error(self) -> None:
        d = _valid_playbook_dict()
        d["metadata"]["version"] = "1.0.0"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(d, f)
            fpath = f.name
        try:
            with pytest.raises(PlaybookLoadError, match=r"Requested version.*does not match"):
                load_playbook(Path(fpath), pin_version="2.0.0")
        finally:
            Path(fpath).unlink()


class TestBundledPlaybooks:
    def test_precheck_bundled_loads(self) -> None:
        playbook = load_bundled()
        assert playbook.id == "precheck-nda-v1"
        assert playbook.mode == "precheck"
        assert playbook.metadata.version == "1.0.0"

    def test_dealcheck_playbook_loads(self) -> None:
        from openreview_cli.review.playbook import BUNDLED_PLAYBOOK_PATH

        dealcheck_path = BUNDLED_PLAYBOOK_PATH.parent / "dealcheck-nda-v1.yaml"
        playbook = load_playbook(dealcheck_path)
        assert playbook.id == "dealcheck-nda-v1"
        assert playbook.mode == "dealcheck"
        assert playbook.metadata.version == "1.0.0"

    def test_hirecheck_playbook_loads(self) -> None:
        from openreview_cli.review.playbook import BUNDLED_PLAYBOOK_PATH

        hirecheck_path = BUNDLED_PLAYBOOK_PATH.parent / "hirecheck-terms-v1.yaml"
        playbook = load_playbook(hirecheck_path)
        assert playbook.id == "hirecheck-terms-v1"
        assert playbook.mode == "hirecheck"
        assert playbook.metadata.version == "1.0.0"


class TestNewPositionNaming:
    def test_new_position_names_accepted(self) -> None:
        d = {
            "id": "new-playbook",
            "mode": "precheck",
            "metadata": {"version": "1.0.0", "description": "Test", "author": "test"},
            "categories": [
                {
                    "id": "test-cat",
                    "name": "Test Category",
                    "description": "A test category",
                    "preferred": {
                        "description": "Good position",
                        "exemplars": ["good example"],
                    },
                    "acceptable": {
                        "description": "OK position",
                        "exemplars": ["ok example"],
                    },
                    "walkaway": {
                        "description": "Bad position",
                        "exemplars": ["bad example"],
                    },
                    "default_position": "preferred",
                }
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(d, f)
            fpath = f.name
        try:
            playbook = load_playbook(Path(fpath))
            assert playbook.id == "new-playbook"
            assert len(playbook.categories) == 1
        finally:
            Path(fpath).unlink()
