# Phase 1 — Data Model: 3-Position Playbook with Versioning

## 1. New Entity: VersionedPlaybook

The `VersionedPlaybook` entity represents an immutable snapshot of a playbook at a specific version number. It lives in the local SQLite database.

### Table: `playbook_versions`

```sql
-- Migration 006: Playbook versioning (append-only, mirrors prompt_versions)
CREATE TABLE IF NOT EXISTS playbook_versions (
    playbook_id TEXT NOT NULL,
    version     INTEGER NOT NULL,
    content     TEXT NOT NULL,  -- JSON-serialized Playbook dataclass
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (playbook_id, version)
);
CREATE INDEX IF NOT EXISTS idx_playbook_versions_lookup
    ON playbook_versions(playbook_id, version DESC);
```

### Python representation

```python
@dataclass
class VersionedPlaybook:
    playbook_id: str
    version: int
    content: str  # JSON string of the serialized Playbook
    created_at: str  # ISO-8601 datetime string
```

### Lookup patterns

- **Latest version**: `SELECT * FROM playbook_versions WHERE playbook_id = ? ORDER BY version DESC LIMIT 1`
- **Specific version**: `SELECT * FROM playbook_versions WHERE playbook_id = ? AND version = ?`
- **All playbooks (latest per ID)**: `SELECT playbook_id, MAX(version) AS version, created_at FROM playbook_versions GROUP BY playbook_id ORDER BY playbook_id`
- **Next version number**: `SELECT COALESCE(MAX(version), 0) + 1 FROM playbook_versions WHERE playbook_id = ?`

## 2. Existing Entities (modified)

### Playbook (existing — YAML schema unchanged at file level)

```yaml
# YAML playbook schema (with new position keys + legacy key support)
id: nda-v2
mode: precheck
metadata:
  version: "2.0"
  description: Standard NDA v2
  author: Legal Team
categories:
  - id: confidentiality
    name: Confidentiality
    description: Provisions governing confidential information
    preferred:          # ← renamed from "favorable"
      description: Broad mutual protection
      exemplars:
        - "Each party agrees to hold..."
    acceptable:         # ← renamed from "neutral"
      description: Standard one-way protection
      exemplars:
        - "Receiving party shall..."
    walkaway:           # ← renamed from "unfavorable"
      description: No confidentiality clause
      exemplars:
        - "Information may be disclosed..."
    default_position: preferred  # ← renamed from "favorable"
```

### Position enum (renamed)

```python
class Position(StrEnum):
    """Contract clause position from the reviewer's perspective."""
    PREFERRED   = "preferred"     # Was "favorable"  — Best-case outcome
    ACCEPTABLE  = "acceptable"    # Was "neutral"    — Livable fallback
    WALKAWAY    = "walkaway"      # Was "unfavorable" — Hard dealbreaker
    UNCERTAIN   = "uncertain"     # Unchanged
```

**Backward compatibility**: The existing `load_playbook()` function is extended to map legacy YAML keys (`favorable`/`neutral`/`unfavorable`) to the new enum values with a `DeprecationWarning`.

### PositionDef (unchanged — only the parent key label changes)

```python
@dataclass
class PositionDef:
    description: str
    exemplars: list[str]
```

The `Category` dataclass continues to hold three `PositionDef` instances. Only the attribute access changes (e.g., `cat.favorable` → `cat.preferred`).

### Category (modified — attribute rename)

```python
@dataclass
class Category:
    id: str
    name: str
    description: str
    preferred: PositionDef       # Was favorable
    acceptable: PositionDef      # Was neutral
    walkaway: PositionDef        # Was unfavorable
    default_position: Position   # Maps through rename (old values accepted)
```

### PlaybookMetadata (unchanged — no schema change needed)

```python
@dataclass
class PlaybookMetadata:
    version: str
    description: str
    author: str
```

### Playbook (unchanged structure, only Category attribute rename)

```python
@dataclass
class Playbook:
    id: str
    mode: str
    categories: list[Category]
    metadata: PlaybookMetadata
```

### ClauseAssessment (unchanged — uses Position enum)

```python
@dataclass
class ClauseAssessment:
    position: Position              # ✅ Still works with renamed enum
    confidence: Confidence
    qa_verdict: QAVerdict
    # ...
```

### ReviewReport (modified — add playbook_version field)

```python
@dataclass
class ReviewReport:
    schema_version: str = "1.1.0"
    playbook_id: str = ""
    playbook_version: int | None = None  # NEW: version stamp (None for file-sourced)
    generated_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    document_name: str = ""
    assessments: list[ClauseAssessment] = field(default_factory=list)
    summary: str = ""
```

## 3. Colour Mapping (C-27)

| Position | Colour | ANSI code | Existing (unchanged logic) |
|----------|--------|-----------|---------------------------|
| Preferred | Green | `\033[92m` | Was favorable→Green |
| Acceptable | Amber | `\033[93m` | Was neutral→Amber |
| Walkaway | Red | `\033[91m` | Was unfavorable→Red |
| Uncertain | Yellow | `\033[93m` | Unchanged |

The `colors.py` module uses a dictionary mapping Position enum values to colour functions. Only the dictionary keys change to match the renamed enum.

## 4. Migration Plan

### Current schema: version 5 (migration 005)

### New migration: `006_playbooks.sql`

```sql
CREATE TABLE IF NOT EXISTS playbook_versions (
    playbook_id TEXT NOT NULL,
    version     INTEGER NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (playbook_id, version)
);
CREATE INDEX IF NOT EXISTS idx_playbook_versions_lookup
    ON playbook_versions(playbook_id, version DESC);
PRAGMA user_version = 6;
```

### Migration runner changes

In `src/openreview_cli/storage/database.py`:
1. Add `006_playbooks.sql` to the migrations dict
2. Increment `SCHEMA_VERSION` (or equivalent constant) from 5 to 6

### Existing `reviews` table (unchanged — column already exists)

The reviews table from migration 001 already has:
```sql
playbook_version INTEGER DEFAULT 0
```

NX-3 populates this column with the actual version number when a database-sourced playbook is used. For file-sourced playbooks, it remains `0`.

## 5. Entity Relationship Summary

```
┌──────────────────────┐
│   playbook_versions  │ ← NEW entity (append-only, immutable rows)
│──────────────────────│
│ PK playbook_id TEXT  │──┐
│ PK version INTEGER   │  │
│   content TEXT (JSON)│  │
│   created_at TEXT    │  │
└──────────────────────┘  │
                          │ references via
                          │ playbook_id + version
                          ▼
┌──────────────────────┐
│     reviews          │ ← Existing table (migration 001)
│──────────────────────│
│   ...                │
│   playbook_version   │ ← Column now wired to actual version
│   playbook_id TEXT   │ ← Column now wired to actual ID
└──────────────────────┘

┌──────────────────────┐
│   prompt_versions    │ ← Existing mirror pattern (migration 004)
│──────────────────────│
│ PK name TEXT          │
│ PK version INTEGER   │
│   prompt TEXT         │
│   created_at TEXT     │
└──────────────────────┘
```
