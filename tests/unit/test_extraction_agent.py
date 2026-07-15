"""Unit tests for extraction agent (prompt building, confidence parsing)."""

from __future__ import annotations

import pytest

from openreview_cli.review.models import Category, Playbook, PlaybookMetadata, Position, PositionDef


@pytest.fixture
def sample_playbook() -> Playbook:
    fav = PositionDef(description="Short term", exemplars=["3 years", "2 years"])
    neu = PositionDef(description="Standard term", exemplars=["5 years"])
    unfav = PositionDef(description="Indefinite", exemplars=["perpetuity"])
    cat = Category(
        id="confidentiality-term",
        name="Confidentiality Term",
        description="Defines how long confidentiality obligations survive",
        preferred=fav,
        acceptable=neu,
        walkaway=unfav,
        default_position=Position.ACCEPTABLE,
    )
    meta = PlaybookMetadata(version="1.0.0", description="Test", author="test")
    return Playbook(id="test", mode="precheck", categories=[cat], metadata=meta)


class TestExtractionAgent:
    """Tests for the extraction agent."""

    def test_match_clause_to_category_by_heading(self, sample_playbook: Playbook) -> None:
        """Heading match should find the confidentiality-term category."""
        from openreview_cli.review.extraction import match_category

        match = match_category("Confidentiality", sample_playbook)
        assert match is not None
        assert match.id == "confidentiality-term"

    def test_match_clause_to_category_no_match(self, sample_playbook: Playbook) -> None:
        """No heading match returns None."""
        from openreview_cli.review.extraction import match_category

        match = match_category("Governing Law", sample_playbook)
        assert match is None

    def test_match_clause_to_category_case_insensitive(self, sample_playbook: Playbook) -> None:
        """Heading matching should be case-insensitive."""
        from openreview_cli.review.extraction import match_category

        match = match_category("confidentiality term", sample_playbook)
        assert match is not None
        assert match.id == "confidentiality-term"

    def test_build_extraction_messages_includes_clause(self) -> None:
        """Extraction messages should contain the clause text."""
        from openreview_cli.review.prompts import _build_extraction_messages_common

        messages = _build_extraction_messages_common(
            clause_text="Confidential Info shall be kept secret for 3 years.",
            category_id="confidentiality-term",
            category_name="Confidentiality Term",
            category_description="",
            preferred_desc="Short term",
            preferred_exemplars=["3 years", "2 years"],
            acceptable_desc="Standard",
            acceptable_exemplars=["5 years"],
            walkaway_desc="Indefinite",
            walkaway_exemplars=["perpetuity"],
            default_position="acceptable",
        )
        combined = " ".join(m["content"] for m in messages)
        assert "3 years" in combined
        assert "Confidentiality Term" in combined

    def test_extract_from_clause_with_gateway(
        self, sample_playbook: Playbook, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Integration-style test: extract from a clause using mocked Gateway."""
        from openreview_cli.review.extraction import extract_clause

        def mock_chat(_slot: str, _messages: list[dict[str, str]], **_kwargs: object) -> str:
            return (
                '{"position": "preferred", "confidence": 0.85, '
                '"citation": "for 3 years", "category_match": true}'
            )

        monkeypatch.setattr("openreview_cli.review.extraction.call_gateway_chat", mock_chat)

        result = extract_clause(
            clause_text="Confidential Information shall be kept secret for 3 years.",
            clause_id="clause-001",
            category=sample_playbook.categories[0],
            extraction_model="test-slot",
            mode="precheck",
        )
        assert result.position == Position.PREFERRED
        assert result.confidence == 0.85
        assert not result.is_amber  # high confidence, no QA yet

    def test_extract_clause_with_unmatched_position_fallsback_to_default(
        self, sample_playbook: Playbook, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When extraction returns 'no-match' position, falls back to category default."""
        from openreview_cli.review.extraction import extract_clause

        def mock_chat(_slot: str, _messages: list[dict[str, str]], **_kwargs: object) -> str:
            return (
                '{"position": "no-match", "confidence": 0.0, '
                '"citation": "", "category_match": false}'
            )

        monkeypatch.setattr("openreview_cli.review.extraction.call_gateway_chat", mock_chat)

        result = extract_clause(
            clause_text="This Agreement is entered into on...",
            clause_id="clause-099",
            category=sample_playbook.categories[0],
            extraction_model="test-slot",
            mode="precheck",
        )
        # Falls back to category default_position (acceptable)
        assert result.position == Position.ACCEPTABLE
        assert result.confidence == 0.0
