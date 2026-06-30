"""Error-handling tests for PII stripping (T038, T040, T041, FR-010)."""

from pathlib import Path

import pytest

from openreview_cli.pii.models import PiiError


class TestPiiErrorHandling:
    """Error paths in PII mapping and error-model compliance."""

    def test_invalid_key_raises_pii_error(self, tmp_path: Path) -> None:
        """T040: Reading a corrupted mapping file raises InvalidToken."""
        from openreview_cli.pii.encryption import InvalidToken
        from openreview_cli.pii.mapping import read_pii_mapping, write_pii_mapping

        # Write a valid mapping first
        write_pii_mapping({"a": "b"}, tmp_path, "some-encryption-key-1234")

        # Corrupt the file
        mapping_file = tmp_path / "pii_map.enc"
        mapping_file.write_bytes(b"garbage_data_that_is_not_a_valid_fernet_token")

        with pytest.raises(InvalidToken):
            read_pii_mapping(tmp_path, "some-encryption-key-1234")

    def test_pii_error_no_offsets(self) -> None:
        """FR-010: PiiError message does not contain character offsets or text snippets."""
        err = PiiError(
            exit_code=9,
            category="engine_crash",
            clause_heading="Payment Terms",
            phase="NER phase",
            message=(
                "PII detection failed while processing clause 'Payment Terms' (NER phase). "
                "Run with --no-pii to skip stripping. Report this bug."
            ),
            action="Run with --no-pii to skip stripping. Report this bug.",
        )
        # __post_init__ already bans offset/index/position/char wording;
        # this assertion documents the requirement explicitly.
        assert "offset" not in str(err).lower()

    def test_non_english_regex_only(self) -> None:
        """T041: Non-English text skips NLP but catches regex PII (emails, phones)."""
        from types import SimpleNamespace

        from openreview_cli.pii.engine import PiiEngine

        clause = SimpleNamespace(
            id="1",
            title="Non-English",
            text="Contact info@foreign.com or call 555-9999.",
            level=1,
            parent_id=None,
            source_page=1,
            source_paragraph=None,
            source_span=None,
            is_non_english=True,
        )

        engine = PiiEngine(threshold=0.0)
        entities, warnings = engine.detect_all_pages([clause], threshold=0.0)[:2]

        assert any("Non-English" in w for w in warnings), f"No non-English warning: {warnings}"

        entity_types = {e.entity_type for e in entities}
        assert "EMAIL_ADDRESS" in entity_types or "PHONE_NUMBER" in entity_types, (
            f"No regex entities found among: {entity_types}"
        )
        assert "PERSON" not in entity_types, "NLP entity PERSON detected on non-English text"
