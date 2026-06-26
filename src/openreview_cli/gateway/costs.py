import sqlite3
import time
from pathlib import Path
from typing import Any

from openreview_cli.config.paths import get_data_dir
from openreview_cli.gateway.models import CostRecord, ReviewSession


class CostStore:
    """Manages SQLite storage for cost tracking and session state."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is not None:
            self.db_path = db_path
        else:
            self.db_path = get_data_dir() / "gateway.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS review_sessions (
                    session_id TEXT PRIMARY KEY,
                    started_at REAL NOT NULL,
                    ended_at REAL,
                    total_cost_usd REAL NOT NULL DEFAULT 0.0,
                    total_input_tokens INTEGER NOT NULL DEFAULT 0,
                    total_output_tokens INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cost_records (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES review_sessions(session_id),
                    slot TEXT NOT NULL,
                    model TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    fallback_used INTEGER NOT NULL CHECK (fallback_used IN (0, 1)),
                    latency_ms INTEGER NOT NULL
                )
            """)
            conn.commit()

    def create_session(self, session_id: str) -> ReviewSession:
        """Create a new review session in the store."""
        sess = ReviewSession(
            session_id=session_id,
            started_at=time.time(),
        )
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO review_sessions
                (session_id, started_at, ended_at, total_cost_usd, total_input_tokens, total_output_tokens)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    sess.session_id,
                    sess.started_at,
                    sess.ended_at,
                    sess.total_cost_usd,
                    sess.total_input_tokens,
                    sess.total_output_tokens,
                ),
            )
            conn.commit()
        return sess

    def get_session(self, session_id: str) -> ReviewSession | None:
        """Retrieve a review session from the store."""
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT session_id, started_at, ended_at, total_cost_usd, total_input_tokens, total_output_tokens
                FROM review_sessions WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
            if row:
                return ReviewSession(
                    session_id=row["session_id"],
                    started_at=row["started_at"],
                    ended_at=row["ended_at"],
                    total_cost_usd=row["total_cost_usd"],
                    total_input_tokens=row["total_input_tokens"],
                    total_output_tokens=row["total_output_tokens"],
                )
            return None

    def complete_session(self, session_id: str) -> None:
        """Mark a review session as completed."""
        now = time.time()
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE review_sessions SET ended_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            conn.commit()

    def insert_record(self, record: CostRecord) -> None:
        """Insert a cost record and update session totals."""
        with self._get_conn() as conn:
            # First ensure the session exists (implicit/lazy session creation)
            conn.execute(
                """
                INSERT OR IGNORE INTO review_sessions
                (session_id, started_at, ended_at, total_cost_usd, total_input_tokens, total_output_tokens)
                VALUES (?, ?, NULL, 0.0, 0, 0)
                """,
                (record.session_id, record.timestamp),
            )
            # Insert cost record
            conn.execute(
                """
                INSERT INTO cost_records
                (session_id, slot, model, provider, input_tokens, output_tokens, cost_usd, timestamp, fallback_used, latency_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.session_id,
                    record.slot,
                    record.model,
                    record.provider,
                    record.input_tokens,
                    record.output_tokens,
                    record.cost_usd,
                    record.timestamp,
                    1 if record.fallback_used else 0,
                    record.latency_ms,
                ),
            )
            # Update session totals
            conn.execute(
                """
                UPDATE review_sessions
                SET total_cost_usd = total_cost_usd + ?,
                    total_input_tokens = total_input_tokens + ?,
                    total_output_tokens = total_output_tokens + ?
                WHERE session_id = ?
                """,
                (
                    record.cost_usd,
                    record.input_tokens,
                    record.output_tokens,
                    record.session_id,
                ),
            )
            conn.commit()

    def get_session_cost(self, session_id: str) -> float:
        """Get total cost (USD) for a specific session."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(total_cost_usd, 0.0) FROM review_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return float(row[0]) if row else 0.0

    def get_daily_cost(self) -> float:
        """Get total cost (USD) for today (UTC)."""
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(cost_usd), 0.0) FROM cost_records
                WHERE date(timestamp, 'unixepoch') = date('now')
                """
            ).fetchone()
            return float(row[0]) if row else 0.0

    def clear(self) -> None:
        """Clear all cost and session records."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM cost_records")
            conn.execute("DELETE FROM review_sessions")
            conn.commit()

    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM review_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return bool(row)

    def get_summary(
        self, days: float | None = None, session_id: str | None = None
    ) -> dict[str, Any]:
        """Get aggregated cost and token statistics."""
        where_clauses = []
        params: list[Any] = []

        if session_id is not None:
            where_clauses.append("session_id = ?")
            params.append(session_id)
        elif days is not None:
            cutoff = time.time() - (days * 86400)
            where_clauses.append("timestamp >= ?")
            params.append(cutoff)

        where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        with self._get_conn() as conn:
            # Overall totals
            tot = conn.execute(
                f"""
                SELECT
                    COALESCE(SUM(cost_usd), 0.0) as total_cost,
                    COALESCE(SUM(input_tokens), 0) as total_input,
                    COALESCE(SUM(output_tokens), 0) as total_output,
                    COUNT(record_id) as total_calls
                FROM cost_records
                {where_str}
                """,
                params,
            ).fetchone()

            # By slot
            slots_rows = conn.execute(
                f"""
                SELECT
                    slot,
                    COALESCE(SUM(cost_usd), 0.0) as cost,
                    COALESCE(SUM(input_tokens + output_tokens), 0) as tokens,
                    COUNT(record_id) as calls
                FROM cost_records
                {where_str}
                GROUP BY slot
                """,
                params,
            ).fetchall()

            # By provider
            prov_rows = conn.execute(
                f"""
                SELECT
                    provider,
                    COALESCE(SUM(cost_usd), 0.0) as cost,
                    COALESCE(SUM(input_tokens + output_tokens), 0) as tokens,
                    COUNT(record_id) as calls
                FROM cost_records
                {where_str}
                GROUP BY provider
                """,
                params,
            ).fetchall()

        return {
            "total_cost": float(tot["total_cost"]),
            "total_input": int(tot["total_input"]),
            "total_output": int(tot["total_output"]),
            "total_calls": int(tot["total_calls"]),
            "slots": {
                r["slot"]: {"cost": r["cost"], "tokens": r["tokens"], "calls": r["calls"]}
                for r in slots_rows
            },
            "providers": {
                r["provider"]: {"cost": r["cost"], "tokens": r["tokens"], "calls": r["calls"]}
                for r in prov_rows
            },
        }
