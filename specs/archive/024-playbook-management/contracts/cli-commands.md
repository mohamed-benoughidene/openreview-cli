# CLI Command Contracts: Playbook Management

**Feature**: 024-playbook-management | **Audience**: Implementation reference

These contracts define the CLI surface. All commands are subcommands under the existing `playbook` Typer group defined in `src/openreview_cli/app.py` (~line 424).

---

## `openreview playbook export <playbook_id> [--version VERSION] --output FILE`

Export a playbook version from SQLite to YAML.

**Arguments**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `playbook_id` | str | Yes | Saved playbook identifier |
| `--version` | int | No | Version to export; defaults to current/latest |
| `--output` | Path | Yes | Destination file path |

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Success — YAML written |
| 1 | Playbook ID not found |
| 1 | Version not found for playbook |
| 1 | Output path invalid (parent dir missing) |
| 1 | YAML serialisation failure |

**Output**: YAML file written to `--output` path. Stderr message on success or error.

**Errors**:
- `"Error: Playbook '<id>' not found."` — playbook_id absent from playbook_versions
- `"Error: Version <N> not found for playbook '<id>' (latest: <M>)."` — bad version
- `"Error: Cannot write to '<path>': parent directory does not exist."` — invalid output path

**Existing file behaviour**: Overwrite with warning: `"Warning: Overwriting existing file '<path>'."` (matching POSIX `cp` semantics, per spec's open decision).

---

## `openreview playbook diff <playbook_id> <v1> <v2>`

Compare two versions of a saved playbook structurally.

**Arguments**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `playbook_id` | str | Yes | Saved playbook identifier |
| `v1` | int | Yes | First version to compare |
| `v2` | int | Yes | Second version to compare |

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Success — diff displayed |
| 1 | Playbook ID not found |
| 1 | Either version not found |

**Output**: Terminal-formatted diff to stdout:
```
Changes between version <v1> and <v2> of <playbook_id>:

New categories:
  - indemnification

Removed categories:
  (none)

Changed categories:
  confidentiality:
    description: "Standard NDA terms" → "Broad NDA terms"
  limitation-of-liability:
    exemplar added: "Example text here"
  governing-law:
    default_position: "acceptable" → "walkaway"

No changes between version <v1> and version <v2>.
```

**Order normalisation**: If v1 > v2, swap internally (v1 becomes the lower version). No error. Always display "v1 vs v2" with v1 < v2 in output.

---

## `openreview playbook set-current <playbook_id> <version>`

Set the effective current version for a playbook.

**Arguments**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `playbook_id` | str | Yes | Saved playbook identifier |
| `version` | int | Yes | Version to mark as current |

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Success — current version updated |
| 1 | Playbook ID not found |
| 1 | Version not found |

**Output**:
- On success: `"Set current version of '<id>' to <N>."`
- On idempotent: `"Version <N> is already the current version of '<id>'."`
- Re-activates deleted playbook (sets `deleted_at = NULL`).

---

## `openreview playbook delete <playbook_id>`

Soft-delete a playbook (tombstone, never hard-delete).

**Arguments**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `playbook_id` | str | Yes | Saved playbook identifier |

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Success — playbook deleted |
| 1 | Playbook ID not found |

**Output**:
- On success: `"Deleted playbook '<id>'."`
- On already deleted: `"Playbook '<id>' is already deleted."`
- On non-existent: `"Error: Playbook '<id>' not found."`

---

## `openreview playbook history <playbook_id>`

Show version timeline of a playbook.

**Arguments**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `playbook_id` | str | Yes | Saved playbook identifier |

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Success — table displayed |
| 1 | Playbook ID not found |

**Output**: Rich Table with columns: `Version`, `Created`, `Status`. Sample:
```
┌─────────┬──────────────────────┬──────────┐
│ Version │ Created              │ Status   │
├─────────┼──────────────────────┼──────────┤
│ 1       │ 2026-06-01 12:00:00 │          │
│ 2       │ 2026-06-15 14:30:00 │ Current  │
│ 3       │ 2026-07-01 09:00:00 │ Latest   │
└─────────┴──────────────────────┴──────────┘
```

If playbook is deleted, show `(deleted)` in Status column header or per-row.

---

## Precedence Warning (T055/T056)

**Location**: Existing review command(s) in `app.py` (or `_check_playbook_args` helper).

**Contract**:
- If both `--playbook` and `--playbook-path` flags are set:
  - Emit to stderr: `"Warning: Both --playbook (<name>) and --playbook-path (<path>) provided. --playbook takes precedence."`
- If only one flag: no output.
- Warning is non-fatal — command proceeds.
