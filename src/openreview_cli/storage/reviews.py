"""Review reports — save, load, and list review data."""

import json
from pathlib import Path
from typing import Any

from openreview_cli.storage.database import init_database, transaction


def save_review_report(
    db_path: Path,
    report_id: str,
    filename: str,
    mode: str,
    report_json: str,
    green_count: int = 0,
    amber_count: int = 0,
    red_count: int = 0,
    client_id: str | None = None,
) -> None:
    """Save a review report to the review_reports table.

    Uses INSERT OR REPLACE so re-saving the same report_id updates the row.
    """
    init_database(db_path)
    with transaction(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO review_reports "
            "(id, filename, mode, report_json, green_count, amber_count, red_count, created_at, client_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, "
            "  COALESCE((SELECT created_at FROM review_reports WHERE id = ?), datetime('now')), ?)",
            (
                report_id,
                filename,
                mode,
                report_json,
                green_count,
                amber_count,
                red_count,
                report_id,
                client_id,
            ),
        )


def load_review_report(db_path: Path, report_id: str) -> dict[str, Any] | None:
    """Load a review report's JSON data from the database.

    Returns the deserialised report dict, or None if not found.
    """
    init_database(db_path)
    with transaction(db_path) as conn:
        row = conn.execute(
            "SELECT report_json FROM review_reports WHERE id = ?",
            (report_id,),
        ).fetchone()
    if row is None:
        return None
    report_json: dict[str, Any] | None = json.loads(row["report_json"])
    return report_json


def list_recent_reviews(db_path: Path, limit: int = 5) -> list[dict[str, Any]]:
    """Return the most recent review reports, ordered by created_at DESC.

    Each row contains: id, filename, mode, green_count, amber_count,
    red_count, created_at.
    """
    init_database(db_path)
    with transaction(db_path) as conn:
        rows = conn.execute(
            "SELECT id, filename, mode, green_count, amber_count, red_count, created_at "
            "FROM review_reports ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_reviews_for_client(db_path: Path, client_id: str) -> list[dict[str, Any]]:
    """Return review reports for a specific client, ordered by created_at DESC.

    Each row contains: id, filename, mode, green_count, amber_count,
    red_count, created_at.
    """
    init_database(db_path)
    with transaction(db_path) as conn:
        rows = conn.execute(
            "SELECT id, filename, mode, green_count, amber_count, red_count, created_at "
            "FROM review_reports WHERE client_id = ? ORDER BY created_at DESC",
            (client_id,),
        ).fetchall()
    return [dict(r) for r in rows]
