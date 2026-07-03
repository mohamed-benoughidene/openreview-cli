"""Unit tests for grounding data models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

import pytest

from openreview_cli.grounding.models import (
    CGMetrics,
    CGReport,
    CitationProvenance,
    DiscriminationAuditEntry,
    GroundingResult,
    GroundingVerdict,
)


class TestGroundingVerdict:
    def test_enum_values(self) -> None:
        assert GroundingVerdict.GROUNDED.value == "grounded"
        assert GroundingVerdict.UNGROUNDED.value == "ungrounded"
        assert GroundingVerdict.UNCERTAIN.value == "uncertain"

    def test_enum_is_strenum(self) -> None:
        assert issubclass(GroundingVerdict, StrEnum)

    def test_enum_members(self) -> None:
        assert set(GroundingVerdict.__members__) == {"GROUNDED", "UNGROUNDED", "UNCERTAIN"}

    def test_enum_comparison_to_string(self) -> None:
        # StrEnum compares equal to its string value
        assert GroundingVerdict.GROUNDED == "grounded"
        assert GroundingVerdict.UNGROUNDED == "ungrounded"
        assert GroundingVerdict.UNCERTAIN == "uncertain"


class TestCitationProvenance:
    def test_construction(self) -> None:
        p = CitationProvenance(clause_id="4.3", paragraph_index=2, confidence=0.95)
        assert p.clause_id == "4.3"
        assert p.paragraph_index == 2
        assert p.confidence == 0.95

    def test_slots_behavior(self) -> None:
        p = CitationProvenance(clause_id="4.3", paragraph_index=2, confidence=0.95)
        with pytest.raises(AttributeError):
            p.nonexistent = 1  # type: ignore[attr-defined]

    def test_repr(self) -> None:
        p = CitationProvenance(clause_id="4.3", paragraph_index=2, confidence=0.95)
        assert "CitationProvenance" in repr(p)
        assert "4.3" in repr(p)


class TestGroundingResult:
    def test_accepts_all_verdicts(self) -> None:
        for verdict in GroundingVerdict:
            result = GroundingResult(
                claim_index=0,
                verdict=verdict,
                provenances=[],
                reason=None,
            )
            assert result.verdict == verdict

    def test_reason_defaults_to_none(self) -> None:
        result = GroundingResult(claim_index=0, verdict=GroundingVerdict.GROUNDED, provenances=[])
        assert result.reason is None

    def test_with_provenances(self) -> None:
        prov = CitationProvenance(clause_id="4.3", paragraph_index=2, confidence=0.95)
        result = GroundingResult(
            claim_index=1,
            verdict=GroundingVerdict.GROUNDED,
            provenances=[prov],
            reason="Found in clause 4.3",
        )
        assert result.claim_index == 1
        assert len(result.provenances) == 1
        assert result.provenances[0].clause_id == "4.3"
        assert result.reason == "Found in clause 4.3"

    def test_empty_provenances(self) -> None:
        result = GroundingResult(
            claim_index=2,
            verdict=GroundingVerdict.UNGROUNDED,
            provenances=[],
            reason="No matching clause found",
        )
        assert result.provenances == []

    def test_slots_behavior(self) -> None:
        result = GroundingResult(claim_index=0, verdict=GroundingVerdict.GROUNDED, provenances=[])
        with pytest.raises(AttributeError):
            result.nonexistent = 1  # type: ignore[attr-defined]


class TestCGMetrics:
    def test_field_ranges_valid(self) -> None:
        metrics = CGMetrics(citation_precision=1.0, citation_relevance=0.75, citation_locality=0.5)
        assert metrics.citation_precision == 1.0
        assert metrics.citation_relevance == 0.75
        assert metrics.citation_locality == 0.5

    def test_zero_values(self) -> None:
        metrics = CGMetrics(citation_precision=0.0, citation_relevance=0.0, citation_locality=0.0)
        assert metrics.citation_precision == 0.0
        assert metrics.citation_relevance == 0.0
        assert metrics.citation_locality == 0.0

    @pytest.mark.parametrize(
        "field", ["citation_precision", "citation_relevance", "citation_locality"]
    )
    def test_negative_value_raises(self, field: str) -> None:
        kwargs = {"citation_precision": 0.5, "citation_relevance": 0.5, "citation_locality": 0.5}
        kwargs[field] = -0.1
        with pytest.raises(ValueError, match="must be in range"):
            CGMetrics(**kwargs)

    @pytest.mark.parametrize(
        "field", ["citation_precision", "citation_relevance", "citation_locality"]
    )
    def test_over_one_raises(self, field: str) -> None:
        kwargs = {"citation_precision": 0.5, "citation_relevance": 0.5, "citation_locality": 0.5}
        kwargs[field] = 1.1
        with pytest.raises(ValueError, match="must be in range"):
            CGMetrics(**kwargs)

    def test_slots_behavior(self) -> None:
        metrics = CGMetrics(citation_precision=1.0, citation_relevance=0.75, citation_locality=0.5)
        with pytest.raises(AttributeError):
            metrics.nonexistent = 1  # type: ignore[attr-defined]


class TestCGReport:
    def test_field_defaults(self) -> None:
        report = CGReport(
            verdicts=[],
            mode="strict",
            metrics=CGMetrics(
                citation_precision=0.0, citation_relevance=0.0, citation_locality=0.0
            ),
            total_claims=0,
            grounded_count=0,
            ungrounded_count=0,
            uncertain_count=0,
        )
        assert report.verdicts == []
        assert report.mode == "strict"
        assert report.total_claims == 0
        assert report.grounded_count == 0
        assert report.ungrounded_count == 0
        assert report.uncertain_count == 0

    def test_merge_into_signature(self) -> None:
        """Verify merge_into() exists and accepts a ReviewReport."""
        from openreview_cli.review.models import ReviewReport

        report = CGReport(
            verdicts=[],
            mode="strict",
            metrics=CGMetrics(
                citation_precision=0.0, citation_relevance=0.0, citation_locality=0.0
            ),
            total_claims=0,
            grounded_count=0,
            ungrounded_count=0,
            uncertain_count=0,
        )
        # Create a minimal ReviewReport
        from datetime import datetime

        from openreview_cli.review.models import DocMeta, ReviewSummary

        doc_meta = DocMeta(filename="test.pdf", page_count=1, clause_count=0, pii_stripped=False)
        summary = ReviewSummary()
        review_report = ReviewReport(
            document=doc_meta,
            assessments=[],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )
        result = report.merge_into(review_report)
        assert result is review_report  # Returns same report (mutated in place or returns it)

    def test_merge_into_sets_lenient_fields(self) -> None:
        """In lenient mode, merge_into sets grounding fields on assessments."""
        from datetime import datetime

        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            QAVerdict,
            ReviewReport,
            ReviewSummary,
        )

        assessment = ClauseAssessment(
            clause_id="4.3",
            clause_text="Test clause",
            playbook_category="confidentiality",
            position=Position.favorable,
            confidence=0.9,
            citation="4.3",
            qa_verdict=QAVerdict.agree,
            extraction_model="test",
            qa_model="test",
        )
        doc_meta = DocMeta(filename="test.pdf", page_count=1, clause_count=1, pii_stripped=False)
        summary = ReviewSummary()
        review_report = ReviewReport(
            document=doc_meta,
            assessments=[assessment],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        prov = CitationProvenance(clause_id="4.3", paragraph_index=0, confidence=0.95)
        result = GroundingResult(
            claim_index=0,
            verdict=GroundingVerdict.GROUNDED,
            provenances=[prov],
            reason=None,
        )
        cg_report = CGReport(
            verdicts=[result],
            mode="lenient",
            metrics=CGMetrics(
                citation_precision=1.0, citation_relevance=1.0, citation_locality=1.0
            ),
            total_claims=1,
            grounded_count=1,
            ungrounded_count=0,
            uncertain_count=0,
        )
        cg_report.merge_into(review_report)
        assert review_report.assessments[0].grounding_verdict == GroundingVerdict.GROUNDED
        assert review_report.assessments[0].grounding_provenances == [prov]
        assert review_report.assessments[0].grounding_confidence == 0.95

    def test_merge_into_removes_ungrounded_in_strict(self) -> None:
        """In strict mode, UNGROUNDED and UNCERTAIN claims are removed."""
        from datetime import datetime

        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            QAVerdict,
            ReviewReport,
            ReviewSummary,
        )

        grounded = ClauseAssessment(
            clause_id="4.3",
            clause_text="Grounded",
            playbook_category="confidentiality",
            position=Position.favorable,
            confidence=0.9,
            citation="4.3",
            qa_verdict=QAVerdict.agree,
            extraction_model="test",
            qa_model="test",
        )
        ungrounded = ClauseAssessment(
            clause_id="7.1",
            clause_text="Ungrounded",
            playbook_category="confidentiality",
            position=Position.favorable,
            confidence=0.9,
            citation="7.1",
            qa_verdict=QAVerdict.agree,
            extraction_model="test",
            qa_model="test",
        )
        doc_meta = DocMeta(filename="test.pdf", page_count=1, clause_count=2, pii_stripped=False)
        summary = ReviewSummary()
        review_report = ReviewReport(
            document=doc_meta,
            assessments=[grounded, ungrounded],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        prov = CitationProvenance(clause_id="4.3", paragraph_index=0, confidence=0.95)
        results = [
            GroundingResult(
                claim_index=0,
                verdict=GroundingVerdict.GROUNDED,
                provenances=[prov],
                reason=None,
            ),
            GroundingResult(
                claim_index=1,
                verdict=GroundingVerdict.UNGROUNDED,
                provenances=[],
                reason="Not found",
            ),
        ]
        cg_report = CGReport(
            verdicts=results,
            mode="strict",
            metrics=CGMetrics(
                citation_precision=1.0, citation_relevance=0.5, citation_locality=1.0
            ),
            total_claims=2,
            grounded_count=1,
            ungrounded_count=1,
            uncertain_count=0,
        )
        cg_report.merge_into(review_report)
        assert len(review_report.assessments) == 1
        assert review_report.assessments[0].clause_id == "4.3"

    def test_merge_into_removes_uncertain_in_strict(self) -> None:
        """UNCERTAIN verdicts are also removed in strict mode."""
        from datetime import datetime

        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            QAVerdict,
            ReviewReport,
            ReviewSummary,
        )

        uncertain = ClauseAssessment(
            clause_id="5.1",
            clause_text="Uncertain",
            playbook_category="confidentiality",
            position=Position.favorable,
            confidence=0.9,
            citation="5.1",
            qa_verdict=QAVerdict.agree,
            extraction_model="test",
            qa_model="test",
        )
        doc_meta = DocMeta(filename="test.pdf", page_count=1, clause_count=1, pii_stripped=False)
        summary = ReviewSummary()
        review_report = ReviewReport(
            document=doc_meta,
            assessments=[uncertain],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        result = GroundingResult(
            claim_index=0,
            verdict=GroundingVerdict.UNCERTAIN,
            provenances=[],
            reason="Ambiguous provenance",
        )
        cg_report = CGReport(
            verdicts=[result],
            mode="strict",
            metrics=CGMetrics(
                citation_precision=0.0, citation_relevance=0.0, citation_locality=0.0
            ),
            total_claims=1,
            grounded_count=0,
            ungrounded_count=0,
            uncertain_count=1,
        )
        cg_report.merge_into(review_report)
        assert len(review_report.assessments) == 0

    def test_empty_claims_list(self) -> None:
        """Edge case: empty claims list produces empty CGReport."""
        report = CGReport(
            verdicts=[],
            mode="strict",
            metrics=CGMetrics(
                citation_precision=0.0, citation_relevance=0.0, citation_locality=0.0
            ),
            total_claims=0,
            grounded_count=0,
            ungrounded_count=0,
            uncertain_count=0,
        )
        assert report.total_claims == 0
        assert report.grounded_count == 0
        assert report.ungrounded_count == 0
        assert report.uncertain_count == 0
        assert report.verdicts == []


class TestDiscriminationAuditEntry:
    def test_sha256_hash_deterministic(self) -> None:
        text = "The receiving party shall not disclose confidential information"
        hash1 = DiscriminationAuditEntry._hash_claim(text)
        hash2 = DiscriminationAuditEntry._hash_claim(text)
        assert hash1 == hash2

    def test_sha256_hash_different_text(self) -> None:
        text1 = "Claim one"
        text2 = "Claim two"
        hash1 = DiscriminationAuditEntry._hash_claim(text1)
        hash2 = DiscriminationAuditEntry._hash_claim(text2)
        assert hash1 != hash2

    def test_sha256_hash_length(self) -> None:
        text = "Test claim text"
        h = DiscriminationAuditEntry._hash_claim(text)
        assert len(h) == 64  # SHA-256 hex digest is 64 chars
        assert all(c in "0123456789abcdef" for c in h)

    def test_construction(self) -> None:
        entry = DiscriminationAuditEntry(
            claim_hash="abc123",
            verdict=GroundingVerdict.GROUNDED,
            confidence=0.95,
            provenances=[],
            reason=None,
        )
        assert entry.claim_hash == "abc123"
        assert entry.verdict == GroundingVerdict.GROUNDED
        assert entry.confidence == 0.95
        assert entry.provenances == []
        assert entry.reason is None
        assert entry.timestamp is not None  # auto-set

    def test_reason_for_ungrounded(self) -> None:
        entry = DiscriminationAuditEntry(
            claim_hash="def456",
            verdict=GroundingVerdict.UNGROUNDED,
            confidence=0.3,
            provenances=[],
            reason="Claim text not found in cited clause",
        )
        assert entry.reason == "Claim text not found in cited clause"

    def test_timestamp_defaults_to_now(self) -> None:
        entry = DiscriminationAuditEntry(
            claim_hash="ghi789",
            verdict=GroundingVerdict.UNCERTAIN,
            confidence=0.5,
            provenances=[],
            reason="Boundary case",
        )
        assert isinstance(entry.timestamp, datetime)
