"""GDPR-aligned retention for encrypted PII mappings.

- 30-day default expiry for encrypted PII mappings
- On-demand deletion via document hash prefix
- Background cleanup of expired entries
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def _get_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def cleanup_expired(db_path: Path) -> int:
    now = datetime.now(UTC).isoformat()
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT document_hash, mapping_path, review_result_path FROM pii_cache WHERE expiry_at < ?",
            (now,),
        ).fetchall()
        for row in rows:
            for path_key in ("mapping_path", "review_result_path"):
                p = Path(row[path_key])
                if p.exists():
                    p.unlink()
        expired_hashes = tuple(r["document_hash"] for r in rows)
        if expired_hashes:
            placeholders = ",".join("?" for _ in expired_hashes)
            conn.execute(
                f"DELETE FROM pii_audit_trail WHERE document_hash IN ({placeholders})",
                expired_hashes,
            )
        deleted = conn.execute("DELETE FROM pii_cache WHERE expiry_at < ?", (now,)).rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()


def delete_pii_data(db_path: Path, document_hash_prefix: str) -> dict[str, bool | int]:
    if len(document_hash_prefix) < 8:
        raise ValueError("document_hash_prefix must be at least 8 characters")
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT document_hash, mapping_path, review_result_path FROM pii_cache WHERE document_hash LIKE ?",
            (f"{document_hash_prefix}%",),
        ).fetchall()
        if not rows:
            return {"mapping_removed": False, "audit_records": 0, "cache_removed": False}
        for row in rows:
            for path_key in ("mapping_path", "review_result_path"):
                p = Path(row[path_key])
                if p.exists():
                    p.unlink()
        cache_deleted = conn.execute(
            "DELETE FROM pii_cache WHERE document_hash LIKE ?",
            (f"{document_hash_prefix}%",),
        ).rowcount
        audit_count = conn.execute(
            "DELETE FROM pii_audit_trail WHERE document_hash LIKE ?",
            (f"{document_hash_prefix}%",),
        ).rowcount
        conn.commit()
        return {
            "mapping_removed": True,
            "audit_records": audit_count,
            "cache_removed": cache_deleted > 0,
        }
    finally:
        conn.close()


__all__ = ["cleanup_expired", "delete_pii_data"]
