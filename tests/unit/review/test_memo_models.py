"""Unit tests for memo data models (MemoFormat, MemoReport, etc.)."""

from __future__ import annotations

from openreview_cli.review.memo.models import (
    MemoCitation,
    MemoClause,
    MemoFormat,
    MemoReport,
    MemoSummary,
    MemoTierInfo,
)


class TestMemoFormat:
    def test_enum_values(self) -> None:
        assert MemoFormat.MARKDOWN.value == "md"
        assert MemoFormat.JSON.value == "json"
        assert MemoFormat.DOCX.value == "docx"

    def test_membership(self) -> None:
        assert "md" in {f.value for f in MemoFormat}

    def test_str_conversion(self) -> None:
        assert str(MemoFormat.MARKDOWN) == "md"
        assert str(MemoFormat.JSON) == "json"
        assert str(MemoFormat.DOCX) == "docx"


class TestMemoCitation:
    def test_minimal(self) -> None:
        mc = MemoCitation(clause_id="§12.3", paragraph_index=0)
        assert mc.clause_id == "§12.3"
        assert mc.paragraph_index == 0

    def test_zero_paragraph_index(self) -> None:
        mc = MemoCitation(clause_id="§1.1", paragraph_index=0)
        assert mc.paragraph_index == 0


class TestMemoTierInfo:
    def test_maximum_tier(self) -> None:
        ti = MemoTierInfo(privacy_tier="maximum", pii_stripped=True, entities_redacted=12)
        assert ti.privacy_tier == "maximum"
        assert ti.pii_stripped is True
        assert ti.entities_redacted == 12

    def test_performance_tier(self) -> None:
        ti = MemoTierInfo(privacy_tier="performance", pii_stripped=False, entities_redacted=0)
        assert ti.privacy_tier == "performance"
        assert ti.pii_stripped is False

    def test_zero_redacted(self) -> None:
        ti = MemoTierInfo(privacy_tier="balanced", pii_stripped=True, entities_redacted=0)
        assert ti.entities_redacted == 0


class TestMemoSummary:
    def test_all_fields(self) -> None:
        ms = MemoSummary(
            recommendation="approve",
            clauses_checked=15,
            matches=12,
            differences=3,
            confidence_avg=0.87,
        )
        assert ms.recommendation == "approve"
        assert ms.clauses_checked == 15
        assert ms.matches == 12
        assert ms.differences == 3
        assert ms.confidence_avg == 0.87

    def test_revise_recommendation(self) -> None:
        ms = MemoSummary(
            recommendation="revise",
            clauses_checked=10,
            matches=5,
            differences=5,
            confidence_avg=0.65,
        )
        assert ms.recommendation == "revise"

    def test_reject_recommendation(self) -> None:
        ms = MemoSummary(
            recommendation="reject",
            clauses_checked=8,
            matches=1,
            differences=7,
            confidence_avg=0.35,
        )
        assert ms.recommendation == "reject"

    def test_confidence_avg_zero(self) -> None:
        ms = MemoSummary(
            recommendation="approve",
            clauses_checked=0,
            matches=0,
            differences=0,
            confidence_avg=0.0,
        )
        assert ms.confidence_avg == 0.0


class TestMemoClause:
    def test_minimal(self) -> None:
        mc = MemoClause(
            id="clause-003",
            title="Confidentiality Term",
            playbook_requirement="Preferred: 3 years",
            contract_text="The term shall be 3 years.",
            assessment="match",
            color="green",
            confidence=0.92,
        )
        assert mc.id == "clause-003"
        assert mc.assessment == "match"
        assert mc.color == "green"
        assert mc.confidence == 0.92
        assert mc.citation is None
        assert mc.severity is None
        assert mc.source_filename is None

    def test_with_citation(self) -> None:
        citation = MemoCitation(clause_id="§5.1", paragraph_index=2)
        mc = MemoClause(
            id="clause-001",
            title="Permitted Disclosures",
            playbook_requirement="Acceptable: with NDA",
            contract_text="Disclosures permitted with NDA.",
            assessment="difference",
            color="amber",
            confidence=0.65,
            citation=citation,
            severity="major",
            source_filename="nda.pdf",
        )
        assert mc.citation == citation
        assert mc.severity == "major"
        assert mc.source_filename == "nda.pdf"

    def test_high_confidence(self) -> None:
        mc = MemoClause(
            id="clause-010",
            title="Governing Law",
            playbook_requirement="Preferred: Delaware",
            contract_text="Delaware law governs.",
            assessment="match",
            color="green",
            confidence=0.99,
        )
        assert mc.confidence == 0.99

    def test_low_confidence(self) -> None:
        mc = MemoClause(
            id="clause-020",
            title="Indemnification",
            playbook_requirement="Walkaway: No indemnification",
            contract_text="Party shall indemnify...",
            assessment="difference",
            color="red",
            confidence=0.15,
        )
        assert mc.confidence == 0.15


class TestMemoReport:
    def test_complete(self) -> None:
        summary = MemoSummary(
            recommendation="approve",
            clauses_checked=3,
            matches=3,
            differences=0,
            confidence_avg=0.93,
        )
        clauses = [
            MemoClause(
                id="c1",
                title="Confidentiality",
                playbook_requirement="3 years",
                contract_text="3 year term.",
                assessment="match",
                color="green",
                confidence=0.95,
            ),
        ]
        report = MemoReport(
            memo_version="1.0",
            mode="precheck",
            document_name="nda.pdf",
            playbook_name="precheck-nda-v1",
            playbook_version="1.2.0",
            review_date="2026-07-05T14:30:22+00:00",
            overall=summary,
            clauses=clauses,
            disclaimer="AI-generated review. Not legal advice.",
        )
        assert report.memo_version == "1.0"
        assert report.mode == "precheck"
        assert report.document_name == "nda.pdf"
        assert report.playbook_name == "precheck-nda-v1"
        assert report.playbook_version == "1.2.0"
        assert report.overall.matches == 3
        assert len(report.clauses) == 1
        assert report.disclaimer == "AI-generated review. Not legal advice."
        assert report.tier_info is None

    def test_with_tier_info(self) -> None:
        tier = MemoTierInfo(privacy_tier="maximum", pii_stripped=True, entities_redacted=5)
        summary = MemoSummary(
            recommendation="revise",
            clauses_checked=2,
            matches=1,
            differences=1,
            confidence_avg=0.70,
        )
        report = MemoReport(
            memo_version="1.0",
            mode="dealcheck",
            document_name="merger.pdf",
            playbook_name="merger-v2",
            playbook_version="2.0.0",
            review_date="2026-07-05T15:00:00+00:00",
            overall=summary,
            clauses=[],
            disclaimer="AI-generated. Verify with counsel.",
            tier_info=tier,
        )
        assert report.tier_info is not None
        assert report.tier_info.privacy_tier == "maximum"

    def test_empty_clauses_list(self) -> None:
        summary = MemoSummary(
            recommendation="approve",
            clauses_checked=0,
            matches=0,
            differences=0,
            confidence_avg=0.0,
        )
        report = MemoReport(
            memo_version="1.0",
            mode="precheck",
            document_name="empty.pdf",
            playbook_name="nda-v1",
            playbook_version="1.0.0",
            review_date="2026-07-05T12:00:00+00:00",
            overall=summary,
            clauses=[],
            disclaimer="Test",
        )
        assert len(report.clauses) == 0

    def test_dealcheck_mode(self) -> None:
        summary = MemoSummary(
            recommendation="reject",
            clauses_checked=1,
            matches=0,
            differences=1,
            confidence_avg=0.25,
        )
        report = MemoReport(
            memo_version="1.0",
            mode="dealcheck",
            document_name="agreement.pdf",
            playbook_name="merger-v2",
            playbook_version="1.0.0",
            review_date="2026-07-05T00:00:00+00:00",
            overall=summary,
            clauses=[],
            disclaimer="Test",
        )
        assert report.mode == "dealcheck"
