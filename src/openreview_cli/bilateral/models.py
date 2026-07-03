"""Data models for the bilateral comparison pipeline (NX-1).

Defines 8 entities: 3 enums, 5 dataclasses. Reuses ``ClauseAssessment``,
``DocMeta`` from ``openreview_cli.review.models`` and ``AssessmentColor``
from ``openreview_cli.review.colors``. No new runtime dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from openreview_cli.parsing.models import Clause
    from openreview_cli.review.colors import AssessmentColor
    from openreview_cli.review.models import ClauseAssessment, DocMeta


class RCBSFDimension(StrEnum):
    """RCBSF 5-dimension risk taxonomy for bilateral divergence, plus no_divergence."""

    category = "category"
    """Clause types differ between parties."""
    location = "location"
    """Same concept in different sub-clauses."""
    evidence = "evidence"
    """Different evidentiary basis / standard."""
    issue = "issue"
    """Risk assessment differs."""
    suggestion = "suggestion"
    """Remedy / action differs."""
    no_divergence = "no_divergence"
    """No material divergence detected."""


class MatchingMethod(StrEnum):
    """How a clause pair was aligned between two documents."""

    exact = "exact"
    """Case-insensitive heading match."""
    fuzzy = "fuzzy"
    """difflib.SequenceMatcher ratio >= threshold."""
    positional = "positional"
    """Same positional index fallback."""


class DivergenceVerdict(StrEnum):
    """Verdict on whether a clause pair diverges materially."""

    divergent = "divergent"
    """Material divergence detected between the two clauses."""
    aligned = "aligned"
    """No material divergence — clauses are substantially aligned."""
    uncertain = "uncertain"
    """Confidence too low to determine divergence."""


@dataclass(slots=True)
class AlignmentPair:
    """A matched clause pair between two documents.

    Attributes
    ----------
    pair_id : str
        Unique identifier (format: "A{index_a}-B{index_b}").
    clause_a : Clause
        Clause from Party A's document.
    clause_b : Clause
        Clause from Party B's document.
    method : MatchingMethod
        How the pair was aligned.
    score : float
        Alignment confidence 0.0-1.0 (1.0 = exact heading match).
    """

    pair_id: str
    clause_a: Clause
    clause_b: Clause
    method: MatchingMethod
    score: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be in range 0.0-1.0")


@dataclass(slots=True)
class AlignmentTable:
    """Complete clause alignment output for a bilateral comparison.

    Attributes
    ----------
    matched_pairs : list[AlignmentPair]
        All successfully matched clause pairs.
    unmatched_a : list[Clause]
        Clauses present only in Document A.
    unmatched_b : list[Clause]
        Clauses present only in Document B.
    alignment_method : str
        Name of the alignment strategy used (default: "heading-cascade").
    """

    matched_pairs: list[AlignmentPair]
    unmatched_a: list[Clause]
    unmatched_b: list[Clause]
    alignment_method: str = "heading-cascade"

    @property
    def matched_count(self) -> int:
        """Number of successfully matched clause pairs."""
        return len(self.matched_pairs)

    @property
    def alignment_rate(self) -> float:
        """Percentage of clauses successfully paired (0.0-1.0).

        Calculated as ``matched_pairs * 2 / (total_a + total_b)`` where
        ``total_a`` and ``total_b`` counts each clause once.
        """
        total = len(self.matched_pairs) * 2 + len(self.unmatched_a) + len(self.unmatched_b)
        if total == 0:
            return 0.0
        return (len(self.matched_pairs) * 2) / total


@dataclass(slots=True)
class PairedAssessment:
    """Comparison result for one aligned clause pair.

    Attributes
    ----------
    pair_id : str
        Unique identifier for this paired assessment.
    alignment : AlignmentPair
        The underlying clause alignment.
    party_a_assessment : ClauseAssessment
        Single-party assessment for Party A's version.
    party_b_assessment : ClauseAssessment
        Single-party assessment for Party B's version.
    divergence : DivergenceVerdict
        Whether the pair diverges materially.
    primary_dimension : RCBSFDimension | None
        Most divergent RCBSF dimension, if any.
    rcbsf_details : dict[RCBSFDimension, str]
        Per-dimension explanation text.
    alignment_quality : float
        Match quality of the clause alignment 0.0-1.0.
    confidence : float
        Confidence score 0.0-1.0 for the divergence detection.
    citations : list[str]
        Text excerpts from both sides supporting the divergence detection.
    rationale : str
        Comparison agent's reasoning for the divergence classification.
    color : AssessmentColor | None
        Three-color status (Green/Amber/Red), set at output time.
    error : str | None
        Error message if the comparison agent failed for this pair.
    """

    pair_id: str
    alignment: AlignmentPair
    party_a_assessment: ClauseAssessment
    party_b_assessment: ClauseAssessment
    divergence: DivergenceVerdict
    primary_dimension: RCBSFDimension | None = None
    rcbsf_details: dict[RCBSFDimension, str] = field(default_factory=dict)
    alignment_quality: float = 1.0
    confidence: float = 0.0
    citations: list[str] = field(default_factory=list)
    rationale: str = ""
    color: AssessmentColor | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.alignment_quality <= 1.0:
            raise ValueError("alignment_quality must be in range 0.0-1.0")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in range 0.0-1.0")

    @property
    def has_divergence(self) -> bool:
        """True if a material divergence was detected."""
        return self.divergence == DivergenceVerdict.divergent


@dataclass(slots=True)
class ComparisonSummary:
    """Aggregate statistics for a bilateral comparison run.

    Attributes
    ----------
    divergent_count : int
        Pairs with material divergence.
    aligned_count : int
        Pairs with no divergence.
    uncertain_count : int
        Pairs where divergence could not be determined.
    green_count : int
        Pairs with Green (no material divergence) status.
    amber_count : int
        Pairs with Amber (uncertain) status.
    red_count : int
        Pairs with Red (material divergence) status.
    total_pairs : int
        Total aligned clause pairs processed.
    avg_alignment_quality : float
        Average alignment quality across all pairs.
    agreement_rate : float
        Percentage of pairs with no divergence (green_count / total_pairs).

    Properties
    ----------
    overall_color : str
        Worst-clause-wins: Red if any Red, Amber if any Amber, else Green.
    """

    divergent_count: int = 0
    aligned_count: int = 0
    uncertain_count: int = 0
    green_count: int = 0
    amber_count: int = 0
    red_count: int = 0
    total_pairs: int = 0
    avg_alignment_quality: float = 0.0
    agreement_rate: float = 0.0

    @property
    def overall_color(self) -> str:
        """Worst-clause-wins: Red > Amber > Green."""
        if self.red_count > 0:
            return "red"
        if self.amber_count > 0:
            return "amber"
        return "green"


@dataclass(slots=True)
class ComparisonReport:
    """Complete output of a bilateral comparison run.

    Attributes
    ----------
    experimental : bool
        Always True — marks output as experimental NX-1.
    disclaimer : str
        Accuracy caveat and legal disclaimer text.
    document_a : DocMeta
        Metadata for Document A.
    document_b : DocMeta
        Metadata for Document B.
    alignment_table : AlignmentTable
        Clause alignment results.
    assessments : list[PairedAssessment]
        Per-pair comparison results.
    summary : ComparisonSummary
        Aggregate statistics.
    playbook_id : str
        Identifier of the playbook used.
    generated_at : datetime
        Timestamp when the report was generated.
    confidence_threshold : float
        Confidence threshold used for this run.
    schema_version : str
        Output schema version for downstream compatibility.
    """

    document_a: DocMeta
    document_b: DocMeta
    alignment_table: AlignmentTable
    assessments: list[PairedAssessment]
    summary: ComparisonSummary
    playbook_id: str
    generated_at: datetime
    experimental: bool = True
    disclaimer: str = ""
    confidence_threshold: float = 0.7
    schema_version: str = "1.0.0"
