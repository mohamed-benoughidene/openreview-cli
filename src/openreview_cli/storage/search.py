"""Search — full-text search across reviews, clients, and playbooks."""

from pathlib import Path
from typing import Any

from openreview_cli.storage.database import init_database, transaction


def search_all(db_path: Path, query: str) -> dict[str, list[dict[str, Any]]]:
    """Search across reviews, clients, and playbooks.

    Matches reviews by filename, clients by id/name, playbooks by id.
    Returns dict with keys ``reviews``, ``clients``, ``playbooks``.
    """
    init_database(db_path)
    lowered = query.lower()
    results: dict[str, list[dict[str, Any]]] = {
        "reviews": [],
        "clients": [],
        "playbooks": [],
    }

    with transaction(db_path) as conn:
        rows = conn.execute(
            "SELECT id, filename, mode, green_count, amber_count, red_count, created_at "
            "FROM review_reports WHERE LOWER(filename) LIKE ? "
            "ORDER BY created_at DESC LIMIT 20",
            (f"%{lowered}%",),
        ).fetchall()
    results["reviews"] = [dict(r) for r in rows]

    with transaction(db_path) as conn:
        rows = conn.execute(
            "SELECT id, name FROM clients WHERE LOWER(id) LIKE ? OR LOWER(name) LIKE ? ORDER BY id",
            (f"%{lowered}%", f"%{lowered}%"),
        ).fetchall()
    results["clients"] = [dict(r) for r in rows]

    with transaction(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT playbook_id FROM playbook_versions "
            "WHERE LOWER(playbook_id) LIKE ? "
            "ORDER BY playbook_id",
            (f"%{lowered}%",),
        ).fetchall()
    results["playbooks"] = [{"playbook_id": str(r["playbook_id"])} for r in rows]

    return results
