"""Client management — CRUD for clients."""

from pathlib import Path

from openreview_cli.storage.database import transaction


def add_client(db_path: Path, client_id: str, name: str) -> None:
    with transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO clients (id, name) VALUES (?, ?)",
            (client_id, name),
        )


def delete_client(db_path: Path, client_id: str, force: bool = False) -> bool:
    with transaction(db_path) as conn:
        if force:
            conn.execute(
                "DELETE FROM cost_logs WHERE session_id IN (SELECT id FROM reviews WHERE client_id = ?)",
                (client_id,),
            )
            conn.execute(
                "DELETE FROM review_diffs WHERE review_id IN (SELECT id FROM reviews WHERE client_id = ?)",
                (client_id,),
            )
            conn.execute("DELETE FROM reviews WHERE client_id = ?", (client_id,))
        cursor = conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        return cursor.rowcount > 0


def client_has_reviews(db_path: Path, client_id: str) -> bool:
    with transaction(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM reviews WHERE client_id = ?", (client_id,)
        ).fetchone()
        return int(row[0]) > 0


def list_clients(db_path: Path) -> list[dict[str, str]]:
    """List all clients ordered by id.

    Returns list of dicts with keys: id, name.
    """
    with transaction(db_path) as conn:
        rows = conn.execute("SELECT id, name FROM clients ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_client(db_path: Path, client_id: str) -> dict[str, str] | None:
    """Get a single client by id.

    Returns dict with keys id, name, or None if not found.
    """
    with transaction(db_path) as conn:
        row = conn.execute(
            "SELECT id, name FROM clients WHERE id = ?",
            (client_id,),
        ).fetchone()
    return dict(row) if row else None
