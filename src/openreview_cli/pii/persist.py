"""PII governance persistence — audit trail rows and cache persistence.

Writes the results of a PII stripping run into the SQLite governance tables
(``pii_audit_trail``, ``pii_cache``) so that the PII lifecycle commands
(``pii list``, ``pii delete``, retention cleanup) can govern detected PII.

This module is the DB-persistence half of PII governance.  The encrypted
mapping file and audit JSON file are handled by
:func:`openreview_cli.pii.mapping.write_pii_mapping` and
:func:`openreview_cli.pii.audit.write_pii_audit`.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from openreview_cli.pii.cache import PiiCache
from openreview_cli.pii.mapping import write_pii_mapping
from openreview_cli.pii.models import PiiResult

_VALID_STATUSES = ("success", "partial", "failed")


def write_audit_trail_row(
    db_path: Path,
    *,
    document_hash: str,
    config_hash: str,
    pii_result: PiiResult,
    status: str,
) -> None:
    """Write one row to the ``pii_audit_trail`` table.

    Args:
        db_path: Path to the SQLite database (schema initialized).
        document_hash: SHA-256 hex digest of the source document.
        config_hash: Hash of the active privacy config section.
        pii_result: The PII stripping result to record.
        status: One of ``"success"``, ``"partial"``, ``"failed"``.
    """
    if status not in _VALID_STATUSES:
        raise ValueError(f"status must be one of {_VALID_STATUSES}, got {status!r}")

    entity_count = len(pii_result.entities)
    entity_type_distribution: dict[str, int] = {}
    for entity in pii_result.entities:
        t = entity.entity_type
        entity_type_distribution[t] = entity_type_distribution.get(t, 0) + 1

    processing_time_ms = int(pii_result.duration_seconds * 1000)
    timestamp = datetime.now(UTC).isoformat()
    failed_pages = json.dumps(pii_result.failed_pages or [])

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO pii_audit_trail "
            "(document_hash, timestamp, entity_count, entity_type_distribution, "
            " processing_time_ms, config_hash, status, failed_pages) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                document_hash,
                timestamp,
                entity_count,
                json.dumps(entity_type_distribution, sort_keys=True),
                processing_time_ms,
                config_hash,
                status,
                failed_pages,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def persist_pii_result(
    db_path: Path,
    *,
    document_hash: str,
    config_hash: str,
    pii_result: PiiResult,
    review_dir: Path,
    encryption_key: str,
    ttl_days: int = 30,
) -> None:
    """Persist a PII stripping result to the PII governance lifecycle.

    When ``pii_result.mapping`` is non-empty (PII was detected), writes the
    encrypted mapping file, the stripped text, a ``pii_cache`` row and a
    ``pii_audit_trail`` row.  When the mapping is empty (no PII detected)
    nothing is written — there is nothing to govern.

    Args:
        db_path: Path to the SQLite database (schema initialized).
        document_hash: SHA-256 hex digest of the source document.
        config_hash: Hash of the active privacy config section.
        pii_result: The PII stripping result to persist.
        review_dir: Directory for the encrypted mapping + stripped text files.
        encryption_key: Key used to encrypt the mapping file.
        ttl_days: Cache expiry in days (default 30).
    """
    if not pii_result.mapping:
        return

    mapping_path = write_pii_mapping(pii_result.mapping, review_dir, encryption_key)

    review_result_path = review_dir / "stripped.txt"
    review_result_path.write_text(pii_result.stripped_text, encoding="utf-8")

    PiiCache(db_path).put(
        document_hash,
        config_hash,
        str(review_result_path),
        str(mapping_path),
        ttl_days=ttl_days,
    )

    write_audit_trail_row(
        db_path,
        document_hash=document_hash,
        config_hash=config_hash,
        pii_result=pii_result,
        status="partial" if pii_result.failed_pages else "success",
    )


__all__ = ["persist_pii_result", "write_audit_trail_row"]
