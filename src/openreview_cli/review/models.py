"""Data models for the PAKTON 3-agent review pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

    from openreview_cli.grounding.models import (
        CGMetrics,
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
    mode_threshold_overrides: dict[str, float] | None = None
    schema_version: str = "1.1.0"
    playbook_version: int | None = None
    cg_metrics: CGMetrics | None = None
    mode: str = "precheck"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewReport:
        """Reconstruct a ReviewReport from a dict produced by ``dataclasses.asdict()``.

        Handles StrEnum reconstruction, nested dataclass fields, and ISO
        datetime parsing.  Designed to round-trip JSON produced by
        ``format_json`` / ``_report_to_dict``.

        Parameters
        ----------
        data : dict[str, object]
            Serialised report data (from JSON).

        Returns
        -------
        ReviewReport
            Fully reconstructed report object.
        """
        from datetime import datetime as _dt

        from openreview_cli.grounding.models import (
            CGMetrics as _CGMetrics,
        )
        from openreview_cli.grounding.models import (
            CitationProvenance as _CitationProvenance,
        )
        from openreview_cli.grounding.models import (
            GroundingVerdict as _GroundingVerdict,
        )
        from openreview_cli.review.colors import (
            AmberReason as _AmberReason,
        )
        from openreview_cli.review.colors import (
            AssessmentColor as _AssessmentColor,
        )

        # ── Document metadata ──
        doc_raw = dict(data["document"])
        parsed_at_raw = doc_raw.get("parsed_at")
        if isinstance(parsed_at_raw, str):
            doc_raw["parsed_at"] = _dt.fromisoformat(parsed_at_raw)
        document = DocMeta(**doc_raw)

        # ── Assessments ──
        assessments_raw = list(data["assessments"])
        assessments: list[ClauseAssessment] = []
        for a_raw in assessments_raw:
            a: dict[str, Any] = dict(a_raw)

            # Map 'is_amber' property → dataclass field '_is_amber'
            is_amber_val = a.pop("is_amber", None)
            if is_amber_val is not None:
                a["_is_amber"] = is_amber_val

            # Position enumeration
            if isinstance(a.get("position"), str):
                a["position"] = Position(str(a["position"]))
            if isinstance(a.get("qa_revised_position"), str):
                a["qa_revised_position"] = Position(str(a["qa_revised_position"]))

            # QA verdict
            if isinstance(a.get("qa_verdict"), str):
                a["qa_verdict"] = QAVerdict(str(a["qa_verdict"]))

            # Color
            if isinstance(a.get("color"), str):
                a["color"] = _AssessmentColor(str(a["color"]))

            # Amber reasons
            amber_raw = a.get("amber_reasons")
            if isinstance(amber_raw, list):
                a["amber_reasons"] = [
                    _AmberReason(str(r)) if isinstance(r, str) else r for r in amber_raw
                ]

            # Grounding fields
            if isinstance(a.get("grounding_verdict"), str):
                a["grounding_verdict"] = _GroundingVerdict(str(a["grounding_verdict"]))
            prov_raw = a.get("grounding_provenances")
            if isinstance(prov_raw, list):
                a["grounding_provenances"] = [
                    _CitationProvenance(**cp) if isinstance(cp, dict) else cp for cp in prov_raw
                ]

            assessments.append(ClauseAssessment(**a))

        # ── Summary ──
        summary = ReviewSummary(**data["summary"])

        # ── Datetime ──
        generated_at = _dt.fromisoformat(str(data["generated_at"]))

        # ── Optional CGMetrics ──
        cg_raw = data.get("cg_metrics")
        cg_metrics = _CGMetrics(**cg_raw) if cg_raw is not None else None

        return cls(
            document=document,
            assessments=assessments,
            summary=summary,
            generated_at=generated_at,
            cg_metrics=cg_metrics,
            playbook_id=str(data["playbook_id"]),
            confidence_threshold=float(data.get("confidence_threshold", 0.7)),
            mode_threshold_overrides=data.get("mode_threshold_overrides"),
            schema_version=str(data.get("schema_version", "1.1.0")),
            playbook_version=int(data["playbook_version"])
            if data.get("playbook_version") is not None
            else None,
            mode=str(data.get("mode", "precheck")),
        )
