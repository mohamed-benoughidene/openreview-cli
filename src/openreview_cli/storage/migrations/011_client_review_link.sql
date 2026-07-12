-- Migration 011: Link review_reports to clients (FR-025a client detail view)
ALTER TABLE review_reports ADD COLUMN client_id TEXT;
CREATE INDEX IF NOT EXISTS idx_review_reports_client_id ON review_reports(client_id);
