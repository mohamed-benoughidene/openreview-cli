-- D-31: Persistent recovery state across CLI invocations
CREATE TABLE IF NOT EXISTS recovery_state (
    id TEXT PRIMARY KEY,
    pipeline_id TEXT NOT NULL,
    stage_name TEXT NOT NULL,
    context_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_recovery_state_pipeline ON recovery_state(pipeline_id);

PRAGMA user_version = 9;
