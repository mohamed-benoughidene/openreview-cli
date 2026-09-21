"""PII governance persistence — audit trail rows and cache persistence.

Writes the results of a PII stripping run into the SQLite governance tables
(``pii_audit_trail``, ``pii_cache``) so that the PII lifecycle commands
(``pii list``, ``pii delete``, retention cleanup) can govern detected PII.

Every strip records one ``pii_audit_trail`` row, clean documents included
(``entity_count`` 0).  The encrypted mapping file, the stripped text and the
``pii_cache`` row are written only when PII was detected.  Mapping encryption
and the legacy ``pii_audit.json`` file are handled by
:func:`openreview_cli.pii.mapping.write_pii_mapping` and
:func:`openreview_cli.pii.audit.write_pii_audit`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from openreview_cli.pii.cache import PiiCache
from openreview_cli.pii.config_hash import compute_config_hash
from openreview_cli.pii.mapping import ensure_encryption_key, write_pii_mapping
from openreview_cli.pii.models import PiiResult

logger = logging.getLogger(__name__)

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

    Always writes one ``pii_audit_trail`` row — a clean document
    (``pii_result.mapping`` empty) records ``entity_count`` 0 with no
    mapping or cache artifacts.  When PII was detected, additionally writes
    the encrypted mapping file, the stripped text and a ``pii_cache`` row.

    Args:
        db_path: Path to the SQLite database (schema initialized).
        document_hash: SHA-256 hex digest of the source document.
        config_hash: Hash of the active privacy config section.
        pii_result: The PII stripping result to persist.
        review_dir: Directory for the encrypted mapping + stripped text files.
        encryption_key: Key used to encrypt the mapping file.
        ttl_days: Cache expiry in days (default 30).
    """
    if pii_result.mapping:
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


__all__ = ["persist_pii_for_document", "persist_pii_result", "write_audit_trail_row"]


def persist_pii_for_document(
    document_path: str | Path,
    pii_result: PiiResult,
    *,
    config_path: Path | None = None,
) -> None:
    """Persist a PII stripping result to the governance lifecycle for one
    document.

    Used by callers that hold only the document path and a PiiResult (the
    bilateral path; the legacy ReviewCommand path; the StripStage in the
    new pipeline). Loads config + encryption key, computes the document
    hash + config hash, and writes the same governance records as
    :func:`persist_pii_result`:

      * one row in ``pii_audit_trail`` on every strip, clean documents
        included (``entity_count`` 0)
      * when PII was detected, additionally the encrypted mapping file at
        ``<data>/reviews/<doc_hash[:12]>/pii_map.enc`` and one row in
        ``pii_cache``

    Persistence failures are non-fatal — a PII strip is the security
    boundary, governance writes must not block it.
    """
    try:
        doc_path = Path(document_path)
        if not doc_path.exists():
            return

        from openreview_cli.config.loader import load_config
        from openreview_cli.config.paths import get_config_dir, get_data_dir

        cfg_path = config_path if config_path is not None else get_config_dir() / "config.yml"
        config = load_config(cfg_path)
        config_hash = compute_config_hash(config.get("privacy", {}))
        encryption_key = ensure_encryption_key(config, cfg_path)

        document_hash = hashlib.sha256(doc_path.read_bytes()).hexdigest()
        review_dir = get_data_dir() / "reviews" / document_hash[:12]
        db_path = get_data_dir() / "openreview.db"

        persist_pii_result(
            db_path,
            document_hash=document_hash,
            config_hash=config_hash,
            pii_result=pii_result,
            review_dir=review_dir,
            encryption_key=encryption_key,
        )
    except Exception as exc:
        logger.warning("PII persistence failed (non-fatal): %s", exc)
