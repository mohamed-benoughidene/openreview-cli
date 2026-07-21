-- Migration 013: Recreate cost_logs with TEXT id, nullable session_id, no FK.
--
-- The production database had a legacy schema with:
--   id INTEGER PRIMARY KEY AUTOINCREMENT  (crashes on UUID string insert)
--   session_id TEXT  (nullable, FK -> sessions, no longer exists)
--
-- The fresh-migration schema (001+003) instead has:
--   id TEXT PRIMARY KEY
--   session_id TEXT NOT NULL REFERENCES reviews(id)
--
-- This migration replaces BOTH with a single canonical target (also merging
-- the spec 035 change to make session_id nullable and drop the FK):
--   id TEXT PRIMARY KEY
--   session_id TEXT  (nullable, no FK)
--   slot TEXT  (nullable)
--   provider TEXT NOT NULL
--   model TEXT NOT NULL
--   prompt_tokens INTEGER DEFAULT 0
--   completion_tokens INTEGER DEFAULT 0
--   cost_cents INTEGER NOT NULL
--   created_at TEXT NOT NULL DEFAULT (datetime('now'))

CREATE TABLE IF NOT EXISTS cost_logs_new (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    slot TEXT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    cost_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO cost_logs_new (
    id, session_id, slot, provider, model,
    prompt_tokens, completion_tokens, cost_cents, created_at
)
SELECT
    CAST(id AS TEXT), session_id, slot, provider, model,
    prompt_tokens, completion_tokens, cost_cents, created_at
FROM cost_logs
WHERE NOT EXISTS (SELECT 1 FROM cost_logs_new);

DROP TABLE IF EXISTS cost_logs;
ALTER TABLE cost_logs_new RENAME TO cost_logs;

CREATE INDEX IF NOT EXISTS idx_cost_logs_session_id ON cost_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_cost_logs_slot ON cost_logs(slot);
