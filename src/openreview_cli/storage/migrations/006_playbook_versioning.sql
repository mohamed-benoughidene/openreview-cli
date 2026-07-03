CREATE TABLE IF NOT EXISTS playbook (
    id TEXT PRIMARY KEY,
    mode TEXT,
    description TEXT,
    author TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS playbook_version (
    id TEXT NOT NULL,
    version TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content TEXT NOT NULL,
    category_count INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (id, version),
    FOREIGN KEY (id) REFERENCES playbook(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_playbook_version_hash ON playbook_version(content_hash);

INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (6, datetime('now'));
