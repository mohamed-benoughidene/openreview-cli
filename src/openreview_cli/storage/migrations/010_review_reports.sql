-- Migration 010: Review reports storage for TUI recent-reviews list
-- Enables US2: returning user re-opens past review

CREATE TABLE IF NOT EXISTS review_reports (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    mode TEXT NOT NULL,
    report_json TEXT NOT NULL,
    green_count INTEGER DEFAULT 0,
    amber_count INTEGER DEFAULT 0,
    red_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_review_reports_created_at ON review_reports(created_at);
