"""TUI domain wrapper for stored PII data.

Reads through the same shared inventory query as ``openreview pii list`` and
deletes through ``openreview_cli.pii.retention.delete_pii_data``, so the TUI
and the CLI can never disagree about what is stored or what deletion does.

The ``openreview_cli.pii`` package is imported inside the functions: the TUI
keeps non-trivial module-level imports out of its startup path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openreview_cli.config.paths import get_data_dir


def get_db_path() -> Path:
    """Resolve the SQLite database path."""
    return get_data_dir() / "openreview.db"


def list_stored_pii_via_tui() -> list[dict[str, Any]]:
    """Return stored PII records, newest first.

    Each row carries document_hash, created_at, expiry_at, entity_count and
    mapping_path, plus ``filename`` (the source document's basename, or
    ``None`` for records written before migration 014). The schema is created
    on demand so the screen also works when it is opened before any command
    has initialized the database.
    """
    from openreview_cli.pii.inventory import list_pii_documents, list_pii_filenames
    from openreview_cli.storage import init_database

    db_path = get_db_path()
    init_database(db_path)
    rows = list_pii_documents(db_path)
    filenames = list_pii_filenames(db_path)
    for row in rows:
        row["filename"] = filenames.get(str(row["document_hash"]))
    return rows


def delete_pii_document_via_tui(document_hash: str) -> dict[str, bool | int]:
    """Delete one document's stored PII data via the shared retention logic.

    ``document_hash`` must be the full stored hash; the retention function
    matches on a ``LIKE`` prefix, so a truncated hash could remove more than
    the document the user selected.
    """
    from openreview_cli.pii.retention import delete_pii_data
    from openreview_cli.storage import init_database

    db_path = get_db_path()
    init_database(db_path)
    return delete_pii_data(db_path, document_hash)


__all__ = ["delete_pii_document_via_tui", "get_db_path", "list_stored_pii_via_tui"]
