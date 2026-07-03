# Data Model: Playbook Versioning

**Phase**: 1 — Design & Contracts
**Date**: 2026-07-03

## Entity-Relationship Overview

```
PlaybookRecord (1) ──── (N) PlaybookVersion (1) ──── (N) ReviewReport
     │                         │                           │
     │                         │                           │
     │ id (PK)                 │ (id, version) (PK)        │ playbook_id = <id>@<version>
     │ mode                    │ FK → PlaybookRecord.id    │ (flat string, no FK)
     │ description             │ content_hash              │
     │ author                  │ content (full YAML)       │
                               │ created_at                │
                               │ category_count            │
```

**§6.7 scope note**: Single-party only. ReviewReport references PlaybookVersion via a flat string (`<id>@<version>`), not via a foreign key. SQLite-based report storage is deferred to a future phase.

## Entity: Position3

The 3-position taxonomy replacing the existing Position enum with decision-oriented vocabulary. Defined as a Python `StrEnum` in `review/models.py`.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| value | str (enum) | `preferred`, `acceptable`, `walkaway`, `uncertain` | Decision-oriented position label |

**Validation rules**:
- `uncertain` is assigned by the pipeline only (extraction + QA disagreement, or low confidence), never set from YAML
- Old names (`favorable`, `neutral`, `unfavorable`) are accepted at parse time and mapped to the new values
- `default_position` in YAML accepts both old and new names (mapped on load)

**§6.4 mapping**: Preferred → benefits reviewing party, Acceptable → neutral/standard market, Walkaway → harms reviewing party, Uncertain → Amber (pipeline ambiguity).

**§6.5 rationale**: Positions are "model parameters" — versioned, tested, optimized like prompts. The Position3 enum exists per-playbook-version, not globally, since each version may redefine what "preferred" means for a given category.

## Entity: PlaybookRecord

Top-level playbook metadata in SQLite. Populated on first store of any version of a playbook. One row per `id`.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | TEXT | NOT NULL | — | Playbook identifier (e.g., `"precheck-nda-v1"`) — primary key |
| `mode` | TEXT | NOT NULL | — | Product mode this playbook serves (e.g., `"precheck"`) |
| `description` | TEXT | NULL | — | Human-readable description from YAML metadata |
| `author` | TEXT | NULL | — | Author name from YAML metadata |

**Primary key**: `id`

**Relationships**:
- One-to-many: `PlaybookRecord` → `PlaybookVersion`
- Children: `PlaybookVersion.id` is FK → `PlaybookRecord.id`

**Validation rules**:
- `id` must be non-empty, kebab-case or snake_case (no spaces, no special chars beyond `-` and `_`)
- `mode` must be one of the known product modes (checked against registry — `precheck`, `dealcheck`, `hirecheck` initially per Q-4)
- `description` and `author` may be updated on subsequent version loads (soft update — only the latest values are stored in the metadata row). Authorship drift is tracked through version history, not through this row.

**State transitions**: None. INSERT on first version load. UPDATE for `description`/`author` on subsequent version loads with different metadata values. No DELETE.

## Entity: PlaybookVersion

A specific, immutable version of a playbook. One row per `(id, version)` pair.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | TEXT | NOT NULL | — | Playbook identifier (FK → PlaybookRecord.id) |
| `version` | TEXT | NOT NULL | — | Semver string, possibly with `+N` content-change suffix |
| `content_hash` | TEXT | NOT NULL | — | SHA-256 hex digest of raw YAML content |
| `content` | TEXT | NOT NULL | — | Full YAML content text (for reproduction from DB) |
| `created_at` | TEXT | NOT NULL | — | ISO-8601 timestamp when first loaded |
| `category_count` | INTEGER | NOT NULL | 0 | Number of categories in this playbook version |

**Primary key**: `(id, version)`

**Foreign key**: `id` → `PlaybookRecord.id` (CASCADE on delete — if a playbook record is deleted, all its versions are deleted)

**Indexes**:
- `idx_pv_id_version` on `(id, version)` — PK lookup (already covered by PK)
- `idx_pv_content_hash` on `(content_hash)` — content-change detection lookup

**Validation rules**:
- `version` must be a valid semver string (major.minor.patch, optionally with `+N` build suffix). Pattern: `^\d+\.\d+\.\d+(\+\d+)?$`
- `content_hash` must be a valid SHA-256 hex string (64 hex characters)
- `content` must be valid YAML (verified at parse time, before storage)
- `created_at` must be ISO-8601 format (e.g., `"2026-07-03T12:00:00"`)
- `category_count` must be >= 0, must match the parsed category count

**State transitions**:
- INSERT-only: versions are immutable once stored
- No UPDATE path for an existing `(id, version)` pair
- When content changes with same version: INSERT new row with `version+"+<N>"` where `N` is auto-incremented (FR-4)
- No DELETE in NX-3 scope (future `--prune-playbook-versions` flag may add this)

**Content-change suffix algorithm** (per Q3):
```
def next_content_version(id: str, version: str) -> str:
    """Compute the next +N suffix for a content-changed playbook version."""
    max_n = query("SELECT MAX(CAST(SUBSTR(version, INSTR(version, '+') + 1) AS INTEGER)) "
                  "FROM playbook_version WHERE id=? AND version LIKE ? || '+%'",
                  (id, version))
    n = (max_n or 0) + 1
    return f"{version}+{n}"
```

## Entity: ReviewReport (version-extension)

The existing `ReviewReport` dataclass (spec 011) already has a `playbook_id` field. NX-3 changes the format from a bare playbook ID to `<id>@<version>`.

| Field | Type | Existing? | NX-3 Change |
|-------|------|-----------|-------------|
| `playbook_id` | str | Yes | Format changes to `<id>@<version>` (e.g., `"precheck-nda-v1@1.0.0"`) |

No new fields are added to ReviewReport for NX-3. The `playbook_version_rowid` field is deferred (requires SQLite report storage, which is out of scope).

**Validation**: The `@` in `playbook_id` is the canonical separator. Code that reads `playbook_id` without parsing the `@` format still works (the prefix before `@` is the playbook ID).

## SQL Schema

```sql
-- Table: playbook (top-level metadata)
CREATE TABLE IF NOT EXISTS playbook (
    id          TEXT PRIMARY KEY NOT NULL,
    mode        TEXT NOT NULL,
    description TEXT,
    author      TEXT
);

-- Table: playbook_version (immutable version records)
CREATE TABLE IF NOT EXISTS playbook_version (
    id             TEXT NOT NULL REFERENCES playbook(id) ON DELETE CASCADE,
    version        TEXT NOT NULL,
    content_hash   TEXT NOT NULL,
    content        TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    category_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (id, version)
);

-- Index for content-hash lookups (change detection)
CREATE INDEX IF NOT EXISTS idx_playbook_version_hash 
    ON playbook_version(content_hash);
```

## Data Flow

```
YAML file on disk
    │
    ▼
1. Read raw bytes → hashlib.sha256()
    │
    ├──► content_hash ← hex digest
    │
    ▼
2. yaml.safe_load() → Python dict
    │
    ├──► extract id, version, categories
    ├──► map position names (old → new)
    │
    ▼
3. SQLite query: (id, version) in playbook_version?
    │
    ├── found + hash match → reuse existing record
    ├── found + hash mismatch → insert version+"+<N>"
    └── not found → insert new record (and PlaybookRecord if first)
    │
    ▼
4. Return PlaybookVersion with row info
    │
    ▼
5. Review pipeline uses versioned playbook for assessments
    │
    ▼
6. ReviewReport.playbook_id = "<id>@<version>"
```

## State Transition Diagram

```
[YAML on disk] ──load──► [parsed dict] 
                            │
                            ├──► [no DB record] ──► INSERT PlaybookRecord + INSERT PlaybookVersion
                            │
                            ├──► [DB record, hash match] ──► reuse (no INSERT)
                            │
                            └──► [DB record, hash mismatch] ──► INSERT PlaybookVersion(version+"+N")
                                                            │
                                                            └──► warn "content changed"
```

All transitions are idempotent — running the same YAML file through the loader multiple times produces the same state (no duplicate rows).

## Key Citations

- **§6.4**: 3-position framework (Preferred/Acceptable/Walkaway + Amber for uncertain) — answers F1≤64% ceiling
- **§6.5**: Playbook positions are model parameters — must be versioned, tested, optimized
- **§6.7**: Single-party review only; bilateral comparison deferred to NX-1
- **C-03**: SQLite storage layer — existing infrastructure
- **C-22**: 3-position playbook system — existing YAML loader
- **C-23**: Version-stamped reviews — audit trail for ORPHAN-2
- **Q-4**: Three modes first (PreCheck, DealCheck, HireCheck)
- **Q-7**: Task-level routing, not document-type
- **Q-8**: G/A/R output format
- **R-7**: Single-party scope only
