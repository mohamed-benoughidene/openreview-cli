"""Unit tests for HireCheck playbook schema and loading."""

from pathlib import Path

import pytest
import yaml

from openreview_cli.review.playbook import PlaybookLoadError, load_playbook

PLAYBOOKS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "src"
    / "openreview_cli"
    / "review"
    / "playbooks"
)

HIRECHECK_YAML = "hirecheck-v1.yaml"


class TestHireCheckPlaybook:
    """HireCheck playbook validation."""

    def test_hirecheck_yaml_exists(self) -> None:
        path = PLAYBOOKS_DIR / HIRECHECK_YAML
        assert path.exists(), f"HireCheck playbook not found: {path}"

    def test_hirecheck_loads_successfully(self) -> None:
        path = PLAYBOOKS_DIR / HIRECHECK_YAML
        playbook = load_playbook(path)
        assert playbook.id == "hirecheck-v1"
        assert playbook.mode == "hirecheck"
        assert playbook.metadata.version is not None
        assert playbook.metadata.description is not None
        assert playbook.metadata.author is not None
        assert len(playbook.categories) > 0

    def test_hirecheck_has_required_top_level_keys(self) -> None:
        path = PLAYBOOKS_DIR / HIRECHECK_YAML
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict)
        for key in ("id", "mode", "metadata", "categories"):
            assert key in raw, f"Missing required key '{key}'"

    def test_hirecheck_categories_have_three_positions(self) -> None:
        path = PLAYBOOKS_DIR / HIRECHECK_YAML
        playbook = load_playbook(path)
        for cat in playbook.categories:
            assert cat.id
            assert cat.name
            assert cat.description
            # Each category must have all three positions defined
            assert cat.preferred.description, f"Category '{cat.id}' preferred missing description"
            assert cat.preferred.exemplars, f"Category '{cat.id}' preferred missing exemplars"
            assert cat.acceptable.description, f"Category '{cat.id}' acceptable missing description"
            assert cat.acceptable.exemplars, f"Category '{cat.id}' acceptable missing exemplars"
            assert cat.walkaway.description, f"Category '{cat.id}' walkaway missing description"
            assert cat.walkaway.exemplars, f"Category '{cat.id}' walkaway missing exemplars"
            assert cat.default_position is not None

    def test_hirecheck_categories_count(self) -> None:
        path = PLAYBOOKS_DIR / HIRECHECK_YAML
        playbook = load_playbook(path)
        assert len(playbook.categories) == 6

    def test_hirecheck_non_existent_raises_error(self) -> None:
        with pytest.raises(PlaybookLoadError):
            load_playbook(PLAYBOOKS_DIR / "nonexistent.yaml")
