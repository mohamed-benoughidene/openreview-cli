"""Bilateral comparison module — experimental two-party contract comparison.

NX-1 compares two documents clause-by-clause, detects divergences using the
RCBSF 5-dimension taxonomy, and produces a paired side-by-side assessment
with three-color status. This module is EXPERIMENTAL — accuracy ceiling is
≤64% F1 for binary discrepancy (P-4).

Pipeline (sequential per Q2):
1. Parse Document A → extract clauses → run extraction + QA → release A
2. Parse Document B → extract clauses → run extraction + QA → release B
3. Align clauses (3-tier heading cascade)
4. Compare each aligned pair (comparison agent)
5. Build ComparisonReport
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from openreview_cli.parsing.models import Clause
    from openreview_cli.review.models import ClauseAssessment

from openreview_cli.bilateral.align import align_clauses
from openreview_cli.bilateral.colors import assign_paired_colors
from openreview_cli.bilateral.comparison import compare_pair
from openreview_cli.bilateral.models import (
    ComparisonReport,
    ComparisonSummary,
    PairedAssessment,
)
from openreview_cli.bilateral.report import EXPERIMENTAL_DISCLAIMER, compute_summary
from openreview_cli.config.paths import get_data_dir
from openreview_cli.review.extraction import extract_clause, match_category
from openreview_cli.review.models import (
    ClauseAssessment,
    DocMeta,
    Playbook,
    Position,
    QAVerdict,
)
from openreview_cli.review.playbook import load_bundled, load_playbook
from openreview_cli.review.qa import verify_assessment

logger = logging.getLogger(__name__)

__all__ = [
    "ComparisonReport",
    "_check_first_run",
    "assign_paired_colors",
    "compute_summary",
    "run_comparison",
]

_FIRST_RUN_MARKER = ".bilateral_first_run"


def _check_first_run() -> None:
    """Check for first-run marker and print warning to stderr if needed.

    First invocation on a machine prints the full experimental warning
    and creates a marker file. Subsequent invocations print a short reminder.
    Non-suppressible per spec FR-9.
    """
    data_dir = get_data_dir()
    marker = data_dir / _FIRST_RUN_MARKER
    if not marker.exists():
        import sys

        print(
            "⚠ NX-1 Bilateral Comparison is EXPERIMENTAL.\n"
            "  Comparison accuracy has known limitations.\n"
            "  Review all results manually before relying on them.\n"
            "  See https://github.com/mohamed-benoughidene/openreview-specs/014 for details.",
            file=sys.stderr,
        )
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("")
    else:
        import sys

        print(
            "Bilateral comparison: experimental feature. See --help for details.",
            file=sys.stderr,
        )


def run_comparison(
    doc_a_path: str,
    doc_b_path: str,
    playbook: Playbook | None = None,
    extraction_model: str = "extraction",
    qa_model: str | None = None,
    no_pii: bool = False,
    verbose: bool = False,
    confidence_threshold: float = 0.7,
    align_only: bool = False,
    grounding_mode: str | None = None,
) -> ComparisonReport:
    """Run the bilateral comparison pipeline on two documents.

    Processes Document A fully (parse → extract → QA), then Document B,
    then aligns clauses, runs the comparison agent on each pair, and
    builds a ``ComparisonReport``.

    Parameters
    ----------
    doc_a_path : str
        Path to Party A's document (.pdf, .docx).
    doc_b_path : str
        Path to Party B's document (.pdf, .docx).
    playbook : Playbook | None
        Playbook to use for extraction. ``None`` loads the bundled NDA playbook.
    extraction_model : str
        Model slot name for the extraction agent (also used for comparison per FR-3/Q3).
    qa_model : str | None
        Model slot name for QA verification. ``None`` uses the same slot as extraction.
    no_pii : bool
        Skip PII stripping when ``True``.
    verbose : bool
        Print per-clause progress to stderr when ``True``.
    confidence_threshold : float
        Threshold for Green/Amber/Red assignment (0.0-1.0). Default 0.7.
    align_only : bool
        When ``True``, only align clauses — skip extraction, QA, and comparison.
    grounding_mode : str | None
        Citation grounding mode (``"strict"``, ``"lenient"``, or ``None``).

    Returns
    -------
    ComparisonReport
        Full comparison report including alignment table, paired assessments,
        and aggregate summary.
    """
    # Print first-run warning to stderr (non-suppressible per spec FR-9)
    _check_first_run()

    if qa_model is None:
        qa_model = extraction_model

    # Resolve playbook
    if playbook is None:
        playbook = load_bundled()

    # ---- Phase 1: Process Document A ----
    doc_a_meta, clauses_a, assessments_a = _process_document(
        doc_a_path,
        playbook,
        extraction_model,
        qa_model,
        no_pii=no_pii,
        verbose=verbose,
        align_only=align_only,
        grounding_mode=grounding_mode,
    )

    # ---- Release A's inference state (conceptual; Python GC handles memory) ----

    # ---- Phase 2: Process Document B ----
    doc_b_meta, clauses_b, assessments_b = _process_document(
        doc_b_path,
        playbook,
        extraction_model,
        qa_model,
        no_pii=no_pii,
        verbose=verbose,
        align_only=align_only,
        grounding_mode=grounding_mode,
    )

    # ---- Phase 3: Align clauses ----
    alignment_table = align_clauses(clauses_a, clauses_b)

    # ---- Phase 4: Compare aligned pairs (skip if align_only) ----
    paired_assessments: list[PairedAssessment] = []

    if not align_only:
        assessments_by_id_a = {a.clause_id: a for a in assessments_a}
        assessments_by_id_b = {a.clause_id: a for a in assessments_b}

        for pair in alignment_table.matched_pairs:
            ass_a = assessments_by_id_a.get(pair.clause_a.id)
            ass_b = assessments_by_id_b.get(pair.clause_b.id)

            if ass_a is None or ass_b is None:
                logger.warning(
                    "Missing assessment for pair %s: a=%s, b=%s",
                    pair.pair_id,
                    pair.clause_a.id,
                    pair.clause_b.id,
                )
                continue

            # Find the playbook category for this clause pair
            category = match_category(pair.clause_a.text, playbook)

            paired = compare_pair(
                alignment=pair,
                party_a_assessment=ass_a,
                party_b_assessment=ass_b,
                playbook_category=category,
                model=extraction_model,
            )
            paired_assessments.append(paired)

    # ---- Phase 4b: Assign colors ----
    assign_paired_colors(paired_assessments, confidence_threshold=confidence_threshold)

    # ---- Phase 5: Build summary ----
    summary = compute_summary(paired_assessments)

    # ---- Phase 6: Build report ----
    report = ComparisonReport(
        document_a=doc_a_meta,
        document_b=doc_b_meta,
        alignment_table=alignment_table,
        assessments=paired_assessments,
        summary=summary,
        playbook_id=playbook.id,
        generated_at=datetime.now(UTC),
        confidence_threshold=confidence_threshold,
        disclaimer=EXPERIMENTAL_DISCLAIMER,
    )

    return report


def _process_document(
    doc_path: str,
    playbook: Playbook,
    extraction_model: str,
    qa_model: str,
    no_pii: bool = False,
    verbose: bool = False,
    align_only: bool = False,
    grounding_mode: str | None = None,
) -> tuple[DocMeta, list[Clause], list[ClauseAssessment]]:
    """Run the single-party pipeline on one document.

    Returns ``(doc_meta, clauses, assessments)``.
    """
    doc_path_obj = Path(doc_path)
    doc, clauses = _parse_document(doc_path)

    assessments: list[ClauseAssessment] = []

    if align_only:
        # Still build DocMeta even in align-only mode
        doc_meta = DocMeta(
            filename=doc_path_obj.name,
            page_count=getattr(doc, "page_count", 0) or 0,
            clause_count=len(clauses),
            pii_stripped=not no_pii,
            parsed_at=datetime.now(UTC),
        )
        return doc_meta, clauses, assessments

    for clause in clauses:
        if verbose:
            import sys  # inline import per existing pattern

            print(
                f"  {doc_path_obj.name}: Clause {clause.id}: matching...",
                file=sys.stderr,
            )

        # Phase 1: Match clause to playbook category
        category = match_category(clause.text, playbook)

        # Phase 2: Extract position
        assessment = extract_clause(
            clause_text=clause.text,
            clause_id=clause.id,
            category=category,
            extraction_model=extraction_model,
            mode="precheck",
        )

        # Phase 3: QA verification
        if category is not None and assessment.playbook_category != "no-match":
            assessment = verify_assessment(assessment, category, qa_model=qa_model)

        assessments.append(assessment)

    doc_meta = DocMeta(
        filename=doc_path_obj.name,
        page_count=getattr(doc, "page_count", 0) or 0,
        clause_count=len(assessments),
        pii_stripped=not no_pii,
        parsed_at=datetime.now(UTC),
    )

    return doc_meta, clauses, assessments


def _parse_document(doc_path: str) -> tuple[Any, list[Clause]]:
    """Parse a document into clauses using ``stream_clauses()``.

    Returns ``(doc, clauses)`` — mirrors ``review/__init__.py`` pattern.
    """
    from openreview_cli.parsing.stream import parse_document

    return parse_document(doc_path)
