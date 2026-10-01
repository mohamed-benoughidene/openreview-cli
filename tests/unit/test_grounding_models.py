"""Unit tests for grounding data models."""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

import pytest

from openreview_cli.grounding.models import (
    CGMetrics,
    CGReport,
    CitationProvenance,
    DiscriminationAuditEntry,
    GroundingResult,
    GroundingVerdict,
)
from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Position,
    QAVerdict,
    ReviewReport,
    ReviewSummary,
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
        assert GroundingVerdict.GROUNDED.value == "grounded"
        assert GroundingVerdict.UNGROUNDED.value == "ungrounded"
        assert GroundingVerdict.UNCERTAIN.value == "uncertain"


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

    def test_presence_defaults_to_none_and_false(self) -> None:
        """A result that never measured a claim carries no number and no hint."""
        result = GroundingResult(claim_index=0, verdict=GroundingVerdict.GROUNDED, provenances=[])
        assert result.grounding_presence is None
        assert result.wording_absent is False


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
            position=Position.PREFERRED,
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

    def test_merge_into_copies_presence_and_absence(self) -> None:
        """The two presence signals ride from the GroundingResult onto the assessment."""
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
            position=Position.PREFERRED,
            confidence=0.9,
            citation="4.3",
            qa_verdict=QAVerdict.agree,
            extraction_model="test",
            qa_model="test",
        )
        review_report = ReviewReport(
            document=DocMeta(filename="test.pdf", page_count=1, clause_count=1, pii_stripped=False),
            assessments=[assessment],
            summary=ReviewSummary(),
            playbook_id="test",
            generated_at=datetime.now(),
        )

        prov = CitationProvenance(clause_id="4.3", paragraph_index=0, confidence=0.95)
        result = GroundingResult(
            claim_index=0,
            verdict=GroundingVerdict.GROUNDED,
            provenances=[prov],
            reason=None,
            grounding_presence=0.42,
            wording_absent=True,
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

        assert review_report.assessments[0].grounding_presence == 0.42
        assert review_report.assessments[0].wording_absent is True

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
            position=Position.PREFERRED,
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
            position=Position.PREFERRED,
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
            position=Position.PREFERRED,
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


class TestNewGroundingFields:
    """FIX 6: the three fields and the memo counts land in ONE migration."""

    def _report_and_cg(
        self,
        mode: Literal["strict", "lenient"],
        verdict: GroundingVerdict,
        **result_fields: Any,
    ) -> tuple[ReviewReport, CGReport]:
        review = ReviewReport(
            document=DocMeta(filename="test.pdf", page_count=1, clause_count=1, pii_stripped=False),
            assessments=[
                ClauseAssessment(
                    clause_id="4.3",
                    clause_text="Test clause",
                    playbook_category="confidentiality",
                    position=Position.PREFERRED,
                    confidence=0.9,
                    citation="4.3",
                    qa_verdict=QAVerdict.agree,
                    extraction_model="test",
                    qa_model="test",
                )
            ],
            summary=ReviewSummary(),
            playbook_id="test",
            generated_at=datetime.now(),
        )
        cg = CGReport(
            verdicts=[
                GroundingResult(claim_index=0, verdict=verdict, provenances=[], **result_fields)
            ],
            mode=mode,
            metrics=CGMetrics(
                citation_precision=1.0, citation_relevance=1.0, citation_locality=1.0
            ),
            total_claims=1,
            grounded_count=1 if verdict is GroundingVerdict.GROUNDED else 0,
            ungrounded_count=1 if verdict is GroundingVerdict.UNGROUNDED else 0,
            uncertain_count=1 if verdict is GroundingVerdict.UNCERTAIN else 0,
        )
        return review, cg

    def test_defaults_keep_every_existing_construction_working(self) -> None:
        result = GroundingResult(claim_index=0, verdict=GroundingVerdict.GROUNDED, provenances=[])
        assert (result.miscited_to_clause_id, result.pass_disagreement, result.not_sure) == (
            None,
            False,
            False,
        )

    def test_merge_copies_the_three_new_fields(self) -> None:
        review, cg = self._report_and_cg(
            "lenient",
            GroundingVerdict.GROUNDED,
            miscited_to_clause_id="4.7",
            pass_disagreement=True,
            not_sure=True,
        )
        cg.merge_into(review)
        merged = review.assessments[0]
        assert (merged.miscited_to_clause_id, merged.pass_disagreement, merged.not_sure) == (
            "4.7",
            True,
            True,
        )

    def test_strict_merge_records_the_exclusion_counts_for_the_memo(self) -> None:
        review, cg = self._report_and_cg("strict", GroundingVerdict.UNGROUNDED)
        cg.merge_into(review)
        assert review.assessments == []
        assert (review.grounding_excluded_unsupported, review.grounding_excluded_unsure) == (1, 0)

    def test_from_dict_reads_the_two_memo_counts(self) -> None:
        """The counts the strict merge recorded survive a JSON round-trip (Task 8 reads them)."""
        review, _cg = self._report_and_cg("strict", GroundingVerdict.GROUNDED)
        review.grounding_excluded_unsupported = 2
        review.grounding_excluded_unsure = 1
        reloaded = ReviewReport.from_dict(asdict(review))
        assert (reloaded.grounding_excluded_unsupported, reloaded.grounding_excluded_unsure) == (
            2,
            1,
        )


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


class _RecordingHandler(logging.Handler):
    """A handler that keeps every record it is given, for the negative control."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class TestStrictRemovalLogging:
    """#160: the strict-mode exclusion log must never carry clause text."""

    _CANARY = "CANARYCLAUSETEXT-" + "x" * 80

    def _build(self) -> tuple[CGReport, Any]:
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
            clause_text=self._CANARY,
            playbook_category="confidentiality",
            position=Position.PREFERRED,
            confidence=0.9,
            citation="4.3",
            qa_verdict=QAVerdict.agree,
            extraction_model="test",
            qa_model="test",
        )
        report = ReviewReport(
            document=DocMeta(filename="test.pdf", page_count=1, clause_count=1, pii_stripped=False),
            assessments=[assessment],
            summary=ReviewSummary(),
            playbook_id="test",
            generated_at=datetime.now(),
        )
        cg_report = CGReport(
            verdicts=[
                GroundingResult(
                    claim_index=0,
                    verdict=GroundingVerdict.UNGROUNDED,
                    provenances=[],
                    reason="Not found",
                )
            ],
            mode="strict",
            metrics=CGMetrics(
                citation_precision=0.0, citation_relevance=0.0, citation_locality=0.0
            ),
            total_claims=1,
            grounded_count=0,
            ungrounded_count=1,
            uncertain_count=0,
        )
        return cg_report, report

    def test_strict_removal_logs_reason_and_citation_but_no_clause_text(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        cg_report, report = self._build()

        with caplog.at_level("WARNING", logger="openreview_cli.grounding.models"):
            cg_report.merge_into(report)

        assert "Claim #0" in caplog.text
        assert "Not found" in caplog.text
        assert "4.3" in caplog.text
        assert self._CANARY not in caplog.text
        assert self._CANARY[:40] not in caplog.text

    def test_negative_control_a_canary_reaches_a_recording_handler(self) -> None:
        """The canary *is* observable through the same logger when it is logged.

        Proves the absence assertion above is not vacuous: were ``clause_text``
        re-added to the warning, this is the path that would surface it.
        """
        handler = _RecordingHandler()
        grounding_logger = logging.getLogger("openreview_cli.grounding.models")
        grounding_logger.addHandler(handler)
        try:
            grounding_logger.warning("canary %s", self._CANARY)
        finally:
            grounding_logger.removeHandler(handler)

        assert any(self._CANARY in record.getMessage() for record in handler.records)
