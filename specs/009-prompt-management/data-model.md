# Data Model: Prompt Management

**Feature**: 009-prompt-management | **Date**: 2026-07-02

## Entities

### Prompt (logical)

A named, versioned artifact. Not a single table row — represented by the `prompt_versions` table with a shared `name`.

| Attribute | Type | Constraints | Notes |
|-----------|------|-------------|-------|
| name | TEXT | NOT NULL, part of composite PK | Unique identifier |
| version | INTEGER | NOT NULL, part of composite PK | Auto-incremented per name |
| content | TEXT | NOT NULL, max 16 KB | Prompt instruction text |
| created_at | TEXT | NOT NULL, ISO 8601 | Timestamp |
| tags | TEXT | NULLABLE | JSON array of tags |
| description | TEXT | NULLABLE | Human-readable description |
| test_results | TEXT | NULLABLE | JSON array of A/B test outcomes |
| optimization_meta | TEXT | NULLABLE | JSON object with GRPO run metadata |

### PromptBinding

Associates a gateway model slot with a specific prompt version.

| Attribute | Type | Constraints | Notes |
|-----------|------|-------------|-------|
| slot | TEXT | PRIMARY KEY | Gateway slot name (extraction, reasoning, etc.) |
| prompt_name | TEXT | NOT NULL | References prompt name |
| prompt_version | INTEGER | NOT NULL | References specific version |
| created_at | TEXT | NOT NULL, ISO 8601 | When binding was created |

### PromptStore (service)

Not a table — a Python class that wraps SQLite operations.

**Methods**:
- `create(name, content, metadata) → PromptVersion` — create version 1
- `update(name, content, metadata) → PromptVersion` — create next version
- `get(name, version) → PromptVersion` — get specific version
- `get_latest(name) → PromptVersion` — get latest version
- `list(page, per_page) → list[Prompt]` — list all prompts with latest version
- `delete(name)` — delete all versions
- `resolve(slot_name) → str` — resolve prompt content for a gateway slot
- `bind(slot, name, version)` — create binding
- `unbind(slot)` — remove binding
- `bindings() → list[PromptBinding]` — list all bindings
- `export(name) → dict` — export prompt with all versions
- `import_prompt(data)` — import from export format

## SQLite Schema

### Migration 004: `004_prompts.sql`

```sql
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

-- Update schema version
PRAGMA user_version = 4;
```

## Validation Rules

| Rule | Implementation |
|------|---------------|
| Content max 16 KB | SQLite CHECK constraint + Pydantic validator |
| (name, version) unique | Composite PRIMARY KEY |
| Slot must be valid | Gateway `VALID_SLOTS` set: {reasoning, extraction, embedding, reranking, graph} |
| Binding references existing version | Foreign key constraint |
| Version auto-increment | `SELECT MAX(version) + 1 FROM prompt_versions WHERE name = ?` |

## State Transitions

**None** — append-only versioning. Versions are immutable once created. Delete removes all versions of a prompt.

## Relationships

```
prompt_versions (name, version)
    ↓ (1:N by name)
prompt_versions (all versions of same prompt)

prompt_bindings (slot)
    ↓ (N:1)
prompt_versions (name, version)
```

## Memory Budget

| Operation | Estimated Memory |
|-----------|-----------------|
| Create/update | <1 MB (SQLite insert) |
| List (1 page) | <1 MB (25 rows) |
| Resolve | <100 KB (single prompt content) |
| Export | <1 MB (YAML serialization) |
| Import | <1 MB (YAML parsing) |

All well under 100 MB constitutional limit.
