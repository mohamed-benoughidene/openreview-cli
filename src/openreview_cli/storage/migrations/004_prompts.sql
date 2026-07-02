-- Prompt versions (append-only)
CREATE TABLE IF NOT EXISTS prompt_versions (
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL CHECK(length(content) <= 16384),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    tags TEXT,
    description TEXT,
    test_results TEXT,
    optimization_meta TEXT,
    PRIMARY KEY (name, version)
);

-- Prompt-to-slot bindings
CREATE TABLE IF NOT EXISTS prompt_bindings (
    slot TEXT PRIMARY KEY,
    prompt_name TEXT NOT NULL,
    prompt_version INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (prompt_name, prompt_version) REFERENCES prompt_versions(name, version) ON DELETE SET NULL
);

-- Index for listing prompts by name
CREATE INDEX IF NOT EXISTS idx_prompt_versions_name ON prompt_versions(name);

PRAGMA user_version = 4;
