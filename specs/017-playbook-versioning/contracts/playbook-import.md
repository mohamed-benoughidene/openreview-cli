# CLI Contract: `openreview playbook import`

## Purpose

Import a YAML playbook file into the local database as a new append-only version.

## Signature

```
openreview playbook import <yaml-path>
```

## Arguments

| Position | Name | Type | Required | Description |
|----------|------|------|----------|-------------|
| 1 | `yaml-path` | `Path` (existing file) | Yes | Path to a YAML playbook file |

## Options

None.

## Behaviour

1. Validate the YAML file exists and is readable. Exit code 2 (`USAGE_ERROR`) if not.
2. Parse the YAML using the existing `load_playbook()` function. This triggers the existing YAML validation, including:
   - Required fields: `id`, `mode`, `metadata` (with `version`, `description`, `author`), `categories`
   - Each category requires: `id`, `name`, `description`, three position blocks and `default_position`
   - Each position block requires: `description`, `exemplars` (list of strings)
   - Legacy key aliasing: `favorable`/`neutral`/`unfavorable` accepted with deprecation warning.
3. Load the database via the standard database connection (`get_connection()`).
4. Compute next version number: `SELECT COALESCE(MAX(version), 0) + 1 FROM playbook_versions WHERE playbook_id = ?`.
5. Serialise the parsed `Playbook` object to JSON using `dataclasses.asdict()` + `json.dumps()`.
6. Insert row: `INSERT INTO playbook_versions (playbook_id, version, content) VALUES (?, ?, ?)`.
7. Commit and close.
8. Print confirmation: `"Imported playbook '{playbook_id}' as version {next_version}."`
   - If a prior version exists: append `"(previous version: {prev_version})."`
   - If first import: no "previous version" clause.
9. Exit code 0.

## Error Cases

| Condition | Exit Code | Message |
|-----------|-----------|---------|
| File does not exist | 2 | `Error: File not found: <path>` |
| File is not a valid YAML playbook | 2 | `Error: Invalid playbook: <specific validation error>` |
| YAML has unknown categories | 2 | `Error: Unknown categories: [list]` |
| Database write fails | 1 | `Error: Failed to save playbook: <db error>` |
| Database connection fails | 1 | `Error: Database error: <db error>` |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — playbook imported |
| 1 | Internal error (DB, unexpected failure) |
| 2 | User error (invalid file, bad YAML, unknown categories) |

## Output Format

### Success (new playbook)
```
Imported playbook 'nda-v2' as version 1.
```

### Success (existing playbook, new version)
```
Imported playbook 'nda-v2' as version 3 (previous version: 2).
```

### Error
```
Error: File not found: /path/to/nonexistent.yaml
Error: Invalid playbook: missing 'id' field
Error: Unknown categories: [confidentiality_unknown]
```

## Test Scenarios (mapped from spec Acceptance Scenarios)

1. Valid YAML → stored with version 1, confirmation printed. (SC-001)
2. Same YAML imported twice → two versions, version increments. (SC-002)
3. Malformed YAML → validation error, zero rows written. (SC-008)
4. Legacy-key YAML (`favorable`/`neutral`/`unfavorable`) → imported successfully with deprecation warning. (SC-006)
