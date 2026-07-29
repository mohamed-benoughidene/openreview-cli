"""Unit tests for prompt template registry."""

import pytest

from openreview_cli.review.prompts import MODE_VOCABULARY, _build_extraction_messages_common


class TestModeVocabulary:
    """Tests for MODE_VOCABULARY and _build_extraction_messages_common()."""

    def test_vocabulary_contains_all_modes(self) -> None:
        expected_modes = {"licensecheck", "leasecheck", "privacycheck"}
        assert expected_modes.issubset(set(MODE_VOCABULARY))

    def test_all_modes_have_required_keys(self) -> None:
        required = {"specialization", "domain", "vocabulary"}
        for mode, vocab in MODE_VOCABULARY.items():
            missing = required - set(vocab)
            assert not missing, f"Mode '{mode}' missing keys: {missing}"

    def test_unknown_mode_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            _build_extraction_messages_common(
                clause_text="test",
                category_id="c",
                category_name="C",
                category_description="",
                preferred_desc="P",
                preferred_exemplars=["a"],
                acceptable_desc="A",
                acceptable_exemplars=["b"],
                walkaway_desc="W",
                walkaway_exemplars=["c"],
                default_position="acceptable",
                mode="nonexistent",
            )


class TestModePromptContent:
    """Verify domain vocabulary appears in mode-specific system prompts."""

    def _build_for_mode(self, mode: str, clause_text: str = "test clause") -> list[dict[str, str]]:
        return _build_extraction_messages_common(
            mode=mode,
            clause_text=clause_text,
            category_id="test-cat",
            category_name="Test Category",
            category_description="A test category",
            preferred_desc="Preferred",
            preferred_exemplars=["Example 1"],
            acceptable_desc="Acceptable",
            acceptable_exemplars=["Example 2"],
            walkaway_desc="Walkaway",
            walkaway_exemplars=["Example 3"],
            default_position="acceptable",
        )

    def test_licensecheck_contains_saas_vocabulary(self) -> None:
        messages = self._build_for_mode("licensecheck")
        system = messages[0]["content"] if messages else ""
        domain_terms = ["SaaS", "license grant", "royalty"]
        for term in domain_terms:
            assert term.lower() in system.lower(), f"Missing domain term: {term}"

    def test_leasecheck_contains_lease_vocabulary(self) -> None:
        messages = self._build_for_mode("leasecheck")
        system = messages[0]["content"] if messages else ""
        domain_terms = ["commercial lease", "CAM charges", "subletting"]
        for term in domain_terms:
            assert term.lower() in system.lower(), f"Missing domain term: {term}"

    def test_privacycheck_contains_dpa_vocabulary(self) -> None:
        messages = self._build_for_mode("privacycheck")
        system = messages[0]["content"] if messages else ""
        domain_terms = ["data controller", "data processor", "DPA"]
        for term in domain_terms:
            assert term.lower() in system.lower(), f"Missing domain term: {term}"

    def test_prompt_returns_valid_message_structure(self) -> None:
        messages = self._build_for_mode("licensecheck")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "test clause" in messages[1]["content"]
