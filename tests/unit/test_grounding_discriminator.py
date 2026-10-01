"""Unit tests for CitationGroundingDiscriminator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from openreview_cli.parsing.models import Clause
    from openreview_cli.review.models import ReviewReport

from openreview_cli.grounding import presence
from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
from openreview_cli.grounding.models import (
    CGReport,
    GroundingVerdict,
)

# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_gateway() -> MagicMock:
    gw = MagicMock()
    gw.chat.return_value = '[{"claim_index": 0, "verdict": "grounded", "provenances": [{"clause_id": "4.3", "paragraph_index": 2, "confidence": 0.95}], "confidence": 0.95, "reason": null}]'
    return gw


@pytest.fixture
def discriminator(mock_gateway: MagicMock) -> CitationGroundingDiscriminator:
    """Create a discriminator with mocked gateway (strict mode by default)."""
    return CitationGroundingDiscriminator(
        mode="strict",
        gateway=mock_gateway,
    )


@pytest.fixture
def lenient_discriminator(mock_gateway: MagicMock) -> CitationGroundingDiscriminator:
    return CitationGroundingDiscriminator(
        mode="lenient",
        gateway=mock_gateway,
    )


@pytest.fixture
def sample_report() -> MagicMock:
    """Create a mock ReviewReport with assessable claims."""

    report = MagicMock()

    # Create 10 mock assessments
    assessments = []
    for i in range(10):
        assessment = MagicMock()
        assessment.clause_text = f"Claim {i}: The receiving party shall not disclose"
        assessment.citation = "4.3"
        assessment.qa_verdict = MagicMock()
        assessment.qa_verdict.__eq__ = lambda self, other: other.value == "agree"
        assessment.qa_verdict.value = "agree"
        assessment.grounding_verdict = None
        assessment.grounding_provenances = None
        assessment.grounding_confidence = None
        assessments.append(assessment)

    report.assessments = assessments
    report.summary = MagicMock()
    return report


@pytest.fixture
def sample_document() -> MagicMock:
    doc = MagicMock()
    doc.source_path = MagicMock()
    doc.source_path.name = "test.pdf"
    return doc


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestCitationGroundingDiscriminator:
    def test_default_strict_mode(self) -> None:
        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator

        d = CitationGroundingDiscriminator()
        assert d.mode == "strict"

    def test_explicit_lenient_mode(self) -> None:
        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator

        d = CitationGroundingDiscriminator(mode="lenient")
        assert d.mode == "lenient"

    def test_custom_gateway(self, mock_gateway: MagicMock) -> None:
        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator

        d = CitationGroundingDiscriminator(gateway=mock_gateway)
        assert d._gateway is mock_gateway

    def test_ground_claim_returns_tuple(self, discriminator: MagicMock) -> None:
        # Use discriminator fixture which has a mocked gateway
        verdict, provenances, confidence = discriminator.ground_claim(
            claim_text="The receiving party shall not disclose",
            cited_clause_id="4.3",
            clause_text="The receiving party shall not disclose confidential information",
        )
        assert isinstance(verdict, GroundingVerdict)
        assert isinstance(provenances, list)
        assert isinstance(confidence, float)

    def test_ground_claim_zero_length(self, discriminator: MagicMock) -> None:
        verdict, provenances, confidence = discriminator.ground_claim(
            claim_text="",
            cited_clause_id="4.3",
            clause_text="Some clause text",
        )
        assert verdict == GroundingVerdict.UNGROUNDED
        assert provenances == []
        assert confidence == 0.0

    def test_ground_report_empty(
        self, discriminator: MagicMock, sample_document: MagicMock
    ) -> None:
        # Create an empty report
        from datetime import datetime

        from openreview_cli.review.models import DocMeta, ReviewReport, ReviewSummary

        doc_meta = DocMeta(filename="test.pdf", page_count=1, clause_count=0, pii_stripped=False)
        summary = ReviewSummary()
        empty_report = ReviewReport(
            document=doc_meta,
            assessments=[],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )
        result = discriminator.ground_report(empty_report, sample_document)
        assert isinstance(result, CGReport)
        assert result.total_claims == 0
        assert result.grounded_count == 0
        assert result.ungrounded_count == 0
        assert result.uncertain_count == 0
        assert result.verdicts == []

    def test_skip_citation_invalid(
        self, mock_gateway: MagicMock, sample_document: MagicMock
    ) -> None:
        """Claims where QA verdict is disagree are skipped."""
        # Create report with one valid and one disagree'd claim
        from datetime import datetime

        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            QAVerdict,
            ReviewReport,
            ReviewSummary,
        )

        valid = ClauseAssessment(
            clause_id="4.3",
            clause_text="Valid claim",
            playbook_category="confidentiality",
            position=Position.PREFERRED,
            confidence=0.9,
            citation="4.3",
            qa_verdict=QAVerdict.agree,
            extraction_model="test",
            qa_model="test",
        )
        skipped = ClauseAssessment(
            clause_id="7.1",
            clause_text="Skipped claim",
            playbook_category="confidentiality",
            position=Position.PREFERRED,
            confidence=0.9,
            citation="7.1",
            qa_verdict=QAVerdict.disagree,
            extraction_model="test",
            qa_model="test",
        )
        doc_meta = DocMeta(filename="test.pdf", page_count=1, clause_count=2, pii_stripped=False)
        summary = ReviewSummary()
        report = ReviewReport(
            document=doc_meta,
            assessments=[valid, skipped],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)
        result = d.ground_report(report, sample_document)
        # The mock returns one result for claim 0
        assert result.total_claims == 2
        # At least one claim should go through
        assert len(result.verdicts) > 0

    def test_skip_no_citation(self, mock_gateway: MagicMock, sample_document: MagicMock) -> None:
        """Assessments with empty citation are skipped (no tautology grounding)."""
        from datetime import datetime

        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            QAVerdict,
            ReviewReport,
            ReviewSummary,
        )

        no_cite = ClauseAssessment(
            clause_id="clause-0",
            clause_text="NON-DISCLOSURE AGREEMENT",
            playbook_category="no-match",
            position=Position.UNCERTAIN,
            confidence=0.0,
            citation="",  # Empty — no extraction citation to ground
            qa_verdict=QAVerdict.agree,
            extraction_model="test",
            qa_model="test",
        )
        doc_meta = DocMeta(filename="test.pdf", page_count=1, clause_count=1, pii_stripped=False)
        summary = ReviewSummary()
        report = ReviewReport(
            document=doc_meta,
            assessments=[no_cite],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)
        result = d.ground_report(report, sample_document)
        assert result.total_claims == 1
        assert len(result.verdicts) == 0, (
            "No-citation assessment should produce zero verdicts (skipped)"
        )
        assert result.grounded_count == 0
        assert result.ungrounded_count == 0
        assert result.uncertain_count == 0

    def test_merge_into_strict_removes_ungrounded(
        self, mock_gateway: MagicMock, sample_document: MagicMock
    ) -> None:
        """In strict mode, merge_into removes ungrounded claims."""
        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
        from openreview_cli.review.models import QAVerdict

        # Override mock to return ungrounded for first claim
        mock_gateway.chat.return_value = '[{"claim_index": 0, "verdict": "ungrounded", "provenances": [], "confidence": 0.2, "reason": "Not supported"}]'

        from datetime import datetime

        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            ReviewReport,
            ReviewSummary,
        )

        assessment = ClauseAssessment(
            clause_id="4.3",
            clause_text="Test claim",
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
        report = ReviewReport(
            document=doc_meta,
            assessments=[assessment],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)
        cg_report = d.ground_report(report, sample_document)
        result = cg_report.merge_into(report)
        # In strict mode, ungrounded claim should be removed
        assert len(result.assessments) == 0

    def test_merge_into_lenient_retains_all(
        self, mock_gateway: MagicMock, sample_document: MagicMock
    ) -> None:
        """In lenient mode, all claims are retained."""
        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
        from openreview_cli.review.models import QAVerdict

        mock_gateway.chat.return_value = '[{"claim_index": 0, "verdict": "ungrounded", "provenances": [], "confidence": 0.2, "reason": "Not supported"}]'

        from datetime import datetime

        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            ReviewReport,
            ReviewSummary,
        )

        assessment = ClauseAssessment(
            clause_id="4.3",
            clause_text="Test claim",
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
        report = ReviewReport(
            document=doc_meta,
            assessments=[assessment],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        d = CitationGroundingDiscriminator(mode="lenient", gateway=mock_gateway)
        cg_report = d.ground_report(report, sample_document)
        result = cg_report.merge_into(report)
        # In lenient mode, all claims retained
        assert len(result.assessments) == 1
        assert result.assessments[0].grounding_verdict == GroundingVerdict.UNGROUNDED

    def test_empty_claims_no_error(
        self, discriminator: MagicMock, sample_document: MagicMock
    ) -> None:
        """Empty claims list returns empty CGReport with no error."""
        from datetime import datetime

        from openreview_cli.review.models import DocMeta, ReviewReport, ReviewSummary

        doc_meta = DocMeta(filename="test.pdf", page_count=1, clause_count=0, pii_stripped=False)
        summary = ReviewSummary()
        empty_report = ReviewReport(
            document=doc_meta,
            assessments=[],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )
        result = discriminator.ground_report(empty_report, sample_document)
        assert result.total_claims == 0
        assert len(result.verdicts) == 0

    def test_claim_index_linkage(self, mock_gateway: MagicMock, sample_document: MagicMock) -> None:
        """GroundingResult.claim_index maps to ClauseAssessment position."""
        from datetime import datetime

        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            QAVerdict,
            ReviewReport,
            ReviewSummary,
        )

        assessments = [
            ClauseAssessment(
                clause_id="4.3",
                clause_text=f"Claim {i}",
                playbook_category="confidentiality",
                position=Position.PREFERRED,
                confidence=0.9,
                citation="4.3",
                qa_verdict=QAVerdict.agree,
                extraction_model="test",
                qa_model="test",
            )
            for i in range(3)
        ]
        doc_meta = DocMeta(filename="test.pdf", page_count=1, clause_count=3, pii_stripped=False)
        summary = ReviewSummary()
        report = ReviewReport(
            document=doc_meta,
            assessments=assessments,
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)
        cg_report = d.ground_report(report, sample_document)
        for v in cg_report.verdicts:
            assert 0 <= v.claim_index < 3

    def test_gateway_failure_graceful(
        self, mock_gateway: MagicMock, sample_document: MagicMock
    ) -> None:
        """Gateway failure logs warning and marks claims uncertain."""
        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
        from openreview_cli.review.models import QAVerdict

        mock_gateway.chat.side_effect = RuntimeError("Gateway unavailable")

        from datetime import datetime

        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            ReviewReport,
            ReviewSummary,
        )

        assessment = ClauseAssessment(
            clause_id="4.3",
            clause_text="Test claim",
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
        report = ReviewReport(
            document=doc_meta,
            assessments=[assessment],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)
        cg_report = d.ground_report(report, sample_document)
        assert len(cg_report.verdicts) >= 1
        # At least one claim should be uncertain due to gateway failure
        assert cg_report.verdicts[0].verdict == GroundingVerdict.UNCERTAIN

    def test_reason_populated_for_ungrounded(
        self, mock_gateway: MagicMock, sample_document: MagicMock
    ) -> None:
        """Reason field should be populated for ungrounded verdicts."""
        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
        from openreview_cli.review.models import QAVerdict

        mock_gateway.chat.return_value = '[{"claim_index": 0, "verdict": "ungrounded", "provenances": [], "confidence": 0.1, "reason": "Claim not found in clause"}]'

        from datetime import datetime

        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            ReviewReport,
            ReviewSummary,
        )

        assessment = ClauseAssessment(
            clause_id="4.3",
            clause_text="Test claim",
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
        report = ReviewReport(
            document=doc_meta,
            assessments=[assessment],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)
        cg_report = d.ground_report(report, sample_document)
        if cg_report.verdicts:
            v = cg_report.verdicts[0]
            if v.verdict == GroundingVerdict.UNGROUNDED:
                assert v.reason is not None

    # ── Clause-threading tests (F1) ────────────────────────────────────────────

    def test_get_clauses_for_batch_returns_clause_text(
        self, mock_gateway: MagicMock, sample_document: MagicMock
    ) -> None:
        """_get_clauses_for_batch returns matching Clause objects with text."""
        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
        from openreview_cli.parsing.models import Clause

        source_clauses = [
            Clause(
                id="4.1",
                title=None,
                text="Receiving party shall not disclose confidential information.",
                level=1,
                parent_id=None,
                source_page=1,
                source_paragraph=None,
                source_span=None,
            ),
            Clause(
                id="4.3",
                title=None,
                text="Confidential Information excludes publicly known information.",
                level=1,
                parent_id=None,
                source_page=1,
                source_paragraph=None,
                source_span=None,
            ),
            Clause(
                id="7.1",
                title=None,
                text="Termination does not relieve obligations.",
                level=1,
                parent_id=None,
                source_page=2,
                source_paragraph=None,
                source_span=None,
            ),
        ]

        batch = [
            (0, "Claim 0: receiving party shall not disclose", "4.3"),
            (1, "Claim 1: termination obligations", "7.1"),
        ]

        d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)
        result = d._get_clauses_for_batch(batch, sample_document, source_clauses)

        assert len(result) == 2
        ids = {c.id for c in result}
        assert "4.3" in ids
        assert "7.1" in ids
        # Verify clause text is present
        for clause in result:
            if clause.id == "4.3":
                assert "Confidential Information excludes" in clause.text
            elif clause.id == "7.1":
                assert "Termination does not relieve" in clause.text

    def test_get_clauses_for_batch_no_clauses_fallback(
        self, discriminator: MagicMock, sample_document: MagicMock
    ) -> None:
        """_get_clauses_for_batch returns [] when source_clauses is None."""
        batch = [(0, "Claim text", "4.3")]
        result = discriminator._get_clauses_for_batch(batch, sample_document)
        assert result == []

    def test_ground_report_with_clause_text(
        self, mock_gateway: MagicMock, sample_document: MagicMock
    ) -> None:
        """ground_report with source_clauses passes clause text to prompt builder."""
        from datetime import datetime

        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
        from openreview_cli.parsing.models import Clause
        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            QAVerdict,
            ReviewReport,
            ReviewSummary,
        )

        clause_text = "The receiving party shall protect Confidential Information."
        source_clauses = [
            Clause(
                id="4.3",
                title=None,
                text=clause_text,
                level=1,
                parent_id=None,
                source_page=1,
                source_paragraph=None,
                source_span=None,
            ),
        ]

        assessment = ClauseAssessment(
            clause_id="4.3",
            clause_text="The receiving party shall protect",
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
        report = ReviewReport(
            document=doc_meta,
            assessments=[assessment],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)
        d.ground_report(report, sample_document, source_clauses)

        # Verify the gateway was called with a message containing clause text
        # (The mock just returns a canned response — we check that the call happened
        #  and that the message actually includes the source clause text)
        call_args = mock_gateway.chat.call_args
        assert call_args is not None
        messages = call_args[0][1] if len(call_args[0]) > 1 else call_args[0][0]
        # messages is a list of dicts; find the user message content
        user_content = next(
            (
                m["content"]
                for m in (messages if isinstance(messages, list) else [messages])
                if m.get("role") == "user"
            ),
            "",
        )
        assert clause_text in user_content, "Clause text should appear in grounding prompt"

    def test_ground_report_uses_citation_not_clause_text(
        self, mock_gateway: MagicMock, sample_document: MagicMock
    ) -> None:
        """ground_report must use assessment.citation as the claim text and
        assessment.clause_id as the cited clause ID, NOT clause_text / citation
        (the old swapped-field bug)."""
        from datetime import datetime

        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
        from openreview_cli.parsing.models import Clause
        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            QAVerdict,
            ReviewReport,
            ReviewSummary,
        )

        # Create source clause
        source_clauses = [
            Clause(
                id="clause-1",
                title=None,
                text="The receiving party shall protect Confidential Information.",
                level=1,
                parent_id=None,
                source_page=1,
                source_paragraph=None,
                source_span=None,
            ),
        ]

        # Assessment where citation (a short quote) is DIFFERENT from clause_text
        # This is the scenario the old bug mishandled:
        assessment = ClauseAssessment(
            clause_id="clause-1",
            clause_text="The receiving party shall protect Confidential Information.",
            playbook_category="confidentiality",
            position=Position.PREFERRED,
            confidence=0.9,
            citation="the specific short quote from the clause",  # ← claim text should be THIS
            qa_verdict=QAVerdict.agree,
            extraction_model="test",
            qa_model="test",
        )
        doc_meta = DocMeta(filename="test.pdf", page_count=1, clause_count=1, pii_stripped=False)
        summary = ReviewSummary()
        report = ReviewReport(
            document=doc_meta,
            assessments=[assessment],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        d = CitationGroundingDiscriminator(mode="lenient", gateway=mock_gateway)
        d.ground_report(report, sample_document, source_clauses)

        # Verify the gateway was called with a message containing the CITATION
        # as the claim text, NOT the full clause_text.
        call_args = mock_gateway.chat.call_args
        assert call_args is not None
        messages = call_args[0][1] if len(call_args[0]) > 1 else call_args[0][0]
        user_content = next(
            (
                m["content"]
                for m in (messages if isinstance(messages, list) else [messages])
                if m.get("role") == "user"
            ),
            "",
        )
        assert "the specific short quote from the clause" in user_content, (
            "Claim text in grounding prompt must be the CITATION, not the full clause_text"
        )

    # ── Audit log tests (T014) ─────────────────────────────────────────────────
    # These tests verify the GroundingAuditLog integration with the discriminator

    def test_audit_log_completeness(
        self, mock_gateway: MagicMock, sample_document: MagicMock, tmp_path: Path
    ) -> None:
        """After grounding 10 claims, audit log contains exactly 10 entries."""
        import json
        from datetime import datetime

        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            QAVerdict,
            ReviewReport,
            ReviewSummary,
        )

        responses = [
            {
                "claim_index": i,
                "verdict": "grounded",
                "provenances": [{"clause_id": "4.3", "paragraph_index": i, "confidence": 0.95}],
                "confidence": 0.95,
                "reason": None,
            }
            for i in range(10)
        ]
        mock_gateway.chat.return_value = json.dumps(responses)

        assessments = [
            ClauseAssessment(
                clause_id="4.3",
                clause_text=f"Claim {i}: test",
                playbook_category="confidentiality",
                position=Position.PREFERRED,
                confidence=0.9,
                citation="4.3",
                qa_verdict=QAVerdict.agree,
                extraction_model="test",
                qa_model="test",
            )
            for i in range(10)
        ]
        doc_meta = DocMeta(filename="test.pdf", page_count=1, clause_count=10, pii_stripped=False)
        summary = ReviewSummary()
        report = ReviewReport(
            document=doc_meta,
            assessments=assessments,
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        d = CitationGroundingDiscriminator(
            mode="strict",
            gateway=mock_gateway,
            output_dir=str(tmp_path),
        )
        d.ground_report(report, sample_document)

        audit_path = tmp_path / "grounding-audit.jsonl"
        assert audit_path.exists()
        lines = [line for line in audit_path.read_text().strip().split("\n") if line]
        assert len(lines) == 10

    def test_audit_log_content(
        self, mock_gateway: MagicMock, sample_document: MagicMock, tmp_path: Path
    ) -> None:
        """Each audit entry has valid claim_hash, verdict, confidence, timestamp."""
        import json
        from datetime import datetime

        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            QAVerdict,
            ReviewReport,
            ReviewSummary,
        )

        mock_gateway.chat.return_value = json.dumps(
            [
                {
                    "claim_index": 0,
                    "verdict": "grounded",
                    "provenances": [{"clause_id": "4.3", "paragraph_index": 0, "confidence": 0.95}],
                    "confidence": 0.95,
                    "reason": None,
                }
            ]
        )

        assessment = ClauseAssessment(
            clause_id="4.3",
            clause_text="The receiving party shall not disclose",
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
        report = ReviewReport(
            document=doc_meta,
            assessments=[assessment],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        d = CitationGroundingDiscriminator(
            mode="strict",
            gateway=mock_gateway,
            output_dir=str(tmp_path),
        )
        d.ground_report(report, sample_document)

        audit_path = tmp_path / "grounding-audit.jsonl"
        lines = [line for line in audit_path.read_text().strip().split("\n") if line]
        assert len(lines) >= 1
        entry = json.loads(lines[0])

        assert isinstance(entry["claim_hash"], str)
        assert len(entry["claim_hash"]) == 64  # SHA-256 hex
        assert entry["verdict"] in ("grounded", "ungrounded", "uncertain")
        assert 0.0 <= float(entry["confidence"]) <= 1.0
        assert "timestamp" in entry

    def test_audit_log_reason(
        self, mock_gateway: MagicMock, sample_document: MagicMock, tmp_path: Path
    ) -> None:
        """Ungrounded/uncertain claims have populated reason; grounded have None."""
        import json
        from datetime import datetime

        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            QAVerdict,
            ReviewReport,
            ReviewSummary,
        )

        mock_gateway.chat.return_value = json.dumps(
            [
                {
                    "claim_index": 0,
                    "verdict": "ungrounded",
                    "provenances": [],
                    "confidence": 0.1,
                    "reason": "Claim not found in clause 4.3",
                }
            ]
        )

        assessment = ClauseAssessment(
            clause_id="4.3",
            clause_text="Fabricated claim",
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
        report = ReviewReport(
            document=doc_meta,
            assessments=[assessment],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        d = CitationGroundingDiscriminator(
            mode="strict",
            gateway=mock_gateway,
            output_dir=str(tmp_path),
        )
        d.ground_report(report, sample_document)

        audit_path = tmp_path / "grounding-audit.jsonl"
        lines = [line for line in audit_path.read_text().strip().split("\n") if line]
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry["verdict"] == "ungrounded"
        assert entry["reason"] is not None
        assert len(entry["reason"]) > 0

    def test_audit_log_integrity(
        self, mock_gateway: MagicMock, sample_document: MagicMock, tmp_path: Path
    ) -> None:
        """Same claim text produces same hash across multiple runs."""
        import json
        from datetime import datetime

        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            QAVerdict,
            ReviewReport,
            ReviewSummary,
        )

        mock_gateway.chat.return_value = json.dumps(
            [
                {
                    "claim_index": 0,
                    "verdict": "grounded",
                    "provenances": [{"clause_id": "4.3", "paragraph_index": 0, "confidence": 0.95}],
                    "confidence": 0.95,
                    "reason": None,
                }
            ]
        )

        # Create a second discriminator with separate tmp_path
        mock_gateway2 = MagicMock()
        mock_gateway2.chat.return_value = mock_gateway.chat.return_value
        import tempfile

        tmp2 = Path(tempfile.mkdtemp())

        assessment = ClauseAssessment(
            clause_id="4.3",
            clause_text="Deterministic hash test",
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
        report = ReviewReport(
            document=doc_meta,
            assessments=[assessment],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        d1 = CitationGroundingDiscriminator(
            mode="strict", gateway=mock_gateway, output_dir=str(tmp_path)
        )
        d1.ground_report(report, sample_document)

        d2 = CitationGroundingDiscriminator(
            mode="strict", gateway=mock_gateway2, output_dir=str(tmp2)
        )
        d2.ground_report(report, sample_document)

        a1 = json.loads((tmp_path / "grounding-audit.jsonl").read_text().strip().split("\n")[0])
        a2 = json.loads((tmp2 / "grounding-audit.jsonl").read_text().strip().split("\n")[0])
        assert a1["claim_hash"] == a2["claim_hash"]

    def test_audit_log_skip(
        self, mock_gateway: MagicMock, sample_document: MagicMock, tmp_path: Path
    ) -> None:
        """Claims skipped due to QA disagree do NOT appear in audit log."""
        import json
        from datetime import datetime

        from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator
        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            QAVerdict,
            ReviewReport,
            ReviewSummary,
        )

        mock_gateway.chat.return_value = json.dumps(
            [
                {
                    "claim_index": 0,
                    "verdict": "grounded",
                    "provenances": [{"clause_id": "4.3", "paragraph_index": 0, "confidence": 0.95}],
                    "confidence": 0.95,
                    "reason": None,
                }
            ]
        )

        valid = ClauseAssessment(
            clause_id="4.3",
            clause_text="Valid claim",
            playbook_category="confidentiality",
            position=Position.PREFERRED,
            confidence=0.9,
            citation="4.3",
            qa_verdict=QAVerdict.agree,
            extraction_model="test",
            qa_model="test",
        )
        skipped = ClauseAssessment(
            clause_id="7.1",
            clause_text="Skipped claim",
            playbook_category="confidentiality",
            position=Position.PREFERRED,
            confidence=0.9,
            citation="7.1",
            qa_verdict=QAVerdict.disagree,
            extraction_model="test",
            qa_model="test",
        )
        doc_meta = DocMeta(filename="test.pdf", page_count=1, clause_count=2, pii_stripped=False)
        summary = ReviewSummary()
        report = ReviewReport(
            document=doc_meta,
            assessments=[valid, skipped],
            summary=summary,
            playbook_id="test",
            generated_at=datetime.now(),
        )

        d = CitationGroundingDiscriminator(
            mode="strict",
            gateway=mock_gateway,
            output_dir=str(tmp_path),
        )
        d.ground_report(report, sample_document)

        audit_path = tmp_path / "grounding-audit.jsonl"
        lines = [line for line in audit_path.read_text().strip().split("\n") if line]
        # Only the valid claim should have an entry
        assert len(lines) == 1


def test_model_override_passed_to_gateway(
    mock_gateway: MagicMock, sample_document: MagicMock
) -> None:
    """Regression: CitationGroundingDiscriminator(model=...) must override the
    config default and reach Gateway.chat as the `model` kwarg. Without this,
    run_grounding(model=...) / the CLI --model flag silently did nothing and
    the config slot's primary was always used."""
    d = CitationGroundingDiscriminator(
        mode="lenient",
        gateway=mock_gateway,
        model="openrouter/deepseek/deepseek-r1",
    )
    d.ground_claim(
        claim_text="The term is twelve months.",
        cited_clause_id="clause-2",
        clause_text="Clause 2. Term. Twelve months.",
    )
    assert mock_gateway.chat.called
    _, kwargs = mock_gateway.chat.call_args
    assert kwargs.get("model") == "openrouter/deepseek/deepseek-r1"


def test_no_model_override_omits_model_kwarg(mock_gateway: MagicMock) -> None:
    """When no model is given, the discriminator must NOT pass model=None
    (which would clobber the config default). It should leave the model
    resolution to Gateway via the slot config."""
    d = CitationGroundingDiscriminator(mode="lenient", gateway=mock_gateway)
    d.ground_claim(
        claim_text="The term is twelve months.",
        cited_clause_id="clause-2",
        clause_text="Clause 2. Term. Twelve months.",
    )
    assert mock_gateway.chat.called
    _, kwargs = mock_gateway.chat.call_args
    assert "model" not in kwargs


def test_an_unreadable_answer_increments_the_counter(mock_gateway: MagicMock) -> None:
    mock_gateway.chat.return_value = "I cannot help with that."
    d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)

    verdict, _provenances, confidence = d.ground_claim("claim text", "4.3", "clause text")

    assert verdict is GroundingVerdict.UNCERTAIN
    assert confidence == 0.0
    assert d.unreadable_answers == 1


def test_a_readable_answer_leaves_the_counter_at_zero(mock_gateway: MagicMock) -> None:
    """A counter that never increments also "leaves" the count at zero, so make
    the SAME discriminator spend its next call on an unreadable answer: only a
    zero that then moves proves the zero came from a readable reply."""
    d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)

    d.ground_claim("claim text", "4.3", "clause text")

    assert d.unreadable_answers == 0

    mock_gateway.chat.return_value = "I cannot help with that."
    d.ground_claim("claim text", "4.3", "clause text")

    assert d.unreadable_answers == 1


def test_a_gateway_failure_is_not_counted_as_unreadable(mock_gateway: MagicMock) -> None:
    mock_gateway.chat.side_effect = RuntimeError("connection refused")
    d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)

    verdict, _provenances, confidence = d.ground_claim("claim text", "4.3", "clause text")

    assert verdict is GroundingVerdict.UNCERTAIN
    assert confidence == 0.0
    assert d.unreadable_answers == 0


def test_only_the_claims_missing_from_a_partial_batch_are_counted(
    mock_gateway: MagicMock, sample_report: MagicMock, sample_document: MagicMock
) -> None:
    """The reader answered 1 of 3 claims; the other 2 are still unreadable.

    A partially parsable answer used to count zero, so a model that dropped most
    of its verdicts looked like a fully readable run.
    """
    sample_report.assessments = sample_report.assessments[:3]
    mock_gateway.chat.return_value = json.dumps(
        [
            {
                "claim_index": 1,
                "verdict": "grounded",
                "provenances": [],
                "confidence": 0.9,
                "reason": None,
            }
        ]
    )
    d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)

    cg_report = d.ground_report(sample_report, sample_document)

    assert d.unreadable_answers == 2
    assert {v.claim_index: v.verdict for v in cg_report.verdicts} == {
        0: GroundingVerdict.UNCERTAIN,
        1: GroundingVerdict.GROUNDED,
        2: GroundingVerdict.UNCERTAIN,
    }


def test_an_unreadable_batch_counts_every_claim_in_it(
    mock_gateway: MagicMock, sample_report: MagicMock, sample_document: MagicMock
) -> None:
    """The batch path has no early return: it maps missing indices to UNCERTAIN.

    The `sample_report` fixture's 10 assessments all cite `4.3` with a QA verdict
    of agree, so none is filtered out and they form exactly one batch of 10 under
    `_BATCH_SIZE` — the whole batch is unreadable here.
    """
    mock_gateway.chat.return_value = "I cannot help with that."
    d = CitationGroundingDiscriminator(mode="strict", gateway=mock_gateway)

    d.ground_report(sample_report, sample_document)

    # Nothing in the batch parsed, so every claim in it counts as unreadable.
    assert d.unreadable_answers == len(sample_report.assessments)


class TestGroundingPresenceRecorded:
    """Item 1: the batch path records, on every GroundingResult, the share of the
    claim's wording that appears in the clause it cites, and whether that wording is
    absent. Neither value may influence a verdict; these tests pin only the recording.
    """

    _CLAIM = "The receiving party shall not disclose confidential information"
    _CLAUSE = "The receiving party shall not disclose confidential information to any third party"
    _FABRICATED = "Liquidated damages of five million dollars are payable upon breach"

    def _report(self, citation: str, clause_id: str = "4.3") -> ReviewReport:
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
            clause_id=clause_id,
            clause_text="Some clause text",
            playbook_category="confidentiality",
            position=Position.PREFERRED,
            confidence=0.9,
            citation=citation,
            qa_verdict=QAVerdict.agree,
            extraction_model="test",
            qa_model="test",
        )
        return ReviewReport(
            document=DocMeta(filename="test.pdf", page_count=1, clause_count=1, pii_stripped=False),
            assessments=[assessment],
            summary=ReviewSummary(),
            playbook_id="test",
            generated_at=datetime.now(),
        )

    def _source_clauses(self, clause_id: str = "4.3") -> list[Clause]:
        from openreview_cli.parsing.models import Clause

        return [
            Clause(
                id=clause_id,
                title=None,
                text=self._CLAUSE,
                level=1,
                parent_id=None,
                source_page=1,
                source_paragraph=None,
                source_span=None,
            )
        ]

    def _answer(self, verdict: str) -> str:
        return json.dumps(
            [
                {
                    "claim_index": 0,
                    "verdict": verdict,
                    "provenances": [{"clause_id": "4.3", "paragraph_index": 0, "confidence": 0.9}],
                    "confidence": 0.9,
                    "reason": None,
                }
            ]
        )

    def test_a_grounded_claim_carries_a_number_between_zero_and_one(
        self, mock_gateway: MagicMock, sample_document: MagicMock
    ) -> None:
        mock_gateway.chat.return_value = self._answer("grounded")
        d = CitationGroundingDiscriminator(mode="lenient", gateway=mock_gateway)

        cg_report = d.ground_report(
            self._report(self._CLAIM), sample_document, self._source_clauses()
        )

        result = cg_report.verdicts[0]
        assert result.verdict is GroundingVerdict.GROUNDED
        assert result.grounding_presence is not None
        # The claim is verbatim in the clause, so coverage is total.
        assert result.grounding_presence == 1.0
        # The claim is verbatim in the clause, so the hint does not fire.
        assert result.wording_absent is False

    def test_an_ungrounded_claim_also_carries_a_number(
        self, mock_gateway: MagicMock, sample_document: MagicMock
    ) -> None:
        mock_gateway.chat.return_value = self._answer("ungrounded")
        d = CitationGroundingDiscriminator(mode="lenient", gateway=mock_gateway)

        cg_report = d.ground_report(
            self._report(self._FABRICATED), sample_document, self._source_clauses()
        )

        result = cg_report.verdicts[0]
        assert result.verdict is GroundingVerdict.UNGROUNDED
        assert result.grounding_presence is not None
        # None of the claim's wording is in the clause, so coverage is zero.
        assert result.grounding_presence == 0.0
        # The claim's wording is not in the clause: the hint fires, the verdict is untouched.
        assert result.wording_absent is True

    def test_a_claim_whose_clause_text_is_unavailable_carries_none_and_false(
        self, mock_gateway: MagicMock, sample_document: MagicMock
    ) -> None:
        mock_gateway.chat.return_value = self._answer("grounded")
        d = CitationGroundingDiscriminator(mode="lenient", gateway=mock_gateway)

        # The claim cites 9.9, but the only clause text in hand is for 4.3.
        cg_report = d.ground_report(
            self._report(self._CLAIM, clause_id="9.9"),
            sample_document,
            self._source_clauses("4.3"),
        )

        result = cg_report.verdicts[0]
        assert result.grounding_presence is None
        assert result.wording_absent is False

    def test_a_zero_length_claim_carries_none_and_false(
        self, mock_gateway: MagicMock, sample_document: MagicMock
    ) -> None:
        d = CitationGroundingDiscriminator(mode="lenient", gateway=mock_gateway)

        # A whitespace-only citation is truthy (so it is not skipped) but has no claim.
        cg_report = d.ground_report(self._report("   "), sample_document, self._source_clauses())

        result = cg_report.verdicts[0]
        assert result.verdict is GroundingVerdict.UNGROUNDED
        assert result.reason == "Zero-length claim text"
        assert result.grounding_presence is None
        assert result.wording_absent is False
        assert not mock_gateway.chat.called


class TestWordingAbsentHintReachesTheModel:
    """Item 2: a claim whose wording is absent from the clause it cites is named on
    its own line of the prompt, and only that claim. The hint never decides a
    verdict; these tests pin only the text that reaches the gateway.
    """

    _PRESENT = "The receiving party shall not disclose confidential information"
    _ABSENT = "Liquidated damages of five million dollars are payable upon breach"
    _CLAUSE = "The receiving party shall not disclose confidential information to any third party"
    _HINT = (
        "[the claim's wording does not appear in the cited clause; "
        "answer grounded only if the clause still entails it]"
    )

    def _report(self) -> ReviewReport:
        from datetime import datetime

        from openreview_cli.review.models import (
            ClauseAssessment,
            DocMeta,
            Position,
            QAVerdict,
            ReviewReport,
            ReviewSummary,
        )

        def assessment(claim: str) -> ClauseAssessment:
            return ClauseAssessment(
                clause_id="4.3",
                clause_text="Some clause text",
                playbook_category="confidentiality",
                position=Position.PREFERRED,
                confidence=0.9,
                citation=claim,
                qa_verdict=QAVerdict.agree,
                extraction_model="test",
                qa_model="test",
            )

        return ReviewReport(
            document=DocMeta(filename="test.pdf", page_count=1, clause_count=1, pii_stripped=False),
            assessments=[assessment(self._PRESENT), assessment(self._ABSENT)],
            summary=ReviewSummary(),
            playbook_id="test",
            generated_at=datetime.now(),
        )

    def _source_clauses(self) -> list[Clause]:
        from openreview_cli.parsing.models import Clause

        return [
            Clause(
                id="4.3",
                title=None,
                text=self._CLAUSE,
                level=1,
                parent_id=None,
                source_page=1,
                source_paragraph=None,
                source_span=None,
            )
        ]

    def _claim_line(self, content: str, index: int) -> str:
        # Anchored on the opening quote so the template's own numbered list ("1. Is the
        # claim supported…") is never mistaken for a claim line.
        return next(line for line in content.splitlines() if line.startswith(f'{index}. "'))

    def test_only_the_absent_claims_line_carries_the_hint(
        self, mock_gateway: MagicMock, sample_document: MagicMock
    ) -> None:
        mock_gateway.chat.return_value = json.dumps(
            [
                {
                    "claim_index": index,
                    "verdict": "grounded",
                    "provenances": [],
                    "confidence": 0.9,
                    "reason": None,
                }
                for index in (0, 1)
            ]
        )
        d = CitationGroundingDiscriminator(mode="lenient", gateway=mock_gateway)

        d.ground_report(self._report(), sample_document, self._source_clauses())

        messages = mock_gateway.chat.call_args[0][1]
        content = next(m["content"] for m in messages if m["role"] == "user")

        assert self._HINT in self._claim_line(content, 1)
        assert self._HINT not in self._claim_line(content, 0)


class TestGroundClaimAsksTheProductQuestion:
    """The single-finding entry point sends the same hint the batch path sends.

    The hint comes from the product's primitive (``presence.measure``), so a high-coverage
    paraphrase — not a substring of the clause, yet substantially present — must NOT be
    flagged. A naive ``claim_text not in clause_text`` test would flag it. Every expectation
    here is the primitive's own verdict on the two texts the entry point was handed, never a
    threshold written into this file: a hint that used its own threshold, or the two texts the
    other way round, contradicts at least one of these assertions."""

    _HINT = (
        "[the claim's wording does not appear in the cited clause; "
        "answer grounded only if the clause still entails it]"
    )
    _ABSENT = "Liquidated damages of five million dollars are payable upon breach"
    _PARAPHRASE = "The recipient must not disclose confidential information to any third party"
    # Long enough — twenty-one tokens to the paraphrase's eleven — that the operand order
    # decides the paraphrase's hint: the paraphrase covers 0.82 of the clause in its own
    # words, while the clause's own words are only 0.43 covered by the paraphrase.
    _CLAUSE = (
        "The receiving party shall not disclose confidential information to any third party "
        "without the prior written consent of the disclosing party"
    )
    # A finding the primitive calls absent — a third of its words are this clause's — even
    # though more than half of this clause's own words recur in the finding. The two operand
    # orders disagree on this pair, so the hint's presence is what tells them apart.
    _ORDER_CLAUSE = "The Confidential Information term excludes public disclosure"
    _ORDER_FINDING = (
        "The Supplier shall keep all Confidential Information strictly segregated from public "
        "release"
    )

    def _content(self, gateway: MagicMock) -> str:
        content: str = next(
            m["content"] for m in gateway.chat.call_args[0][1] if m["role"] == "user"
        )
        return content

    def test_an_absent_wording_claim_gets_the_hint(self, mock_gateway: MagicMock) -> None:
        CitationGroundingDiscriminator(mode="lenient", gateway=mock_gateway).ground_claim(
            self._ABSENT,
            "4.3",
            self._CLAUSE,
        )

        # The endpoint this fixture stands for, and the hint the primitive asks for.
        assert presence.measure(self._ABSENT, self._CLAUSE)[1] is True
        assert (self._HINT in self._content(mock_gateway)) is presence.measure(
            self._ABSENT, self._CLAUSE
        )[1]

    def test_a_high_coverage_paraphrase_gets_no_hint(self, mock_gateway: MagicMock) -> None:
        CitationGroundingDiscriminator(mode="lenient", gateway=mock_gateway).ground_claim(
            self._PARAPHRASE,
            "4.3",
            self._CLAUSE,
        )

        assert presence.measure(self._PARAPHRASE, self._CLAUSE)[1] is False
        assert (self._HINT in self._content(mock_gateway)) is presence.measure(
            self._PARAPHRASE, self._CLAUSE
        )[1]

    def test_the_hint_follows_the_measure_asked_claim_first(self, mock_gateway: MagicMock) -> None:
        CitationGroundingDiscriminator(mode="lenient", gateway=mock_gateway).ground_claim(
            self._ORDER_FINDING,
            "4.3",
            self._ORDER_CLAUSE,
        )

        claim_first = presence.measure(self._ORDER_FINDING, self._ORDER_CLAUSE)[1]
        clause_first = presence.measure(self._ORDER_CLAUSE, self._ORDER_FINDING)[1]
        # The premise: this pair's answer flips with the operands, so a hint that does not
        # follow ``measure(claim, clause)`` surfaces here as the wrong presence.
        assert claim_first is not clause_first
        assert (self._HINT in self._content(mock_gateway)) is claim_first
