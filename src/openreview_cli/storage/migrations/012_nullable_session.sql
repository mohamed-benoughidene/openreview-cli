-- Migration: 012_nullable_session.sql
-- Makes session_id nullable in cost_logs. Cost tracking must succeed
-- regardless of whether a session reference is available.
--
-- SQLite does not support ALTER DROP CONSTRAINT. Strategy:
--   1. Ensure sessions table exists (FK target)
--   2. Create new table with nullable session_id
--   3. Copy data
--   4. Drop old table
--   5. Rename new table

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    user_id TEXT,
    tool_version TEXT
);

CREATE TABLE cost_logs_new (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    slot TEXT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cost_cents INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

INSERT INTO cost_logs_new SELECT * FROM cost_logs;
DROP TABLE cost_logs;
ALTER TABLE cost_logs_new RENAME TO cost_logs;

CREATE INDEX IF NOT EXISTS idx_cost_logs_session_id ON cost_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_cost_logs_created_at ON cost_logs(created_at);
