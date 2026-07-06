# Data Model: Playbook Management

**Phase**: 1 — Design & Contracts | **Feature**: 024-playbook-management

## Entities

### PlaybookMeta

Metadata for a saved playbook — independent of version content.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `playbook_id` | TEXT (PK) | Unique playbook identifier, e.g., `"nda-v2"` | Must match existing `playbook_versions.playbook_id` |
| `current_version` | INTEGER | The version used when no explicit version is specified | Must be >= 1 and <= max version for this playbook |
| `deleted_at` | TEXT (nullable) | ISO 8601 datetime when soft-deleted; NULL = active | Valid ISO datetime or NULL |

**Storage**: New table `playbook_meta` in migration 007.

**State transitions**:
- `playbook_meta` row is created lazily on first `set-current`, `delete`, or query via helper
- `current_version` defaults to the highest version in `playbook_versions` (initialised on lazy creation)
- `deleted_at` moves from NULL ↔ ISO datetime via `delete` / `set-current`
- Row is never hard-deleted (append-only)

### PlaybookVersion (already exists, unchanged)

Immutable snapshot of a playbook's content at a point in time.

| Field | Type | Description |
|-------|------|-------------|
| `playbook_id` | TEXT | Composite key with version |
| `version` | INTEGER | Monotonically increasing version number |
| `content` | TEXT | JSON-serialised Playbook dataclass |
| `created_at` | TEXT | ISO 8601 creation timestamp |

**Storage**: Existing `playbook_versions` table (migration 006). No changes.

### VersionDiff

Transient — computed at query time, not persisted.

| Field | Type | Description |
|-------|------|-------------|
| `added_categories` | list[str] | Category IDs present in v2 but not v1 |
| `removed_categories` | list[str] | Category IDs present in v1 but not v2 |
| `changed_categories` | dict[str, CategoryChange] | Category ID → {field, before, after} for categories in both versions |
| `status` | str | `"unchanged"` if no differences, `"changed"` otherwise |

**CategoryChange**:
| Field | Type | Description |
|-------|------|-------------|
| `field` | str | One of: `"description"`, `"exemplars"`, `"default_position"` |
| `before` | str | Value in v1 |
| `after` | str | Value in v2 |
| `change_type` | str | One of: `"modified"`, `"exemplar_added"`, `"exemplar_removed"` |

### VersionHistory

Transient — query result, not persisted.

| Field | Type | Description |
|-------|------|-------------|
| `versions` | list[VersionRow] | Sorted ascending by version |
| `current_version` | int | The effective current version |
| `is_deleted` | bool | Whether the playbook is tombstoned |

**VersionRow**:
| Field | Type | Description |
|-------|------|-------------|
| `version` | int | Version number |
| `created_at` | str | Creation timestamp |
| `is_current` | bool | Whether this version is the effective current |
| `is_latest` | bool | Whether this is the highest-numbered version |

## Relationships

```
playbook_meta (0..1) ──> playbook_versions (1..N)
    playbook_id                playbook_id (FK)
    current_version ─────────> version
```

- Each playbook has exactly one `playbook_meta` row (created lazily)
- Each playbook has 1+ `playbook_version` rows
- `current_version` references a valid `version` within `playbook_versions`

## Query Patterns

| Use Case | Query |
|----------|-------|
| Get effective version | `SELECT COALESCE(m.current_version, MAX(v.version)) FROM playbook_meta m RIGHT JOIN playbook_versions v ON m.playbook_id = v.playbook_id WHERE v.playbook_id = ?` |
| Set current version | `INSERT INTO playbook_meta (playbook_id, current_version) VALUES (?, ?) ON CONFLICT(playbook_id) DO UPDATE SET current_version = excluded.current_version, deleted_at = NULL` |
| Soft-delete | `INSERT INTO playbook_meta (playbook_id, current_version, deleted_at) VALUES (?, COALESCE((SELECT current_version FROM playbook_meta WHERE playbook_id = ?), (SELECT MAX(version) FROM playbook_versions WHERE playbook_id = ?)), ?) ON CONFLICT(playbook_id) DO UPDATE SET deleted_at = excluded.deleted_at` |
| List active playbooks | `SELECT v.playbook_id, MAX(v.version) AS version, v.created_at FROM playbook_versions v LEFT JOIN playbook_meta m ON v.playbook_id = m.playbook_id WHERE m.deleted_at IS NULL GROUP BY v.playbook_id ORDER BY v.playbook_id` |
| List all playbooks | Same as above, remove `WHERE m.deleted_at IS NULL` |
| History | `SELECT version, created_at FROM playbook_versions WHERE playbook_id = ? ORDER BY version ASC` |

## Validation Rules

1. **Export**: Playbook ID must exist in `playbook_versions`. Version number must be >= 1 and <= max version.
2. **Diff**: Same validation as export + v1 != v2 is allowed (equal versions produce "No changes").
3. **Set-Current**: Playbook ID must exist. Version must exist (query playbook_versions).
4. **Delete**: Playbook ID must exist (redundant with export check). Idempotent: already-deleted playbook produces "already deleted" message.
5. **History**: Playbook ID must exist.
