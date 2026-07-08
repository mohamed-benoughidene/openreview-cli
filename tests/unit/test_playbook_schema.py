"""Unit tests for playbook schema validation across all modes."""

from pathlib import Path

import pytest
import yaml

from openreview_cli.review.playbook import (
    BUNDLED_PLAYBOOKS,
    PlaybookLoadError,
    load_playbook,
)
from openreview_cli.review.prompts import MODE_VOCABULARY

PLAYBOOKS_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "src"
    / "openreview_cli"
    / "review"
    / "playbooks"
)


class TestBundledPlaybooks:
    """Validate all bundled playbook YAML files load without error."""

    @pytest.mark.parametrize(
        "mode, filename",
        [
            ("precheck", "precheck-nda-v1.yaml"),
            ("licensecheck", "saas-license-v1.yaml"),
            ("leasecheck", "commercial-lease-v1.yaml"),
            ("privacycheck", "dpa-v1.yaml"),
            ("dealcheck", "dealcheck-v1.yaml"),
            ("hirecheck", "hirecheck-v1.yaml"),
            ("indemnitycheck", "indemnification-v1.yaml"),
            ("consultcheck", "consulting-agreement-v1.yaml"),
            ("workcheck", "work-for-hire-v1.yaml"),
            ("loicheck", "letter-of-intent-v1.yaml"),
            ("subcheck", "subcontractor-agreement-v1.yaml"),
            ("settlementcheck", "settlement-agreement-v1.yaml"),
        ],
    )
    def test_playbook_loads_successfully(self, mode: str, filename: str) -> None:
        path = PLAYBOOKS_DIR / filename
        assert path.exists(), f"Playbook not found: {path}"
        playbook = load_playbook(path)
        assert playbook.id is not None
        assert playbook.mode == mode
        assert len(playbook.categories) > 0
        assert playbook.metadata.version is not None
        assert playbook.metadata.description is not None
        assert playbook.metadata.author is not None

    @pytest.mark.parametrize(
        "mode, filename",
        [
            ("precheck", "precheck-nda-v1.yaml"),
            ("licensecheck", "saas-license-v1.yaml"),
            ("leasecheck", "commercial-lease-v1.yaml"),
            ("privacycheck", "dpa-v1.yaml"),
            ("dealcheck", "dealcheck-v1.yaml"),
            ("hirecheck", "hirecheck-v1.yaml"),
            ("indemnitycheck", "indemnification-v1.yaml"),
            ("consultcheck", "consulting-agreement-v1.yaml"),
            ("workcheck", "work-for-hire-v1.yaml"),
            ("loicheck", "letter-of-intent-v1.yaml"),
            ("subcheck", "subcontractor-agreement-v1.yaml"),
            ("settlementcheck", "settlement-agreement-v1.yaml"),
        ],
    )
    def test_playbook_has_valid_categories(self, mode: str, filename: str) -> None:
        path = PLAYBOOKS_DIR / filename
        playbook = load_playbook(path)

        for cat in playbook.categories:
            assert cat.id, f"Category missing id in {filename}"
            assert cat.name, f"Category '{cat.id}' missing name"
            assert cat.description, f"Category '{cat.id}' missing description"
            assert cat.preferred.description, f"Category '{cat.id}' preferred missing description"
            assert cat.preferred.exemplars, f"Category '{cat.id}' preferred missing exemplars"
            assert cat.acceptable.description, f"Category '{cat.id}' acceptable missing description"
            assert cat.acceptable.exemplars, f"Category '{cat.id}' acceptable missing exemplars"
            assert cat.walkaway.description, f"Category '{cat.id}' walkaway missing description"
            assert cat.walkaway.exemplars, f"Category '{cat.id}' walkaway missing exemplars"
            assert cat.default_position is not None

    def test_bundled_playbooks_mapping_all_modes(self) -> None:
        """Verify BUNDLED_PLAYBOOKS dict covers all known modes."""
        expected_modes = {
            "precheck",
            "licensecheck",
            "leasecheck",
            "privacycheck",
            "dealcheck",
            "hirecheck",
            "indemnitycheck",
            "consultcheck",
            "workcheck",
            "loicheck",
            "subcheck",
            "settlementcheck",
        }
        assert set(BUNDLED_PLAYBOOKS) == expected_modes

    def test_bundled_playbook_paths_exist(self) -> None:
        for mode, path in BUNDLED_PLAYBOOKS.items():
            assert path.exists(), f"Bundled playbook for '{mode}' not found at {path}"

    def test_non_existent_playbook_raises_error(self) -> None:
        with pytest.raises(PlaybookLoadError):
            load_playbook(PLAYBOOKS_DIR / "nonexistent.yaml")


class TestNewModePlaybooks:
    """Domain-specific validation for product-mode playbooks."""

    @pytest.mark.parametrize(
        "mode, filename, expected_categories",
        [
            ("licensecheck", "saas-license-v1.yaml", 9),
            ("leasecheck", "commercial-lease-v1.yaml", 9),
            ("privacycheck", "dpa-v1.yaml", 8),
            ("dealcheck", "dealcheck-v1.yaml", 6),
            ("hirecheck", "hirecheck-v1.yaml", 6),
            ("indemnitycheck", "indemnification-v1.yaml", 4),
            ("consultcheck", "consulting-agreement-v1.yaml", 5),
            ("workcheck", "work-for-hire-v1.yaml", 5),
            ("loicheck", "letter-of-intent-v1.yaml", 5),
            ("subcheck", "subcontractor-agreement-v1.yaml", 5),
            ("settlementcheck", "settlement-agreement-v1.yaml", 5),
        ],
    )
    def test_category_count(self, mode: str, filename: str, expected_categories: int) -> None:
        path = PLAYBOOKS_DIR / filename
        playbook = load_playbook(path)
        assert len(playbook.categories) == expected_categories, (
            f"{mode} expected {expected_categories} categories, got {len(playbook.categories)}"
        )

    def test_saas_license_v1_metadata(self) -> None:
        path = PLAYBOOKS_DIR / "saas-license-v1.yaml"
        playbook = load_playbook(path)
        assert playbook.id == "saas-license-v1"
        assert playbook.mode == "licensecheck"
        assert "SaaS" in playbook.metadata.description

    def test_commercial_lease_v1_metadata(self) -> None:
        path = PLAYBOOKS_DIR / "commercial-lease-v1.yaml"
        playbook = load_playbook(path)
        assert playbook.id == "commercial-lease-v1"
        assert playbook.mode == "leasecheck"
        assert "lease" in playbook.metadata.description

    def test_dpa_v1_metadata(self) -> None:
        path = PLAYBOOKS_DIR / "dpa-v1.yaml"
        playbook = load_playbook(path)
        assert playbook.id == "dpa-v1"
        assert playbook.mode == "privacycheck"
        assert (
            "DPA" in playbook.metadata.description or "Processing" in playbook.metadata.description
        )

    def test_playbook_yaml_structure(self) -> None:
        """Verify YAML structure has required top-level keys."""
        for filename in (
            "saas-license-v1.yaml",
            "commercial-lease-v1.yaml",
            "dpa-v1.yaml",
            "dealcheck-v1.yaml",
            "hirecheck-v1.yaml",
            "indemnification-v1.yaml",
            "consulting-agreement-v1.yaml",
            "work-for-hire-v1.yaml",
            "letter-of-intent-v1.yaml",
            "subcontractor-agreement-v1.yaml",
            "settlement-agreement-v1.yaml",
        ):
            path = PLAYBOOKS_DIR / filename
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert isinstance(raw, dict), f"{filename} is not a mapping"
            for key in ("id", "mode", "metadata", "categories"):
                assert key in raw, f"{filename} missing required key '{key}'"
            assert isinstance(raw["categories"], list), f"{filename} categories not a list"
            assert len(raw["categories"]) > 0, f"{filename} has no categories"


class TestModeVocabulary:
    """Validate MODE_VOCABULARY entries for all product modes."""

    @pytest.mark.parametrize(
        "mode",
        [
            "precheck",
            "licensecheck",
            "leasecheck",
            "privacycheck",
            "dealcheck",
            "hirecheck",
            "indemnitycheck",
            "consultcheck",
            "workcheck",
            "loicheck",
            "subcheck",
            "settlementcheck",
        ],
    )
    def test_mode_vocabulary_entry_exists(self, mode: str) -> None:
        assert mode in MODE_VOCABULARY, f"MODE_VOCABULARY missing '{mode}' entry"
        entry = MODE_VOCABULARY[mode]
        assert "specialization" in entry, f"MODE_VOCABULARY['{mode}'] missing 'specialization'"
        assert "domain" in entry, f"MODE_VOCABULARY['{mode}'] missing 'domain'"
        assert "vocabulary" in entry, f"MODE_VOCABULARY['{mode}'] missing 'vocabulary'"
        assert len(entry["domain"]) > 0, f"MODE_VOCABULARY['{mode}'] domain empty"
