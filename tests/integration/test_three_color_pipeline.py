"""Integration tests for three-color pipeline integration with confidence_threshold."""

from __future__ import annotations

from datetime import UTC, datetime

from openreview_cli.grounding.models import GroundingVerdict
from openreview_cli.review.colors import AmberReason, AssessmentColor, assign_colors
from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Position,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
)


def _make_assessment(
    cid: str,
    pos: Position,
    conf: float,
    qa_verdict: QAVerdict = QAVerdict.agree,
    error: str | None = None,
    grounding_verdict: GroundingVerdict | None = None,
) -> ClauseAssessment:
    return ClauseAssessment(
        clause_id=cid,
        clause_text=f"Clause {cid} text.",
        playbook_category="confidentiality-term",
        position=pos,
        confidence=conf,
        citation=f"citation {cid}",
        qa_verdict=qa_verdict,
        extraction_model="m1",
        qa_model="m1",
        error=error,
        grounding_verdict=grounding_verdict,
    )


def _make_report(
    assessments: list[ClauseAssessment],
    threshold: float = 0.7,
) -> ReviewReport:
    dm = DocMeta(
        filename="test.pdf",
        page_count=5,
        clause_count=len(assessments),
        pii_stripped=False,
    )
    summary = ReviewSummary(
        favorable_count=sum(1 for a in assessments if a.position == Position.favorable),
        neutral_count=sum(1 for a in assessments if a.position == Position.neutral),
        unfavorable_count=sum(1 for a in assessments if a.position == Position.unfavorable),
        uncertain_count=sum(1 for a in assessments if a.position == Position.uncertain),
        no_match_count=0,
        amber_count=sum(1 for a in assessments if a.is_amber),
        avg_confidence=sum(a.confidence for a in assessments) / max(len(assessments), 1),
    )
    return ReviewReport(
        document=dm,
        assessments=assessments,
        summary=summary,
        playbook_id="precheck-nda-v1",
        generated_at=datetime.now(UTC),
        confidence_threshold=threshold,
    )


class TestThresholdPropagation:
    def test_default_threshold_colors(self) -> None:
        assessments = [
            _make_assessment("c1", Position.favorable, 0.92),
            _make_assessment("c2", Position.neutral, 0.45),
        ]
        assign_colors(assessments, threshold=0.7)
        assert assessments[0].color == AssessmentColor.green
        assert assessments[1].color == AssessmentColor.amber

    def test_custom_threshold_more_amber(self) -> None:
        assessments = [
            _make_assessment("c1", Position.favorable, 0.85),
            _make_assessment("c2", Position.neutral, 0.72),
        ]
        # 0.7 threshold: both >= 0.7 → both green
        assign_colors(assessments, threshold=0.7)
        assert assessments[0].color == AssessmentColor.green
        assert assessments[1].color == AssessmentColor.green

        # Reset and apply 0.9 threshold: 0.85 < 0.9 → amber
        for a in assessments:
            a.color = None
            a.amber_reasons = None
            a.effective_confidence = None
        assign_colors(assessments, threshold=0.9)
        assert assessments[0].color == AssessmentColor.amber  # type: ignore[comparison-overlap]
        assert assessments[1].color == AssessmentColor.amber

    def test_custom_threshold_fewer_amber(self) -> None:
        assessments = [
            _make_assessment("c1", Position.favorable, 0.3),
            _make_assessment("c2", Position.neutral, 0.45),
        ]
        # 0.7 threshold: both < 0.7 → both amber
        assign_colors(assessments, threshold=0.7)
        assert assessments[0].color == AssessmentColor.amber
        assert assessments[1].color == AssessmentColor.amber

        # Reset and apply 0.3 threshold: 0.3 < 0.3 is False → only 0.45 stays amber from low_confidence
        for a in assessments:
            a.color = None
            a.amber_reasons = None
            a.effective_confidence = None
        assign_colors(assessments, threshold=0.3)
        # 0.3 is NOT < 0.3, so c1 is not amber from threshold alone
        # But c1 position is favorable and conf >= threshold, so green
        assert assessments[0].color == AssessmentColor.green  # type: ignore[comparison-overlap]
        # 0.45 < 0.3 is False, so c2 is also not amber from threshold
        # position neutral, conf >= threshold, so green
        assert assessments[1].color == AssessmentColor.green

    def test_ninety_threshold_on_eighty_five(self) -> None:
        """Clause with confidence 0.85 and threshold 0.9 → Amber."""
        assessments = [
            _make_assessment("c1", Position.favorable, 0.85),
        ]
        assign_colors(assessments, threshold=0.9)
        assert assessments[0].color == AssessmentColor.amber
        assert AmberReason.low_confidence in assessments[0].amber_reasons  # type: ignore[operator]

    def test_threshold_at_boundary(self) -> None:
        """Clause with confidence 0.5 and threshold 0.5 → NOT Amber from threshold."""
        assessments = [
            _make_assessment("c1", Position.favorable, 0.5),
        ]
        assign_colors(assessments, threshold=0.5)
        # 0.5 < 0.5 is False, so no low_confidence trigger
        # Position favorable, conf >= threshold → Green
        assert assessments[0].color == AssessmentColor.green

    def test_empty_assessment_list(self) -> None:
        assign_colors([], threshold=0.7)
        # Should not raise

    def test_report_records_confidence_threshold(self) -> None:
        assessments = [
            _make_assessment("c1", Position.favorable, 0.92),
        ]
        report = _make_report(assessments, threshold=0.7)
        assert report.confidence_threshold == 0.7

    def test_report_records_custom_threshold(self) -> None:
        assessments = [
            _make_assessment("c1", Position.favorable, 0.92),
        ]
        report = _make_report(assessments, threshold=0.3)
        assert report.confidence_threshold == 0.3

    def test_report_default_threshold(self) -> None:
        report = _make_report([])
        assert report.confidence_threshold == 0.7

    def test_schema_version_is_1_1_0(self) -> None:
        assessments = [
            _make_assessment("c1", Position.favorable, 0.92),
        ]
        report = _make_report(assessments)
        assert report.schema_version == "1.1.0"

    def test_summary_green_red_counts_after_colors(self) -> None:
        assessments = [
            _make_assessment("c1", Position.favorable, 0.92),
            _make_assessment("c2", Position.unfavorable, 0.85),
            _make_assessment("c3", Position.favorable, 0.45),
        ]
        assign_colors(assessments, threshold=0.7)
        report = _make_report(assessments)
        green_count = sum(1 for a in report.assessments if a.color == AssessmentColor.green)
        red_count = sum(1 for a in report.assessments if a.color == AssessmentColor.red)
        assert green_count == 1
        assert red_count == 1
        assert len(assessments) - green_count - red_count == 1  # amber

    def test_avg_effective_confidence_calculated(self) -> None:
        assessments = [
            _make_assessment("c1", Position.favorable, 0.92),
            _make_assessment("c2", Position.neutral, 0.85),
        ]
        assign_colors(assessments, threshold=0.7)
        vals = [a.effective_confidence for a in assessments if a.effective_confidence is not None]
        avg = sum(vals) / len(vals) if vals else 0.0
        assert avg == 0.885

    def test_backward_compat_is_amber_accessible(self) -> None:
        """is_amber should be accessible after assign_colors."""
        assessments = [
            _make_assessment("c1", Position.favorable, 0.92),
            _make_assessment("c2", Position.favorable, 0.45),
        ]
        # Before assign_colors, is_amber returns _is_amber (default False)
        assert assessments[0].is_amber is False
        assert assessments[1].is_amber is False

        assign_colors(assessments, threshold=0.7)
        # After assign_colors, is_amber reflects the assigned color
        assert assessments[0].is_amber is False  # green
        assert assessments[1].is_amber is True  # amber
        assert assessments[0].color == AssessmentColor.green
        assert assessments[1].color == AssessmentColor.amber


class TestPerformanceAndDeterminism:
    def test_thousand_assessments_under_100ms(self) -> None:
        import time

        assessments = [
            _make_assessment(
                str(i),
                Position.favorable
                if i % 3 == 0
                else Position.unfavorable
                if i % 3 == 1
                else Position.neutral,
                0.3 + (i % 7) * 0.1,
                grounding_verdict=GroundingVerdict.UNGROUNDED if i % 5 == 0 else None,
            )
            for i in range(1000)
        ]
        start = time.perf_counter()
        assign_colors(assessments, threshold=0.7)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1, f"assign_colors took {elapsed:.3f}s, expected <0.1s"

    def test_deterministic_output(self) -> None:
        assessments1 = [
            _make_assessment("c1", Position.favorable, 0.6),
            _make_assessment("c2", Position.unfavorable, 0.9),
        ]
        assessments2 = [
            _make_assessment("c1", Position.favorable, 0.6),
            _make_assessment("c2", Position.unfavorable, 0.9),
        ]
        assign_colors(assessments1, threshold=0.7)
        assign_colors(assessments2, threshold=0.7)
        for a1, a2 in zip(assessments1, assessments2, strict=True):
            assert a1.color == a2.color
            assert a1.effective_confidence == a2.effective_confidence
            assert a1.amber_reasons == a2.amber_reasons
