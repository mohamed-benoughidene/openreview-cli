-- openreview SQLite Schema — Contract
-- Phase 1: Config + Storage Foundation
--
-- Migration 001: Initial schema
-- Applies to: main database (openreview.db)
--
-- This schema is forward-only. Rollback is done by restoring from backup.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Clients
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,                          -- slug: "acme"
    name TEXT NOT NULL,                           -- display name: "Acme Corp"
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Reviews
CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,                          -- "2026-06-21_acme-nda"
    client_id TEXT NOT NULL REFERENCES clients(id),
    contract_path TEXT NOT NULL,                   -- path to original contract file
    contract_hash TEXT NOT NULL,                   -- SHA-256 for dedup
    playbook_version INTEGER DEFAULT 0,            -- version of playbook used
    mode TEXT NOT NULL,                            -- "precheck", "hirecheck", ...
    status TEXT NOT NULL DEFAULT 'in_progress'     -- 'in_progress' | 'completed'
        CHECK (status IN ('in_progress', 'completed')),
    total_questions INTEGER DEFAULT 0,
    deviations INTEGER DEFAULT 0,
    cost_cents INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    memo_path TEXT                                 -- path to generated memo file
);

-- Review diffs (per-question comparison results)
CREATE TABLE IF NOT EXISTS review_diffs (
    id TEXT PRIMARY KEY,                           -- UUID
    review_id TEXT NOT NULL REFERENCES reviews(id),
    question_key TEXT NOT NULL,                    -- "confidentiality_period"
    contract_answer TEXT,                          -- what the contract says
    playbook_value TEXT,                           -- P, A, or W
    status TEXT NOT NULL                           -- 'match' | 'deviation' | 'missing'
        CHECK (status IN ('match', 'deviation', 'missing')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Cost logs (immutable, one row per API call)
CREATE TABLE IF NOT EXISTS cost_logs (
    id TEXT PRIMARY KEY,                           -- UUID
    review_id TEXT NOT NULL REFERENCES reviews(id),
    model TEXT NOT NULL,                           -- "openai/gpt-4o"
    provider TEXT NOT NULL,                        -- "openai", "anthropic", "ollama"
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    cost_cents INTEGER NOT NULL,                   -- integer cents, no floats
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_reviews_client_id ON reviews(client_id);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status);
CREATE INDEX IF NOT EXISTS idx_review_diffs_review_id ON review_diffs(review_id);
CREATE INDEX IF NOT EXISTS idx_cost_logs_review_id ON cost_logs(review_id);
CREATE INDEX IF NOT EXISTS idx_cost_logs_created_at ON cost_logs(created_at);
