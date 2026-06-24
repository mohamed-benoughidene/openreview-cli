-- Migration 001: Initial schema
-- Creates all Phase 1 tables

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id),
    contract_path TEXT NOT NULL,
    contract_hash TEXT NOT NULL,
    playbook_version INTEGER DEFAULT 0,
    mode TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'completed')),
    total_questions INTEGER DEFAULT 0,
    deviations INTEGER DEFAULT 0,
    cost_cents INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    memo_path TEXT
);

CREATE TABLE IF NOT EXISTS review_diffs (
    id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL REFERENCES reviews(id),
    question_key TEXT NOT NULL,
    contract_answer TEXT,
    playbook_value TEXT,
    status TEXT NOT NULL
        CHECK (status IN ('match', 'deviation', 'missing')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cost_logs (
    id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL REFERENCES reviews(id),
    model TEXT NOT NULL,
    provider TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    cost_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reviews_client_id ON reviews(client_id);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status);
CREATE INDEX IF NOT EXISTS idx_review_diffs_review_id ON review_diffs(review_id);
CREATE INDEX IF NOT EXISTS idx_cost_logs_review_id ON cost_logs(review_id);
CREATE INDEX IF NOT EXISTS idx_cost_logs_created_at ON cost_logs(created_at);

INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (1, datetime('now'));
