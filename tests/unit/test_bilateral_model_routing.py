"""Tests for D-13: --comparison-model flag threading."""

from __future__ import annotations

from unittest.mock import patch

from openreview_cli.bilateral.comparison import compare_pair
from openreview_cli.bilateral.models import (
    AlignmentPair,
    MatchingMethod,
    PairedAssessment,
)
from openreview_cli.parsing.models import Clause
from openreview_cli.review.models import ClauseAssessment, Position, QAVerdict


def _make_alignment() -> AlignmentPair:
    return AlignmentPair(
        pair_id="A0-B0",
        clause_a=Clause(
            id="a0",
            title=None,
            text="Party A clause.",
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=0,
            source_span=(0, 14),
            paragraph_count=1,
        ),
        clause_b=Clause(
            id="b0",
            title=None,
            text="Party B clause.",
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=0,
            source_span=(0, 14),
            paragraph_count=1,
        ),
        method=MatchingMethod.exact,
        score=1.0,
    )


def _make_assessment(
    clause_id: str = "a0", clause_text: str = "Party A clause."
) -> ClauseAssessment:
    return ClauseAssessment(
        clause_id=clause_id,
        clause_text=clause_text,
        playbook_category="nda",
        position=Position.PREFERRED,
        confidence=0.9,
        citation="",
        qa_verdict=QAVerdict.agree,
        extraction_model="extraction",
        qa_model="qa",
    )


class TestComparePairComparisonModel:
    def test_default_model_is_none(self) -> None:
        """Default comparison_model is None — existing behaviour unchanged."""
        with patch(
            "openreview_cli.bilateral.comparison.call_gateway_chat",
            return_value='{"divergence": "no_divergence"}',
        ):
            result = compare_pair(
                alignment=_make_alignment(),
                party_a_assessment=_make_assessment("a0"),
                party_b_assessment=_make_assessment("b0"),
                playbook_category=None,
                model="extraction",
            )
        assert isinstance(result, PairedAssessment)

    def test_comparison_model_passed_to_gateway(self) -> None:
        """When comparison_model is set, it overrides the model param in call_gateway_chat."""
        with patch("openreview_cli.bilateral.comparison.call_gateway_chat") as mock_chat:
            mock_chat.return_value = '{"divergence": "no_divergence"}'
            compare_pair(
                alignment=_make_alignment(),
                party_a_assessment=_make_assessment("a0"),
                party_b_assessment=_make_assessment("b0"),
                playbook_category=None,
                model="extraction",
                comparison_model="comparison-special",
            )
            # The model passed to call_gateway_chat should be "comparison-special", not "extraction"
            _, kwargs = mock_chat.call_args
            assert (
                kwargs.get("model") == "comparison-special"
                or mock_chat.call_args[0][0] == "comparison-special"
            )

    def test_compare_pair_default_none_same_model(self) -> None:
        """With comparison_model=None, the model param is used directly."""
        with patch("openreview_cli.bilateral.comparison.call_gateway_chat") as mock_chat:
            mock_chat.return_value = '{"divergence": "no_divergence"}'
            compare_pair(
                alignment=_make_alignment(),
                party_a_assessment=_make_assessment("a0"),
                party_b_assessment=_make_assessment("b0"),
                playbook_category=None,
                model="extraction",
            )
            _, kwargs = mock_chat.call_args
            assert mock_chat.call_args[0][0] == "extraction"
