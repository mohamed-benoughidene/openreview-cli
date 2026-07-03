"""Unit tests for review data models (ClauseAssessment, Playbook, ReviewReport)."""

from datetime import UTC, datetime

import pytest

from openreview_cli.review.colors import assign_colors
from openreview_cli.review.models import (
    Category,
    ClauseAssessment,
    DocMeta,
    Playbook,
    PlaybookMetadata,
    Position,
    PositionDef,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
)


class TestPosition:
    def test_enum_values(self) -> None:
        assert Position.favorable.value == "favorable"
        assert Position.neutral.value == "neutral"
        assert Position.unfavorable.value == "unfavorable"
        assert Position.uncertain.value == "uncertain"


class TestQAVerdict:
    def test_enum_values(self) -> None:
        assert QAVerdict.agree.value == "agree"
        assert QAVerdict.disagree.value == "disagree"
        assert QAVerdict.uncertain.value == "uncertain"


class TestPositionDef:
    def test_minimal(self) -> None:
        p = PositionDef(description="Short term", exemplars=["3 years"])
        assert p.description == "Short term"
        assert p.exemplars == ["3 years"]

    def test_empty_exemplars_raises(self) -> None:
        with pytest.raises(ValueError, match="exemplars"):
            PositionDef(description="test", exemplars=[])

    def test_multiple_exemplars(self) -> None:
        p = PositionDef(description="test", exemplars=["a", "b", "c"])
        assert len(p.exemplars) == 3


class TestCategory:
    def test_minimal(self) -> None:
        fav = PositionDef(description="Short term", exemplars=["3 years"])
        neu = PositionDef(description="5 years", exemplars=["5 years"])
        unfav = PositionDef(description="Indefinite", exemplars=["perpetuity"])
        cat = Category(
            id="confidentiality-term",
            name="Confidentiality Term",
            description="Defines how long confidentiality obligations survive",
            favorable=fav,
            neutral=neu,
            unfavorable=unfav,
            default_position=Position.neutral,
        )
        assert cat.id == "confidentiality-term"
        assert cat.default_position == Position.neutral

    def test_default_position_not_uncertain(self) -> None:
        """default_position must be favorable/neutral/unfavorable, never uncertain."""
        fav = PositionDef(description="a", exemplars=["a"])
        neu = PositionDef(description="b", exemplars=["b"])
        unfav = PositionDef(description="c", exemplars=["c"])
        with pytest.raises(ValueError, match="default_position"):
            Category(
                id="test",
                name="Test",
                description="test",
                favorable=fav,
                neutral=neu,
                unfavorable=unfav,
                default_position=Position.uncertain,
            )


class TestPlaybookMetadata:
    def test_minimal(self) -> None:
        m = PlaybookMetadata(version="1.0.0", description="test", author="test")
        assert m.version == "1.0.0"


class TestPlaybook:
    def make_category(self, cat_id: str) -> Category:
        fav = PositionDef(description="a", exemplars=["a"])
        neu = PositionDef(description="b", exemplars=["b"])
        unfav = PositionDef(description="c", exemplars=["c"])
        return Category(
            id=cat_id,
            name=cat_id,
            description="test",
            favorable=fav,
            neutral=neu,
            unfavorable=unfav,
            default_position=Position.neutral,
        )

    def test_minimal(self) -> None:
        meta = PlaybookMetadata(version="1.0.0", description="test", author="test")
        cat = self.make_category("confidentiality-term")
        p = Playbook(id="test", mode="precheck", categories=[cat], metadata=meta)
        assert p.id == "test"
        assert p.mode == "precheck"

    def test_empty_categories_raises(self) -> None:
        meta = PlaybookMetadata(version="1.0.0", description="test", author="test")
        with pytest.raises(ValueError, match="categories"):
            Playbook(id="test", mode="precheck", categories=[], metadata=meta)

    def test_duplicate_category_ids_raises(self) -> None:
        meta = PlaybookMetadata(version="1.0.0", description="test", author="test")
        with pytest.raises(ValueError, match="duplicate"):
            Playbook(
                id="test",
                mode="precheck",
                categories=[self.make_category("same"), self.make_category("same")],
                metadata=meta,
            )


class TestClauseAssessment:
    def test_minimal(self) -> None:
        ca = ClauseAssessment(
            clause_id="clause-001",
            clause_text="Confidential Information shall be kept secret for 3 years.",
            playbook_category="confidentiality-term",
            position=Position.favorable,
            confidence=0.92,
            citation="for 3 years",
            qa_verdict=QAVerdict.agree,
            extraction_model="ollama/llama3.2:3b",
            qa_model="ollama/llama3.2:3b",
        )
        assert ca.clause_id == "clause-001"
        assert ca.is_amber is False  # no disagreement, high confidence

    def test_low_confidence_triggers_amber(self) -> None:
        ca = ClauseAssessment(
            clause_id="c1",
            clause_text="text",
            playbook_category="test",
            position=Position.neutral,
            confidence=0.3,
            citation="text",
            qa_verdict=QAVerdict.agree,
            extraction_model="m1",
            qa_model="m1",
        )
        assign_colors([ca])
        assert ca.is_amber is True

    def test_qa_disagreement_triggers_amber(self) -> None:
        ca = ClauseAssessment(
            clause_id="c1",
            clause_text="text",
            playbook_category="test",
            position=Position.favorable,
            confidence=0.9,
            citation="text",
            qa_verdict=QAVerdict.disagree,
            qa_revised_position=Position.neutral,
            qa_revised_rationale="The clause is standard market language",
            extraction_model="m1",
            qa_model="m1",
        )
        assign_colors([ca])
        assert ca.is_amber is True
        assert ca.qa_revised_position == Position.neutral

    def test_error_triggers_amber(self) -> None:
        ca = ClauseAssessment(
            clause_id="c1",
            clause_text="text",
            playbook_category="test",
            position=Position.uncertain,
            confidence=0.0,
            citation="",
            qa_verdict=QAVerdict.uncertain,
            extraction_model="m1",
            qa_model="m1",
            error="Model returned unparseable output",
        )
        assign_colors([ca])
        assert ca.is_amber is True

    def test_confidence_range_validation(self) -> None:
        with pytest.raises(ValueError):
            ClauseAssessment(
                clause_id="c1",
                clause_text="text",
                playbook_category="test",
                position=Position.neutral,
                confidence=1.5,  # out of range
                citation="text",
                qa_verdict=QAVerdict.agree,
                extraction_model="m1",
                qa_model="m1",
            )

    def test_no_match_category(self) -> None:
        ca = ClauseAssessment(
            clause_id="c1",
            clause_text="Recitals page",
            playbook_category="no-match",
            position=Position.uncertain,
            confidence=0.0,
            citation="",
            qa_verdict=QAVerdict.uncertain,
            extraction_model="m1",
            qa_model="m1",
        )
        assign_colors([ca])
        assert ca.is_amber is True
        assert ca.playbook_category == "no-match"


class TestDocMeta:
    def test_minimal(self) -> None:
        dm = DocMeta(filename="nda.docx", page_count=12, clause_count=28, pii_stripped=True)
        assert dm.filename == "nda.docx"
        assert dm.page_count == 12


class TestReviewSummary:
    def test_counts(self) -> None:
        rs = ReviewSummary(
            favorable_count=10,
            neutral_count=8,
            unfavorable_count=4,
            uncertain_count=2,
            no_match_count=0,
            amber_count=3,
            avg_confidence=0.85,
        )
        assert rs.total == 24
        assert rs.favorable_count == 10


class TestReviewReport:
    def make_assessment(self, cid: str, pos: Position, conf: float) -> ClauseAssessment:
        return ClauseAssessment(
            clause_id=cid,
            clause_text="Some clause text for " + cid,
            playbook_category="test",
            position=pos,
            confidence=conf,
            citation="clause text",
            qa_verdict=QAVerdict.agree,
            extraction_model="m1",
            qa_model="m1",
        )

    def test_minimal(self) -> None:
        dm = DocMeta(filename="nda.docx", page_count=5, clause_count=3, pii_stripped=False)
        assessments = [
            self.make_assessment("c1", Position.favorable, 0.9),
            self.make_assessment("c2", Position.neutral, 0.8),
        ]
        summary = ReviewSummary(
            favorable_count=1,
            neutral_count=1,
            unfavorable_count=0,
            uncertain_count=0,
            no_match_count=0,
            amber_count=0,
            avg_confidence=0.85,
        )
        now = datetime.now(UTC)
        report = ReviewReport(
            document=dm,
            assessments=assessments,
            summary=summary,
            playbook_id="precheck-nda-v1",
            generated_at=now,
        )
        assert report.schema_version == "1.1.0"
        assert len(report.assessments) == 2
        assert report.playbook_id == "precheck-nda-v1"
