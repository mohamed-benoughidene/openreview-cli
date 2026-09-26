# Research: Playbook Management

**Phase**: 0 — Outline & Research | **Feature**: 024-playbook-management

## Overview

All NEEDS CLARIFICATION items from spec.md are already resolved. This research confirms integration patterns for the 3 key technical concerns.

---

## 1. YAML Export (Round-Trip Fidelity)

### Decision
Use `yaml.safe_dump()` with `default_flow_style=False` and `sort_keys=False` to serialise Playbook dataclass → dict → YAML string → file write via `pathlib.Path.write_text()`.

### Rationale
- `yaml.safe_dump` prevents arbitrary object serialisation (security by default)
- `sort_keys=False` preserves field ordering matching the import schema so round-trip diff is clean
- `default_flow_style=False` produces block-style YAML matching spec 011 format
- PyYAML is already installed (`pyyaml` in pyproject.toml)

### Alternatives considered
- `yaml.dump` with default Dumper (safe vs full) — safe is sufficient, no custom objects needed
- `ruamel.yaml` for comment-preserving round-trip — not installed, not needed (comments not part of schema)
- `json.dumps` then parse as YAML — unnecessary intermediary

### Integration pattern
```python
# In app.py export command:
import yaml
from pathlib import Path
from openreview_cli.storage.database import get_playbook_version

content = get_playbook_version(db_path, playbook_id, version)
data = json.loads(content)
Path(output).write_text(yaml.safe_dump(data, default_flow_style=False, sort_keys=False))
```

---

## 2. Structural Diff Between Playbook Versions

### Decision
Compute diff at the Python dict level after parsing both versions. Compare:
- Set of category IDs (keys of the categories dict) — added/removed
- For categories in both: compare `description`, `exemplars` (as set diff), `default_position`

### Rationale
- No library needed — pure Python set/dict comparison
- Categories are keyed by ID in the YAML schema (spec 011), making identity checks trivial
- Exemplars are lists; convert to set for add/remove detection
- Output using Rich Table for terminal display (consistent with existing `list` command)

### Alternatives considered
- `difflib.Differ` / `difflib.unified_diff` — line-level, loses semantic category structure
- `deepdiff` library — not installed, not worth adding for this use case
- JSON patch format — overkill for a local CLI tool

### Integration pattern
```python
# Structural diff function in database.py or a new diff module
def diff_playbooks(v1_data: dict, v2_data: dict) -> dict[str, list]:
    cats1 = set(v1_data.get("categories", {}).keys())
    cats2 = set(v2_data.get("categories", {}).keys())
    added = cats2 - cats1
    removed = cats1 - cats2
    changed = {}
    for cid in cats1 & cats2:
        changes = _category_diff(v1_data["categories"][cid], v2_data["categories"][cid])
        if changes:
            changed[cid] = changes
    return {"added": sorted(added), "removed": sorted(removed), "changed": changed}
```

---

## 3. Database Schema Extension (Migration 007)

### Decision
Create new table `playbook_meta` with columns `playbook_id TEXT PRIMARY KEY`, `current_version INTEGER NOT NULL DEFAULT 1`, `deleted_at TEXT`. No ALTER TABLE on `playbook_versions`.

### Rationale
- Spec says "adding a `current_version` column and a `deleted_at` column to the playbook metadata table"
- Separate table avoids altering the append-only `playbook_versions` table
- `current_version` defaults to the highest version (updated on first access or explicitly via `set-current`)
- `deleted_at` stores ISO datetime when deleted; NULL means active
- Join view or function resolves effective current version

### Alternatives considered
- Adding columns to `playbook_versions` — would alter the immutable version rows, wrong semantics
- Separate `playbook_current` table with single row per playbook — same as `playbook_meta`, name chosen for clarity

### Migration 007 SQL
```sql
CREATE TABLE IF NOT EXISTS playbook_meta (
    playbook_id TEXT PRIMARY KEY,
    current_version INTEGER NOT NULL DEFAULT 1,
    deleted_at TEXT
);

PRAGMA user_version = 7;
```

---

## 4. Precedence Warning (T055/T056)

### Decision
Add warning check in the existing review base command (`base.py` or the command function). If both `--playbook` and `--playbook-path` are set, emit warning to stderr via `typer.echo(message, err=True)`.

### Rationale
- Logic already exists (name wins over path) — only stderr warning is missing
- Non-fatal per spec (R6 acceptance scenario 2)
- `typer.echo(..., err=True)` is the existing pattern for stderr output

### Alternatives considered
- `warnings.warn()` — less visible, mixes with Python warning system
- `rich.print(...)` — inconsistent with existing error patterns in app.py

---

## 5. Soft-Delete Architecture

### Decision
Set `deleted_at = datetime.now().isoformat()` in `playbook_meta`. All existing queries (`list_playbooks`, `get_playbook_version`, `get_latest_playbook_version`) remain unchanged — users can still reference by ID. A new `list_playbooks(include_deleted=True)` variant or an additional `--include-deleted` filter in the CLI.

### Rationale
- Append-only invariant: never destroyed, just hidden from default views
- Existing functions work as-is: by-ID lookups bypass the deleted check
- Re-activation via `set-current` sets `deleted_at = NULL`

---

## 6. CLI Command Patterns

All 5 commands follow the existing Typer patterns in app.py:
- `@playbook_app.command("export")` with arguments and options
- Use `typer.Argument(...)` for positional args (playbook_id, version numbers)
- Use `typer.Option(...)` for `--version`, `--output`, `--include-deleted`
- Error handling via `typer.echo(f"Error: ...", err=True); raise typer.Exit(code=1)`
- Rich Table for `history` and tabular output
- `typer.echo(...)` for simple text output (diff, set-current confirmation, delete confirmation)

---

## Summary of Changes

| Area | Change | Risk |
|------|--------|------|
| `database.py` | +5 functions: export_version, diff_versions, set_current, delete_playbook, get_playbook_history | Low |
| `database.py` | +1 helper: get_meta (lazy-init current_version) | Low |
| `migrations/007_playbook_meta.sql` | New file | Low |
| `app.py` | +5 subcommands in playbook group + precedence warning in review commands | Low |
| Tests | ~8 new test files (unit + integration) | Low |

**No new dependencies. No constitutional concerns.**
