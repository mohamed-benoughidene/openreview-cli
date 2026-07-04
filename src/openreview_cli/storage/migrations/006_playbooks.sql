-- Playbook versions (append-only, mirrors prompt_versions)
CREATE TABLE IF NOT EXISTS playbook_versions (
    playbook_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (playbook_id, version)
);

CREATE INDEX IF NOT EXISTS idx_playbook_versions_lookup
    ON playbook_versions(playbook_id, version DESC);

PRAGMA user_version = 6;
