# CLI Contract: `--playbook <id>` flag on review commands

## Purpose

Allow users to run a review using a playbook stored in the database by ID, instead of only by file path.

## Signature

```
openreview precheck <document> --playbook <id> [other options...]
```

## Flag

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `--playbook` | `str` | No (mutually exclusive with `--playbook-path` in practice) | Playbook ID to load from database |

## Precedence Rules

1. If **only** `--playbook` is provided: load the latest version of that playbook from the database.
2. If **only** `--playbook-path` is provided: load from the YAML file (existing behaviour, unchanged).
3. If **both** `--playbook` and `--playbook-path` are provided: use the database-sourced playbook and print a warning: `Warning: Both --playbook and --playbook-path provided. Using database playbook '...'. --playbook-path ignored.`
4. If **neither** is provided: load the bundled playbook (existing behaviour, unchanged).

## Behaviour

1. If `--playbook` is provided:
   - Query DB: `SELECT * FROM playbook_versions WHERE playbook_id = ? ORDER BY version DESC LIMIT 1`.
   - If no rows found: exit code 2 with `Error: Playbook '<id>' not found in database.`
   - Deserialise `content` JSON to `Playbook`.
   - Set `playbook_version` to the row's version number.
2. Proceed with the existing review pipeline (extraction, QA, report).
3. Stamp `ReviewReport.playbook_id = <id>` and `ReviewReport.playbook_version = <version>`.
4. If `--playbook-path` was the source (no `--playbook`), set `ReviewReport.playbook_version = None`.
5. Existing review output (terminal table + JSON) both include the version stamp.

## Error Cases

| Condition | Exit Code | Message |
|-----------|-----------|---------|
| `--playbook` ID not in database | 2 | `Error: Playbook '<id>' not found in database.` |
| Database connection fails | 1 | `Error: Database error: <db error>` |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — review completed (with or without DB playbook) |
| 1 | Internal error |
| 2 | User error (playbook not found, bad arguments) |

## Integration with Existing Code

### `ReviewCommand` (base.py)

The `ReviewCommand` base class (used by the `precheck` command) currently:

```python
def __init__(self, ..., playbook_path: Path | None = None, ...):
    if playbook_path:
        self.playbook = load_playbook(playbook_path)
    else:
        self.playbook = load_bundled()
```

Extend to:

```python
def __init__(self, ..., playbook_path: Path | None = None, playbook_id: str | None = None, ...):
    if playbook_id:
        self.playbook, self.playbook_version = load_playbook_from_db(playbook_id)
    elif playbook_path:
        self.playbook = load_playbook(playbook_path)
        self.playbook_version = None
    else:
        self.playbook = load_bundled()
        self.playbook_version = None
```

### `run_review()` (review/__init__.py)

Accept an optional `playbook_id: str | None = None` parameter, pass through to `ReviewCommand`.

### `app.py`

The existing `precheck` Typer command gains `--playbook: str = typer.Option(None, "--playbook", ...)`.

## Test Scenarios (mapped from spec Acceptance Scenarios)

1. Review with `--playbook <id>` → Report contains `playbook_id` and `playbook_version`. (SC-003)
2. Review with both `--playbook` and `--playbook-path` → DB playbook wins, warning printed. (SC-003)
3. Review with `--playbook` for nonexistent ID → "playbook not found" error. (SC-008)
4. Review with `--playbook-path` only (no DB) → `playbook_version` is None/absent. (SC-007)
5. Version stamp correctness: review against version N, import version N+1, re-review reports N+1. (SC-004)
