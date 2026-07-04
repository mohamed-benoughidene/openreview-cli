# CLI Contract: `openreview playbook show`

## Purpose

Display the full contents of a specific playbook version from the database.

## Signature

```
openreview playbook show <id> <version>
```

## Arguments

| Position | Name | Type | Required | Description |
|----------|------|------|----------|-------------|
| 1 | `id` | `str` | Yes | Playbook ID (from YAML `id` field) |
| 2 | `version` | `int` | Yes | Version number to display |

## Options

None.

## Behaviour

1. Validate that `version` is a positive integer. Exit code 2 if not.
2. Load the database via the standard database connection.
3. Query: `SELECT * FROM playbook_versions WHERE playbook_id = ? AND version = ?`.
4. If no row found, print error and exit code 2 (user error — bad ID or version).
5. Deserialise `content` JSON back to a `Playbook` dataclass.
6. Display the full playbook contents. Format:
   ```
   Playbook: nda-v2 (version 3)
   Mode: precheck
   Description: Standard NDA v2
   Author: Legal Team
   Created: 2026-07-03 14:30:00
   
   Categories:
   
   1. confidentiality — Confidentiality
      Default: preferred
      Preferred: Broad mutual protection
      Acceptable: Standard one-way protection
      Walkaway: No confidentiality clause
   
   2. ...
   ```
7. Exit code 0.

**Design note on output format**: The human-readable format above is the current intent. Use `rich.Table` and `rich.Panel` if the existing `report.py` pattern already does so for consistency. The exact formatting can be determined during implementation; what matters is that every semantic field from the playbook is visible.

## Error Cases

| Condition | Exit Code | Message |
|-----------|-----------|---------|
| Playbook ID not found | 2 | `Error: Playbook 'nda-v2' not found.` |
| Version not found (ID valid) | 2 | `Error: Version 99 not found for playbook 'nda-v2'.` |
| Version is not a positive integer | 2 | `Error: Version must be a positive integer.` |
| Database connection fails | 1 | `Error: Database error: <db error>` |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — playbook version displayed |
| 1 | Internal error (DB, unexpected failure) |
| 2 | User error (bad ID, bad version) |

## Test Scenarios (mapped from spec Acceptance Scenarios)

1. Valid ID + version → full contents displayed. (SC-002)
2. Valid ID + nonexistent version → "version not found" error. (SC-008)
3. Nonexistent ID → "playbook not found" error. (SC-008)
4. Version 0 or negative → validation error. (SC-008)
