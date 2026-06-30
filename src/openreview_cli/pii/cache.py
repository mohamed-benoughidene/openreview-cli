"""PiiCache — SQLite-backed cache for PII processing results.

Wraps the pii_cache table for config change detection and expiry management.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class PiiCache:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _get_conn(self) -> Any:
        import sqlite3

        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get(self, document_hash: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM pii_cache WHERE document_hash = ?", (document_hash,)
            ).fetchone()
            if row is None:
                return None
            return dict(row)
        finally:
            conn.close()

    def put(
        self,
        document_hash: str,
        config_hash: str,
        review_result_path: str,
        mapping_path: str,
        ttl_days: int = 30,
    ) -> None:
        now = datetime.now(UTC)
        expiry = now + timedelta(days=ttl_days)
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO pii_cache "
                "(document_hash, config_hash, review_result_path, mapping_path, created_at, expiry_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    document_hash,
                    config_hash,
                    review_result_path,
                    mapping_path,
                    now.isoformat(),
                    expiry.isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def is_valid(self, document_hash: str, current_config_hash: str) -> bool:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT 1 FROM pii_cache WHERE document_hash = ? AND config_hash = ?",
                (document_hash, current_config_hash),
            ).fetchone()
            return row is not None
        finally:
            conn.close()


__all__ = ["PiiCache"]
