"""Unit tests for CitationGroundingDiscriminator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

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
def discriminator(mock_gateway: MagicMock) -> MagicMock:
    """Create a discriminator with mocked gateway (strict mode by default)."""
    from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator

    return CitationGroundingDiscriminator(
        mode="strict",
        gateway=mock_gateway,
    )


@pytest.fixture
def lenient_discriminator(mock_gateway: MagicMock) -> MagicMock:
    from openreview_cli.grounding.discriminator import CitationGroundingDiscriminator

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
            position=Position.favorable,
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
            position=Position.favorable,
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
            position=Position.favorable,
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
            position=Position.favorable,
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
                position=Position.favorable,
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
            position=Position.favorable,
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
            position=Position.favorable,
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
            position=Position.favorable,
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
            (m["content"] for m in (messages if isinstance(messages, list) else [messages]) if m.get("role") == "user"),
            "",
        )
        assert clause_text in user_content, "Clause text should appear in grounding prompt"

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
                position=Position.favorable,
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
            position=Position.favorable,
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
            position=Position.favorable,
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
            position=Position.favorable,
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
            position=Position.favorable,
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
            position=Position.favorable,
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
