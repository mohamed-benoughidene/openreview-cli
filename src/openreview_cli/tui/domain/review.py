"""TUI domain wrapper around openreview_cli.review.run_review.

PII stripping is enabled by default per FR-045 and SC-007.
Also wraps review report persistence for the recent-reviews list (US2).
"""

from __future__ import annotations

import json
import logging
import uuid as _uuid

from openreview_cli.config.paths import get_data_dir
from openreview_cli.review import ReviewReport, run_review

logger = logging.getLogger(__name__)

_db_path = get_data_dir() / "openreview.db"


def run_review_via_tui(
    paths: list[str],
    mode: str = "precheck",
    playbook_path: str | None = None,
    playbook_id: str | None = None,
    disable_pii: bool = False,
    extraction_model: str = "extraction",
    qa_model: str | None = None,
    confidence_threshold: float = 0.7,
    verbose: bool = False,
) -> list[ReviewReport]:
    """Run a review from the TUI with PII stripping enabled by default."""
    reports = run_review(
        paths=paths,
        playbook_path=playbook_path,
        playbook_id=playbook_id,
        extraction_model=extraction_model,
        qa_model=qa_model,
        no_pii=disable_pii,
        verbose=verbose,
        confidence_threshold=confidence_threshold,
        mode=mode,
    )

    # Persist each report to the database for the recent-reviews list
    from dataclasses import asdict as _asdict

    from openreview_cli.storage.database import (
        save_review_report as _save_review_report,
    )

    for report in reports:
        report_id = str(_uuid.uuid4())
        filename = report.document.filename if report.document else "unknown"
        report_json = json.dumps(_asdict(report), default=str)
        green = report.summary.green_count if report.summary else 0
        amber = report.summary.amber_count if report.summary else 0
        red = report.summary.red_count if report.summary else 0
        _save_review_report(
            _db_path,
            report_id,
            filename,
            mode,
            report_json,
            green,
            amber,
            red,
        )
        logger.info("Saved review report %s for %s", report_id, filename)

    return reports


def list_recent_reviews_via_tui(limit: int = 5) -> list[dict[str, object]]:
    """Return the most recent review reports for the Home tab list.

    Each dict has keys: id, filename, mode, green_count, amber_count,
    red_count, created_at.
    """
    from openreview_cli.storage.database import (
        list_recent_reviews as _list_recent_reviews,
    )

    return _list_recent_reviews(_db_path, limit)


def load_review_report_via_tui(report_id: str) -> ReviewReport | None:
    """Load a saved ReviewReport from the database by its report ID.

    Returns None if the report is not found.
    """
    from openreview_cli.review.models import ReviewReport as _ReviewReport
    from openreview_cli.storage.database import (
        load_review_report as _load_review_report,
    )

    data = _load_review_report(_db_path, report_id)
    if data is None:
        return None
    return _ReviewReport.from_dict(data)
