"""Unit tests for SettlementCheck v2 — playbook resolution, vocabulary, backward compat."""

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


class TestSettlementCheckV2Playbook:
    """SettlementCheck v2 playbook resolution and structure."""

    def test_v2_playbook_registered(self) -> None:
        assert "settlementcheck_v2" in BUNDLED_PLAYBOOKS
        path = BUNDLED_PLAYBOOKS["settlementcheck_v2"]
        assert path.exists()

    def test_v2_playbook_loads(self) -> None:
        path = BUNDLED_PLAYBOOKS["settlementcheck_v2"]
        playbook = load_playbook(path)
        assert playbook.id == "settlement-agreement-v2"
        assert playbook.mode == "settlementcheck"

    def test_v2_has_nine_categories(self) -> None:
        path = BUNDLED_PLAYBOOKS["settlementcheck_v2"]
        playbook = load_playbook(path)
        assert len(playbook.categories) == 9

    def test_v2_includes_all_v1_categories(self) -> None:
        path = BUNDLED_PLAYBOOKS["settlementcheck_v2"]
        playbook = load_playbook(path)
        v1_ids = {
            "release-scope",
            "payment-terms-timing",
            "confidentiality-non-disparagement",
            "waiver-unknown-claims",
            "breach-consequences",
        }
        v2_ids = {c.id for c in playbook.categories}
        assert v1_ids.issubset(v2_ids)

    def test_v2_has_new_categories(self) -> None:
        path = BUNDLED_PLAYBOOKS["settlementcheck_v2"]
        playbook = load_playbook(path)
        new_ids = {
            "structured-payment-obligations",
            "class-action-procedures",
            "multi-party-releases",
            "regulatory-cooperation",
        }
        v2_ids = {c.id for c in playbook.categories}
        assert new_ids.issubset(v2_ids)


class TestSettlementCheckV2Vocabulary:
    """SettlementCheck v2 MODE_VOCABULARY entry."""

    def test_vocabulary_entry_exists(self) -> None:
        assert "settlementcheck_v2" in MODE_VOCABULARY

    def test_vocabulary_has_required_keys(self) -> None:
        entry = MODE_VOCABULARY["settlementcheck_v2"]
        assert "specialization" in entry
        assert "domain" in entry
        assert "vocabulary" in entry

    def test_vocabulary_includes_complex_terms(self) -> None:
        entry = MODE_VOCABULARY["settlementcheck_v2"]
        vocab = entry["vocabulary"]
        assert "claims administrator" in vocab
        assert "settlement class" in vocab
        assert "Bar date" in vocab
        assert "opt-out" in vocab
        assert "structured payments" in vocab
        assert "cross-indemnity" in vocab
        assert "regulatory cooperation" in vocab
        assert "no-admit" in vocab
        assert "CAFA" in vocab

    def test_vocabulary_includes_v1_terms(self) -> None:
        entry = MODE_VOCABULARY["settlementcheck_v2"]
        vocab = entry["vocabulary"]
        assert "release" in vocab
        assert "Section 1542" in vocab
        assert "liquidated damages" in vocab


class TestBackwardCompat:
    """v1 settlementcheck must still work."""

    def test_v1_playbook_unchanged(self) -> None:
        path = BUNDLED_PLAYBOOKS["settlementcheck"]
        playbook = load_playbook(path)
        assert playbook.id == "settlement-agreement-v1"
        assert len(playbook.categories) == 5

    def test_v1_vocabulary_unchanged(self) -> None:
        assert "settlementcheck" in MODE_VOCABULARY
        entry = MODE_VOCABULARY["settlementcheck"]
        assert "release" in entry["vocabulary"]
        assert "claims administrator" not in entry["vocabulary"]
