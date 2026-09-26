# Storage API Contracts: Playbook Management

**Feature**: 024-playbook-management | **Audience**: Implementation reference

All functions live in `src/openreview_cli/storage/database.py`. Following existing patterns — `db_path: Path` as first arg, `transaction()` context manager for atomicity, `sqlite3.Row` row factory.

---

## `ensure_playbook_meta(db_path, playbook_id) -> None`

Lazy-create a `playbook_meta` row if one doesn't exist.

```python
def ensure_playbook_meta(db_path: Path, playbook_id: str) -> None
```

**Logic**:
1. Query `playbook_meta` for `playbook_id`.
2. If no row exists, query `SELECT COALESCE(MAX(version), 0) FROM playbook_versions WHERE playbook_id = ?`.
3. If version count > 0, insert `(playbook_id, max_version, NULL)` into `playbook_meta`.
4. If no versions exist, raise `ValueError(f"Playbook '{playbook_id}' not found.")`

**Called by**: `set_current`, `delete`, `get_current_version` before their main operations.

---

## `get_current_version(db_path, playbook_id) -> int`

Get the effective current version for a playbook.

```python
def get_current_version(db_path: Path, playbook_id: str) -> int
```

**Logic**:
```sql
SELECT COALESCE(
    (SELECT current_version FROM playbook_meta WHERE playbook_id = ?),
    (SELECT MAX(version) FROM playbook_versions WHERE playbook_id = ?)
) AS effective_version
```

**Returns**: Version number (int). **Raises**: `ValueError` if playbook_id not found in `playbook_versions`.

---

## `export_playbook_version(db_path, playbook_id, version) -> str | None`

Get the content of a specific version (thin wrapper around `get_playbook_version`, exists for API consistency).

```python
def export_playbook_version(db_path: Path, playbook_id: str, version: int | None = None) -> str | None
```

**Logic**:
- If `version` is None, call `get_current_version()` then `get_playbook_version()`.
- If `version` is given, call `get_playbook_version()`.
- Returns content string or None.

---

## `diff_playbook_versions(db_path, playbook_id, v1, v2) -> dict`

Compute structural diff between two versions.

```python
def diff_playbook_versions(db_path: Path, playbook_id: str, v1: int, v2: int) -> dict
```

**Returns**:
```python
{
    "status": "changed" | "unchanged",
    "v1": int,           # lower version (normalised)
    "v2": int,           # higher version (normalised)
    "added_categories": [str, ...],      # cat IDs in v2 not in v1
    "removed_categories": [str, ...],    # cat IDs in v1 not in v2
    "changed_categories": {              # keyed by category ID
        "category-id": {
            "description": {"before": str, "after": str} | None,   # omitted if unchanged
            "default_position": {"before": str, "after": str} | None,
            "exemplars_added": [str, ...],    # exemplars in v2 not in v1
            "exemplars_removed": [str, ...],  # exemplars in v1 not in v2
        }
    }
}
```

**Validation**: Both versions must exist. Raises `ValueError` if not found.
**Normalisation**: If `v1 > v2`, swap internally to v1 < v2.

---

## `set_current_version(db_path, playbook_id, version) -> tuple[bool, str]`

Set the effective current version. Also re-activates deleted playbooks.

```python
def set_current_version(db_path: Path, playbook_id: str, version: int) -> tuple[bool, str]
```

**Returns**: `(was_changed, message)` where `was_changed` is True if the version was actually updated, False for idempotent.

**Logic**:
1. Validate playbook_id exists in `playbook_versions`.
2. Validate version exists for playbook_id.
3. Call `ensure_playbook_meta()`.
4. If `current_version == version` and `deleted_at IS NULL`: return `(False, "already current")`.
5. UPDATE `current_version = version, deleted_at = NULL` in `playbook_meta`.
6. Return `(True, f"Set current version of '<id>' to {version}.")`

**Raises**: `ValueError` if playbook_id or version not found.

---

## `delete_playbook(db_path, playbook_id) -> tuple[bool, str]`

Soft-delete a playbook by setting `deleted_at`.

```python
def delete_playbook(db_path: Path, playbook_id: str) -> tuple[bool, str]
```

**Returns**: `(was_changed, message)` where `was_changed` is True if newly deleted, False for idempotent.

**Logic**:
1. Validate playbook_id exists in `playbook_versions`.
2. Call `ensure_playbook_meta()`.
3. If `deleted_at IS NOT NULL`: return `(False, "already deleted")`.
4. UPDATE `deleted_at = datetime.now().isoformat()` in `playbook_meta`.
5. Return `(True, f"Deleted playbook '<id>'.")`

**Raises**: `ValueError` if playbook_id not found.

---

## `get_playbook_history(db_path, playbook_id) -> tuple[list[dict], int, bool]`

Get the version timeline for a playbook.

```python
def get_playbook_history(db_path: Path, playbook_id: str) -> tuple[list[dict], int, bool]
```

**Returns**: `(rows, current_version, is_deleted)`

Each row:
```python
{
    "version": int,
    "created_at": str,
    "is_current": bool,
    "is_latest": bool,
}
```

**Logic**:
1. Validate playbook_id exists in `playbook_versions`.
2. Get `current_version` from `playbook_meta` (or max version if meta missing).
3. Get max version from aggregate query.
4. Query all versions for playbook_id, sorted ASC.
5. Build row list with `is_current` and `is_latest` flags.
6. Query `deleted_at` from `playbook_meta` for `is_deleted`.

**Raises**: `ValueError` if playbook_id not found.

---

## `list_playbooks(db_path, include_deleted=False) -> list[tuple]`

Extended version of existing `list_playbooks` with deleted filter.

```python
def list_playbooks(db_path: Path, include_deleted: bool = False) -> list[tuple[str, int, str, bool]]
```

**Returns**: `[(playbook_id, max_version, created_at, is_deleted), ...]`

**Logic**:
- Existing: `SELECT playbook_id, MAX(version), created_at FROM playbook_versions GROUP BY playbook_id`
- Add LEFT JOIN on `playbook_meta` to get `deleted_at`
- If `include_deleted=False`, filter `WHERE m.deleted_at IS NULL`

**Backward compatible**: Existing callers continue to work (they don't pass `include_deleted` and get the same filtered result).

---

## Migration 007: `007_playbook_meta.sql`

```sql
CREATE TABLE IF NOT EXISTS playbook_meta (
    playbook_id TEXT PRIMARY KEY,
    current_version INTEGER NOT NULL DEFAULT 1,
    deleted_at TEXT
);

PRAGMA user_version = 7;
```

**Note**: `current_version` defaults to 1 but is overridden on first query via `ensure_playbook_meta()` with the actual max version from `playbook_versions`.
