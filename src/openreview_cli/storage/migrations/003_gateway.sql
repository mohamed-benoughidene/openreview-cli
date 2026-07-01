DROP INDEX IF EXISTS idx_cost_logs_review_id;
ALTER TABLE cost_logs RENAME COLUMN review_id TO session_id;
ALTER TABLE cost_logs ADD COLUMN slot TEXT;
CREATE INDEX IF NOT EXISTS idx_cost_logs_session_id ON cost_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_cost_logs_slot ON cost_logs(slot);
