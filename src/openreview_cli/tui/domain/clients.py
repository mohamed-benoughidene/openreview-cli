"""TUI domain wrapper around openreview_cli.storage.database client CRUD."""

from __future__ import annotations

from pathlib import Path

from openreview_cli.config.paths import get_data_dir
from openreview_cli.storage.database import (
    add_client,
    client_has_reviews,
    delete_client,
    get_client,
    list_clients,
    list_reviews_for_client,
)


def get_db_path() -> Path:
    """Resolve database file path."""
    return get_data_dir() / "openreview.db"


def add_client_via_tui(client_id: str, name: str, notes: str | None = None) -> None:
    """Add a client. Notes accepted for UI completeness, not persisted in v1."""
    add_client(get_db_path(), client_id, name)


def list_clients_via_tui() -> list[dict[str, str]]:
    """List all clients."""
    return list_clients(get_db_path())


def get_client_via_tui(client_id: str) -> dict[str, str] | None:
    """Get a single client by id."""
    return get_client(get_db_path(), client_id)


def list_reviews_for_client_via_tui(client_id: str) -> list[dict[str, object]]:
    """Return review reports for a specific client."""
    return list_reviews_for_client(get_db_path(), client_id)


def delete_client_via_tui(client_id: str, cascade: bool = False) -> str:
    """Delete a client, returning 'ok' or 'has_reviews'."""
    db_path = get_db_path()
    if not cascade and client_has_reviews(db_path, client_id):
        return "has_reviews"
    delete_client(db_path, client_id, force=cascade)
    return "ok"
