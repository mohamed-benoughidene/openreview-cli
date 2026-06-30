-- Migration 002: PII tables (encrypted mapping cache, audit trail)
-- Schema per data-model.md §4: Schema Migrations

CREATE TABLE IF NOT EXISTS pii_cache (
    document_hash TEXT PRIMARY KEY,
    config_hash TEXT NOT NULL,
    review_result_path TEXT NOT NULL,
    mapping_path TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    expiry_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS pii_audit_trail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_hash TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    entity_count INTEGER NOT NULL,
    entity_type_distribution TEXT NOT NULL,
    processing_time_ms INTEGER NOT NULL,
    config_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('success', 'partial', 'failed')),
    failed_pages TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_document_hash ON pii_audit_trail(document_hash);
CREATE INDEX IF NOT EXISTS idx_cache_expiry ON pii_cache(expiry_at);

INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (2, datetime('now'));
