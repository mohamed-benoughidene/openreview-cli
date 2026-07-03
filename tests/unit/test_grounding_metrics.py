"""Unit tests for CG metrics computation (T018)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from openreview_cli.grounding.metrics import compute_cg_metrics
from openreview_cli.grounding.models import (
    CGMetrics,
    CitationProvenance,
    GroundingResult,
    GroundingVerdict,
)
from openreview_cli.parsing.models import Clause


def _make_verdict(
    claim_index: int,
    verdict: GroundingVerdict,
    clause_id: str = "1.0",
    paragraph_index: int = 0,
    confidence: float = 0.9,
) -> GroundingResult:
    return GroundingResult(
        claim_index=claim_index,
        verdict=verdict,
        provenances=[
            CitationProvenance(
                clause_id=clause_id, paragraph_index=paragraph_index, confidence=confidence
            )
        ],
    )


@pytest.fixture
def source_doc() -> MagicMock:
    doc = MagicMock()
    doc.source_path = Path("/dev/null/test.pdf")
    doc.format = "pdf"
    doc.page_count = 5
    doc.clause_count = 3
    doc.parse_duration_seconds = 0.5
    doc.warnings = []
    return doc


@pytest.fixture
def source_clauses() -> list[Clause]:
    """Three real Clause objects with multi-paragraph text for CL tests."""
    from openreview_cli.parsing.models import Clause

    return [
        Clause(
            id="1.0",
            title="Definition",
            text="Confidential Information means all information disclosed.",
            level=1,
            parent_id=None,
            source_page=1,
            source_paragraph=None,
            source_span=None,
        ),
        Clause(
            id="2.0",
            title="Obligations",
            text="Receiving party shall protect Confidential Information.\n\nRecipient may disclose to employees.\n\nTerm survives termination.",
            level=1,
            parent_id=None,
            source_page=1,
            source_paragraph=None,
            source_span=None,
        ),
        Clause(
            id="3.0",
            title="Exclusions",
            text="Information publicly known. Information independently developed.",
            level=1,
            parent_id=None,
            source_page=2,
            source_paragraph=None,
            source_span=None,
        ),
    ]


class TestCGMetrics:
    """Structural CG metrics: CP, CR, CL."""

    def test_cp_all_valid(self, source_doc: MagicMock) -> None:
        """100% CP when all cited clause_ids exist (fallback: no source_clauses)."""
        verdicts = [
            _make_verdict(0, GroundingVerdict.GROUNDED, clause_id="1.0"),
            _make_verdict(1, GroundingVerdict.GROUNDED, clause_id="2.0"),
        ]
        metrics = compute_cg_metrics(verdicts, source_doc)
        assert metrics.citation_precision == 1.0

    def test_cp_some_invalid(self, source_doc: MagicMock) -> None:
        """CP < 1.0 when clause_id is empty (fallback: no source_clauses)."""
        verdicts = [
            _make_verdict(0, GroundingVerdict.GROUNDED, clause_id="1.0"),
            GroundingResult(
                claim_index=1,
                verdict=GroundingVerdict.GROUNDED,
                provenances=[],
            ),
        ]
        metrics = compute_cg_metrics(verdicts, source_doc)
        assert metrics.citation_precision == 0.5

    def test_cp_with_clause_text_aware(
        self, source_doc: MagicMock, source_clauses: list[Clause]
    ) -> None:
        """CP < 1.0 when cited clause_id does NOT exist in source clauses."""
        verdicts = [
            _make_verdict(0, GroundingVerdict.GROUNDED, clause_id="1.0"),
            _make_verdict(1, GroundingVerdict.GROUNDED, clause_id="nonexistent"),
        ]
        metrics = compute_cg_metrics(verdicts, source_doc, source_clauses=source_clauses)
        assert metrics.citation_precision == 0.5

    def test_cp_all_exist_in_source(
        self, source_doc: MagicMock, source_clauses: list[Clause]
    ) -> None:
        """CP = 1.0 when all cited clause_ids exist in source."""
        verdicts = [
            _make_verdict(0, GroundingVerdict.GROUNDED, clause_id="1.0"),
            _make_verdict(1, GroundingVerdict.GROUNDED, clause_id="2.0"),
        ]
        metrics = compute_cg_metrics(verdicts, source_doc, source_clauses=source_clauses)
        assert metrics.citation_precision == 1.0

    def test_cp_zero_claims(self, source_doc: MagicMock) -> None:
        """CP is 1.0 when no grounded claims (vacuously precise)."""
        metrics = compute_cg_metrics([], source_doc)
        assert metrics.citation_precision == 1.0

    def test_cr_all_valid(self, source_doc: MagicMock) -> None:
        """100% CR when all claims are grounded (fallback: no source_clauses)."""
        verdicts = [
            _make_verdict(0, GroundingVerdict.GROUNDED),
            _make_verdict(1, GroundingVerdict.GROUNDED),
        ]
        metrics = compute_cg_metrics(verdicts, source_doc)
        assert metrics.citation_relevance == 1.0

    def test_cr_some_invalid(self, source_doc: MagicMock) -> None:
        """CR is still 1.0 in simplified computation (fallback: no source_clauses)."""
        verdicts = [
            _make_verdict(0, GroundingVerdict.GROUNDED),
            GroundingResult(
                claim_index=1,
                verdict=GroundingVerdict.UNGROUNDED,
                provenances=[],
            ),
        ]
        metrics = compute_cg_metrics(verdicts, source_doc)
        # Only grounded claims count, so 1/1 = 1.0
        assert metrics.citation_relevance == 1.0

    def test_cr_zero_claims(self, source_doc: MagicMock) -> None:
        """CR is 1.0 when no grounded claims."""
        metrics = compute_cg_metrics([], source_doc)
        assert metrics.citation_relevance == 1.0

    def test_cr_with_clause_text_match(
        self, source_doc: MagicMock, source_clauses: list[Clause]
    ) -> None:
        """CR = 1.0 when claim text appears in cited clause text."""
        claim_texts = {
            0: "Receiving party shall protect Confidential Information",
            1: "Information publicly known",
        }
        verdicts = [
            GroundingResult(
                claim_index=0,
                verdict=GroundingVerdict.GROUNDED,
                provenances=[
                    CitationProvenance(clause_id="2.0", paragraph_index=0, confidence=0.9)
                ],
            ),
            GroundingResult(
                claim_index=1,
                verdict=GroundingVerdict.GROUNDED,
                provenances=[
                    CitationProvenance(clause_id="3.0", paragraph_index=0, confidence=0.9)
                ],
            ),
        ]
        metrics = compute_cg_metrics(
            verdicts, source_doc, source_clauses=source_clauses, claim_text_by_index=claim_texts
        )
        assert metrics.citation_relevance == 1.0

    def test_cr_with_no_match(self, source_doc: MagicMock, source_clauses: list[Clause]) -> None:
        """CR = 0.0 when claim text is absent from cited clause text."""
        claim_texts = {0: "Completely unrelated made-up statement"}
        verdicts = [
            GroundingResult(
                claim_index=0,
                verdict=GroundingVerdict.GROUNDED,
                provenances=[
                    CitationProvenance(clause_id="1.0", paragraph_index=0, confidence=0.9)
                ],
            ),
        ]
        metrics = compute_cg_metrics(
            verdicts, source_doc, source_clauses=source_clauses, claim_text_by_index=claim_texts
        )
        assert metrics.citation_relevance == 0.0

    def test_cr_empty_claim_text(self, source_doc: MagicMock, source_clauses: list[Clause]) -> None:
        """CR skips empty claim text (not counted relevant)."""
        claim_texts = {0: ""}
        verdicts = [
            GroundingResult(
                claim_index=0,
                verdict=GroundingVerdict.GROUNDED,
                provenances=[
                    CitationProvenance(clause_id="1.0", paragraph_index=0, confidence=0.9)
                ],
            ),
        ]
        metrics = compute_cg_metrics(
            verdicts, source_doc, source_clauses=source_clauses, claim_text_by_index=claim_texts
        )
        assert metrics.citation_relevance == 0.0

    def test_cl_all_valid(self, source_doc: MagicMock) -> None:
        """CL is 1.0 when all paragraph indices >= 0 (fallback: no source_clauses)."""
        verdicts = [
            _make_verdict(0, GroundingVerdict.GROUNDED, paragraph_index=0),
            _make_verdict(1, GroundingVerdict.GROUNDED, paragraph_index=2),
        ]
        metrics = compute_cg_metrics(verdicts, source_doc)
        assert metrics.citation_locality == 1.0

    def test_cl_some_invalid(self, source_doc: MagicMock) -> None:
        """CL < 1.0 when some paragraph indices are negative (fallback: no source_clauses)."""
        verdicts = [
            _make_verdict(0, GroundingVerdict.GROUNDED, paragraph_index=0),
            GroundingResult(
                claim_index=1,
                verdict=GroundingVerdict.GROUNDED,
                provenances=[
                    CitationProvenance(clause_id="1.0", paragraph_index=-1, confidence=0.9)
                ],
            ),
        ]
        metrics = compute_cg_metrics(verdicts, source_doc)
        assert metrics.citation_locality == 0.5

    def test_cl_zero_claims(self, source_doc: MagicMock) -> None:
        """CL is 1.0 when no grounded claims."""
        metrics = compute_cg_metrics([], source_doc)
        assert metrics.citation_locality == 1.0

    def test_cl_with_source_out_of_range(
        self, source_doc: MagicMock, source_clauses: list[Clause]
    ) -> None:
        """CL < 1.0 when paragraph_index exceeds clause paragraph count."""
        # Clause "2.0" has 3 paragraphs (split by \n\n)
        verdicts = [
            _make_verdict(0, GroundingVerdict.GROUNDED, clause_id="2.0", paragraph_index=0),
            GroundingResult(
                claim_index=1,
                verdict=GroundingVerdict.GROUNDED,
                provenances=[
                    CitationProvenance(clause_id="2.0", paragraph_index=5, confidence=0.9)
                ],
            ),
        ]
        metrics = compute_cg_metrics(verdicts, source_doc, source_clauses=source_clauses)
        assert metrics.citation_locality == 0.5

    def test_cl_with_source_in_range(
        self, source_doc: MagicMock, source_clauses: list[Clause]
    ) -> None:
        """CL = 1.0 when all paragraph indices are within clause paragraph count."""
        # Clause "2.0" has 3 paragraphs; indices 0, 1, 2 are valid
        verdicts = [
            _make_verdict(0, GroundingVerdict.GROUNDED, clause_id="2.0", paragraph_index=0),
            _make_verdict(1, GroundingVerdict.GROUNDED, clause_id="2.0", paragraph_index=2),
        ]
        metrics = compute_cg_metrics(verdicts, source_doc, source_clauses=source_clauses)
        assert metrics.citation_locality == 1.0

    def test_all_metrics_together(self, source_doc: MagicMock) -> None:
        """Mixed corpus: CP=1.0, CR=1.0, CL=0.75 (fallback: no source_clauses)."""
        verdicts = [
            _make_verdict(0, GroundingVerdict.GROUNDED, clause_id="1.0", paragraph_index=0),
            _make_verdict(1, GroundingVerdict.GROUNDED, clause_id="2.0", paragraph_index=1),
            _make_verdict(2, GroundingVerdict.GROUNDED, clause_id="3.0", paragraph_index=2),
            GroundingResult(
                claim_index=3,
                verdict=GroundingVerdict.GROUNDED,
                provenances=[
                    CitationProvenance(clause_id="4.0", paragraph_index=-1, confidence=0.5)
                ],
            ),
        ]
        metrics = compute_cg_metrics(verdicts, source_doc)
        assert metrics.citation_precision == 1.0
        assert metrics.citation_relevance == 1.0
        assert metrics.citation_locality == 0.75

    def test_all_metrics_with_clause_text(
        self, source_doc: MagicMock, source_clauses: list[Clause]
    ) -> None:
        """CP/CR/CL with full clause-text awareness."""
        claim_texts = {
            0: "Confidential Information means all",
            1: "Receiving party shall protect",
            2: "Information publicly known",
            3: "Completely made up claim",
        }
        verdicts = [
            GroundingResult(
                claim_index=0,
                verdict=GroundingVerdict.GROUNDED,
                provenances=[
                    CitationProvenance(clause_id="1.0", paragraph_index=0, confidence=0.9)
                ],
            ),
            GroundingResult(
                claim_index=1,
                verdict=GroundingVerdict.GROUNDED,
                provenances=[
                    CitationProvenance(clause_id="2.0", paragraph_index=0, confidence=0.9)
                ],
            ),
            GroundingResult(
                claim_index=2,
                verdict=GroundingVerdict.GROUNDED,
                provenances=[
                    CitationProvenance(clause_id="3.0", paragraph_index=0, confidence=0.9)
                ],
            ),
            GroundingResult(
                claim_index=3,
                verdict=GroundingVerdict.GROUNDED,
                provenances=[
                    CitationProvenance(clause_id="1.0", paragraph_index=0, confidence=0.5)
                ],
            ),
        ]
        metrics = compute_cg_metrics(
            verdicts, source_doc, source_clauses=source_clauses, claim_text_by_index=claim_texts
        )
        # CP: all clause_ids exist in source → 4/4 = 1.0
        assert metrics.citation_precision == 1.0
        # CR: claims 0,1,2 match their clause text; claim 3 does not → 3/4 = 0.75
        assert metrics.citation_relevance == 0.75
        # CL: all paragraph_index=0 valid → 4/4 = 1.0
        assert metrics.citation_locality == 1.0

    def test_metrics_no_grounded_claims(self, source_doc: MagicMock) -> None:
        """No grounded claims: metrics return 1.0 (vacuously valid)."""
        verdicts = [
            GroundingResult(
                claim_index=0,
                verdict=GroundingVerdict.UNGROUNDED,
                provenances=[],
            ),
        ]
        metrics = compute_cg_metrics(verdicts, source_doc)
        assert metrics.citation_precision == 1.0
        assert metrics.citation_relevance == 1.0
        assert metrics.citation_locality == 1.0

    def test_returns_cgmetrics_instance(self, source_doc: MagicMock) -> None:
        """Returns a proper CGMetrics instance."""
        result = compute_cg_metrics([], source_doc)
        assert isinstance(result, CGMetrics)

    def test_values_in_range(self, source_doc: MagicMock) -> None:
        """All metrics return floats in [0.0, 1.0]."""
        verdicts = [
            _make_verdict(0, GroundingVerdict.GROUNDED, paragraph_index=0),
            GroundingResult(
                claim_index=1,
                verdict=GroundingVerdict.GROUNDED,
                provenances=[CitationProvenance(clause_id="", paragraph_index=-1, confidence=0.0)],
            ),
        ]
        metrics = compute_cg_metrics(verdicts, source_doc)
        assert 0.0 <= metrics.citation_precision <= 1.0
        assert 0.0 <= metrics.citation_relevance <= 1.0
        assert 0.0 <= metrics.citation_locality <= 1.0
