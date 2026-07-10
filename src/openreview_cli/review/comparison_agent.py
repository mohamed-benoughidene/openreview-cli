"""ComparisonAgent — bilateral PAKTON architecture.

Aligns clause assessments from two independent PAKTON runs (Party A and
Party B), classifies divergences using a rule-based 3-category taxonomy
(equivalent / addition / contradiction), and produces a structured
ComparisonReport.

This implements the L4M-style adversarial dual-agent + verifier pattern,
adapted for contracts: two independent review agents produce assessments,
then the ComparisonAgent (verifier) detects and classifies differences.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openreview_cli.review.models import ClauseAssessment

logger = logging.getLogger(__name__)


class DivergenceType(StrEnum):
    """Three-category divergence taxonomy for bilateral comparison."""

    EQUIVALENT = "equivalent"
    ADDITION = "addition"
    CONTRADICTION = "contradiction"
    NO_DIVERGENCE = "no_divergence"


@dataclass
class AlignmentPair:
    """A single aligned or unaligned clause pair across two documents."""

    party_a_idx: int | None
    party_b_idx: int | None
    heading: str
    alignment_quality: float  # 0.0-1.0 (1.0 = exact heading match)


@dataclass
class AlignmentTable:
    """Clause alignment output before full comparison."""

    pairs: list[AlignmentPair]
    unmatched_a: list[int]
    unmatched_b: list[int]
    total_a: int
    total_b: int

    @property
    def alignment_rate(self) -> float:
        """Fraction of clauses successfully aligned."""
        total = self.total_a + self.total_b
        if total == 0:
            return 1.0
        return (len(self.pairs) * 2) / total


@dataclass
class PairedAssessment:
    """Outcome of comparing one aligned clause pair across both documents."""

    pair_id: str
    clause_heading: str
    party_a_assessment: ClauseAssessment | None
    party_b_assessment: ClauseAssessment | None
    divergence: DivergenceType
    confidence: float
    alignment_quality: float
    color: str  # green, amber, red
    citations: list[str] = field(default_factory=list)
    rationale: str = ""
    is_amber: bool = False


@dataclass
class ComparisonSummary:
    """Aggregate statistics for a comparison run."""

    total_pairs: int = 0
    divergences: int = 0
    divergences_by_type: dict[str, int] = field(default_factory=dict)
    unmatched_a: int = 0
    unmatched_b: int = 0
    agreement_rate: float = 1.0
    green_count: int = 0
    amber_count: int = 0
    red_count: int = 0
    overall_color: str = "green"
    avg_alignment_quality: float = 1.0


@dataclass
class ComparisonReport:
    """Top-level output of a bilateral comparison run."""

    experimental: bool = True
    disclaimer: str = (
        "EXPERIMENTAL — comparison accuracy has known limitations. "
        "Do not rely on this tool for legal advice."
    )
    assessments: list[PairedAssessment] = field(default_factory=list)
    alignment: AlignmentTable | None = None
    summary: ComparisonSummary | None = None
    schema_version: str = "1.0.0"


class ComparisonAgent:
    """Compares clause assessments from two independent PAKTON runs.

    Steps:
    1. Align clauses by heading (exact → fuzzy → position fallback)
    2. For each aligned pair, classify divergence (equivalent/addition/contradiction)
    3. Compute confidence scores and colors
    4. Return structured ComparisonReport
    """

    def __init__(self, confidence_threshold: float = 0.7) -> None:
        self.confidence_threshold = confidence_threshold

    # ── Public API ──

    def compare(
        self,
        party_a_assessments: list[ClauseAssessment],
        party_b_assessments: list[ClauseAssessment],
    ) -> ComparisonReport:
        """Run full comparison pipeline.

        Parameters
        ----------
        party_a_assessments:
            Clause assessments from Party A's PAKTON run.
        party_b_assessments:
            Clause assessments from Party B's PAKTON run.

        Returns
        -------
        ComparisonReport
            Structured report with alignment, assessments, and summary.
        """
        alignment = self._align_clauses(party_a_assessments, party_b_assessments)
        paired = self._assess_pairs(alignment, party_a_assessments, party_b_assessments)
        summary = self._compute_summary(paired, alignment)
        return ComparisonReport(
            assessments=paired,
            alignment=alignment,
            summary=summary,
        )

    # ── Alignment ──

    def _align_clauses(
        self,
        a: list[ClauseAssessment],
        b: list[ClauseAssessment],
    ) -> AlignmentTable:
        """Align clauses by heading: exact match → fuzzy → position fallback."""
        pairs: list[AlignmentPair] = []
        matched_b: set[int] = set()

        # Phase 1: exact heading match
        for i, ca in enumerate(a):
            heading = self._heading_from_clause(ca)
            for j, cb in enumerate(b):
                if j in matched_b:
                    continue
                if heading == self._heading_from_clause(cb):
                    pairs.append(
                        AlignmentPair(
                            party_a_idx=i,
                            party_b_idx=j,
                            heading=heading,
                            alignment_quality=1.0,
                        )
                    )
                    matched_b.add(j)
                    break
            else:
                # Phase 2: fuzzy match (normalized heading)
                for j, cb in enumerate(b):
                    if j in matched_b:
                        continue
                    cb_heading = self._heading_from_clause(cb)
                    quality = self._fuzzy_match(heading, cb_heading)
                    if quality >= 0.7:
                        pairs.append(
                            AlignmentPair(
                                party_a_idx=i,
                                party_b_idx=j,
                                heading=heading,
                                alignment_quality=quality,
                            )
                        )
                        matched_b.add(j)
                        break
                else:
                    pairs.append(
                        AlignmentPair(
                            party_a_idx=i,
                            party_b_idx=None,
                            heading=heading,
                            alignment_quality=0.0,
                        )
                    )

        # Remaining unmatched B clauses
        for j, cb in enumerate(b):
            if j not in matched_b:
                pairs.append(
                    AlignmentPair(
                        party_a_idx=None,
                        party_b_idx=j,
                        heading=self._heading_from_clause(cb),
                        alignment_quality=0.0,
                    )
                )

        unmatched_a = [i for i in range(len(a)) if not any(p.party_a_idx == i for p in pairs)]
        unmatched_b_list = [j for j in range(len(b)) if j not in matched_b]

        return AlignmentTable(
            pairs=pairs,
            unmatched_a=unmatched_a,
            unmatched_b=unmatched_b_list,
            total_a=len(a),
            total_b=len(b),
        )

    # ── Per-pair assessment ──

    def _assess_pairs(
        self,
        alignment: AlignmentTable,
        a: list[ClauseAssessment],
        b: list[ClauseAssessment],
    ) -> list[PairedAssessment]:
        """Classify divergence for each aligned pair."""
        assessments: list[PairedAssessment] = []

        for idx, pair in enumerate(alignment.pairs):
            ca = a[pair.party_a_idx] if pair.party_a_idx is not None else None
            cb = b[pair.party_b_idx] if pair.party_b_idx is not None else None

            divergence, confidence, citations, rationale = self._classify(ca, cb)
            color = self._compute_color(divergence, confidence, pair.alignment_quality)
            is_amber = color == "amber"

            pair_id = f"pair_{idx}"
            assessments.append(
                PairedAssessment(
                    pair_id=pair_id,
                    clause_heading=pair.heading,
                    party_a_assessment=ca,
                    party_b_assessment=cb,
                    divergence=divergence,
                    confidence=confidence,
                    alignment_quality=pair.alignment_quality,
                    color=color,
                    citations=citations,
                    rationale=rationale,
                    is_amber=is_amber,
                )
            )

        return assessments

    # ── Divergence classification (rule-based) ──

    @staticmethod
    def _classify(
        ca: ClauseAssessment | None,
        cb: ClauseAssessment | None,
    ) -> tuple[DivergenceType, float, list[str], str]:
        """Classify divergence between two clause assessments.

        Rule-based using existing position fields — no LLM call.
        """
        if ca is None and cb is None:
            return DivergenceType.EQUIVALENT, 1.0, [], "both sides absent"

        if ca is None:
            return (
                DivergenceType.ADDITION,
                0.6,
                [],
                "clause present only in Party B",
            )
        if cb is None:
            return (
                DivergenceType.ADDITION,
                0.6,
                [],
                "clause present only in Party A",
            )

        citations: list[str] = []
        rationale_parts: list[str] = []

        if ca.position == cb.position:
            divergence = DivergenceType.EQUIVALENT
            confidence = 0.95
            rationale_parts.append(f"both parties share {ca.position.value} position")
        else:
            divergence = DivergenceType.CONTRADICTION
            if ca.position.value == "uncertain" or cb.position.value == "uncertain":
                confidence = 0.5
            else:
                confidence = 0.8
            rationale_parts.append(f"Party A: {ca.position.value}, Party B: {cb.position.value}")
            citations.append(f"A ({ca.position.value}): {ca.citation}")
            citations.append(f"B ({cb.position.value}): {cb.citation}")

        return divergence, confidence, citations, "; ".join(rationale_parts)

    # ── Color computation ──

    def _compute_color(
        self,
        divergence: DivergenceType,
        confidence: float,
        alignment_quality: float,
    ) -> str:
        """Compute three-color status for a paired assessment."""
        if divergence == DivergenceType.EQUIVALENT:
            return "green"

        if alignment_quality < 0.3:
            return "amber"

        if confidence < self.confidence_threshold:
            return "amber"

        if divergence == DivergenceType.CONTRADICTION:
            return "red"

        # ADDITION with high confidence and good alignment
        return "amber"

    # ── Summary ──

    @staticmethod
    def _compute_summary(
        assessments: list[PairedAssessment],
        alignment: AlignmentTable,
    ) -> ComparisonSummary:
        """Aggregate per-pair results into summary statistics."""
        total = len(assessments)
        if total == 0:
            return ComparisonSummary()

        divergences = sum(1 for a in assessments if a.divergence != DivergenceType.EQUIVALENT)
        divergences_by_type: dict[str, int] = {}
        for a in assessments:
            divergences_by_type[a.divergence.value] = (
                divergences_by_type.get(a.divergence.value, 0) + 1
            )

        green = sum(1 for a in assessments if a.color == "green")
        amber = sum(1 for a in assessments if a.color == "amber")
        red = sum(1 for a in assessments if a.color == "red")

        # overall_color: worst-clause-wins: red > amber > green
        overall_color = "green"
        if red > 0:
            overall_color = "red"
        elif amber > 0:
            overall_color = "amber"

        avg_alignment = sum(a.alignment_quality for a in assessments) / total if total > 0 else 1.0

        return ComparisonSummary(
            total_pairs=total,
            divergences=divergences,
            divergences_by_type=divergences_by_type,
            unmatched_a=len(alignment.unmatched_a),
            unmatched_b=len(alignment.unmatched_b),
            agreement_rate=green / total if total > 0 else 1.0,
            green_count=green,
            amber_count=amber,
            red_count=red,
            overall_color=overall_color,
            avg_alignment_quality=avg_alignment,
        )

    # ── Helpers ──

    @staticmethod
    def _heading_from_clause(ca: ClauseAssessment) -> str:
        """Extract heading from a clause assessment.

        Uses playbook_category as the heading identifier.
        """
        return ca.playbook_category

    @staticmethod
    def _fuzzy_match(heading_a: str, heading_b: str) -> float:
        """Simple fuzzy heading match on normalized text.

        Returns 1.0 for exact match after normalization,
        0.7 for partial overlap, 0.0 otherwise.
        """
        norm_a = heading_a.lower().replace("-", " ").replace("_", " ").strip()
        norm_b = heading_b.lower().replace("-", " ").replace("_", " ").strip()

        if norm_a == norm_b:
            return 1.0

        a_words = set(norm_a.split())
        b_words = set(norm_b.split())

        if not a_words or not b_words:
            return 0.0

        intersection = a_words & b_words
        # Jaccard-like overlap
        overlap = len(intersection) / min(len(a_words), len(b_words))
        return 0.7 if overlap >= 0.5 else 0.0
