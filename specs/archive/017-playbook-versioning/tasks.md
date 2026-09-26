---
description: "Implementation tasks for 3-Position Playbook with Versioning"
---

# Tasks: 3-Position Playbook with Versioning (Preferred/Acceptable/Walkaway)

**Input**: Design documents from `specs/017-playbook-versioning/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**TDD Requirement**: Tests MUST be written FIRST and FAIL before implementation code is written (per AGENTS.md). Every implementation task has a corresponding test task that precedes it.

**Organization**: Tasks are grouped by user story. Each story phase has Tests (written first) followed by Implementation.

**Format**: `[ID] [P?] [Story] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies on sibling tasks)
- **[Story]**: Which user story this task belongs to (US1–US7)

---

## Phase 1: Setup

**Purpose**: Branch readiness and environment verification for the 3-position playbook with versioning

- [X] T001 Switch to `feat/017-playbook-versioning` branch and verify `uv sync` completes cleanly
- [X] T002 Review existing `prompt_versions` pattern in `src/openreview_cli/storage/migrations/004_prompts.sql` and migration runner in `src/openreview_cli/storage/database.py` as template

**Checkpoint**: Branch is ready, migration pattern understood.

---

## Phase 2: Foundational — US1 Position Enum Rename (Priority: P1) 🎯 MVP

**Goal**: Rename `favorable`/`neutral`/`unfavorable` → `preferred`/`acceptable`/`walkaway` across all code surfaces (models, loader, prompts, colors, YAML, tests). Add backward-compatible legacy key aliasing with deprecation warning.

**Why this is foundational**: Every other user story (US2–US7) references the renamed enum values. Until the rename is done, no new code can be written using the new vocabulary.

**Independent Test**: `grep -r 'favorable\|unfavorable' src/ tests/` returns zero results (excluding the legacy-key alias path in the YAML loader). A legacy YAML playbook using old keys loads with a `DeprecationWarning`.

### Tests for US1 (write first, ensure FAIL before implementation)

- [X] T003 [P] [US1] Unit test: `Position` enum exposes `PREFERRED`, `ACCEPTABLE`, `WALKAWAY`, `UNCERTAIN` with correct string values in `tests/unit/test_position_rename.py`
- [X] T004 [P] [US1] Unit test: legacy YAML keys `favorable`/`neutral`/`unfavorable` map to `preferred`/`acceptable`/`walkaway` with `DeprecationWarning` in `tests/unit/test_position_rename.py`
- [X] T005 [P] [US1] Unit test: `default_position` in legacy YAML maps through the same alias mechanism in `tests/unit/test_position_rename.py`
- [X] T006 [P] [US1] Unit test: colour mapping dictionary uses new position keys (Preferred→Green, Acceptable→Amber, Walkaway→Red) in `tests/unit/test_position_rename.py`

### Implementation for US1

- [X] T007 [P] [US1] Rename `Position` enum values in `src/openreview_cli/review/models.py`
- [X] T008 [P] [US1] Rename `Category` dataclass attributes (`favorable`→`preferred`, `neutral`→`acceptable`, `unfavorable`→`walkaway`) in `src/openreview_cli/review/models.py`
- [X] T009 [P] [US1] Update colour mapping dictionary keys in `src/openreview_cli/review/colors.py`
- [X] T010 [US1] Add legacy-key aliasing to `_parse_category()` / `_parse_position_def()` in `src/openreview_cli/review/playbook.py` — accept both old and new keys, emit `DeprecationWarning` for old keys
- [X] T011 [US1] Update extraction and QA prompt templates in `src/openreview_cli/review/prompts.py` — replace all occurrences of `favorable`/`neutral`/`unfavorable`
- [X] T012 [US1] Update bundled playbook YAML keys in `src/openreview_cli/review/playbooks/precheck-nda-v1.yaml`
- [X] T013 [P] [US1] Create legacy-key YAML test fixture at `tests/fixtures/playbooks/legacy-keys-nda.yaml`
- [X] T014 [US1] Update all existing test files referencing old position names — grep sweep of `tests/` (including `tests/unit/test_models.py`, integration tests, and any fixture YAML files)

**Checkpoint**: `grep -r 'favorable\|unfavorable' src/ tests/` returns zero results (excluding the explicit legacy-key alias handler). `grep -r '\bneutral\b' src/openreview_cli/review/'` returns zero results (excluding non-position uses). All existing tests pass with renamed vocabulary.

---

## Phase 3: US2 — Playbook Database Storage + Migration (Priority: P1) 🎯 MVP

**Goal**: Create the `playbook_versions` table (append-only, mirrors `prompt_versions`), add DB storage functions (save, get by version, get latest, list IDs), and add `VersionedPlaybook` dataclass.

**Why this priority**: Storage is the foundation for US3–US7. Without it, no playbook can be persisted.

**Independent Test**: Run migration 006, save a playbook version, retrieve it by version, retrieve the latest version, list all playbooks — all return correct data.

### Tests for US2

- [X] T015 [P] [US2] Unit test: migration 006 creates `playbook_versions` table with correct schema in `tests/unit/test_playbook_storage.py`
- [X] T016 [P] [US2] Unit test: `save_playbook_version()`, `get_playbook_version()`, `get_latest_version()`, `list_playbooks()` storage functions with correct version increment in `tests/unit/test_playbook_storage.py`
- [X] T017 [P] [US2] Unit test: `list_playbooks()` returns `(playbook_id, max_version, created_at)` grouped by ID, handles empty DB in `tests/unit/test_playbook_storage.py`

### Implementation for US2

- [X] T018 [P] [US2] Create migration `006_playbooks.sql` at `src/openreview_cli/storage/migrations/006_playbooks.sql` — `CREATE TABLE playbook_versions` mirroring `004_prompts.sql`, including `idx_playbook_versions_lookup` index
- [X] T019 [US2] Register migration 006 in `src/openreview_cli/storage/database.py` — migration runner auto-discovers 006_playbooks.sql
- [X] T020 [P] [US2] Add `VersionedPlaybook` dataclass to `src/openreview_cli/review/models.py`
- [X] T021 [US2] Implement DB storage functions (`save_playbook_version`, `get_playbook_version`, `get_latest_version`, `list_playbooks`) in `src/openreview_cli/storage/database.py`

**Checkpoint**: `playbook_versions` table exists after migration. All four storage functions work with correct version increment. Empty DB returns empty list (not crash).

---

## Phase 4: US3 — Import Command (`openreview playbook import <yaml>`) (Priority: P1)

**Goal**: CLI command that loads a YAML playbook file, validates it, and saves it as a new versioned row. Shows confirmation with playbook ID and version.

**Why this priority**: Import is the entry point for the storage pipeline. Without it, no playbooks enter the database and US4–US7 cannot function.

**Independent Test**: `openreview playbook import tests/fixtures/playbooks/legacy-keys-nda.yaml` outputs confirmation. List shows the playbook. Importing again increments version.

### Tests for US3

- [X] T022 [P] [US3] Unit test: YAML validation rejects malformed YAML (invalid categories, missing required fields) with clear error in `tests/unit/test_playbook_versioning.py`
- [X] T023 [P] [US3] Unit test: duplicate import (same YAML twice) creates version 2 without overwriting version 1 in `tests/unit/test_playbook_versioning.py`
- [X] T024 [US3] Integration test: `openreview playbook import <yaml>` CLI smoke test in `tests/integration/test_playbook_commands.py` — verify confirmation message, version increment, and error on bad YAML

### Implementation for US3

- [X] T025 [P] [US3] Implement `load_playbook_from_db()` in `src/openreview_cli/review/playbook.py` — loads `Playbook` from JSON-serialized DB row
- [X] T026 [P] [US3] Implement `import_playbook_yaml()` storage function in `src/openreview_cli/storage/database.py` — parse YAML, validate, serialize to JSON, insert with next version number
- [X] T027 [US3] Add `playbook` Typer command group to `src/openreview_cli/app.py`
- [X] T028 [US3] Implement `import` subcommand in `src/openreview_cli/app.py` — parse Playbook from YAML, call storage function, print confirmation
- [X] T029 [US3] Wire the `playbook` group into the Typer app in `src/openreview_cli/app.py` (register with app.add_typer or decorator)

**Checkpoint**: `openreview playbook import <valid.yaml>` succeeds with confirmation. `openreview playbook import <invalid.yaml>` exits with validation error. `openreview playbook import <valid.yaml>` twice produces version 1 and version 2.

---

## Phase 5: US4 — List Command (`openreview playbook list`) (Priority: P1)

**Goal**: CLI command that displays all saved playbooks in a human-readable table (ID, description, latest version, import date).

**Why this priority**: Listing is the discovery mechanism. Without it, users cannot find which playbook ID to reference with `--playbook`.

**Independent Test**: Import two playbooks with different names, run `list`, verify both appear with correct latest versions. Empty list shows "No playbooks saved yet."

### Tests for US4

- [X] T030 [US4] Integration test: `openreview playbook list` CLI smoke test in `tests/integration/test_playbook_commands.py` — verify table output, verify empty message when no playbooks

### Implementation for US4

- [X] T031 [US4] Implement `list` subcommand in `src/openreview_cli/app.py` (playbook group) — call `list_playbooks()`, format table via Rich, print "No playbooks saved yet." for empty

**Checkpoint**: `openreview playbook list` shows a table with ID, latest version, date. Empty DB prints helpful message.

---

## Phase 6: US5 — Show Command (`openreview playbook show <id> <version>`) (Priority: P2)

**Goal**: CLI command that displays the full contents of one specific playbook version in human-readable format.

**Why P2**: The primary workflow (import + use in review) works without it. Essential for the version-stamped audit trail — a reviewer can inspect exactly what playbook version produced a review.

**Independent Test**: Import a playbook, create two versions, run `show <id> 1` and `show <id> 2`, verify outputs differ. Run `show <id> 99` and get "version not found" error.

### Tests for US5

- [X] T032 [P] [US5] Unit test: `show` for nonexistent playbook ID and nonexistent version both raise clear errors in `tests/unit/test_playbook_versioning.py`
- [X] T033 [US5] Integration test: `openreview playbook show <id> <version>` CLI smoke test in `tests/integration/test_playbook_commands.py` — verify formatted output, verify error for missing ID/version

### Implementation for US5

- [X] T034 [US5] Implement `show` subcommand in `src/openreview_cli/app.py` (playbook group) — call `get_playbook_version()`, format as structured text/YAML, handle not-found errors

**Checkpoint**: `openreview playbook show nda-v2 1` shows full contents. `openreview playbook show nda-v2 99` exits with clear error. `openreview playbook show nonexistent 1` exits with clear error.

---

## Phase 7: US6 — `--playbook` Flag on Reviews (Priority: P1)

**Goal**: Add `--playbook <id>` flag to `openreview precheck` command that loads the latest version from the database. `--playbook-path` remains available; when both given, `--playbook` takes precedence with a warning.

**Why this priority**: This is the primary consumption path — users import once, then use repeatedly.

**Independent Test**: Import a playbook, run `openreview precheck test.pdf --playbook <id>`, verify review completes and output references the DB-sourced playbook.

### Tests for US6

- [X] T035 [P] [US6] Unit test: `--playbook` flag calls `load_playbook_from_db()` with correct ID in `tests/unit/test_playbook_versioning.py`
- [X] T036 [P] [US6] Unit test: `--playbook` takes precedence over `--playbook-path` with deprecation warning in `tests/unit/test_playbook_versioning.py`
- [X] T037 [P] [US6] Unit test: `--playbook` with nonexistent ID raises clear error in `tests/unit/test_playbook_versioning.py`
- [X] T038 [US6] Integration test: `--playbook` flag with precheck in `tests/integration/test_playbook_commands.py` — verify full review runs with DB-sourced playbook

### Implementation for US6

- [X] T039 [P] [US6] Add `--playbook <id>` Typer argument (`str | None = None`) to `precheck` command in `src/openreview_cli/app.py`
- [X] T040 [US6] Wire `--playbook` flag to DB loader in `src/openreview_cli/review/base.py` (ReviewCommand) — before loading, check `--playbook` first, fall back to `--playbook-path`, error if neither provided

**Checkpoint**: `openreview precheck doc.pdf --playbook nda-v2` runs with DB-sourced playbook. `openreview precheck doc.pdf --playbook nda-v2 --playbook-path ./foo.yaml` uses DB version with a warning. `openreview precheck doc.pdf --playbook nonexistent` exits with clear error.

---

## Phase 8: US7 — Version-Stamped Reviews (Priority: P1)

**Goal**: Stamp every `ReviewReport` with the exact `playbook_id` and `playbook_version` that produced it. Wire the existing `playbook_version` column in the `reviews` table. Surface the stamp in terminal output and JSON serialisation.

**Why this priority**: The version-stamped audit trail is a hard requirement. Without it, review outputs are not reproducible.

**Independent Test**: Run a review with `--playbook nda-v2`, inspect JSON output, verify `playbook_id` and `playbook_version` are present and correct.

### Tests for US7

- [X] T041 [P] [US7] Unit test: `ReviewReport.playbook_version` is `None` for file-sourced playbooks and `int` for DB-sourced playbooks in `tests/unit/test_playbook_versioning.py`
- [X] T042 [P] [US7] Unit test: JSON serialisation of `ReviewReport` includes `playbook_id` and `playbook_version` in `tests/unit/test_playbook_versioning.py`
- [X] T043 [US7] Integration test: review output (terminal + JSON) contains correct `playbook_id` and `playbook_version` in `tests/integration/test_playbook_commands.py`

### Implementation for US7

- [X] T044 [P] [US7] Add `playbook_version: int | None = None` field to `ReviewReport` dataclass in `src/openreview_cli/review/models.py`
- [X] T045 [US7] Wire `playbook_version` through the review pipeline: populate from loaded playbook in `src/openreview_cli/review/base.py` (ReviewCommand), propagate through extraction and QA
- [X] T046 [US7] Update report formatting in `src/openreview_cli/review/report.py` to display `playbook_version` in terminal output (e.g., "Playbook: nda-v2 (version 3)")
- [X] T047 [US7] Wire `playbook_version` to the existing `reviews` table's `playbook_version INTEGER` column (migration 001, already exists)

**Checkpoint**: JSON report contains `"playbook_id": "nda-v2"` and `"playbook_version": 3`. Terminal output shows "Playbook: nda-v2 (version 3)". File-sourced playbooks produce `None`/absent version.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Verification, cleanup, and validation across all stories

- [X] T048 [P] Update public API exports in `src/openreview_cli/review/__init__.py` and `src/openreview_cli/storage/__init__.py`
- [X] T049 Update command help text for `playbook import`, `playbook list`, `playbook show`, and `--playbook` flag
- [X] T050 Run `uv run pre-commit run --all-files` to verify lint/format/types
- [X] T051 Run full test suite (`uv run pytest tests/ -q`) — zero regressions
- [X] T052 Run `quickstart.md` validation scenarios from `specs/017-playbook-versioning/quickstart.md`
- [X] T053 Verify SC-005: `grep -r 'favorable\|unfavorable' src/ tests/` returns zero results (excluding explicit legacy-key alias handler)

---

## Phase 10: Convergence

**Purpose**: Close the remaining gap identified by `/speckit.converge` — the warning when both `--playbook` and `--playbook-path` are provided (FR-005, SC-003 acceptance scenario 3).

- [X] T054 [P] [US6] Add warning in `src/openreview_cli/review/__init__.py` `run_review()` — when both `playbook_id` and `playbook_path` are non-None, emit `warnings.warn()` that the file path is ignored (precedence is DB)
- [X] T055 [P] [US6] Unit test: both `--playbook` and `--playbook-path` provided emits warning in `tests/unit/test_playbook_versioning.py`
- [X] T056 [US6] Integration test: `openreview precheck review --playbook <id> --playbook-path <path>` warns and uses DB playbook in `tests/integration/test_playbook_commands.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **US1 — Rename (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US2 — Storage (Phase 3)**: Depends on US1 (uses renamed enum) — BLOCKS US3–US7
- **US3 — Import (Phase 4)**: Depends on US2 (needs storage) — BLOCKS US6
- **US4 — List (Phase 5)**: Depends on US2 (needs storage) — independent of US3, US5
- **US5 — Show (Phase 6)**: Depends on US2 (needs storage) — independent of US3, US4
- **US6 — `--playbook` Flag (Phase 7)**: Depends on US2 + US3 (needs storage + stored playbooks)
- **US7 — Version Stamp (Phase 8)**: Depends on US2 + US6 (needs storage + `--playbook` flag wire-up)
- **Polish (Phase 9)**: Depends on all preceding phases

### Within Each User Story Phase

1. Tests written first — MUST fail on initial run
2. Implementation written — tests should now pass
3. Run targeted tests for that story only
4. Commit before moving to next phase

### Parallel Opportunities

- All tasks marked **[P]** within a phase can run in parallel (different files, no siblings dependencies)
- **US4 (list)** and **US5 (show)** can be implemented in parallel (independent CLI subcommands, both depend only on US2)
- Tests with **[P]** can be written in parallel (different test files or independent test functions)

### Parallel Example

```bash
# US1: Write all tests in parallel
# T003, T004, T005, T006 are independent test functions in test_position_rename.py

# US1: Implement models + colors in parallel
# T007 (models.py enum) and T009 (colors.py) touch different files

# US4 + US5: Implement list and show in parallel
# T031 (list subcommand) and T034 (show subcommand) are independent file additions
```

---

## MVP Scope

The **MVP** consists of Phases 1 + 2 (US1: rename) + 3 (US2: storage):

- T001–T021: Position rename complete, migration 006 in place, storage functions working
- **What it delivers**: Codebase uses preferred/acceptable/walkaway vocabulary. The `playbook_versions` table exists and can be populated manually. The foundation is ready for CLI commands.
- **What is NOT in MVP**: Import/list/show commands, `--playbook` flag, version stamp on reviews

### Incremental Delivery

1. **MVP** (US1 + US2): Foundation — rename + storage. Tests pass, schema migrated.
2. **Add US3 + US4** (import + list): First user-facing commands. Playbooks can enter the DB and be discovered.
3. **Add US5** (show): Audit inspection works for stored playbooks.
4. **Add US6 + US7** (`--playbook` flag + version stamp): Full end-to-end flow — import → list → review with DB playbook → report with version stamp.

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1: Setup
2. Complete Phase 2: US1 — Position rename (foundational, blocks everything)
3. Complete Phase 3: US2 — Storage + migration
4. **STOP and VALIDATE**: All storage functions work, migration runs cleanly, rename is grep-clean
5. Continue with remaining phases incrementally

### Key Risk: Rename surface area

The Position rename touches every file in the review module. The grep sweep in T014 must be thorough:
- `src/` — 9+ files (models, playbook, prompts, colors, bundled YAML, extraction, QA, report, base, __init__)
- `tests/` — all unit and integration tests referencing position strings
- YAML fixtures — bundled and test-specific

Use `rg -rn 'favorable|neutral|unfavorable' src/ tests/` after T014 to verify completeness.

---

## Notes

- [P] tasks = different files, no dependencies on sibling tasks within same phase
- [US1–US7] label maps task to specific user story for traceability
- Each user story phase is independently completable and testable
- Verify tests fail before implementing (red → green)
- Commit after each task or logical group (TDD workflow)
- Stop at any checkpoint to validate story independently
- Zero new dependencies — `sqlite3` and `PyYAML` already in stack
- No existing file-based playbook workflow should break (single-party-only scope, FR-009)
