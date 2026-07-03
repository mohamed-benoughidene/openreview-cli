"""Review command module — PAKTON 3-agent pipeline.

Single-party review brings contract analysis to the CLI: a user uploads a
contract and receives a structured, per-clause assessment scored against a
3-position playbook (favorable, neutral, unfavorable). Three pipeline
stages — extraction, QA verification, and a no-op comparison placeholder —
produce citation-grounded, uncertainty-aware output.
"""

from __future__ import annotations

import logging
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

from openreview_cli.review.base import ReviewCommand
from openreview_cli.review.extraction import extract_clause, match_category
from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Playbook,
    Position,
    ReviewReport,
    ReviewSummary,
)
from openreview_cli.review.playbook import load_bundled, load_playbook
from openreview_cli.review.qa import verify_assessment
from openreview_cli.review.report import format_json, format_terminal

logger = logging.getLogger(__name__)

__all__ = [
    "ReviewCommand",
    "ReviewReport",
    "format_json",
    "format_terminal",
    "run_review",
]


def run_review(
    paths: Sequence[str],
    playbook_path: str | None = None,
    extraction_model: str = "extraction",
    qa_model: str | None = None,
    no_pii: bool = False,
    verbose: bool = False,
    grounding_mode: str | None = None,
) -> list[ReviewReport]:
    """Run the PAKTON 3-agent review pipeline on one or more documents.

    Parameters
    ----------
    paths : Sequence[str]
        One or more document file paths (.pdf, .docx). Glob expansion
        is handled by the CLI shell.
    playbook_path : str | None
        Path to a custom YAML playbook. ``None`` uses the bundled NDA playbook.
    extraction_model : str
        Model slot name for the extraction agent.
    qa_model : str | None
        Model slot name for the QA verification agent. ``None`` uses the
        same slot as extraction.
    no_pii : bool
        Skip PII stripping when ``True``.
    verbose : bool
        Print per-clause progress to stderr when ``True``.
    grounding_mode : str | None
        Grounding mode: ``"strict"``, ``"lenient"``, or ``None`` to skip.

    Returns
    -------
    list[ReviewReport]
        One report per document, in input order.
    """
    if qa_model is None:
        qa_model = extraction_model

    # Load playbook
    playbook = load_playbook(Path(playbook_path)) if playbook_path else load_bundled()

    reports: list[ReviewReport] = []

    for path_str in paths:
        doc_path = Path(path_str)
        if not doc_path.exists():
            logger.warning("Document not found, skipping: %s", doc_path)
            continue

        if verbose:
            print(f"Processing: {doc_path.name}", file=sys.stderr)

        try:
            doc, clauses = _parse_clauses(doc_path)
        except Exception as exc:
            logger.warning("Failed to parse %s: %s", doc_path, exc)
            if verbose:
                print(f"  Parse error: {exc}", file=sys.stderr)
            continue
        assessments: list[ClauseAssessment] = []

        for clause in clauses:
            if verbose:
                print(
                    f"  Clause {clause.clause_id}: matching...",
                    file=sys.stderr,
                )

            # Phase 1: Match clause to playbook category
            category = match_category(clause.clause_text, playbook)

            # Phase 2: Extract position
            assessment = extract_clause(
                clause_text=clause.clause_text,
                clause_id=clause.clause_id,
                category=category,
                extraction_model=extraction_model,
            )

            # Phase 3: QA verification
            if category is not None and assessment.playbook_category != "no-match":
                assessment = verify_assessment(assessment, category, qa_model=qa_model)

            # Phase 4: Comparison (no-op for single-party)
            # (comparison runs at report level, not per-clause)

            assessments.append(assessment)

        # Build report
        doc_meta = DocMeta(
            filename=doc_path.name,
            page_count=doc.page_count or 0,
            clause_count=len(assessments),
            pii_stripped=False,
            parsed_at=datetime.now(UTC),
        )
        report = _build_report(doc_meta, assessments, playbook)

        # Phase 5: Comparison — no-op for single-party review

        # Phase 6: Citation Grounding (optional)
        if grounding_mode is not None and report.assessments:
            try:
                from openreview_cli.grounding import run_grounding

                grounding_result = run_grounding(
                    report,
                    doc,
                    mode=grounding_mode,  # type: ignore[arg-type]  # validated as 'strict'/'lenient' above
                    source_clauses=clauses,
                )
                grounding_result.merge_into(report)
                logger.info(
                    "Grounding: %d/%d grounded (%s mode)",
                    grounding_result.grounded_count,
                    grounding_result.total_claims,
                    grounding_mode,
                )
            except Exception:
                logger.warning("Citation grounding failed, skipping", exc_info=True)
                if verbose:
                    print(
                        "  Warning: citation grounding skipped due to error",
                        file=sys.stderr,
                    )

        reports.append(report)

    return reports


def _parse_clauses(doc_path: Path) -> tuple[Any, list]:  # type: ignore[type-arg]  # returns (Document, list[Clause]) from parsing module
    """Parse a document into clauses using ``stream_clauses()``.

    Returns ``(doc, clauses)`` so callers don't need to parse twice.
    """
    from openreview_cli.parsing.stream import parse_document

    return parse_document(str(doc_path))


def _build_report(
    doc_meta: DocMeta,
    assessments: list[ClauseAssessment],
    playbook: Playbook,
) -> ReviewReport:
    """Build a ReviewReport from assessments."""
    total_conf = sum(a.confidence for a in assessments if a.playbook_category != "no-match")
    n_conf = sum(1 for a in assessments if a.playbook_category != "no-match") or 1

    pos_counts = Counter(a.position for a in assessments)
    no_match_count = sum(1 for a in assessments if a.playbook_category == "no-match")
    amber_count = sum(1 for a in assessments if a.is_amber)

    summary = ReviewSummary(
        favorable_count=pos_counts.get(Position.favorable, 0),
        neutral_count=pos_counts.get(Position.neutral, 0),
        unfavorable_count=pos_counts.get(Position.unfavorable, 0),
        uncertain_count=pos_counts.get(Position.uncertain, 0),
        no_match_count=no_match_count,
        amber_count=amber_count,
        avg_confidence=total_conf / n_conf,
    )

    return ReviewReport(
        document=doc_meta,
        assessments=assessments,
        summary=summary,
        playbook_id=playbook.id,
        generated_at=datetime.now(UTC),
    )
