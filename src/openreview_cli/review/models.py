"""Data models for the PAKTON 3-agent review pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from openreview_cli.grounding.models import (
        CitationProvenance,
        GroundingVerdict,
    )
    from openreview_cli.review.colors import AmberReason, AssessmentColor


class Position(StrEnum):
    """Final position for a clause assessment."""

    PREFERRED = "preferred"
    ACCEPTABLE = "acceptable"
    WALKAWAY = "walkaway"
    UNCERTAIN = "uncertain"


class QAVerdict(StrEnum):
    """QA agent's verdict on an extraction."""

    agree = "agree"
    disagree = "disagree"
    uncertain = "uncertain"


@dataclass
class PositionDef:
    """Definition of a single position within a category."""

    description: str
    exemplars: list[str]

    def __post_init__(self) -> None:
        if not self.exemplars:
            raise ValueError("exemplars must contain at least one string")


@dataclass
class Category:
    """A single clause category within a playbook."""

    id: str
    name: str
    description: str
    preferred: PositionDef
    acceptable: PositionDef
    walkaway: PositionDef
    default_position: Position

    def __post_init__(self) -> None:
        if self.default_position == Position.UNCERTAIN:
            raise ValueError("default_position must be preferred, acceptable, or walkaway")


@dataclass
class PlaybookMetadata:
    """Metadata for a playbook."""

    version: str
    description: str
    author: str


@dataclass
class Playbook:
    """A collection of clause categories with position definitions."""

    id: str
    mode: str
    categories: list[Category]
    metadata: PlaybookMetadata

    def __post_init__(self) -> None:
        if not self.categories:
            raise ValueError("categories must contain at least one entry")
        ids = [c.id for c in self.categories]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate category ids: {ids}")


@dataclass
class ClauseAssessment:
    """Outcome of running a single clause through the pipeline."""

    clause_id: str
    clause_text: str
    playbook_category: str
    position: Position
    confidence: float
    citation: str
    qa_verdict: QAVerdict
    extraction_model: str
    qa_model: str
    qa_revised_position: Position | None = None
    qa_revised_rationale: str | None = None
    error: str | None = None
    # Three-color fields (set by assign_colors(), default None)
    color: AssessmentColor | None = None
    amber_reasons: list[AmberReason] | None = None
    effective_confidence: float | None = None
    # Backward-compat amber indicator (set by assign_colors() and accessible via @property)
    _is_amber: bool = field(default=False, repr=False)
    # Citation grounding discriminator fields (all optional, default None)
    grounding_verdict: GroundingVerdict | None = None
    grounding_provenances: list[CitationProvenance] | None = None
    grounding_confidence: float | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in range 0.0-1.0")

    @property
    def is_amber(self) -> bool:
        """Return True if the clause is amber, based on color (if assigned) or stored value."""
        if self.color is not None:
            return str(self.color) == "amber"
        return self._is_amber

    @is_amber.setter
    def is_amber(self, value: bool) -> None:
        self._is_amber = value


@dataclass
class DocMeta:
    """Document metadata from the parsing phase."""

    filename: str
    page_count: int
    clause_count: int
    pii_stripped: bool
    parsed_at: datetime | None = None


@dataclass
class ReviewSummary:
    """Aggregate statistics across all assessments."""

    preferred_count: int = 0
    acceptable_count: int = 0
    walkaway_count: int = 0
    uncertain_count: int = 0
    no_match_count: int = 0
    amber_count: int = 0
    green_count: int = 0
    red_count: int = 0
    avg_confidence: float = 0.0
    avg_effective_confidence: float = 0.0

    @property
    def total(self) -> int:
        return (
            self.preferred_count
            + self.acceptable_count
            + self.walkaway_count
            + self.uncertain_count
            + self.no_match_count
        )


@dataclass
class ReviewReport:
    """Top-level output of a single review run."""

    document: DocMeta
    assessments: list[ClauseAssessment]
    summary: ReviewSummary
    playbook_id: str
    generated_at: datetime
    confidence_threshold: float = 0.7
    schema_version: str = "1.1.0"
    playbook_version: int | None = None
