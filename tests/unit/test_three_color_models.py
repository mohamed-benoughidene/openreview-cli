"""Unit tests for three-color confidence models.

Covers AssessmentColor/AmberReason enums, effective_confidence(),
assign_colors(), and is_amber backward compat.
"""

from __future__ import annotations

import time

from openreview_cli.grounding.models import GroundingVerdict
from openreview_cli.review.colors import (
    AmberReason,
    AssessmentColor,
    assign_colors,
    effective_confidence,
)
from openreview_cli.review.models import (
    ClauseAssessment,
    Position,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
)


class TestAssessmentColor:
    def test_enum_values(self) -> None:
        assert AssessmentColor.green.value == "green"
        assert AssessmentColor.amber.value == "amber"
        assert AssessmentColor.red.value == "red"

    def test_str_enum(self) -> None:
        assert str(AssessmentColor.green) == "green"
        assert str(AssessmentColor.amber) == "amber"
        assert str(AssessmentColor.red) == "red"

    def test_json_serializable(self) -> None:
        import json

        assert json.dumps(AssessmentColor.green) == '"green"'


class TestAmberReason:
    def test_enum_values(self) -> None:
        assert AmberReason.low_confidence.value == "low_confidence"
        assert AmberReason.qa_disagreement.value == "qa_disagreement"
        assert AmberReason.qa_uncertain.value == "qa_uncertain"
        assert AmberReason.error.value == "error"
        assert AmberReason.grounding_failure.value == "grounding_failure"
        assert AmberReason.grounding_uncertain.value == "grounding_uncertain"

    def test_str_enum(self) -> None:
        assert str(AmberReason.low_confidence) == "low_confidence"
        assert str(AmberReason.qa_disagreement) == "qa_disagreement"

    def test_json_serializable(self) -> None:
        import json

        assert json.dumps(AmberReason.error) == '"error"'


class TestEffectiveConfidence:
    def test_all_stages_present(self) -> None:
        assert (
            effective_confidence(
                extraction_confidence=0.8,
                qa_confidence=0.9,
                grounding_confidence=0.7,
            )
            == 0.7
        )

    def test_only_extraction(self) -> None:
        assert effective_confidence(extraction_confidence=0.8) == 0.8

    def test_extraction_none_grounding_0_7(self) -> None:
        assert effective_confidence(extraction_confidence=None, grounding_confidence=0.7) == 0.7

    def test_grounding_none_extraction_0_5(self) -> None:
        assert effective_confidence(extraction_confidence=0.5, grounding_confidence=None) == 0.5

    def test_all_none_defaults_to_one(self) -> None:
        assert effective_confidence() == 1.0

    def test_zero_confidence(self) -> None:
        assert effective_confidence(extraction_confidence=0.0) == 0.0

    def test_min_of_all_values(self) -> None:
        assert (
            effective_confidence(
                extraction_confidence=0.9,
                qa_confidence=0.5,
                grounding_confidence=0.8,
            )
            == 0.5
        )

    def test_all_at_one(self) -> None:
        assert (
            effective_confidence(
                extraction_confidence=1.0,
                qa_confidence=1.0,
                grounding_confidence=1.0,
            )
            == 1.0
        )


def _make_assessment(
    confidence: float = 0.8,
    position: Position = Position.PREFERRED,
    qa_verdict: QAVerdict = QAVerdict.agree,
    error: str | None = None,
    grounding_verdict: GroundingVerdict | None = None,
    grounding_confidence: float | None = None,
) -> ClauseAssessment:
    return ClauseAssessment(
        clause_id="c1",
        clause_text="Some clause text.",
        playbook_category="test",
        position=position,
        confidence=confidence,
        citation="text",
        qa_verdict=qa_verdict,
        extraction_model="m1",
        qa_model="m1",
        error=error,
        grounding_verdict=grounding_verdict,
        grounding_confidence=grounding_confidence,
    )


class TestAssignColors:
    def test_preferred_high_confidence_green(self) -> None:
        a = _make_assessment(confidence=0.85, position=Position.PREFERRED)
        assign_colors([a])
        assert a.color == AssessmentColor.green
        assert a.effective_confidence == 0.85
        assert a.amber_reasons == []

    def test_acceptable_high_confidence_green(self) -> None:
        a = _make_assessment(confidence=0.85, position=Position.ACCEPTABLE)
        assign_colors([a])
        assert a.color == AssessmentColor.green

    def test_walkaway_high_confidence_red(self) -> None:
        a = _make_assessment(confidence=0.85, position=Position.WALKAWAY)
        assign_colors([a])
        assert a.color == AssessmentColor.red
        assert a.effective_confidence == 0.85
        assert a.amber_reasons == []

    def test_low_confidence_amber(self) -> None:
        a = _make_assessment(confidence=0.4, position=Position.PREFERRED)
        assign_colors([a])
        assert a.color == AssessmentColor.amber
        assert AmberReason.low_confidence in (a.amber_reasons or [])

    def test_qa_disagreement_amber(self) -> None:
        a = _make_assessment(qa_verdict=QAVerdict.disagree)
        assign_colors([a])
        assert a.color == AssessmentColor.amber
        assert AmberReason.qa_disagreement in (a.amber_reasons or [])

    def test_qa_uncertain_amber(self) -> None:
        a = _make_assessment(qa_verdict=QAVerdict.uncertain)
        assign_colors([a])
        assert a.color == AssessmentColor.amber
        assert AmberReason.qa_uncertain in (a.amber_reasons or [])

    def test_error_amber(self) -> None:
        a = _make_assessment(error="Model failed")
        assign_colors([a])
        assert a.color == AssessmentColor.amber
        assert AmberReason.error in (a.amber_reasons or [])

    def test_grounding_failure_amber(self) -> None:
        a = _make_assessment(grounding_verdict=GroundingVerdict.UNGROUNDED)
        assign_colors([a])
        assert a.color == AssessmentColor.amber
        assert AmberReason.grounding_failure in (a.amber_reasons or [])

    def test_grounding_uncertain_amber(self) -> None:
        a = _make_assessment(grounding_verdict=GroundingVerdict.UNCERTAIN)
        assign_colors([a])
        assert a.color == AssessmentColor.amber
        assert AmberReason.grounding_uncertain in (a.amber_reasons or [])

    def test_uncertain_position_amber(self) -> None:
        a = _make_assessment(position=Position.UNCERTAIN)
        assign_colors([a])
        assert a.color == AssessmentColor.amber

    def test_threshold_boundary_not_amber(self) -> None:
        """Confidence exactly at threshold is NOT amber from threshold alone."""
        a = _make_assessment(confidence=0.5, position=Position.PREFERRED)
        assign_colors([a], threshold=0.5)
        assert a.color == AssessmentColor.green
        assert AmberReason.low_confidence not in (a.amber_reasons or [])

    def test_custom_threshold(self) -> None:
        a = _make_assessment(confidence=0.75, position=Position.PREFERRED)
        assign_colors([a], threshold=0.9)
        assert a.color == AssessmentColor.amber
        assert AmberReason.low_confidence in (a.amber_reasons or [])

    def test_threshold_zero(self) -> None:
        """threshold=0.0 → no clause goes amber from threshold alone (only from other triggers)."""
        # High-confidence preferred — stays green
        a1 = _make_assessment(confidence=0.92, position=Position.PREFERRED)
        # Low-confidence (0.1) but threshold=0.0 means no low_confidence trigger
        a2 = _make_assessment(confidence=0.1, position=Position.PREFERRED)
        # Error — should still be amber regardless of threshold
        a3 = _make_assessment(confidence=0.8, error="Failed", position=Position.PREFERRED)
        # QA disagree — should still be amber regardless of threshold
        a4 = _make_assessment(
            confidence=0.8, qa_verdict=QAVerdict.disagree, position=Position.PREFERRED
        )

        assign_colors([a1, a2, a3, a4], threshold=0.0)
        assert a1.color == AssessmentColor.green
        # 0.1 < 0.0 is False, so no low_confidence trigger → green
        assert a2.color == AssessmentColor.green
        # Error trigger still fires → amber
        assert a3.color == AssessmentColor.amber
        assert AmberReason.error in (a3.amber_reasons or [])
        # QA disagree trigger still fires → amber
        assert a4.color == AssessmentColor.amber
        assert AmberReason.qa_disagreement in (a4.amber_reasons or [])

    def test_threshold_one(self) -> None:
        """threshold=1.0 → every clause with confidence < 1.0 goes amber (unless other triggers beat it)."""
        a1 = _make_assessment(confidence=0.99, position=Position.PREFERRED)
        a2 = _make_assessment(confidence=0.5, position=Position.PREFERRED)
        # walkaway with conf < 1.0 — still amber because low_confidence, not red
        a3 = _make_assessment(confidence=0.85, position=Position.WALKAWAY)

        assign_colors([a1, a2, a3], threshold=1.0)
        assert a1.color == AssessmentColor.amber
        assert AmberReason.low_confidence in (a1.amber_reasons or [])
        assert a2.color == AssessmentColor.amber
        assert AmberReason.low_confidence in (a2.amber_reasons or [])
        assert a3.color == AssessmentColor.amber
        assert AmberReason.low_confidence in (a3.amber_reasons or [])

    def test_empty_list(self) -> None:
        assign_colors([])

    def test_multiple_triggers(self) -> None:
        a = _make_assessment(
            confidence=0.3,
            position=Position.WALKAWAY,
            qa_verdict=QAVerdict.disagree,
            error="Failed",
            grounding_verdict=GroundingVerdict.UNGROUNDED,
        )
        assign_colors([a])
        assert a.color == AssessmentColor.amber
        assert AmberReason.error in (a.amber_reasons or [])
        assert AmberReason.low_confidence in (a.amber_reasons or [])
        assert AmberReason.qa_disagreement in (a.amber_reasons or [])
        assert AmberReason.grounding_failure in (a.amber_reasons or [])

    def test_no_grounding_data_no_grounding_trigger(self) -> None:
        a = _make_assessment(
            confidence=0.85,
            position=Position.PREFERRED,
            grounding_verdict=None,
            grounding_confidence=None,
        )
        assign_colors([a])
        assert a.color == AssessmentColor.green
        assert a.amber_reasons == []

    def test_performance_1000_assessments(self) -> None:
        assessments = [_make_assessment(confidence=0.5 if i % 2 == 0 else 0.9) for i in range(1000)]
        start = time.perf_counter()
        assign_colors(assessments)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1  # 100 ms

    def test_deterministic(self) -> None:
        a1 = _make_assessment(confidence=0.45, position=Position.ACCEPTABLE)
        a2 = _make_assessment(confidence=0.45, position=Position.ACCEPTABLE)
        assign_colors([a1])
        assign_colors([a2])
        assert a1.color == a2.color
        assert a1.amber_reasons == a2.amber_reasons
        assert a1.effective_confidence == a2.effective_confidence


class TestIsAmberBackwardCompat:
    def test_color_amber_is_amber_true(self) -> None:
        a = _make_assessment(confidence=0.3)
        assign_colors([a])
        assert a.color == AssessmentColor.amber
        assert a.is_amber is True

    def test_color_green_is_amber_false(self) -> None:
        a = _make_assessment(confidence=0.85, position=Position.PREFERRED)
        assign_colors([a])
        assert a.color == AssessmentColor.green
        assert a.is_amber is False

    def test_unassigned_color_still_works(self) -> None:
        a = _make_assessment(confidence=0.3)
        assert a.is_amber is False  # default before assign_colors
        assign_colors([a])
        assert a.is_amber is True  # set by assign_colors

    def test_unassigned_color_green_no_amber(self) -> None:
        a = _make_assessment(confidence=0.9)
        assert a.is_amber is False  # not set by __post_init__

    def test_color_red_is_amber_false(self) -> None:
        a = _make_assessment(confidence=0.85, position=Position.WALKAWAY)
        assign_colors([a])
        assert a.color == AssessmentColor.red
        assert a.is_amber is False


class TestReviewSummaryExtensions:
    def test_defaults(self) -> None:
        s = ReviewSummary()
        assert s.green_count == 0
        assert s.red_count == 0
        assert s.avg_effective_confidence == 0.0

    def test_amber_count_preserved(self) -> None:
        s = ReviewSummary(amber_count=5)
        assert s.amber_count == 5

    def test_with_values(self) -> None:
        s = ReviewSummary(
            preferred_count=10,
            amber_count=3,
            green_count=8,
            red_count=2,
            avg_effective_confidence=0.72,
        )
        assert s.green_count == 8
        assert s.red_count == 2
        assert s.avg_effective_confidence == 0.72


class TestReviewReportExtensions:
    def test_confidence_threshold_default(self) -> None:
        r = ReviewReport(
            document=None,  # type: ignore[arg-type]
            assessments=[],
            summary=ReviewSummary(),
            playbook_id="test",
            generated_at=None,  # type: ignore[arg-type]
        )
        assert r.confidence_threshold == 0.7

    def test_confidence_threshold_custom(self) -> None:
        r = ReviewReport(
            document=None,  # type: ignore[arg-type]
            assessments=[],
            summary=ReviewSummary(),
            playbook_id="test",
            generated_at=None,  # type: ignore[arg-type]
            confidence_threshold=0.9,
        )
        assert r.confidence_threshold == 0.9

    def test_schema_version_bumped(self) -> None:
        r = ReviewReport(
            document=None,  # type: ignore[arg-type]
            assessments=[],
            summary=ReviewSummary(),
            playbook_id="test",
            generated_at=None,  # type: ignore[arg-type]
        )
        assert r.schema_version == "1.1.0"
