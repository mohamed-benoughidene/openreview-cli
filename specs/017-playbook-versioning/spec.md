# Playbook Versioning — 3-Position Playbook with Version-Stamped Storage

**Feature ID**: 016-playbook-versioning
**Status**: Draft Specification
**Created**: 2026-07-03

**Blueprint references**: [P-13], [PR-12], §6.4, §6.5, §6.7, C-03, C-22, C-23, R-5, R-7, R-11, Q-4, Q-7, Q-8

## 1. Executive Summary

Playbook versioning brings three innovations to the existing single-party review pipeline: a **3-position framework** (Preferred / Acceptable / Walkaway) that replaces the simpler favorable/neutral/unfavorable taxonomy with a decision-oriented vocabulary; **version-stamped storage** in SQLite that freezes the playbook at the moment of each review, enabling auditability per ORPHAN-2 (C-23); and a **version lifecycle** that treats every playbook update as a new immutable version, keeping historical reviews reproducible.

This feature operationalises §6.4 (3-position framework with Amber for uncertain matches answers the F1≤64% accuracy ceiling), §6.5 (playbook positions are model parameters — must be versioned, tested, and optimised like prompts), and §6.7 (single-party review first; bilateral comparison deferred). It feeds C-23 (version-stamped reviews) for the ORPHAN-2 audit trail.

The first three product modes — PreCheck, DealCheck, HireCheck [Q-4] — each ship with a bundled versioned playbook. Users supply custom playbooks via `--playbook <path>`; the system versions them on load.

Blueprint references: [PR-12], §6.4, §6.5, §6.7, C-23, Q-4, Q-8

## 2. User Scenarios

### Scenario 1: First Review with Bundled Playbook (Priority: P1)

A user runs their first `openreview precheck review nda.docx`. The system:
1. Loads the bundled playbook (`precheck-nda-v1.yaml`).
2. Reads its `metadata.version` field (`"1.0.0"`).
3. Checks the SQLite database for a playbook record with matching ID and version.
4. On first load, inserts a new playbook version record with the version string, a content hash of the YAML, and a timestamp.
5. Every clause assessment in the review report references the frozen playbook version ID.

**Why this priority**: This is the core workflow — every review depends on a versioned playbook being stored and referenced correctly.

**Independent Test**: A full run with the bundled playbook produces a `ReviewReport` whose `playbook_id` matches the expected `<id>@<version>` format. The SQLite database contains one playbook_version row.

**Acceptance Scenarios**:
1. **Given** a clean install with no prior playbook records, **When** the user runs a review with the bundled playbook, **Then** a playbook version record is created in SQLite and every assessment references it.
2. **Given** a subsequent review with the same bundled playbook (same version), **When** the review runs, **Then** no duplicate playbook version record is created — the existing record is reused.
3. **Given** the bundled playbook has `metadata.version: "1.0.0"`, **When** the system stores it, **Then** the stored version matches exactly `"1.0.0"` and the content hash matches the SHA-256 of the YAML file.

---

### Scenario 2: Custom Playbook with Auto-Versioning (Priority: P1)

A user brings their own playbook without a version field:
```yaml
id: "acme-nda-v2"
mode: "precheck"
metadata:
  description: "Acme Corp custom NDA terms"
  author: "legal@acme.com"
categories: [...]
```

The system detects the missing `metadata.version`, auto-assigns `"0.1.0"`, stores the playbook with that version, and produces a warning in the output:
```
Warning: Playbook "acme-nda-v2" has no version — assigned 0.1.0
```

**Why this priority**: Users will supply custom playbooks; the system must handle incomplete metadata gracefully without failing.

**Independent Test**: A custom playbook YAML without a version field loads successfully, stores as `0.1.0`, and produces a warning on stderr.

**Acceptance Scenarios**:
1. **Given** a custom playbook YAML with no `metadata.version` field, **When** loaded, **Then** it auto-assigns `"0.1.0"` and emits a warning.
2. **Given** the same custom playbook is loaded twice, **When** the version is auto-assigned, **Then** both loads produce the same version string (0.1.0) and content hash, so only one record is stored.

---

### Scenario 3: Playbook Updated Between Reviews (Priority: P2)

A user has version 1.0.0 of a playbook. They edit the YAML (e.g., tighten an unfavorable exemplar), save as version 1.1.0. The next review:
1. Loads the updated YAML, detects version `"1.1.0"`.
2. Inserts a new playbook version record (different content hash, different version).
3. The new review references version 1.1.0.
4. Old reviews still reference version 1.0.0 and are reproducible with that frozen playbook.

**Why this priority**: Version reproducibility is the core value of version-stamped storage. Users must be able to audit old reviews against the playbook that was active at review time.

**Independent Test**: Two reviews with different playbook versions produce reports with different `playbook_id` values. The SQLite database contains both version records. The old report's assessments are reproducible by reloading the old playbook version.

**Acceptance Scenarios**:
1. **Given** a playbook at version 1.0.0 is used in review R1, **When** the playbook is updated to 1.1.0 and review R2 runs, **Then** R1 references version 1.0.0 and R2 references version 1.1.0.
2. **Given** playbook version 1.0.0 is no longer on disk, **When** a user requests the playbook for R1, **Then** it can be reconstructed from the SQLite-stored content hash and version metadata.

---

### Scenario 4: First Three Product Modes Shipped (Priority: P2)

Three bundled playbooks ship with the tool:
- `precheck-nda-v1.yaml` (existing, now versioned)
- `dealcheck-nda-v1.yaml` (new, DealCheck mode)
- `hirecheck-terms-v1.yaml` (new, HireCheck mode)

Each has its own ID and version. All three are registered in SQLite on first use.

**Why this priority**: R-5 (22 product modes unsustainable) mitigation — ship 3 modes first [Q-4].

**Independent Test**: Each mode's bundled playbook loads, versions, and stores independently. Cross-mode playbook interference is impossible because `id` + `version` is the primary key.

**Acceptance Scenarios**:
1. **Given** three bundled playbooks exist, **When** a review in each mode runs, **Then** three distinct playbook version records exist in SQLite.
2. **Given** a review in PreCheck mode, **When** DealCheck or HireCheck playbook is also stored, **Then** no cross-contamination between playbooks occurs.

---

### Scenario 5: Explicit Playbook Version Pin (Priority: P3)

A power user wants to pin a specific playbook version for reproducibility across a team:
```
openreview precheck review nda.docx --playbook my-terms.yaml --playbook-version 1.0.0
```

If version 1.0.0 is already stored, it is reused. If not, the system loads the playbook, checks its metadata version matches the pin, and stores it. A mismatch produces a clear error.

**Why this priority**: This is an advanced use case for teams that manage playbook versions externally.

**Independent Test**: `--playbook-version` with a stored version loads that version. `--playbook-version` with a version that doesn't match the YAML produces an error.

**Acceptance Scenarios**:
1. **Given** version 1.0.0 of a playbook is stored, **When** `--playbook-version 1.0.0` is used, **Then** the stored version is reused without re-parsing the YAML.
2. **Given** the YAML says version 1.1.0 but `--playbook-version 1.0.0` is specified, **Then** the system errors with a version mismatch message.

---

### Edge Cases

- **What happens when the playbook YAML changes on disk but the version string doesn't?** The content hash changes but the version string stays the same. The system detects the hash mismatch, emits a warning ("Playbook content changed but version unchanged — storing as new version"), and stores it with a `+N` suffix (e.g., `"1.0.0+1"`), incrementing N on each subsequent content change with the same version string. The `+N` format uses simple decimal integers without zero-padding (Q3 resolution).
- **What happens when multiple playbooks share the same ID but different versions?** They are independent records. Each `(id, version)` pair is unique.
- **What happens when the SQLite database is corrupted or missing?** The system falls back to loading the playbook from YAML without persistence, emitting a warning.
- **What happens when a user deletes a playbook YAML file that was previously versioned?** The review reports that reference that playbook version remain reproducible from the SQLite-stored metadata and content hash. The full YAML content is stored in the `content` column, enabling exact reproduction from the database even if the original file is lost.

## 3. Functional Requirements

### FR-1: 3-Position Framework (Preferred / Acceptable / Walkaway)

Each playbook category MUST define three positions with the following semantics:

| Position | Meaning | Maps to existing Position enum |
|----------|---------|-------------------------------|
| Preferred | Benefits the reviewing party | `favorable` |
| Acceptable | Neutral / standard market language | `neutral` |
| Walkaway | Harms the reviewing party's position | `unfavorable` |
| Uncertain | Extraction and QA disagree, or confidence below threshold | `uncertain` (Amber, per §6.4) |

The three-position YAML schema SHALL match the existing pattern in `precheck-nda-v1.yaml` (fields: `favorable`, `neutral`, `unfavorable`) with the recommendation that new playbooks use the Preferred/Acceptable/Walkaway naming. Both naming conventions SHALL be accepted on load — the system SHALL map `favorable` → `Preferred`, `neutral` → `Acceptable`, `walkaway` → `Walkaway` at parse time. Old YAML files remain compatible.

Each position definition MUST include:
- `description` — plain English description of what this position means for this clause category
- `exemplars` — list of language patterns (strings) that indicate this position

Each category MUST also define a `default_position` (one of `preferred`, `acceptable`, `walkaway`, `favorable`, `neutral`, `unfavorable`) used when no specific indicators are found.

The `uncertain` position is not a first-class position in the playbook YAML. It is assigned by the pipeline (extraction + QA disagreement, or low confidence) and is always Amber per §6.4.

Blueprint references: [P-13], §6.4 (Amber for uncertain matches), §6.5 (positions as model parameters)

### FR-2: Version-Stamped Playbook Storage (C-03, C-23)

The system MUST store playbook versions in SQLite (C-03) using the following logical schema:

**Table: `playbook`**
| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Playbook identifier (e.g., `"precheck-nda-v1"`) |
| `mode` | TEXT | Product mode this playbook is for (e.g., `"precheck"`) |
| `description` | TEXT | Human-readable description |
| `author` | TEXT | Author name |

Primary key: `id`

**Table: `playbook_version`**
| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Playbook identifier (FK → playbook.id) |
| `version` | TEXT | Semver string (e.g., `"1.0.0"`) |
| `content_hash` | TEXT | SHA-256 hex digest of the canonical YAML content |
| `content` | TEXT | The full YAML content stored as text (for exact reproduction) |
| `created_at` | TEXT | ISO-8601 timestamp when this version was first loaded |
| `category_count` | INTEGER | Number of categories in this playbook version |

Primary key: `(id, version)`

The system SHALL:
- Compute a SHA-256 content hash of the raw YAML bytes on every playbook load (see FR-5 for details).
- On every playbook load, look up `playbook_version` by `(id, version)` and `content_hash`, reusing existing records or inserting new ones per FR-5's resolution logic.
- Store the full YAML content in the `content` column so playbooks can be reproduced from the database even if the original file is lost.

The `playbook` metadata table is populated on first store of any version of that playbook. If the playbook's `description` or `author` changes, the `playbook` row is updated (soft update — there is only one `playbook` row per `id`; authorship drift is tracked through version history, not through the metadata row).

Blueprint references: C-03 (SQLite layer), C-23 (version-stamped reviews)

### FR-3: Version Reference in Review Reports (C-23)

Every `ReviewReport` (see spec 011, §5) MUST carry a reference to the frozen playbook version:

- `playbook_id` field SHALL use the format `<playbook-id>@<version>` (e.g., `"precheck-nda-v1@1.0.0"`).
- Every `ClauseAssessment` SHALL inherit the report's `playbook_id` (no per-clause playbook reference — the entire review uses one playbook version).
- NX-3 does not store ReviewReport in SQLite. The `playbook_id` string is written to JSON output for audit purposes. A `playbook_version_rowid` field in ReviewReport is deferred — it requires SQLite report storage, which is not part of NX-3 scope.

This enables ORPHAN-2 audit: given a review report, the exact playbook that produced it can be reconstructed from SQLite.

Blueprint references: C-23 (version-stamped reviews per ORPHAN-2 audit)

### FR-4: Version Lifecycle — Immutable Versions, No In-Place Update

Playbook versions SHALL be immutable once stored. There is no UPDATE path for an existing `(id, version)` pair — only INSERT of a new version.

When a user edits a playbook YAML and the version string stays the same, the system detects this via content hash mismatch (FR-2) and:
1. Emits a warning: `"Playbook <id> content changed but version <ver> unchanged — storing as <ver>+<N>"`
2. Inserts a new row with version `"<ver>+<N>"` where `N` is auto-incremented per `<id>+<ver>` pair.

When a user increments the version string in the YAML (e.g., 1.0.0 → 1.1.0), a new row is inserted normally.

There is no automatic cleanup or pruning of old versions. A future maintenance feature MAY add a `--prune-playbook-versions <keep-count>` flag.

Blueprint references: §6.5 (positions are model parameters — version every change)

### FR-5: Content Hash Change Detection

On every playbook load, the system SHALL:
1. Compute SHA-256 of the raw YAML bytes as read from disk.
2. Look up `playbook_version` by `(id, version)`.
3. If a row exists:
   - If `content_hash` matches → reuse existing record (no change).
   - If `content_hash` differs → insert new record with version `"<version>+<N>"` (FR-4).
4. If no row exists → insert new record.

The hash computation SHALL use the exact bytes from disk (raw YAML content), not a normalized/re-serialized form. This ensures that the hash represents what was actually loaded, even if YAML formatting changes.

Blueprint references: C-23 (version-stamped reviews)

### FR-6: Bundled Playbooks Versioned

The three bundled playbooks (PreCheck, DealCheck, HireCheck) SHALL each have a `metadata.version` field in their YAML. The existing `precheck-nda-v1.yaml` already has `version: "1.0.0"` — this becomes the canonical initial version.

New bundled playbooks SHALL ship with version `"1.0.0"`. The version is bumped in the repository when the playbook content changes (standard semver: PATCH for exemplar corrections, MINOR for new categories, MAJOR for incompatible position redefinitions).

Blueprint references: [Q-4] (ship 3 modes first), [P-13]

### FR-7: CLI Integration — Version Flags

The existing `--playbook <path>` flag (spec 011, Scenario 2) SHALL be extended with an optional `--playbook-version <semver>` flag that pins a specific stored version (see Scenario 5).

The `--playbook-version` flag REQUIRES `--playbook`. Standalone usage without a playbook file is not supported (use of `--playbook-version` without `--playbook` SHALL produce an error).

Resolution order when both flags are specified:
1. Load the playbook YAML from `--playbook <path>` to extract the playbook `id`.
2. Query SQLite for a `playbook_version` record with matching `(id, --playbook-version)`.
3. If found → reuse the stored version content (skip further YAML parsing).
4. If not found → check the loaded YAML's embedded version against `--playbook-version`. If mismatch → error. If match → store as new version record and proceed.

The `--playbook-version` flag SHALL be validated against the loaded playbook's metadata version. If they don't match, the system SHALL error with:
```
Error: Requested version <X> does not match playbook "<id>" version <Y>
```

No new CLI subcommands are introduced for NX-3. Playbook version management is incidental to the review command, not a standalone workflow.

Blueprint references: Q-7 (task-level routing, not document-type), §6.4

### FR-8: Position Naming Backward Compatibility

The playbook loader SHALL accept both naming conventions at parse time:

| Loader input | Internal representation |
|---|---|
| `favorable` (existing YAML) | Mapped to `preferred` |
| `neutral` (existing YAML) | Mapped to `acceptable` |
| `unfavorable` (existing YAML) | Mapped to `walkaway` |
| `preferred` (new YAML) | Used as-is |
| `acceptable` (new YAML) | Used as-is |
| `walkaway` (new YAML) | Used as-is |
| `default_position: favorable\|neutral\|unfavorable` | Mapped to preferred/acceptable/walkaway |
| `default_position: preferred\|acceptable\|walkaway` | Used as-is |

This ensures the existing `precheck-nda-v1.yaml` loads without modification while new playbooks use the NX-3 terminology.

The `Position` enum in `review/models.py` SHALL be updated to add `preferred`, `acceptable`, `walkaway` as aliases for `favorable`, `neutral`, `unfavorable` respectively, or the enum SHALL be replaced with the new vocabulary entirely (old values mapped on load).

Blueprint references: §6.4 (3-position framework)

## 4. Success Criteria

| Criterion | Target | Verifiable By |
|-----------|--------|---------------|
| Playbook version stored in SQLite on first load | 100% of loads produce a `playbook_version` row | Database query after first review invocation |
| Duplicate playbook (same id+version+content_hash) reuses existing row | No duplicate rows | Consecutive loads with same YAML produce one row |
| Content change with same version detected | Warning emitted, `+N` suffix appended | Modify a playbook YAML without changing version; verify warning and suffix |
| Review report references playbook version | `playbook_id` field = `<id>@<version>` | Review report output |
| Two reviews with different playbook versions produce different `playbook_id` values | Distinct IDs | Run with v1.0.0 then v1.1.0 |
| Old naming (favorable/neutral/unfavorable) accepted without error | Load succeeds, mapped internally | Load existing `precheck-nda-v1.yaml` |
| Custom playbook without version auto-assigned `0.1.0` | Warning + stored as 0.1.0 | Load custom YAML without version |
| `--playbook-version <ver>` mismatch produces clear error | Error message contains both requested and actual version | Run with mismatched version |
| Three bundled playbooks store independently | Three distinct `playbook` rows in SQLite | Run all three modes consecutively |

## 5. Key Entities

### PlaybookRecord
The top-level playbook metadata stored in SQLite (`playbook` table).

| Field | Type | Description |
|-------|------|-------------|
| id | string | Playbook identifier (e.g., "precheck-nda-v1") |
| mode | string | Product mode this playbook serves |
| description | string | Human-readable description from YAML metadata |
| author | string | Author name from YAML metadata |

### PlaybookVersion
A specific, immutable version of a playbook stored in SQLite (`playbook_version` table).

| Field | Type | Description |
|-------|------|-------------|
| id | string | Playbook identifier (FK → PlaybookRecord.id) |
| version | string | Semver string, possibly with `+N` content-change suffix |
| content_hash | string | SHA-256 hex digest of the raw YAML content |
| content | string | Full YAML content (for reproduction from DB) |
| created_at | string | ISO-8601 timestamp |
| category_count | integer | Number of categories in this version |

### VersionedReviewReport
Extension of the existing `ReviewReport` (spec 011) to carry a version-qualified playbook reference.

The existing `playbook_id` field (already present in the dataclass) SHALL use the format `<id>@<version>` (e.g., `"precheck-nda-v1@1.0.0"`). No new fields are added to ReviewReport for NX-3. A `playbook_version_rowid` field is deferred — it requires SQLite-based report storage, which is not part of NX-3 scope.

### Position3
The 3-position taxonomy for playbooks, replacing the existing Position enum with decision-oriented vocabulary.

| Value | Meaning | Maps to existing Position |
|-------|---------|--------------------------|
| preferred | Benefits the reviewing party | favorable |
| acceptable | Neutral / standard market language | neutral |
| walkaway | Harms the reviewing party's position | unfavorable |
| uncertain | Pipeline ambiguity — Amber per §6.4 | uncertain |

## 6. Assumptions

1. **Single-party scope only**: Bilateral comparison is explicitly out of scope for NX-3 [§6.7, R-7]. The version-stamped playbook is consumed by the single-party review pipeline. Bilateral comparison (NX-1) is a downstream consumer that will interact with the same versioning infrastructure.

2. **Position naming equivalence**: Preferred/Acceptable/Walkaway is a vocabulary change over the existing favorable/neutral/unfavorable, not a semantic change. The 3-position semantics remain identical. This is reasonable because the existing taxonomy was designed for the same purpose.

3. **Full YAML content stored in SQLite**: The entire playbook YAML is stored in the `content` column of `playbook_version` to enable exact reproduction. This is reasonable for playbooks that are typically <50 KB. If playbooks grow beyond 1 MB, a content-addressable file store might replace the inline column.

4. **Semver for version strings**: Playbook versions use semantic versioning (major.minor.patch). Auto-assigned version for version-less playbooks is `0.1.0`. This is the industry standard for versioning and matches the existing `precheck-nda-v1.yaml`.

5. **No playbook editing via CLI**: NX-3 does not introduce CLI commands to create or edit playbooks. Playbooks are authored as YAML files externally and loaded at review time. This is consistent with the existing pattern and Principle II (no web server, no daemon).

6. **No migration of existing reviews**: Existing reviews produced before NX-3 do not carry version references. They are pre-versioning artifacts. This is acceptable because the versioning system is new — all reviews going forward will carry version references.

7. **Three modes first**: Per [Q-4], only PreCheck, DealCheck, and HireCheck ship initially [R-5 mitigation]. Additional modes add bundled playbooks incrementally.

8. **Content hash = raw bytes**: The SHA-256 is computed over the raw YAML bytes as-read-from-disk, not a normalized serialization. This means formatting-only changes (whitespace, comment changes) produce a different hash. This is intentional — any file change is a potential semantic change to a position definition.

9. **No playbook diffing**: NX-3 does not implement diffing between playbook versions (showing what changed between 1.0.0 and 1.1.0). That is a potential future feature for playbook authors.

## 7. Dependencies

| Dependency | Type | Notes |
|------------|------|-------|
| SQLite database layer (C-03) | Runtime | Already built — `src/openreview_cli/storage/` |
| 3-position playbook system (C-22) | Runtime | Existing — `review/playbook.py`, `review/models.py` |
| Review pipeline (Spec 011) | Runtime | Consumes versioned playbook for clause assessment |
| AI Gateway (C-12–C-18) | Runtime | Model routing for extraction and QA (unchanged by NX-3) |
| PII stripping (Phase 3) | Runtime | Upstream pipeline — unchanged by NX-3 |
| `pyyaml` | Runtime | Already a dep — playbook parsing |
| `hashlib` (SHA-256) | Runtime | Python stdlib — content hash computation |
| PreCheck, DealCheck, HireCheck modes | Content | Three bundled playbooks — two new + one existing versioned |

## 8. Clarifications

### Session 2026-07-03

No [NEEDS CLARIFICATION] markers remain. All scope decisions have reasonable defaults documented in the Assumptions section.

**Phase 1 — Committed decisions from initial drafting:**

- **Position naming mapping**: Old `favorable/neutral/unfavorable` maps to new `preferred/acceptable/walkaway` at load time. This is documented as an assumption (Assumption 2) and a functional requirement (FR-8).
- **Full YAML in SQLite**: The `content` column stores the entire YAML. This is documented as an assumption (Assumption 3).
- **Semver**: Version strings follow semver. Auto-assigned version for version-less playbooks is `0.1.0`. This is documented as an assumption (Assumption 4).

**Phase 2 — Ambiguity scan resolutions (2026-07-03):**

- **Q1**: Does NX-3 store ReviewReport in SQLite, making `playbook_version_rowid` useful for JOIN queries?
  → A: No. ReviewReport is a Python dataclass output as JSON — NX-3 does not introduce SQLite storage for reports. The `playbook_id` string `<id>@<version>` is sufficient for the ORPHAN-2 audit trail (C-23). The `playbook_version_rowid` field is removed from the NX-3 data model and added to Out of Scope, pending a future phase that stores reports in SQLite. [Blueprint: C-23, FR-3]
- **Q2**: When `--playbook-version` is specified, what is the resolution order if the stored version's playbook id differs from the YAML file's id?
  → A: The YAML file is always loaded first to extract the playbook `id`. SQLite is then queried by `(id, version)`. If a stored version is found, its `content` column is authoritative (the YAML file's position definitions are not re-parsed). If the YAML file's embedded `version` does not match the pin AND no stored version exists, the system errors with a mismatch message. If the YAML file's `id` does not match any stored playbook, a new record is created. [Blueprint: Scenario 5, FR-7, Acceptance Scenario 1]
- **Q3**: What is the exact format of the `+N` content-change suffix (zero-padded? overflow limit?)?
  → A: Simple `+<N>` where N is a decimal integer starting at 1, no zero-padding (e.g., `1.0.0+1`, `1.0.0+2`). Python big integers handle any practical increment without overflow. The `+001` example in the Edge Cases section was illustrative — the normative format is `+N`. [Blueprint: FR-4, FR-5]
- **Q4**: Can `--playbook-version` be used without `--playbook` to retrieve a stored version from SQLite?
  → A: No. Per Q-7, the playbook file is the primary identifier — version is a secondary constraint. Standalone version retrieval from SQLite without a playbook file would require a new subcommand and is deferred. `--playbook-version` always requires `--playbook`. [Blueprint: Q-7, FR-7]
- **Q5**: The `checksum` column in `playbook_version` is redundant with `content_hash`. Should it be kept?
  → A: No. Remove `checksum`. The `content_hash` column (SHA-256 of raw YAML bytes) serves the same purpose. The content column stores the same bytes as were hashed, so the hashes would be identical. Indexed lookups can use `content_hash` with a SQL index. This removal aligns with Principle IV (dependency minimalism — applied to schema design). [Blueprint: FR-2, Principle IV]

All five resolutions are consistent with the single-party scope (R-7) and existing blueprint decisions (Q-4, Q-7, Q-8).

## 9. Out of Scope (Explicit)

The following are explicitly deferred to later phases or separate features:

- **Bilateral comparison (NX-1)**: NX-3 is single-party only. Version-stamped playbook storage is designed to support bilateral comparison as a downstream consumer, but the comparison itself is out of scope [§6.7, R-7].
- **Playbook editing via CLI**: Playbooks are authoring in YAML externally. No `openreview playbook create/edit` commands [Assumption 5].
- **Playbook diffing**: No version-to-version diff output. Users compare YAML files externally.
- **Playbook version pruning**: Old versions accumulate indefinitely. A `--prune-playbook-versions` flag is future work [FR-4].
- **Multi-playbook merging**: A single review uses one playbook. Combining multiple playbooks is deferred [per spec 011].
- **Clause-level caching**: Each review re-extracts all clauses. No cache layer [per spec 011].
- **Web UI / dashboard**: CLI-only per Principle II.
- **Playbook version pinning in JSON output schema**: The `playbook_id` field is `<id>@<version>` in the initial release. A structured `playbook_version` object in the JSON schema is deferred — the flat string is sufficient for the ORPHAN-2 audit trail [C-23].
- **ReviewReport stored in SQLite**: The `playbook_version_rowid` field in ReviewReport is deferred until a future phase adds SQLite-based report storage. NX-3 uses the `playbook_id` string (`<id>@<version>`) for audit trails; no new fields are added to the ReviewReport dataclass for versioning [FR-3 resolution].
- **Standalone `--playbook-version` without `--playbook`**: Retrieving a stored playbook version from SQLite without providing a playbook file is not supported. It would require a new CLI subcommand (`openreview playbook show <id>@<version>` or similar), which is deferred [Q-7, FR-7 resolution].

Blueprint references: §6.7 (Phase 2 bilateral), R-7, Principle II
