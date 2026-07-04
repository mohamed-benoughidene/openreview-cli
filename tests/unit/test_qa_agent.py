"""Unit tests for QA agent (verification, disagreement logic, position revision)."""

from __future__ import annotations

import pytest

from openreview_cli.review.models import (
    Category,
    ClauseAssessment,
    Position,
    PositionDef,
    QAVerdict,
)


@pytest.fixture
def sample_category() -> Category:
    pref = PositionDef(description="Short term", exemplars=["3 years", "2 years"])
    acc = PositionDef(description="Standard term", exemplars=["5 years"])
    walk = PositionDef(description="Indefinite", exemplars=["perpetuity"])
    return Category(
        id="confidentiality-term",
        name="Confidentiality Term",
        description="Defines confidentiality term",
        preferred=pref,
        acceptable=acc,
        walkaway=walk,
        default_position=Position.ACCEPTABLE,
    )


class TestQAAgent:
    """Tests for the QA verification agent."""

    def test_qa_agrees_with_extraction(
        self, sample_category: Category, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """QA agrees with a clearly correct extraction."""
        from openreview_cli.review.qa import verify_assessment

        assessment = ClauseAssessment(
            clause_id="c1",
            clause_text="Confidential Info shall be kept secret for 3 years.",
            playbook_category="confidentiality-term",
            position=Position.PREFERRED,
            confidence=0.92,
            citation="for 3 years",
            qa_verdict=QAVerdict.agree,
            extraction_model="m1",
            qa_model="m1",
        )

        def mock_chat(_slot: str, _messages: list[dict[str, str]]) -> str:
            return (
                '{"verdict": "agree", "revised_position": null, '
                '"rationale": "", "citation_valid": true, '
                '"position_valid": true, "category_valid": true, '
                '"confidence_valid": true}'
            )

        monkeypatch.setattr("openreview_cli.review.qa.call_gateway_chat", mock_chat)

        result = verify_assessment(assessment, sample_category, qa_model="test-slot")

        assert result.qa_verdict == QAVerdict.agree
        assert result.qa_revised_position is None
        assert result.qa_revised_rationale is None
        assert not result.is_amber  # QA agrees, high confidence

    def test_qa_disagrees_and_revises(
        self, sample_category: Category, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """QA disagrees and supplies a revised position."""
        from openreview_cli.review.qa import verify_assessment

        assessment = ClauseAssessment(
            clause_id="c1",
            clause_text="Confidential Info shall be kept secret for 5 years.",
            playbook_category="confidentiality-term",
            position=Position.PREFERRED,  # extraction says preferred
            confidence=0.88,
            citation="5 years",
            qa_verdict=QAVerdict.agree,
            extraction_model="m1",
            qa_model="m1",
        )

        def mock_chat(_slot: str, _messages: list[dict[str, str]]) -> str:
            return (
                '{"verdict": "disagree", "revised_position": "acceptable", '
                '"rationale": "5 years is standard market term, not short", '
                '"citation_valid": true, '
                '"position_valid": false, "category_valid": true, '
                '"confidence_valid": true}'
            )

        monkeypatch.setattr("openreview_cli.review.qa.call_gateway_chat", mock_chat)

        result = verify_assessment(assessment, sample_category, qa_model="test-slot")

        assert result.qa_verdict == QAVerdict.disagree
        assert result.qa_revised_position == Position.ACCEPTABLE
        assert result.qa_revised_rationale is not None
        assert result.is_amber

    def test_qa_uncertain_verdict(
        self, sample_category: Category, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """QA returns uncertain — should trigger is_amber."""
        from openreview_cli.review.qa import verify_assessment

        assessment = ClauseAssessment(
            clause_id="c1",
            clause_text="Confidential Info shall be kept secret for 99 years.",
            playbook_category="confidentiality-term",
            position=Position.WALKAWAY,
            confidence=0.6,
            citation="99 years",
            qa_verdict=QAVerdict.agree,
            extraction_model="m1",
            qa_model="m1",
        )

        def mock_chat(_slot: str, _messages: list[dict[str, str]]) -> str:
            return (
                '{"verdict": "uncertain", "revised_position": null, '
                '"rationale": "Unusual term length, cannot determine confidently", '
                '"citation_valid": true, '
                '"position_valid": true, "category_valid": true, '
                '"confidence_valid": false}'
            )

        monkeypatch.setattr("openreview_cli.review.qa.call_gateway_chat", mock_chat)

        result = verify_assessment(assessment, sample_category, qa_model="test-slot")

        assert result.qa_verdict == QAVerdict.uncertain
        assert result.is_amber

    def test_qa_fallback_on_parse_error(
        self, sample_category: Category, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If QA returns unparseable JSON, fallback to uncertain."""
        from openreview_cli.review.qa import verify_assessment

        assessment = ClauseAssessment(
            clause_id="c1",
            clause_text="Some text",
            playbook_category="confidentiality-term",
            position=Position.ACCEPTABLE,
            confidence=0.8,
            citation="text",
            qa_verdict=QAVerdict.agree,
            extraction_model="m1",
            qa_model="m1",
        )

        def mock_chat(_slot: str, _messages: list[dict[str, str]]) -> str:
            return "This is not JSON"

        monkeypatch.setattr("openreview_cli.review.qa.call_gateway_chat", mock_chat)

        result = verify_assessment(assessment, sample_category, qa_model="test-slot")

        assert result.qa_verdict == QAVerdict.uncertain
        assert result.is_amber
