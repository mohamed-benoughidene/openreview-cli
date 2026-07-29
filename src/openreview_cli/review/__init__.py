"""Review command module — PAKTON 3-agent pipeline.

Single-party review brings contract analysis to the CLI: a user uploads a
contract and receives a structured, per-clause assessment scored against a
3-position playbook (preferred, acceptable, walkaway). Three pipeline
stages — extraction, QA verification, and a no-op comparison placeholder —
produce citation-grounded, uncertainty-aware output.
"""

from __future__ import annotations

from openreview_cli.review.base import ReviewCommand, run_bilateral_comparison
from openreview_cli.review.colors import AmberReason, AssessmentColor, assign_colors
from openreview_cli.review.comparison_agent import (
    ComparisonAgent,
    ComparisonReport,
    ComparisonSummary,
    DivergenceType,
    PairedAssessment,
)

# Memo export public API
from openreview_cli.review.memo import MemoExporter, MemoFormat
from openreview_cli.review.models import ReviewReport
from openreview_cli.review.playbook import (
    VersionDiff,
    compute_playbook_diff,
    load_playbook_from_db,
)
from openreview_cli.review.report import format_json, format_terminal

__all__ = [
    "AmberReason",
    "AssessmentColor",
    "ComparisonAgent",
    "ComparisonReport",
    "ComparisonSummary",
    "DivergenceType",
    "MemoExporter",
    "MemoFormat",
    "PairedAssessment",
    "ReviewCommand",
    "ReviewReport",
    "VersionDiff",
    "assign_colors",
    "compute_playbook_diff",
    "format_json",
    "format_terminal",
    "load_playbook_from_db",
    "run_bilateral_comparison",
    "run_review",
]

from openreview_cli.review.runner import run_review
