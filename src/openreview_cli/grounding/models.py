"""Data models for the Citation Grounding Discriminator."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from openreview_cli.review.models import ReviewReport

logger = logging.getLogger(__name__)


class GroundingVerdict(StrEnum):
    """Verdict for a single claim's citation grounding."""

    GROUNDED = "grounded"
    UNGROUNDED = "ungrounded"
    UNCERTAIN = "uncertain"


@dataclass(slots=True)
class CitationProvenance:
    """A record linking a single claim to a specific location in the source document."""

    clause_id: str
    paragraph_index: int
    confidence: float


@dataclass(slots=True)
class GroundingResult:
    """Per-claim grounding result."""

    claim_index: int
    verdict: GroundingVerdict
    provenances: list[CitationProvenance]
    reason: str | None = None


@dataclass(slots=True)
class CGMetrics:
    """Structural citation grounding metrics — computed deterministically."""

    citation_precision: float
    citation_relevance: float
    citation_locality: float

    def __post_init__(self) -> None:
        for field in (
            "citation_precision",
            "citation_relevance",
            "citation_locality",
        ):
            val = getattr(self, field)
            if not 0.0 <= val <= 1.0:
                raise ValueError(f"{field} must be in range 0.0-1.0, got {val}")


@dataclass
class CGReport:
    """Aggregate output of a discriminator run."""

    verdicts: list[GroundingResult]
    mode: Literal["strict", "lenient"]
    metrics: CGMetrics
    total_claims: int
    grounded_count: int
    ungrounded_count: int
    uncertain_count: int

    def merge_into(self, report: ReviewReport) -> ReviewReport:
        """Merge grounding results into a ReviewReport.

        For each GroundingResult, sets the corresponding ClauseAssessment's
        grounding_verdict, grounding_provenances, and grounding_confidence fields.
        In strict mode, removes UNGROUNDED and UNCERTAIN claims from the report.
        """
        if not report.assessments or not self.verdicts:
            return report

        # Build a mapping from index to ClauseAssessment
        indices_to_keep: list[int] = []
        for result in self.verdicts:
            idx = result.claim_index
            if idx < 0 or idx >= len(report.assessments):
                logger.warning("claim_index %d out of range, skipping", idx)
                continue

            assessment = report.assessments[idx]
            confidence = (
                max(p.confidence for p in result.provenances) if result.provenances else 0.0
            )
            assessment.grounding_verdict = result.verdict
            assessment.grounding_provenances = result.provenances
            assessment.grounding_confidence = confidence

            if self.mode == "strict" and result.verdict in (
                GroundingVerdict.UNGROUNDED,
                GroundingVerdict.UNCERTAIN,
            ):
                logger.warning(
                    "Claim #%d '%s' excluded: %s in clause %s",
                    idx,
                    assessment.clause_text[:40],
                    result.reason or result.verdict.value,
                    assessment.citation,
                )
                # Mark for removal by setting a sentinel
                indices_to_keep.append(idx)
            elif self.mode == "lenient" or result.verdict == GroundingVerdict.GROUNDED:
                indices_to_keep.append(idx)

        if self.mode == "strict":
            # Keep only grounded claims (not in the removal set)
            keep_set = {
                r.claim_index for r in self.verdicts if r.verdict == GroundingVerdict.GROUNDED
            }
            report.assessments = [a for i, a in enumerate(report.assessments) if i in keep_set]
        else:
            # Lenient mode: keep all but populate grounding fields
            pass

        return report


@dataclass
class DiscriminationAuditEntry:
    """Single audit record for one discrimination decision."""

    claim_hash: str
    verdict: GroundingVerdict
    confidence: float
    provenances: list[CitationProvenance]
    reason: str | None = None
    timestamp: datetime | None = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now(UTC)

    @staticmethod
    def _hash_claim(claim_text: str) -> str:
        """Compute SHA-256 hex digest of claim text."""
        return hashlib.sha256(claim_text.encode("utf-8")).hexdigest()
