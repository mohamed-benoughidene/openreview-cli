"""Unit tests for playbook loader (YAML parsing, validation, bundled playbook)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from openreview_cli.review.models import Playbook
from openreview_cli.review.playbook import (
    PlaybookLoadError,
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
        assert len(playbook.categories) >= 6  # at least 6 categories

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
