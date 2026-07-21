"""Migration 013: migrate cost_logs to TEXT id, nullable session_id, no FK.

Handles two legacy schemas:

Legacy (production DB)
  ``id INTEGER PRIMARY KEY AUTOINCREMENT``, ``session_id TEXT`` (nullable,
  FK -> sessions), ``slot TEXT NOT NULL`` (column 3).

Fresh migration (001+003)
  ``id TEXT PRIMARY KEY``, ``session_id TEXT NOT NULL REFERENCES reviews(id)``,
  ``slot TEXT`` (column 9, nullable).

Target: ``id TEXT PRIMARY KEY``, ``session_id TEXT`` (nullable, no FK),
``slot TEXT`` (nullable).  Also merges the spec 035 changes (nullable
session_id, drop the reviews FK) in one shot.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

TARGET_DDL = """\
CREATE TABLE IF NOT EXISTS cost_logs_target (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    slot TEXT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    cost_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)"""


def migrate(conn: Any) -> None:
    """Run the migration (called by ``_exec_py_migration``)."""

    # ── 1. Detect current state ──────────────────────────────────────
    has_old = conn.execute(
        "SELECT name FROM sqlite_master WHERE name='cost_logs'",
    ).fetchone()
    has_new = conn.execute(
        "SELECT name FROM sqlite_master WHERE name='cost_logs_target'",
    ).fetchone()

    # Both tables gone — nothing to do (data already migrated).
    if not has_old and not has_new:
        logger.warning("013: cost_logs and cost_logs_target both missing — nothing to migrate")
        return

    # Only target exists — already migrated.
    if not has_old and has_new:
        logger.info("013: cost_logs already migrated (only target table found)")
        return

    # ── 2. Check if cost_logs already matches the target schema ──────
    ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='cost_logs'",
    ).fetchone()
    if ddl_row is not None:
        ddl: str = ddl_row[0]
        if "TEXT" in ddl and "NOT NULL" not in ddl and "REFERENCES" not in ddl:
            logger.info("013: cost_logs already has target schema — skipping")
            return

    # ── 3. Handle partial-run state (cost_logs_target exists) ────────
    if has_new:
        cnt = conn.execute("SELECT COUNT(*) FROM cost_logs_target").fetchone()[0]
        if cnt == 0:
            conn.execute("DROP TABLE IF EXISTS cost_logs_target")
            logger.info("013: cleaned up empty leftover cost_logs_target")
        else:
            # cost_logs_target has data from a previous partial run;
            # cost_logs still exists too.  Re-insert would duplicate.
            # Drop the partial copy and redo cleanly.
            conn.execute("DROP TABLE IF EXISTS cost_logs_target")
            logger.info("013: dropped stale cost_logs_target with %d rows", cnt)

    # 3a — also drop a stale cost_logs_target if CREATE TABLE below failed
    conn.execute("DROP TABLE IF EXISTS cost_logs_target")

    # ── 4. Create target table & copy data ────────────────────────────
    conn.execute(TARGET_DDL)

    copy_sql = """\
INSERT INTO cost_logs_target (id, session_id, slot, provider, model,
                              prompt_tokens, completion_tokens, cost_cents,
                              created_at)
SELECT CAST(id AS TEXT), session_id, slot, provider, model,
       COALESCE(prompt_tokens, 0), COALESCE(completion_tokens, 0),
       COALESCE(cost_cents, 0), created_at
FROM cost_logs"""

    row_count = conn.execute("SELECT COUNT(*) AS cnt FROM cost_logs").fetchone()
    logger.info("013: copying %d rows from cost_logs → cost_logs_target", row_count["cnt"])
    conn.execute(copy_sql)

    # ── 5. Swap tables ────────────────────────────────────────────────
    conn.execute("DROP TABLE IF EXISTS cost_logs")
    conn.execute("ALTER TABLE cost_logs_target RENAME TO cost_logs")

    # ── 6. Indexes ────────────────────────────────────────────────────
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cost_logs_session_id ON cost_logs(session_id)",
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cost_logs_slot ON cost_logs(slot)")

    migrated = conn.execute("SELECT COUNT(*) AS cnt FROM cost_logs").fetchone()
    logger.info("013: migration complete — cost_logs now has %d rows", migrated["cnt"])
