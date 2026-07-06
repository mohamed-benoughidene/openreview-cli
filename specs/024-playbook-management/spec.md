# Playbook Management — Export, Diff, History, and Append-Only Controls

**Feature ID**: 024-playbook-management
**Status**: Draft Specification
**Created**: 2026-07-06

## Overview

Spec 017 introduced persistent, versioned playbook storage with import, list, and inspect commands — but left playbooks trapped inside the SQLite database. This spec expands the `playbook` command group with three new capabilities that complete the playbook lifecycle:

1. **Export** — save a playbook from SQLite back to YAML (round-trip fidelity with the import command).
2. **Version diff** — compare two versions of a saved playbook and see exactly what changed (categories, descriptions, exemplars, default positions).
3. **Management commands** (append-only preserving) — `set-current` to promote any version as the effective latest, `delete` to tombstone (never hard-delete), and `history` to show the full version timeline.

Together these complete the playbook management surface defined in spec 017, including the convergence tests T055/T056 for precedence warnings when `--playbook` and `--playbook-path` are both provided.

---

## User Scenarios and Testing

### Scenario 1: User exports a playbook to YAML (Priority: P1)

A user has a playbook saved in the local database (imported via `openreview playbook import`) and wants to share it with a colleague or back it up as a file. They export it:

```
openreview playbook export nda-v2 --output ~/nda-export.yaml
```

The system reads version 3 (the current/latest) of `nda-v2` from SQLite, serialises it to YAML using the same schema as the import format, and writes it to the specified file. The output YAML must be a valid playbook that can be re-imported with `openreview playbook import`.

**Why this priority**: Export is the inverse of import. Without it, the versioned storage is a one-way door — data goes in but cannot come out.

**Acceptance Scenarios**:

1. **Given** an imported playbook "nda-v2" with 3 versions, **When** the user runs `openreview playbook export nda-v2 --output export.yaml`, **Then** `export.yaml` contains valid YAML matching the latest version of the playbook, and re-importing it produces the same content.
2. **Given** an imported playbook with 5 versions, **When** the user runs `openreview playbook export nda-v2 --version 2 --output export.yaml`, **Then** `export.yaml` contains version 2's data (not the latest).
3. **Given** a non-existent playbook ID, **When** the user runs `openreview playbook export bad-id --output out.yaml`, **Then** the CLI exits with a clear error: `"Playbook 'bad-id' not found."` and no file is written.
4. **Given** an existing playbook but a non-existent version number, **When** the user runs `openreview playbook export nda-v2 --version 99 --output out.yaml`, **Then** the CLI exits with a clear error: `"Version 99 not found for playbook 'nda-v2' (latest: 3)."` and no file is written.
5. **Given** a valid playbook and version, **When** the user specifies an output path where the parent directory does not exist, **Then** the CLI exits with a suitable filesystem error.
6. **Given** an output file that already exists, **When** the user runs `openreview playbook export nda-v2 --output export.yaml` without `--force`, **Then** the CLI prints a warning to stderr (`"Warning: 'export.yaml' already exists — overwriting."`) and overwrites the file.
7. **Given** an output file that already exists, **When** the user runs `openreview playbook export nda-v2 --output export.yaml --force`, **Then** the CLI overwrites the file silently without warning.

**Independent Test**: Import a known playbook YAML, export it without specifying a version, and compare the exported YAML byte-for-byte with the original (modulo any normalisation the YAML library performs). Then export with an explicit version and verify that version's data is produced.

### Scenario 2: User diffs two playbook versions (Priority: P1)

A user has a playbook with several versions and needs to understand what changed between version 1 and version 3 before deciding which version to use in their next review.

```
openreview playbook diff nda-v2 1 3
```

The system compares the two versions structurally:
- **Category-level changes**: lists categories added or removed between versions.
- **Per-category changes**: for categories present in both versions, reports differences in the category's `description`, `exemplars` (added/removed exemplars), and `default_position`.

The output is human-readable (terminal table or structured diff) and machine-parseable on demand.

**Why this priority**: Version diff is the only way to audit playbook evolution. Without it, a user cannot know what changed between imports, making versioning itself less useful.

**Acceptance Scenarios**:

1. **Given** a playbook with 3 versions where category "indemnification" was added in version 2, **When** diffs v1 and v3, **Then** output shows "indemnification" as a new category (added in v2).
2. **Given** a playbook where version 2 modified the `description` of "confidentiality" from "Standard NDA terms" to "Broad NDA terms", **When** diffs v1 and v2, **Then** output shows the description change.
3. **Given** a playbook where version 3 added an exemplar to "limitation-of-liability", **When** diffs v2 and v3, **Then** output shows the added exemplar.
4. **Given** a playbook where version 2 changed the `default_position` from "acceptable" to "walkaway" for "governing-law", **When** diffs v1 and v2, **Then** output shows the position change.
5. **Given** v1 equals v2, **When** the user diffs v1 and v2, **Then** output reports "No changes between version 1 and version 2."
6. **Given** a non-existent playbook or version, **When** the user runs the diff command, **Then** the CLI exits with a clear validation error.
7. **Given** v1 > v2 (e.g., `diff nda 3 1`), **When** the user runs the diff, **Then** the system either normalises the order or reports an error (choose one behaviour, document it).

**Independent Test**: Create two versions of a playbook with known structural differences (category addition, description change, exemplar addition, position change). Run diff and verify all differences appear in the output.

### Scenario 3: User sets the current version (Priority: P2)

A user has multiple versions of a playbook and wants version 2 (not the latest, version 3) to be the default when running reviews.

```
openreview playbook set-current nda-v2 2
```

The system marks version 2 as the current/effective version without deleting or modifying version 3. The `list` command reflects the change. All subsequent review commands that reference this playbook by name should use version 2 instead of the highest-numbered version.

**Why this priority**: Without `set-current`, the "latest" is always the highest version number. This control gives users agency over which version is active.

**Acceptance Scenarios**:

1. **Given** a playbook with versions 1, 2, 3, **When** the user runs `set-current nda-v2 2`, **Then** `list` shows version 2 as current and version 3 as the latest (highest number).
2. **Given** the `set-current` operation, **When** a review references `--playbook nda-v2`, **Then** version 2 is used (not version 3).
3. **Given** a non-existent playbook or version, **When** the user runs `set-current`, **Then** the CLI exits with a clear validation error.
4. **Given** the current version is already version 2, **When** the user runs `set-current nda-v2 2` again, **Then** the CLI confirms no change was needed (idempotent).

**Independent Test**: Import a playbook 3 times, set version 2 as current, run `openreview playbook list`, and verify the current column shows version 2. Then run a review with `--playbook <id>` and verify the review output references version 2's data.

### Scenario 4: User deletes a playbook (soft-delete, Priority: P2)

A user has an outdated playbook they no longer want to see in their default listing. They soft-delete it to remove it from the active list without destroying the audit trail.

```
openreview playbook delete nda-v1
```

The system tombstone-marks all versions of the identified playbook. The playbook no longer appears in `list` output (unless `--include-deleted` or equivalent flag is used). Review records that reference this playbook remain intact and readable. The playbook can be restored if needed (by setting current or by an undelete command).

**Why this priority**: Append-only means never destroying data. Soft-delete aligns with the immutable versioning architecture while giving users a way to clean up their active view.

**Acceptance Scenarios**:

1. **Given** an active playbook, **When** the user runs `delete nda-v1`, **Then** the playbook no longer appears in `list` output and a confirmation message is printed.
2. **Given** a deleted playbook, **When** the user runs `list --include-deleted`, **Then** the playbook appears with a "deleted" marker.
3. **Given** a deleted playbook, **When** the user references it in a review by ID, **Then** the review still executes (historical reviews are not invalidated by deletion).
4. **Given** a non-existent playbook ID, **When** the user runs `delete bad-id`, **Then** the CLI exits with "Playbook 'bad-id' not found."
5. **Given** an already-deleted playbook, **When** the user runs `delete nda-v1` again, **Then** the CLI reports it is already deleted (idempotent).
6. **Given** a deleted playbook, **When** the user runs `set-current nda-v1 2`, **Then** the playbook is restored (re-activated) and appears in `list` again.

**Independent Test**: Delete a playbook, verify it disappears from `list`, verify it appears in `list --include-deleted`, verify a review with `--playbook <id>` still works.

### Scenario 5: User views playbook history (Priority: P2)

A user wants to see the full version timeline of a playbook before deciding which version to use.

```
openreview playbook history nda-v2
```

The system displays a timeline of all versions: version number, creation date, and which version is current. The output is a table sorted by version number ascending.

**Why this priority**: History is the user-facing version browser. Without it, users cannot see what versions exist or when they were created.

**Acceptance Scenarios**:

1. **Given** a playbook with 5 versions, **When** the user runs `history nda-v2`, **Then** all 5 versions are displayed in a table with version number and creation date.
2. **Given** a playbook where version 2 is current, **When** the user runs `history nda-v2`, **Then** version 2 is visually marked as "current" in the output.
3. **Given** a non-existent playbook ID, **When** the user runs `history bad-id`, **Then** the CLI exits with "Playbook 'bad-id' not found."
4. **Given** a deleted playbook, **When** the user runs `history nda-v1`, **Then** the timeline is still displayed (deletion does not destroy history) with a "deleted" marker.

**Independent Test**: Import 3 versions of a playbook, set version 2 as current, run `history` and verify the output shows 3 versions with version 2 marked current.

### Scenario 6: Precedence warning for conflicting playbook flags (Priority: P1 — Convergence from spec 017)

This scenario is carried forward from spec 017 (T055/T056) and must be finalised as part of this spec. A user runs a review command with both `--playbook` (by name) and `--playbook-path` (by file path) provided simultaneously. The system detects the conflict and issues a clear warning message explaining which argument takes precedence and that the other is ignored.

**Acceptance Scenarios**:

1. **Given** both `--playbook` and `--playbook-path` flags provided, **When** the review command runs, **Then** a warning is emitted on stderr naming both flags and stating which won.
2. **Given** an ambiguity, **When** the command executes, **Then** it proceeds without error (the warning is non-fatal).
3. **Given** only one flag, **When** the command executes, **Then** no warning is emitted.

---

## Functional Requirements

### R1: Playbook Export

The system must export a saved playbook from SQLite to YAML. The export must support specifying a version (optional, defaults to the current/latest). The output YAML must conform to the same schema as the import format (round-trip compatible).

**Acceptance criteria**:
- Export without `--version` produces the current version's data.
- Export with `--version N` produces version N's data.
- Invalid playbook ID produces a clear error and non-zero exit.
- Invalid version number produces a clear error showing the valid range.
- Output YAML is syntactically valid and matches the import schema.
- Pre-existing output file: overwrite-with-warning by default; `--force` flag suppresses warning.

### R2: Version Diff

The system must compute a structural diff between two playbook versions, reporting:
- Categories present in v1 but absent in v2 (removed).
- Categories present in v2 but absent in v1 (added).
- For categories in both versions: changes to `description`, `exemplars` (with add/remove granularity), and `default_position`.

**Acceptance criteria**:
- Changed categories listed with before/after values.
- Unchanged categories omitted from output.
- Equal versions produce "No changes" message.
- Invalid playbook or version produces a clear error.
- Output is human-readable (terminal formatting) and structured enough for machine parsing (JSON on `--json` or similar flag — optional, documented).

### R3: Set Current Version

The system must allow users to mark any existing version of a playbook as the current/effective version. This does not alter the version numbering — the highest-numbered version remains the "latest" for ordering purposes, but "current" determines which version is used when no explicit version is specified.

**Acceptance criteria**:
- Existing version number accepted and persisted.
- Non-existent version produces a clear error.
- Idempotent: setting the already-current version produces a no-op confirmation.
- A `list` command displays both "current" and "latest" version numbers.
- A review referencing the playbook by ID uses the current version.

### R4: Soft-Delete Playbook

The system must support soft-deleting a playbook (all versions) by setting a tombstone flag. Deleted playbooks are excluded from default `list` output but remain accessible:
- Explicit reference by ID in a review command still works.
- `history` command still shows the timeline.
- `list --include-deleted` shows deleted playbooks with a marker.
- Re-activation via `set-current` (or a future `undelete` command).

**Acceptance criteria**:
- Delete marks the playbook as tombstoned (never hard-deleted).
- Non-existent ID produces a clear error.
- Idempotent: deleting an already-deleted playbook produces a no-op confirmation.
- Deleted playbook excluded from default `list`.
- Review with `--playbook <deleted-id>` still works (historical data preserved).

### R5: Version History

The system must display the full version timeline of a playbook as a table with version number, creation date, current/active marker, and deletion status.

**Acceptance criteria**:
- All versions displayed sorted ascending.
- Current version visually marked.
- Deleted playbook shows deletion status in each row.
- Non-existent playbook ID produces a clear error.

### R6: Precedence Warning (Convergence from spec 017)

The system must emit a warning to stderr when both `--playbook` and `--playbook-path` are provided. The warning must name both flags and state which takes precedence.

**Acceptance criteria**:
- Warning appears on stderr when both flags present.
- Warning text contains both flag names.
- Command continues after warning (non-fatal).
- No warning when only one flag present.
- T055 unit test and T056 integration test pass (spec 017 convergence).

---

## Success Criteria

1. All playbook export commands produce round-trip-compatible YAML (import → export → import produces identical content).
2. Version diff accurately reports all structural changes (categories added/removed, descriptions changed, exemplars changed, positions changed) for any two versions.
3. `set-current` changes the effective version used by review commands without altering version numbering or destroying data.
4. Soft-delete removes a playbook from default listings while preserving all historical data and review references.
5. `history` displays a complete, accurate version timeline for any saved playbook.
6. Precedence warning (T055/T056) is fully tested with both unit and integration tests passing in CI.
7. All new commands have consistent error handling: invalid IDs, invalid versions, and filesystem errors produce clear, actionable messages.
8. All new commands preserve the append-only invariant: no hard-deletion, no overwrite of existing version data.
9. Full pre-commit suite passes with no regressions and peak memory under 110 MB.

---

## Key Entities

| Entity | Description |
|--------|-------------|
| Playbook record | A saved playbook identified by ID in the database, with one or more versions |
| Playbook version | An immutable snapshot of a playbook's categories, descriptions, exemplars, and default positions |
| Current version | The version used when no explicit version is specified (overridable via `set-current`) |
| Latest version | The highest-numbered version (always the most recently imported) |
| Version diff | A structural comparison of two versions showing category and field-level changes |
| Tombstone | A soft-delete flag marking a playbook as deleted without destroying data |
| Precedence warning | Warning emitted when both `--playbook` and `--playbook-path` flags are present |

---

## Assumptions

1. The database schema from spec 017 supports adding a `current_version` column and a `deleted_at` column to the playbook metadata table, and a VIEW or query to resolve the effective current version.
2. The YAML playbook schema is already stable and defined (spec 011 + spec 017).
3. The `import`, `list`, and `inspect` commands from spec 017 are already implemented and working.
4. The playbook database tables support querying by playbook ID and version number efficiently.
5. The `--playbook` and `--playbook-path` flags already exist on review commands (per spec 017).
6. The Typer CLI framework supports adding subcommands to the existing `playbook` command group.
7. TDD: tests are written before implementation code.
8. No new dependencies are required — PyYAML (already listed) handles YAML serialisation/deserialisation.

---

## Dependencies

1. Spec 017 (playbook-versioning) — provides the database schema, import/list/inspect commands, and the versioned storage foundation.
2. Spec 011 (single-party review) — defines the YAML playbook schema.
3. Spec 022 (cleanup-polish) — confirms T055/T056 are still pending and need to be finalised here.
4. PyYAML (`pyyaml`) — already in runtime deps, used for YAML export.
5. SQLite — already in use for playbook storage.

---

## Scope Boundaries

### In scope
- `openreview playbook export <id> [--version VERSION] --output FILE`
- `openreview playbook diff <id> <v1> <v2>`
- `openreview playbook set-current <id> <version>`
- `openreview playbook delete <id>`
- `openreview playbook history <id>`
- T055/T056 convergence: precedence warning unit and integration tests
- Database schema changes: `current_version`, `deleted_at` columns
- Terminal output formatting for all new commands
- Error handling for all new commands
- YAML round-trip validation

### Explicitly excluded
- `undelete` command (can be achieved via `set-current`; explicit command deferred)
- `--json` output flag for diff (optional, deferred for later polish)
- Bulk operations (export all, delete all)
- Playbook sharing or network export
- GUI or web interface for playbook management
- Changes to the existing `import`, `list`, or `inspect` commands (except adding `--include-deleted` to `list`)
- Migration of existing data (spec 017 schema assumed to be adequate)
