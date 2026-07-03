"""Unit tests for paired color assignment (three-color output).

Tests the ``assign_paired_colors()`` function that maps each
``PairedAssessment`` to Green/Amber/Red based on confidence,
divergence, QA verdict, and extraction confidence.
"""

from __future__ import annotations

from dataclasses import replace as dataclass_replace

from openreview_cli.bilateral.models import (
    AlignmentPair,
    DivergenceVerdict,
    MatchingMethod,
    PairedAssessment,
)
from openreview_cli.parsing.models import Clause
from openreview_cli.review.colors import AssessmentColor
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
    position: Position = Position.neutral,
    confidence: float = 0.85,
    qa_verdict: QAVerdict = QAVerdict.agree,
) -> ClauseAssessment:
    return ClauseAssessment(
        clause_id=clause_id,
        clause_text="Test clause text",
        playbook_category="test-cat",
        position=position,
        confidence=confidence,
        citation="test excerpt",
        qa_verdict=qa_verdict,
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


def make_paired_assessment(
    pair_id: str = "pair-001",
    divergence: DivergenceVerdict = DivergenceVerdict.aligned,
    confidence: float = 0.85,
    alignment_quality: float = 1.0,
    a_confidence: float = 0.85,
    a_qa: QAVerdict = QAVerdict.agree,
    b_confidence: float = 0.85,
    b_qa: QAVerdict = QAVerdict.agree,
) -> PairedAssessment:
    alignment = make_alignment_pair(pair_id=f"A0-B0-{pair_id}")
    ass_a = make_assessment("a1", confidence=a_confidence, qa_verdict=a_qa)
    ass_b = make_assessment("b1", confidence=b_confidence, qa_verdict=b_qa)
    return PairedAssessment(
        pair_id=pair_id,
        alignment=alignment,
        party_a_assessment=ass_a,
        party_b_assessment=ass_b,
        divergence=divergence,
        confidence=confidence,
        alignment_quality=alignment_quality,
    )


# ---------------------------------------------------------------------------
# Green tests
# ---------------------------------------------------------------------------


class TestGreenAssignment:
    """No divergence + both confident + QA agrees → Green."""

    def test_aligned_both_confident_qa_agree(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        pa = make_paired_assessment(
            divergence=DivergenceVerdict.aligned,
            confidence=0.85,
            a_qa=QAVerdict.agree,
            b_qa=QAVerdict.agree,
        )
        assign_paired_colors([pa], confidence_threshold=0.7)
        assert pa.color == AssessmentColor.green

    def test_no_divergence_high_confidence(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        pa = make_paired_assessment(
            divergence=DivergenceVerdict.aligned,
            confidence=0.95,
        )
        assign_paired_colors([pa], confidence_threshold=0.7)
        assert pa.color == AssessmentColor.green

    def test_multiple_green_pairs(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        pas = [
            make_paired_assessment(
                f"pair-{i}", divergence=DivergenceVerdict.aligned, confidence=0.9
            )
            for i in range(3)
        ]
        assign_paired_colors(pas, confidence_threshold=0.7)
        assert all(p.color == AssessmentColor.green for p in pas)


# ---------------------------------------------------------------------------
# Red tests
# ---------------------------------------------------------------------------


class TestRedAssignment:
    """Divergence detected + confident + QA agrees → Red."""

    def test_divergent_confident(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        pa = make_paired_assessment(
            divergence=DivergenceVerdict.divergent,
            confidence=0.85,
            a_qa=QAVerdict.agree,
            b_qa=QAVerdict.agree,
        )
        assign_paired_colors([pa], confidence_threshold=0.7)
        assert pa.color == AssessmentColor.red

    def test_divergent_high_confidence_qa_agree(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        pa = make_paired_assessment(
            divergence=DivergenceVerdict.divergent,
            confidence=0.95,
        )
        assign_paired_colors([pa], confidence_threshold=0.7)
        assert pa.color == AssessmentColor.red


# ---------------------------------------------------------------------------
# Amber tests
# ---------------------------------------------------------------------------


class TestAmberAssignment:
    """Various amber triggers."""

    def test_confidence_below_threshold(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        pa = make_paired_assessment(
            divergence=DivergenceVerdict.aligned,
            confidence=0.5,
        )
        assign_paired_colors([pa], confidence_threshold=0.7)
        assert pa.color == AssessmentColor.amber

    def test_divergence_uncertain(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        pa = make_paired_assessment(divergence=DivergenceVerdict.uncertain, confidence=0.7)
        assign_paired_colors([pa], confidence_threshold=0.7)
        assert pa.color == AssessmentColor.amber

    def test_qa_disagreement_party_a(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        pa = make_paired_assessment(
            divergence=DivergenceVerdict.aligned,
            confidence=0.85,
            a_qa=QAVerdict.disagree,
        )
        assign_paired_colors([pa], confidence_threshold=0.7)
        assert pa.color == AssessmentColor.amber

    def test_qa_disagreement_party_b(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        pa = make_paired_assessment(
            divergence=DivergenceVerdict.aligned,
            confidence=0.85,
            b_qa=QAVerdict.disagree,
        )
        assign_paired_colors([pa], confidence_threshold=0.7)
        assert pa.color == AssessmentColor.amber

    def test_low_extraction_confidence_party_a(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        pa = make_paired_assessment(
            divergence=DivergenceVerdict.aligned,
            confidence=0.85,
            a_confidence=0.4,
        )
        assign_paired_colors([pa], confidence_threshold=0.7)
        assert pa.color == AssessmentColor.amber

    def test_low_extraction_confidence_party_b(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        pa = make_paired_assessment(
            divergence=DivergenceVerdict.aligned,
            confidence=0.85,
            b_confidence=0.3,
        )
        assign_paired_colors([pa], confidence_threshold=0.7)
        assert pa.color == AssessmentColor.amber

    def test_all_triggers_simultaneously(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        pa = make_paired_assessment(
            divergence=DivergenceVerdict.uncertain,
            confidence=0.3,
            a_confidence=0.3,
            b_confidence=0.3,
            a_qa=QAVerdict.disagree,
            b_qa=QAVerdict.uncertain,
        )
        assign_paired_colors([pa], confidence_threshold=0.7)
        assert pa.color == AssessmentColor.amber

    def test_qa_uncertain_on_either_side_triggers_amber(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        pa_a = make_paired_assessment(
            "p1", DivergenceVerdict.aligned, 0.85, a_qa=QAVerdict.uncertain
        )
        pa_b = make_paired_assessment(
            "p2", DivergenceVerdict.aligned, 0.85, b_qa=QAVerdict.uncertain
        )
        assign_paired_colors([pa_a, pa_b], confidence_threshold=0.7)
        assert pa_a.color == AssessmentColor.amber
        assert pa_b.color == AssessmentColor.amber


# ---------------------------------------------------------------------------
# Threshold sensitivity
# ---------------------------------------------------------------------------


class TestThresholdSensitivity:
    """Threshold=0.9 produces more Amber than threshold=0.5."""

    def test_higher_threshold_more_amber(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        # Confidence = 0.65 — amber at 0.7, green at 0.5
        pas = [
            make_paired_assessment(
                f"pair-{i}",
                divergence=DivergenceVerdict.aligned,
                confidence=0.65,
            )
            for i in range(10)
        ]

        pas_low = [dataclass_replace(p) for p in pas]
        assign_paired_colors(pas_low, confidence_threshold=0.5)
        low_amber = sum(1 for p in pas_low if p.color == AssessmentColor.amber)

        pas_high = [dataclass_replace(p) for p in pas]
        assign_paired_colors(pas_high, confidence_threshold=0.9)
        high_amber = sum(1 for p in pas_high if p.color == AssessmentColor.amber)

        assert high_amber >= low_amber


# ---------------------------------------------------------------------------
# Pure function behavior
# ---------------------------------------------------------------------------


class TestPureFunction:
    """assign_paired_colors must not mutate input list, only color field."""

    def test_returns_same_list(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        pas = [make_paired_assessment("p1", DivergenceVerdict.aligned, 0.85)]
        result = assign_paired_colors(pas, confidence_threshold=0.7)
        assert result is pas

    def test_does_not_add_or_remove_assessments(self) -> None:
        from openreview_cli.bilateral.colors import assign_paired_colors

        pas = [make_paired_assessment("p1"), make_paired_assessment("p2")]
        result = assign_paired_colors(pas, confidence_threshold=0.7)
        assert len(result) == 2
