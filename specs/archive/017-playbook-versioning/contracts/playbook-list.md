# CLI Contract: `openreview playbook list`

## Purpose

Display all playbooks stored in the local database, showing each playbook's ID, description, latest version number, and import date.

## Signature

```
openreview playbook list
```

## Arguments

None.

## Options

None.

## Behaviour

1. Load the database via the standard database connection.
2. Query: `SELECT playbook_id, MAX(version) AS version, created_at FROM playbook_versions GROUP BY playbook_id ORDER BY playbook_id`.
3. If the result set is empty, print: `"No playbooks saved yet."` Exit code 0.
4. If results exist, display as a table with columns:
   - **ID** — playbook_id
   - **Description** — loaded from `content` JSON (deserialise only `metadata.description`)
   - **Latest Version** — MAX(version)
   - **Imported** — created_at (formatted as date only: YYYY-MM-DD)
5. Table uses Rich `Table` (same pattern as existing CLI output in review `report.py`).
6. Exit code 0.

## Error Cases

| Condition | Exit Code | Message |
|-----------|-----------|---------|
| Database connection fails | 1 | `Error: Database error: <db error>` |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — table displayed (or empty message) |
| 1 | Internal error (DB, unexpected failure) |

## Output Format

### Non-empty database
```
ID         Description           Latest Version   Imported
────────────────────────────────────────────────────────────
nda-v2     Standard NDA v2                    3   2026-07-03
nda-v1     Standard NDA v1                    1   2026-06-15
```

### Empty database
```
No playbooks saved yet.
```

## Test Scenarios (mapped from spec Acceptance Scenarios)

1. Two imported playbooks → both appear with correct latest version. (SC-001)
2. No playbooks imported → "No playbooks saved yet." message. (SC-001 edge)
3. Playbook with 5 versions → latest version (5) shown, not intermediate versions. (SC-002)
