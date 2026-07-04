# NX-3: 3-Position Playbook with Versioning — Preferred/Acceptable/Walkaway

**Feature ID**: 017-playbook-versioning
**Status**: Draft Specification
**Created**: 2026-07-03
**Blueprint References**: §7 line 433 (NX-3), §4 lines 214–215 (C-22, C-23), §8 line 465 (R-7), ORPHAN-2 (line 52), §4 line 219 (C-27), §6 lines 214–215 (C-22/C-23 architecture), §7 line 423 (N-4)

---

## 1. Executive Summary

A playbook encodes the positions a user believes their organisation should take on each clause category in a given deal type. The existing playbook system (spec 011) loads playbooks from YAML files only, with a single flat set of categories and a three-position model named `favorable`/`neutral`/`unfavorable`. NX-3 extends this foundation with **persistent, versioned playbook storage** and renames the position vocabulary to `preferred`/`acceptable`/`walkaway` — the standard negotiation-theory terms (BATNA, Fisher & Ury 1981).

**What this delivers:**
- Playbooks stored in a local database instead of only on the filesystem
- Every saved playbook is immutable and version-stamped (append-only, no overwrites)
- Users can import YAML playbooks, list all saved playbooks, inspect a specific version, and reference a playbook by ID when running a review
- Each review is stamped with the exact playbook version that produced it, creating the audit trail required by C-23
- The renamed position vocabulary (preferred/acceptable/walkaway) aligns the codebase with the blueprint and standard legal terminology

Blueprint references: §7 line 433 (NX-3 roadmap), §4 lines 214–215 (C-22, C-23), ORPHAN-2 (C-23 audit dependency)

---

## 2. Terminology Rename

The existing `Position` model uses `favorable`/`neutral`/`unfavorable`/`uncertain`. This spec renames the three core states to `preferred`/`acceptable`/`walkaway`. The `uncertain` state is preserved as-is.

| Current | New | Meaning |
|---------|-----|---------|
| `favorable` | `preferred` | Best-case outcome; clause is in the user's favour as written |
| `neutral` | `acceptable` | Livable fallback; user can accept with minor or no concessions |
| `unfavorable` | `walkaway` | Hard dealbreaker limit; if the counterparty insists, the user exits |
| `uncertain` | `uncertain` (unchanged) | Model cannot determine the position |

This rename touches every surface that exposes the position vocabulary: the YAML playbook schema, the playbook loader, the extraction and QA prompt templates, the terminal output colours, the bundled playbook, and all tests that reference position names by string or enum.

Colour mapping (C-27): Preferred → Green, Acceptable → Amber, Walkaway → Red. The three-color output from spec 013 remains intact; only the labels on the position axis change.

Blueprint reference: §4 line 214 (C-22: "Preferred/Acceptable/Walkaway"), §4 line 219 (C-27: three-color output G/A/R)

---

## 3. User Scenarios & Testing

### Scenario 1 — User imports a YAML playbook into the database (Priority: P1)

A user has a YAML playbook file (e.g., an updated version of their standard NDA playbook). They import it into the local database:

```
openreview playbook import ~/playbooks/nda-v2.yaml
```

The system validates the YAML, saves it as a new versioned row (auto-incremented version number), and confirms: `"Imported playbook 'nda-v2' as version 3 (previous version: 2)."` The user does not need to know about the database — the import command is a single file-to-store operation.

**Why this priority**: Versioned storage is the foundation of NX-3. Without importing, there is nothing to version-stamp against, and the rest of the scenarios cannot function.

**Independent Test**: Run `openreview playbook import` on a valid YAML playbook and verify that `openreview playbook list` shows the imported playbook with the correct version number. Run `openreview playbook import` on the same YAML again and verify the version increments.

**Acceptance Scenarios**:

1. **Given** a valid YAML playbook file at `~/nda.yaml`, **When** the user runs `openreview playbook import ~/nda.yaml`, **Then** the playbook is stored in the database with an auto-incremented version number and a confirmation message is printed.
2. **Given** the same YAML content imported a second time, **When** `openreview playbook import ~/nda.yaml` is run again, **Then** a new version is created (existing rows are never overwritten).
3. **Given** a malformed YAML file, **When** the user runs `openreview playbook import ~/bad.yaml`, **Then** the CLI exits with a clear validation error and zero rows are written.

---

### Scenario 2 — User lists available playbooks (Priority: P1)

A user wants to see what playbooks are available and which versions exist before running a review.

```
openreview playbook list
```

The output shows all playbooks (both file-based and previously imported) as a table: ID, description, latest version, and the date it was imported.

**Why this priority**: Listing is the primary discovery mechanism. Without it, a user cannot find which playbook to reference when running a review.

**Independent Test**: After importing at least two versions of a playbook, run `openreview playbook list` and verify both versions appear with correct metadata.

**Acceptance Scenarios**:

1. **Given** two imported playbooks ("nda-v2" at version 3 and "nda-v1" at version 1), **When** the user runs `openreview playbook list`, **Then** both playbooks appear in the table with their latest version numbers.
2. **Given** no playbooks have been imported, **When** the user runs `openreview playbook list`, **Then** the output shows a message like "No playbooks saved yet."
3. **Given** a playbook with 5 versions saved, **When** the user runs `openreview playbook list`, **Then** the latest version (5) is shown for that playbook.

---

### Scenario 3 — User inspects a specific playbook version (Priority: P2)

A user wants to review the exact contents of a specific playbook version — for example, to understand what the "nda-v2" playbook looked like at version 2 before making changes.

```
openreview playbook show nda-v2 2
```

The output shows the full playbook metadata and category definitions, formatted for human reading.

**Why this priority**: Inspection is essential for the audit trail use case (C-23). The review report stamps the playbook ID and version; the user must be able to view exactly what that playbook contained. P2 because the primary workflow (import + use in review) works without it.

**Independent Test**: Import a playbook, create two versions, run `openreview playbook show <id> 1` and `openreview playbook show <id> 2`, and verify the outputs differ where the YAML changed between versions.

**Acceptance Scenarios**:

1. **Given** an imported playbook with 3 versions, **When** the user runs `openreview playbook show nda-v2 2`, **Then** the full contents of version 2 are displayed.
2. **Given** a playbook ID and a version number that does not exist, **When** the user runs `openreview playbook show nda-v2 99`, **Then** the CLI exits with a clear "version not found" error.
3. **Given** a playbook ID that does not exist, **When** the user runs `openreview playbook show nonexistent 1`, **Then** the CLI exits with a clear "playbook not found" error.

---

### Scenario 4 — User runs a review using a database-sourced playbook (Priority: P1)

A user runs a precheck review using a playbook they previously imported, without specifying a file path:

```
openreview precheck my-nda.pdf --playbook nda-v2
```

The tool loads the latest version of "nda-v2" from the database, runs extraction and QA against its categories, and produces a review report. The report records `playbook_id = "nda-v2"` and `playbook_version = 3` (the latest version at time of review).

The existing `--playbook-path` flag remains available for file-based loading. When both `--playbook` and `--playbook-path` are provided, `--playbook` takes precedence with a warning that the file path is ignored.

**Why this priority**: This is the primary consumption path — users import a playbook once, then use it repeatedly without tracking a filesystem path.

**Independent Test**: Import a playbook, run `openreview precheck test.pdf --playbook <id>`, and verify (a) the review completes successfully, (b) the output includes the playbook ID and version in the report metadata.

**Acceptance Scenarios**:

1. **Given** a playbook "nda-v2" stored at version 3 in the database, **When** the user runs `openreview precheck my-nda.pdf --playbook nda-v2`, **Then** the review runs using playbook version 3 and the report records `playbook_id: nda-v2, playbook_version: 3`.
2. **Given** a playbook ID that does not exist in the database, **When** the user runs `openreview precheck my-nda.pdf --playbook nonexistent`, **Then** the CLI exits with a clear "playbook not found" error.
3. **Given** both `--playbook nda-v2` and `--playbook-path ./foo.yaml` are provided, **When** the user runs the command, **Then** the database-sourced playbook is used and a warning is printed that the file path is ignored.

---

### Scenario 5 — Reviewer verifies which playbook version produced a specific review (Priority: P1)

A reviewer (or any user doing a retrospective check) inspects a previously generated review report. The report clearly states which playbook ID and which exact version number produced the assessments. The reviewer can then run `openreview playbook show <id> <version>` to see exactly what the playbook contained at the time of the review.

**Why this priority**: C-23 mandates a version-stamped audit trail. This is a hard requirement from the blueprint — without it, the review output is not reproducible.

**Independent Test**: Run a review with `--playbook nda-v2`, then inspect the output report (JSON or terminal) and verify that `playbook_id` and `playbook_version` fields are present and non-zero.

**Acceptance Scenarios**:

1. **Given** a review run with `openreview precheck my-nda.pdf --playbook nda-v2`, **When** the JSON report is inspected, **Then** it contains `"playbook_id": "nda-v2"` and `"playbook_version": <N>` where N is the version used.
2. **Given** a review run with `--playbook-path` (file-based, no database), **When** the JSON report is inspected, **Then** `"playbook_id"` is the basename of the file path and `"playbook_version"` is absent or indicates "from file" — the database version stamp applies only to database-sourced playbooks.

---

### Edge Cases

- **Importing the same YAML twice**: Two imports of the same YAML create two versions. The system does not attempt semantic deduplication — each import is a new immutable row. This is intentional: the act of importing is a user decision that creates an audit entry.
- **Importing a YAML with unknown categories**: The validator must reject YAML that references categories not in the playbook schema, with a clear error message citing the unknown category ID.
- **Concurrent imports**: The tool is single-user CLI; concurrent database writes are not a concern. The append-only model guarantees no write conflicts.
- **Playbook referenced by a review then deleted**: Playbooks are never deleted — storage is append-only. A "delete" command is out of scope. Users who want to stop using a playbook simply stop referencing it.
- **Version rollover**: Version numbers are auto-incremented integers. There is no upper-bound limit (practical ceiling is the embedded database's integer range). No rollover handling is needed.
- **Playbook ID collisions**: The playbook ID is derived from the YAML file's `id` field during import. If a playbook with the same ID already exists, the new row becomes the next version of that playbook (linked by name, not by content equivalence).
- **Empty playbook list**: `openreview playbook list` on an empty database must show a helpful message, not an empty table or a crash.
- **File-based playbook usage unchanged**: Existing users who load playbooks from YAML files via `--playbook-path` are unaffected. All existing playbook validation, loading, and usage paths remain intact.

---

## 4. Requirements

### Functional Requirements

- **FR-001 — Versioned playbook storage**: The system MUST store playbooks in a local append-only store. Each import creates a new immutable row with a monotonically increasing version number. Existing rows are never overwritten or deleted. [§7 L433][C-22]

- **FR-002 — YAML playbook import**: The system MUST accept a YAML file path via `openreview playbook import <yaml-path>`, validate the YAML against the playbook schema, and persist it to the store with an auto-incremented version number. On success, the system MUST print a confirmation with the playbook ID and version number. [§7 L433][C-22]

- **FR-003 — Playbook listing**: The system MUST support `openreview playbook list` to display all stored playbooks with their ID, description, latest version number, and import date. The output MUST be a human-readable table. [§7 L433]

- **FR-004 — Playbook version inspection**: The system MUST support `openreview playbook show <id> <version>` to display the full contents of a specific playbook version in human-readable format. If the playbook ID or version does not exist, the system MUST exit with a clear error. [§7 L433][C-23]

- **FR-005 — Review from database playbook**: The `openreview precheck` command (and any future review subcommand) MUST accept a `--playbook <id>` flag to load the latest version of a named playbook from the database. The existing `--playbook-path` flag MUST remain functional for file-based loading. When both are provided, `--playbook` takes precedence with a warning. [§7 L433][C-22]

- **FR-006 — Review-report version stamp**: Every ReviewReport produced with a database-sourced playbook MUST record the exact `playbook_id` and `playbook_version` that produced it. This stamp SHALL appear in both terminal output and JSON serialisation. [§4 L215][C-23][ORPHAN-2]

- **FR-007 — Position vocabulary rename**: The three position states MUST be renamed from `favorable`/`neutral`/`unfavorable` to `preferred`/`acceptable`/`walkaway` across all surfaces: the `Position` enum, YAML playbook schema, playbook loader, extraction and QA prompt templates, terminal output labels, the bundled playbook, and all tests. The `uncertain` state is unchanged. [§4 L214][C-22]

- **FR-008 — Colour mapping**: The colour mapping for output (C-27) MUST be: Preferred → Green, Acceptable → Amber, Walkaway → Red. This aligns the renamed positions with the existing three-color output system from spec 013. [§4 L219][C-27]

- **FR-009 — Existing file-based workflows unchanged**: All existing functionality that loads playbooks from YAML files (`--playbook-path`) MUST continue to work identically. Existing playbook files on disk remain valid and loadable. The version-stamp and database features are additive. [§7 L423][N-4]

- **FR-010 — Playbook YAML schema compatibility**: The YAML schema for playbook files MUST accept both the legacy position keys (`favorable`/`neutral`/`unfavorable`) and the new keys (`preferred`/`acceptable`/`walkaway`) during a deprecation period. The loader SHALL normalise legacy keys to the new vocabulary with a deprecation warning. This allows existing YAML files to load without modification while nudging users toward the new vocabulary. [§4 L214][C-22]

- **FR-011 — Single-party scope**: The versioned playbook system is in scope for single-party review only (per N-4 and R-7). Bilateral comparison (spec 014) and multi-party review are explicitly out of scope for NX-3. [§7 L423][N-4][§8 L465][R-7]

### Key Entities

- **Versioned Playbook**: A playbook, identified by a unique string ID, stored with an immutable version number. Each version is a complete snapshot of the playbook schema (categories, positions, metadata). The combination of `(playbook_id, version)` uniquely identifies one snapshot.

- **Playbook Version Stamp**: A pair of values `(playbook_id, version)` recorded on every ReviewReport produced from a database-sourced playbook. Enables reproducible review outputs and audit trail (C-23).

- **Position (renamed)**: An enumeration with values `preferred`, `acceptable`, `walkaway`, `uncertain`. Replaces the existing `favorable`/`neutral`/`unfavorable`/`uncertain` enum. The rename is a one-time reconciliation with the blueprint vocabulary.

### Integration Points

- **Input**: The `playbook import` command accepts a YAML file path. The `playbook show` and `--playbook` flag accept a playbook ID string. The `playbook list` command takes no arguments.

- **Output**: The playbook management commands produce terminal output (tables for list, formatted YAML or structured text for show). The review command produces the existing output formats (terminal table + JSON) with the added version stamp.

- **Relationship to existing playbook system**: The existing playbook loading mechanism remains for file-based loading. A new database-sourced playbook loader loads from the database. The `review` command selects between them based on whether `--playbook` or `--playbook-path` is provided.

- **Relationship to existing review records**: The review-record field designated for playbook version tracking (currently unused) already exists in review records. NX-3 wires this field to the actual stored version number when a database-sourced playbook is used. For file-based playbooks, the field MAY remain as a default value or be populated with a sentinel value indicating file source.

- **Relationship to existing versioned storage pattern**: The existing append-only versioned storage pattern already used for prompts stores prompt content as an immutable, versioned log. NX-3 mirrors this pattern for playbooks.

---

## 5. Scope

### In Scope (BUILD)

1. Append-only playbook storage in the local database (mirroring the existing append-only versioned storage pattern already used for prompts). Each saved playbook is immutable; new versions are new rows.
2. YAML-to-database import command (`openreview playbook import <yaml-path>`). A user takes an existing YAML playbook file and saves it with an auto-incremented version number.
3. Database playbook loading for reviews. The review command can fetch a playbook by ID + version (or latest) from the database, instead of only from a file path.
4. Version stamp on each review report (C-23 audit trail). The existing playbook version field in review records is wired to the actual stored version.
5. Rename the 3 positions from favorable/neutral/unfavorable to preferred/acceptable/walkaway across the entire codebase (enum, YAML, loader, prompts, colours, bundled playbook, tests).

[§7 L433][C-22][C-23][ORPHAN-2]

### Out of Scope (DO NOT BUILD)

- **Bilateral comparison (two-party contracts)**: Deferred per R-7 — experimental, no research precedent [CON-4]. The versioned playbook storage is single-party only.
- **New product modes (HireCheck, DealCheck, etc.)**: Those are C-26, separate roadmap items.
- **Rebuilding the position model**: The 3-position structure already exists from spec 011. This spec renames it, not rebuilds it.
- **Auto-updating playbooks / AI-suggested playbook changes**: Out of scope for NX-3.
- **Playbook deletion or editing**: Storage is append-only. No edit, delete, or rollback commands.
- **Semantic version comparison (diffs between versions)**: NX-3 stores and retrieves versions but does not implement version-diff tooling.
- **Cloud sync or playbook sharing**: Local-only, per Principle II of the constitution.

[§8 L465][R-7][§7 L423][N-4]

---

## 6. Success Criteria

### Measurable Outcomes

- **SC-001 — Import round-trip**: A user can run `openreview playbook import` on a valid YAML playbook, then immediately run `openreview playbook list` and see the imported playbook with version number 1. Verified by automated test. [§7 L433]

- **SC-002 — Version increment**: Importing the same YAML twice produces version 1 and version 2. `openreview playbook show <id> 1` and `openreview playbook show <id> 2` both return valid data. Verified by automated test. [§7 L433]

- **SC-003 — Review with database playbook**: Running `openreview precheck <doc> --playbook <id>` produces a review report where the terminal output and JSON output contain `playbook_id` and `playbook_version` matching the stored playbook. Verified by automated test. [C-23][ORPHAN-2]

- **SC-004 — Version stamp correctness**: A review run against playbook version 2 records `playbook_version: 2`. If a version 3 is then imported and the same review is re-run, the new report records `playbook_version: 3`. Verified by automated test. [§4 L215][C-23]

- **SC-005 — Position rename complete**: No source file in the project (excluding the legacy YAML backward-compatibility load path) references `favorable` or `unfavorable` as position identifiers. The `Position` enum exposes `preferred`, `acceptable`, `walkaway`, `uncertain`. Verified via `grep` across `src/` and `tests/`. [§4 L214][C-22]

- **SC-006 — Legacy YAML backward compatibility**: An existing YAML playbook using `favorable`/`neutral`/`unfavorable` keys loads successfully via `--playbook-path` and produces a deprecation warning. The loaded positions are correctly mapped to preferred/acceptable/walkaway. Verified by automated test. [§4 L214][C-22]

- **SC-007 — No regression in file-based reviews**: All existing test scenarios for `openreview precheck --playbook-path <yaml>` continue to pass with the renamed position vocabulary. The existing test suite for spec 011 review functionality runs green. [§7 L423][N-4]

- **SC-008 — Error handling for missing playbooks**: `openreview playbook show <id> <version>` for a nonexistent ID or version exits with a clear error. `openreview precheck --playbook <id>` for a nonexistent ID exits with a clear error. `openreview playbook import` on a malformed YAML exits with a validation error. Verified by automated test. [§7 L433]

- **SC-009 — CLI commands exist**: `openreview playbook import`, `openreview playbook list`, `openreview playbook show` each produce help text and respond to `--help`. Verified by smoke test. [§7 L433]

---

## 7. Dependencies and Assumptions

### Dependencies

- **spec 011 (Single-Party Review)**: The playbook model, YAML schema, playbook loader, and review pipeline that NX-3 extends. NX-3 must not break any spec 011 functionality.
- **spec 013 (Three-Color Confidence)**: The color-mapping system (C-27) that NX-3's renamed positions feed into. Preferred→Green, Acceptable→Amber, Walkaway→Red.
- **spec 001 (Config/Storage)**: The local database schema that NX-3 extends with playbook storage. The schema version must be bumped.
- **spec 009 (Prompt Management)**: The existing append-only versioned storage pattern for prompts that NX-3 mirrors for playbook storage.

### Assumptions

- **No new dependencies**: The embedded database engine is in the stdlib. `PyYAML` is already in the dependency stack. This spec requires no new external packages.
- **Single-user, no concurrency**: The tool is a single-user CLI. No concurrent-write protection is needed beyond what the embedded database provides by default.
- **Playbook ID is unique (within the store)**: The `id` field in the YAML playbook is the primary user-facing identifier. Importing a playbook with a known ID creates a new version of the same playbook.
- **Version numbers are integers**: Monotonically increasing, starting at 1 for the first import of a given playbook. No semantic versioning (no `major.minor.patch`).
- **Users understand versioned playbooks**: The workflow is analogous to saving document versions. Each `import` is a deliberate save. The CLI does not auto-save or version on every edit.
- **Existing file-based users are unaffected**: The rename is a source-level change; existing YAML files remain loadable via backward-compatible key aliasing. Users who never use the database continue to work as before.
- **The three-color output system (C-27) is stable**: Spec 013 already implemented colour-mapped terminal output. NX-3 re-labels the position axis but does not change the colour logic.
- **Hardware budget not impacted**: The versioned playbook store adds negligible storage overhead (a few KB per version). The append-only model has no in-memory footprint beyond the single playbook loaded at review time.

---

## 8. Resolved Clarifications

All decisions were confirmed via Checkpoint-1 before this specification was written. There are zero [NEEDS CLARIFICATION] markers remaining.

**Decision 1 — Terminology**: Rename `favorable`/`neutral`/`unfavorable` → `preferred`/`acceptable`/`walkaway`. Keep `uncertain` unchanged. Aligns with C-22 and standard negotiation theory.

**Decision 2 — Scope**: Five items to build (database storage, YAML import, DB-sourced review loading, version stamp on reports, position rename). Four exclusions (no bilateral comparison, no new modes, no position model rebuild, no auto-updating).

**Decision 3 — CLI commands**: Three new commands (`playbook import`, `playbook list`, `playbook show`) plus one new flag (`--playbook <id>` on existing review commands).
