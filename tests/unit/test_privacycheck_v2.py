"""Unit tests for PrivacyCheck v2 (dpa-v2) playbook."""

from pathlib import Path

from openreview_cli.review.playbook import BUNDLED_PLAYBOOKS, load_playbook
from openreview_cli.review.prompts import MODE_VOCABULARY

PLAYBOOKS_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "src"
    / "openreview_cli"
    / "review"
    / "playbooks"
)


class TestPrivacyCheckV2:
    """Validate dpa-v2.yaml privacycheck_v2 mode."""

    def test_dpa_v2_resolves_from_registry(self) -> None:
        path = BUNDLED_PLAYBOOKS.get("privacycheck_v2")
        assert path is not None, "privacycheck_v2 not in BUNDLED_PLAYBOOKS"
        assert path.exists(), f"dpa-v2.yaml not found at {path}"
        assert path.name == "dpa-v2.yaml"

    def test_dpa_v2_loads(self) -> None:
        path = PLAYBOOKS_DIR / "dpa-v2.yaml"
        playbook = load_playbook(path)
        assert playbook.id == "dpa-v2"
        assert playbook.mode == "privacycheck"
        assert len(playbook.categories) == 10

    def test_dpa_v2_has_dedicated_categories(self) -> None:
        path = PLAYBOOKS_DIR / "dpa-v2.yaml"
        playbook = load_playbook(path)
        cat_ids = {c.id for c in playbook.categories}
        assert "cross-border-transfer" in cat_ids
        assert "sub-processor-change-notification" in cat_ids

    def test_dpa_v2_retains_v1_categories(self) -> None:
        path = PLAYBOOKS_DIR / "dpa-v2.yaml"
        playbook = load_playbook(path)
        cat_ids = {c.id for c in playbook.categories}
        v1_categories = {
            "processing-scope",
            "sub-processor-management",
            "breach-notification",
            "retention-deletion",
            "audit-rights",
            "international-transfers",
            "processing-instructions",
            "dpa-termination",
        }
        assert v1_categories.issubset(cat_ids), (
            f"dpa-v2 missing v1 categories: {v1_categories - cat_ids}"
        )

    def test_privacycheck_v2_prompt_exists(self) -> None:
        assert "privacycheck_v2" in MODE_VOCABULARY
        entry = MODE_VOCABULARY["privacycheck_v2"]
        assert "DPA" in entry["domain"]
        assert "cross-border" in entry["vocabulary"]
        assert "sub-processor change notification" in entry["vocabulary"]

    def test_dpa_v2_v1_backward_compat(self) -> None:
        """privacycheck still resolves to dpa-v1.yaml, unchanged."""
        v1_path = BUNDLED_PLAYBOOKS["privacycheck"]
        assert v1_path.name == "dpa-v1.yaml"
        playbook = load_playbook(v1_path)
        assert playbook.id == "dpa-v1"
        assert len(playbook.categories) == 8

    def test_dpa_v2_categories_have_positions(self) -> None:
        path = PLAYBOOKS_DIR / "dpa-v2.yaml"
        playbook = load_playbook(path)
        for cat in playbook.categories:
            assert cat.preferred.exemplars
            assert cat.acceptable.exemplars
            assert cat.walkaway.exemplars
            assert cat.default_position is not None

    def test_dpa_v2_new_categories_position_content(self) -> None:
        path = PLAYBOOKS_DIR / "dpa-v2.yaml"
        playbook = load_playbook(path)
        cats = {c.id: c for c in playbook.categories}

        cb = cats["cross-border-transfer"]
        assert "transfer impact assessment" in cb.preferred.description.lower()
        assert "TIA" in cb.acceptable.description

        scn = cats["sub-processor-change-notification"]
        assert "Advance notice" in scn.preferred.description
        assert "No notice" in scn.walkaway.description
