"""Unit tests for the comparison prompt templates and comparison agent.

Covers system prompt content, message building, comparison agent
success/error paths, and gateway integration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from openreview_cli.bilateral.models import (
    AlignmentPair,
    DivergenceVerdict,
    MatchingMethod,
    RCBSFDimension,
)
from openreview_cli.parsing.models import Clause
from openreview_cli.review.models import ClauseAssessment, Position, QAVerdict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_clause(clause_id: str = "c1", title: str = "Test", text: str = "Test clause") -> Clause:
    return Clause(
        id=clause_id,
        title=title,
        text=text,
        level=1,
        parent_id=None,
        source_page=1,
        source_paragraph=None,
        source_span=(0, len(text)),
    )


def make_assessment(
    clause_id: str = "c1",
    position: Position = Position.ACCEPTABLE,
    confidence: float = 0.85,
) -> ClauseAssessment:
    return ClauseAssessment(
        clause_id=clause_id,
        clause_text="Test clause text",
        playbook_category="test-cat",
        position=position,
        confidence=confidence,
        citation="test excerpt",
        qa_verdict=QAVerdict.agree,
        extraction_model="test-model",
        qa_model="test-model",
    )


def make_alignment_pair(
    pair_id: str = "A0-B0",
    clause_a: Clause | None = None,
    clause_b: Clause | None = None,
) -> AlignmentPair:
    ca = clause_a or make_clause("a1", title="Confidentiality", text="Party A clause")
    cb = clause_b or make_clause("b1", title="Confidentiality", text="Party B clause")
    return AlignmentPair(
        pair_id=pair_id,
        clause_a=ca,
        clause_b=cb,
        method=MatchingMethod.exact,
        score=1.0,
    )


# ---------------------------------------------------------------------------
# Prompt template tests
# ---------------------------------------------------------------------------


class TestComparisonSystemPrompt:
    """Tests for the comparison system prompt."""

    def test_system_prompt_includes_rcbsf_dimensions(self) -> None:
        from openreview_cli.bilateral.prompts import SYSTEM_PROMPT

        prompt = SYSTEM_PROMPT
        assert "category" in prompt.lower()
        assert "location" in prompt.lower()
        assert "evidence" in prompt.lower()
        assert "issue" in prompt.lower()
        assert "suggestion" in prompt.lower()

    def test_system_prompt_includes_accuracy_caveat(self) -> None:
        from openreview_cli.bilateral.prompts import SYSTEM_PROMPT

        prompt = SYSTEM_PROMPT
        assert "64%" in prompt or "64" in prompt
        assert "F1" in prompt
        assert "experimental" in prompt.lower()

    def test_system_prompt_never_prescriptive(self) -> None:
        from openreview_cli.bilateral.prompts import SYSTEM_PROMPT

        prompt = SYSTEM_PROMPT
        assert "sign" not in prompt.lower().split("sign")[0]  # "never prescriptive"

    def test_system_prompt_mentions_json_output(self) -> None:
        from openreview_cli.bilateral.prompts import SYSTEM_PROMPT

        prompt = SYSTEM_PROMPT
        assert "json" in prompt.lower()


class TestBuildComparisonMessages:
    """Tests for the comparison message builder."""

    def test_messages_contain_both_clause_texts(self) -> None:
        from openreview_cli.bilateral.prompts import build_comparison_messages

        messages = build_comparison_messages(
            clause_a_text="Party A says this",
            clause_b_text="Party B says that",
            assessment_a=make_assessment("a1"),
            assessment_b=make_assessment("b1"),
        )
        combined = " ".join(m["content"] for m in messages)
        assert "Party A says this" in combined
        assert "Party B says that" in combined

    def test_messages_contain_both_positions(self) -> None:
        from openreview_cli.bilateral.prompts import build_comparison_messages

        ass_a = make_assessment("a1", position=Position.PREFERRED, confidence=0.9)
        ass_b = make_assessment("b1", position=Position.WALKAWAY, confidence=0.7)
        messages = build_comparison_messages(
            clause_a_text="Text A",
            clause_b_text="Text B",
            assessment_a=ass_a,
            assessment_b=ass_b,
        )
        combined = " ".join(m["content"] for m in messages)
        assert "preferred" in combined
        assert "walkaway" in combined
        assert "0.9" in combined
        assert "0.7" in combined

    def test_messages_include_output_format_request(self) -> None:
        from openreview_cli.bilateral.prompts import build_comparison_messages

        messages = build_comparison_messages(
            clause_a_text="Text A",
            clause_b_text="Text B",
            assessment_a=make_assessment(),
            assessment_b=make_assessment(),
        )
        combined = " ".join(m["content"] for m in messages)
        assert "divergence" in combined
        assert "confidence" in combined
        assert "citations" in combined or "citation" in combined
        assert "rationale" in combined

    def test_messages_have_system_and_user_roles(self) -> None:
        from openreview_cli.bilateral.prompts import build_comparison_messages

        messages = build_comparison_messages(
            clause_a_text="Text A",
            clause_b_text="Text B",
            assessment_a=make_assessment(),
            assessment_b=make_assessment(),
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_messages_with_category(self) -> None:
        from openreview_cli.bilateral.prompts import build_comparison_messages
        from openreview_cli.review.models import Category, PositionDef

        pref = PositionDef(description="Short term", exemplars=["3 years"])
        acc = PositionDef(description="Standard", exemplars=["5 years"])
        walk = PositionDef(description="Indefinite", exemplars=["perpetuity"])
        cat = Category(
            id="confidentiality-term",
            name="Confidentiality Term",
            description="Duration of confidentiality obligations",
            preferred=pref,
            acceptable=acc,
            walkaway=walk,
            default_position=Position.ACCEPTABLE,
        )

        messages = build_comparison_messages(
            clause_a_text="Text A",
            clause_b_text="Text B",
            assessment_a=make_assessment(),
            assessment_b=make_assessment(),
            category=cat,
        )
        combined = " ".join(m["content"] for m in messages)
        assert "Confidentiality Term" in combined


# ---------------------------------------------------------------------------
# Comparison agent tests
# ---------------------------------------------------------------------------


class TestComparisonAgent:
    """Tests for the comparison agent."""

    def test_successful_comparison_returns_paired_assessment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from openreview_cli.bilateral.comparison import compare_pair

        def mock_gateway(_slot: str, _messages: list[dict[str, str]], **_kwargs: object) -> str:
            return (
                '{"divergence": "evidence", "confidence": 0.85, '
                '"citations": ["Party A requires best efforts", '
                '"Party B requires reasonable efforts"], '
                '"rationale": "Different evidentiary standards"}'
            )

        monkeypatch.setattr("openreview_cli.bilateral.comparison.call_gateway_chat", mock_gateway)

        pair = make_alignment_pair()
        ass_a = make_assessment("a1", Position.PREFERRED, 0.9)
        ass_b = make_assessment("b1", Position.WALKAWAY, 0.8)

        result = compare_pair(
            alignment=pair,
            party_a_assessment=ass_a,
            party_b_assessment=ass_b,
            playbook_category=None,
            model="test-slot",
        )

        assert result.pair_id == "A0-B0"
        assert result.divergence == DivergenceVerdict.divergent
        assert result.primary_dimension == RCBSFDimension.evidence
        assert result.alignment_quality == 1.0
        assert result.error is None

    def test_no_divergence_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from openreview_cli.bilateral.comparison import compare_pair

        def mock_gateway(_slot: str, _messages: list[dict[str, str]], **_kwargs: object) -> str:
            return (
                '{"divergence": "no_divergence", "confidence": 0.95, '
                '"citations": [], '
                '"rationale": "Both clauses are substantially aligned"}'
            )

        monkeypatch.setattr("openreview_cli.bilateral.comparison.call_gateway_chat", mock_gateway)

        result = compare_pair(
            alignment=make_alignment_pair(),
            party_a_assessment=make_assessment(),
            party_b_assessment=make_assessment(),
            playbook_category=None,
            model="test-slot",
        )

        assert result.divergence == DivergenceVerdict.aligned
        assert result.primary_dimension is None

    def test_each_rcbsf_dimension_parsed_correctly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from openreview_cli.bilateral.comparison import compare_pair

        dimensions = ["category", "location", "evidence", "issue", "suggestion"]
        for dim in dimensions:

            def _make_gateway(d: str = dim) -> str:  # capture via default arg
                return (
                    f'{{"divergence": "{d}", "confidence": 0.8, '
                    f'"citations": ["a", "b"], "rationale": "test"}}'
                )

            def mock_gateway(_slot: str, _messages: list[dict[str, str]], **_kwargs: object) -> str:
                return _make_gateway()

            monkeypatch.setattr(
                "openreview_cli.bilateral.comparison.call_gateway_chat", mock_gateway
            )

            result = compare_pair(
                alignment=make_alignment_pair(),
                party_a_assessment=make_assessment(),
                party_b_assessment=make_assessment(),
                playbook_category=None,
                model="test-slot",
            )

            assert result.divergence == DivergenceVerdict.divergent
            assert result.primary_dimension is not None
            assert result.primary_dimension.value == dim

    def test_invalid_json_response_returns_uncertain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from openreview_cli.bilateral.comparison import compare_pair

        def mock_gateway(_slot: str, _messages: list[dict[str, str]], **_kwargs: object) -> str:
            return "not valid json"

        monkeypatch.setattr("openreview_cli.bilateral.comparison.call_gateway_chat", mock_gateway)

        result = compare_pair(
            alignment=make_alignment_pair(),
            party_a_assessment=make_assessment(),
            party_b_assessment=make_assessment(),
            playbook_category=None,
            model="test-slot",
        )

        assert result.divergence == DivergenceVerdict.uncertain
        assert result.error is not None

    def test_out_of_range_confidence_clamped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from openreview_cli.bilateral.comparison import compare_pair

        def mock_gateway(_slot: str, _messages: list[dict[str, str]], **_kwargs: object) -> str:
            return (
                '{"divergence": "evidence", "confidence": 1.5, '
                '"citations": [], "rationale": "test"}'
            )

        monkeypatch.setattr("openreview_cli.bilateral.comparison.call_gateway_chat", mock_gateway)

        result = compare_pair(
            alignment=make_alignment_pair(),
            party_a_assessment=make_assessment(),
            party_b_assessment=make_assessment(),
            playbook_category=None,
            model="test-slot",
        )

        # Confidence should be clamped to 0.0-1.0
        assert 0.0 <= result.confidence <= 1.0

    def test_gateway_failure_raises_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from openreview_cli.bilateral.comparison import compare_pair

        def mock_gateway(_slot: str, _messages: list[dict[str, str]], **_kwargs: object) -> str:
            raise RuntimeError("Gateway unreachable")

        monkeypatch.setattr("openreview_cli.bilateral.comparison.call_gateway_chat", mock_gateway)

        result = compare_pair(
            alignment=make_alignment_pair(),
            party_a_assessment=make_assessment(),
            party_b_assessment=make_assessment(),
            playbook_category=None,
            model="test-slot",
        )

        assert result.divergence == DivergenceVerdict.uncertain
        assert result.error is not None
        assert "Gateway unreachable" in result.error

    def test_compare_pair_includes_citations(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from openreview_cli.bilateral.comparison import compare_pair

        citations = ["Party A: 'shall use reasonable efforts'", "Party B: 'shall use best efforts'"]

        def mock_gateway(_slot: str, _messages: list[dict[str, str]], **_kwargs: object) -> str:
            return (
                f'{{"divergence": "evidence", "confidence": 0.82, '
                f'"citations": {citations!s}, '
                f'"rationale": "Different standards of effort"}}'
            )

        monkeypatch.setattr("openreview_cli.bilateral.comparison.call_gateway_chat", mock_gateway)

        result = compare_pair(
            alignment=make_alignment_pair(),
            party_a_assessment=make_assessment(),
            party_b_assessment=make_assessment(),
            playbook_category=None,
            model="test-slot",
        )

        assert len(result.citations) == 2
        assert "reasonable efforts" in result.citations[0]
        assert "best efforts" in result.citations[1]


# ---------------------------------------------------------------------------
# Shared gateway helper tests
# ---------------------------------------------------------------------------
