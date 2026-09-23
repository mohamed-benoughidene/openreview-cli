"""Read-only inventory of stored PII governance records.

Single source of truth for "which documents still have PII data on disk",
shared by the ``openreview pii list`` command and the TUI's stored-PII screen
so the two surfaces can never drift apart.

The default result is driven by ``pii_cache`` — the rows written when a review
actually stored an encrypted mapping.  ``include_audit_only`` adds documents
that have an audit-trail row but no stored mapping (an ``--all`` concern for
the CLI).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

_AUDIT_AGGREGATE = (
    "SELECT document_hash, entity_count, MAX(timestamp) as max_ts "
    "FROM pii_audit_trail GROUP BY document_hash"
)

_BASE = (
    "SELECT pc.document_hash, pc.created_at, pc.expiry_at, "
    "COALESCE(pat.entity_count, 0) as entity_count, "
    "pc.mapping_path "
    "FROM pii_cache pc "
    "LEFT JOIN (" + _AUDIT_AGGREGATE + ") pat "
    "ON pc.document_hash = pat.document_hash "
)

_AUDIT_ONLY_BRANCH = (
    "UNION ALL "
    "SELECT pat.document_hash, pat.max_ts, NULL, pat.entity_count, NULL "
    "FROM (" + _AUDIT_AGGREGATE + ") pat "
    "WHERE NOT EXISTS "
    "(SELECT 1 FROM pii_cache pc WHERE pc.document_hash = pat.document_hash) "
    "ORDER BY created_at DESC"
)


def list_pii_documents(db_path: Path, include_audit_only: bool = False) -> list[dict[str, Any]]:
    """Return stored PII records, newest first.

    Each row carries ``document_hash``, ``created_at``, ``expiry_at``,
    ``entity_count`` and ``mapping_path``.  Callers that may run against a
    database whose schema is not yet created must call
    ``openreview_cli.storage.init_database`` first.
    """
    query = (
        _BASE + _AUDIT_ONLY_BRANCH if include_audit_only else _BASE + "ORDER BY pc.created_at DESC"
    )
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(query).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


__all__ = ["list_pii_documents"]
