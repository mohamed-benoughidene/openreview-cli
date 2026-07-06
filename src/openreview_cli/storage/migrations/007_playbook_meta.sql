-- Playbook metadata table — current version tracking, soft-delete support
CREATE TABLE IF NOT EXISTS playbook_meta (
    playbook_id TEXT PRIMARY KEY,
    current_version INTEGER NOT NULL DEFAULT 1,
    deleted_at TEXT
);

PRAGMA user_version = 7;
