"""Comparison history — record and list contract comparisons."""

import sqlite3
from pathlib import Path
from typing import Any

from openreview_cli.storage.database import transaction


def _ensure_comparison_history_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS comparison_history ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  contract_a_path TEXT NOT NULL,"
        "  contract_a_hash TEXT NOT NULL,"
        "  contract_a_version_label TEXT,"
        "  contract_b_path TEXT NOT NULL,"
        "  contract_b_hash TEXT NOT NULL,"
        "  contract_b_version_label TEXT,"
        "  run_at TEXT NOT NULL DEFAULT (datetime('now')),"
        "  result_json TEXT NOT NULL"
        ")"
    )


def record_comparison(db_path: Path, entry: dict[str, Any]) -> int:
    """Insert a row into comparison_history.

    Returns the new row ID.
    """
    with transaction(db_path) as conn:
        _ensure_comparison_history_table(conn)
        cur = conn.execute(
            "INSERT INTO comparison_history "
            "(contract_a_path, contract_a_hash, contract_a_version_label, "
            " contract_b_path, contract_b_hash, contract_b_version_label, "
            " result_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                entry["contract_a_path"],
                entry["contract_a_hash"],
                entry.get("contract_a_version_label"),
                entry["contract_b_path"],
                entry["contract_b_hash"],
                entry.get("contract_b_version_label"),
                entry["result_json"],
            ),
        )
        return int(cur.lastrowid or 0)


def list_comparison_history(db_path: Path, limit: int = 50) -> list[dict[str, Any]]:
    """Return recent comparison history entries, newest first.

    Parameters
    ----------
    db_path : Path
        Path to the SQLite database.
    limit : int
        Maximum number of rows to return (default 50).

    Returns
    -------
    list[dict[str, Any]]
        Each dict has keys: id, contract_a_path, contract_a_hash,
        contract_a_version_label, contract_b_path, contract_b_hash,
        contract_b_version_label, run_at.
    """
    with transaction(db_path) as conn:
        _ensure_comparison_history_table(conn)
        rows = conn.execute(
            "SELECT id, contract_a_path, contract_a_hash, "
            "  contract_a_version_label, contract_b_path, contract_b_hash, "
            "  contract_b_version_label, run_at "
            "FROM comparison_history "
            "ORDER BY run_at DESC "
            "LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
