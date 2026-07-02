"""Data models for the PAKTON 3-agent review pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class Position(StrEnum):
    """Final position for a clause assessment."""

    favorable = "favorable"
    neutral = "neutral"
    unfavorable = "unfavorable"
    uncertain = "uncertain"


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
    favorable: PositionDef
    neutral: PositionDef
    unfavorable: PositionDef
    default_position: Position

    def __post_init__(self) -> None:
        if self.default_position == Position.uncertain:
            raise ValueError("default_position must be favorable, neutral, or unfavorable")


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
    is_amber: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in range 0.0-1.0")
        # Auto-set is_amber based on rules
        if (
            self.error is not None
            or self.confidence < 0.5
            or self.qa_verdict in (QAVerdict.disagree, QAVerdict.uncertain)
        ):
            self.is_amber = True


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

    favorable_count: int = 0
    neutral_count: int = 0
    unfavorable_count: int = 0
    uncertain_count: int = 0
    no_match_count: int = 0
    amber_count: int = 0
    avg_confidence: float = 0.0

    @property
    def total(self) -> int:
        return (
            self.favorable_count
            + self.neutral_count
            + self.unfavorable_count
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
    schema_version: str = "1.0.0"
