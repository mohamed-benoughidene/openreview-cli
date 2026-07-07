"""Review pipeline stage — wraps existing extraction/QA logic as a pipeline stage.

This module provides ``ReviewStage``, a :class:`Stage` subclass that
encapsulates the per-clause assessment loop (match → extract → verify)
and report building as a single pipeline stage.  Combined with
``ParseStage`` and ``StripStage``, it allows ``run_review()`` to delegate
document preparation to the pipeline framework while keeping the
review-specific extraction/QA logic in a stage.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from openreview_cli.pipeline.base import PipelineContext, Stage

if TYPE_CHECKING:
    from openreview_cli.review.models import ClauseAssessment, Playbook, ReviewReport

logger = logging.getLogger(__name__)


class ReviewStage(Stage):
    """Match clauses to playbook categories, extract positions, and verify with QA.

    This stage wraps the existing review extraction and QA logic into a
    single pipeline stage.  After ``run()`` completes, the produced
    ``ReviewReport`` is available via ``self.report``.

    Reads
        ``ctx["document"]`` — ``Document`` metadata object.
        ``ctx.get("stripped_clauses")`` — ``list[Clause]`` (preferred).
        ``ctx.get("clauses")`` — fallback when stripped_clauses is absent.

    Writes
        ``ctx["review_report"]`` — ``ReviewReport``.
        ``ctx["review_assessments"]`` — ``list[ClauseAssessment]``.
    """

    name = "review"
    critical = False

    def __init__(
        self,
        playbook: Playbook,
        extraction_model: str = "extraction",
        qa_model: str | None = None,
        confidence_threshold: float = 0.7,
        playbook_version: int | None = None,
        verbose: bool = False,
        mode: str = "precheck",
    ) -> None:
        """Initialise the review stage.

        Parameters
        ----------
        playbook:
            Loaded playbook with categories and position definitions.
        extraction_model:
            Model slot name for the extraction agent.
        qa_model:
            Model slot name for QA verification.  Falls back to
            *extraction_model* when ``None``.
        confidence_threshold:
            Threshold for Green/Amber/Red colour assignment.
        playbook_version:
            Database version of the playbook, if loaded from DB.
        verbose:
            Emit per-clause progress to stderr when ``True``.
        """
        self._playbook = playbook
        self._extraction_model = extraction_model
        self._qa_model = qa_model or extraction_model
        self._confidence_threshold = confidence_threshold
        self._playbook_version = playbook_version
        self._verbose = verbose
        self._mode = mode
        self.report: ReviewReport | None = None
        self.document: Any = None
        self.clauses: list[Any] | None = []

    async def run(self, ctx: PipelineContext) -> dict[str, Any] | None:
        # Import here to avoid circular imports at module level
        from openreview_cli.review.extraction import extract_clause, match_category
        from openreview_cli.review.qa import verify_assessment

        self.document = ctx.get("document")
        clauses = ctx.get("stripped_clauses")
        if clauses is None:
            clauses = ctx["clauses"]
        self.clauses = list(clauses) if clauses else []

        if not self.clauses:
            return self._empty_report()

        assessments: list[ClauseAssessment] = []

        for clause in self.clauses:
            if self._verbose:
                print(
                    f"  Clause {clause.clause_id}: matching...",
                    file=sys.stderr,
                )

            category = await asyncio.to_thread(match_category, clause.clause_text, self._playbook)
            assessment = await asyncio.to_thread(
                extract_clause,
                clause_text=clause.clause_text,
                clause_id=clause.clause_id,
                category=category,
                extraction_model=self._extraction_model,
                mode=self._mode,
            )

            if category is not None and assessment.playbook_category != "no-match":
                assessment = await asyncio.to_thread(
                    verify_assessment,
                    assessment,
                    category,
                    qa_model=self._qa_model,
                )

            assessments.append(assessment)

        report = self._build_report(assessments)
        self.report = report
        return {"review_report": report, "review_assessments": assessments}

    def cleanup(self, ctx: PipelineContext) -> None:
        """Release large clause and document references after merge."""
        self.clauses = None
        self.document = None

    def _empty_report(self) -> dict[str, Any]:
        """Return a minimal review report for an empty or unparsed document."""
        from openreview_cli.review.models import ReviewReport, ReviewSummary

        doc_meta = _doc_meta_from_document(self.document, clause_count=0, pii_stripped=False)
        report = ReviewReport(
            document=doc_meta,
            assessments=[],
            summary=ReviewSummary(),
            playbook_id=self._playbook.id,
            generated_at=datetime.now(UTC),
            confidence_threshold=self._confidence_threshold,
            playbook_version=self._playbook_version,
            mode=self._mode,
        )
        self.report = report
        return {"review_report": report, "review_assessments": []}

    def _build_report(self, assessments: list[Any]) -> ReviewReport:
        """Build a ReviewReport from clause assessments."""
        from openreview_cli.review.colors import AssessmentColor, assign_colors
        from openreview_cli.review.models import (
            Position,
            ReviewReport,
            ReviewSummary,
        )

        assign_colors(assessments, self._confidence_threshold)

        total_conf = sum(a.confidence for a in assessments if a.playbook_category != "no-match")
        n_conf = sum(1 for a in assessments if a.playbook_category != "no-match") or 1

        pos_counts = Counter(a.position for a in assessments)
        no_match_count = sum(1 for a in assessments if a.playbook_category == "no-match")
        green_count = sum(1 for a in assessments if a.color == AssessmentColor.green)
        red_count = sum(1 for a in assessments if a.color == AssessmentColor.red)
        amber_count = sum(1 for a in assessments if a.color == AssessmentColor.amber)
        valid_conf = [
            a.effective_confidence
            for a in assessments
            if a.effective_confidence is not None and a.playbook_category != "no-match"
        ]
        avg_effective_confidence = sum(valid_conf) / len(valid_conf) if valid_conf else 0.0

        doc_meta = _doc_meta_from_document(
            self.document,
            clause_count=len(assessments),
            pii_stripped=False,
        )

        summary = ReviewSummary(
            preferred_count=pos_counts.get(Position.PREFERRED, 0),
            acceptable_count=pos_counts.get(Position.ACCEPTABLE, 0),
            walkaway_count=pos_counts.get(Position.WALKAWAY, 0),
            uncertain_count=pos_counts.get(Position.UNCERTAIN, 0),
            no_match_count=no_match_count,
            green_count=green_count,
            red_count=red_count,
            amber_count=amber_count,
            avg_confidence=total_conf / n_conf,
            avg_effective_confidence=avg_effective_confidence,
        )

        return ReviewReport(
            document=doc_meta,
            assessments=assessments,
            summary=summary,
            playbook_id=self._playbook.id,
            generated_at=datetime.now(UTC),
            confidence_threshold=self._confidence_threshold,
            playbook_version=self._playbook_version,
            mode=self._mode,
        )


__all__ = ["ReviewStage"]


def _doc_meta_from_document(
    document: Any,
    clause_count: int = 0,
    pii_stripped: bool = False,
) -> Any:
    """Extract a DocMeta from a document metadata object, deduplicating the
    repeated filename/page_count pattern used in _empty_report and _build_report."""
    from openreview_cli.review.models import DocMeta

    filename: str = "unknown"
    page_count = 0
    if document is not None:
        sp = getattr(document, "source_path", None)
        if sp is not None:
            filename = sp.name if hasattr(sp, "name") else str(sp)
        page_count = getattr(document, "page_count", 0) or 0

    return DocMeta(
        filename=filename,
        page_count=page_count,
        clause_count=clause_count,
        pii_stripped=pii_stripped,
        parsed_at=datetime.now(UTC),
    )
