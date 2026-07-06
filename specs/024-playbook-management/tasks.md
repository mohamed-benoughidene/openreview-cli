---

description: "Feature implementation tasks for Playbook Management (024)"

---

# Tasks: Playbook Management — Export, Diff, History, and Append-Only Controls

**Input**: Design documents from `specs/024-playbook-management/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), data-model.md, contracts/

**Tests**: Test tasks included per spec requirement — spec.md explicitly mandates TDD (tests before implementation).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format

- `[P]` = parallelizable (different files, no dependencies)
- `[Story]` = user story label (US1–US6)
- Exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Understand existing playbook codebase patterns, verify env, load contracts.

- [X] T001 Read existing `src/openreview_cli/storage/database.py` to understand current playbook storage API patterns
- [X] T002 Read existing `src/openreview_cli/app.py` playbook command group (lines ~350-420) to understand CLI pattern
- [X] T003 Read `specs/024-playbook-management/contracts/cli-commands.md` and `contracts/storage-api.md` for interface contracts
- [X] T004 Read `specs/024-playbook-management/data-model.md` for entity definitions
- [X] T005 Read `specs/024-playbook-management/research.md` for key design decisions
- [X] T006 Verify runtime env: `python3 --version`, `uv pip freeze`, pre-commit, pytest pass on existing tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database schema migration + storage layer helpers that all user stories depend on.

⚠️ CRITICAL: No user story work can begin until this phase is complete.

- [X] T007 [P] Create migration `src/openreview_cli/storage/migrations/007_playbook_meta.sql` — add `playbook_meta` table with `current_version INTEGER`, `deleted_at TEXT` columns, foreign key to playbooks table, unique constraint on playbook_id
- [X] T008 [P] Add migration 007 to migration registry in `src/openreview_cli/storage/database.py`
- [X] T009 [P] Implement storage helper: `get_playbook_versions(db, playbook_id) -> list[version_dict]` in `src/openreview_cli/storage/database.py`
- [X] T010 [P] Implement storage helper: `set_playbook_current_version(db, playbook_id, version)` in `src/openreview_cli/storage/database.py`
- [X] T011 [P] Implement storage helper: `soft_delete_playbook(db, playbook_id)` in `src/openreview_cli/storage/database.py`
- [X] T012 [P] Implement storage helper: `restore_playbook(db, playbook_id)` in `src/openreview_cli/storage/database.py`
- [X] T013 [P] Implement storage helper: `get_playbook_version_data(db, playbook_id, version) -> dict` in `src/openreview_cli/storage/database.py`
- [X] T014 [P] Implement storage helper: `get_playbook_history(db, playbook_id) -> list[version_row]` in `src/openreview_cli/storage/database.py`

**Checkpoint**: Foundation ready — storage layer can CRUD playbook metadata. User story implementation can begin.

---

## Phase 3: User Story 1 — Playbook Export (Priority: P1) 🎯 MVP

**Goal**: Export a saved playbook from SQLite to round-trip-compatible YAML file.

**Independent Test**: Import known YAML, export without `--version`, compare byte-for-byte with original. Export with `--version N`, verify version-N data produced.

### Tests for User Story 1 (TDD: write first, ensure failure, then implement)

- [X] T015 [P] [US1] Write unit tests in `tests/unit/test_playbook_export.py` — valid export, export with `--version`, non-existent playbook, bad version number, missing output parent dir, overwrite warning
- [X] T016 [P] [US1] Write integration tests in `tests/integration/test_playbook_export.py` — round-trip import→export→import, version-specific export

### Implementation for User Story 1

- [X] T017 [P] [US1] Implement `export_playbook_to_yaml(dict) -> str` YAML serialiser in `src/openreview_cli/storage/database.py` (uses PyYAML, matches import schema)
- [X] T018 [US1] Register `openreview playbook export <id> [--version VERSION] --output FILE` subcommand in `src/openreview_cli/app.py` playbook group
- [X] T019 [US1] Wire export command → storage layer → YAML serialiser → file write with error handling (playbook not found, version not found, filesystem errors)
- [X] T020 [US1] Implement overwrite-with-warning for export: if output file exists, print warning to stderr and overwrite; add `--force` flag to suppress warning

**Checkpoint**: `openreview playbook export` works end-to-end. YAML is round-trip compatible.

---

## Phase 4: User Story 2 — Version Diff (Priority: P1)

**Goal**: Compute structural diff between two playbook versions — category add/remove, description change, exemplar add/remove, position change.

**Independent Test**: Create 2 versions with known structural differences. Run diff. Verify all differences appear. Run diff on equal versions — verify "No changes".

### Tests for User Story 2 (TDD: write first, ensure failure, then implement)

- [X] T021 [P] [US2] Write unit tests in `tests/unit/test_playbook_diff.py` — category added, category removed, description changed, exemplar added/removed, default_position changed, equal versions, invalid playbook/version
- [X] T022 [P] [US2] Write integration tests in `tests/integration/test_playbook_diff.py` — full-stack import→versioning→diff, verify terminal output formatting

### Implementation for User Story 2

- [X] T023 [P] [US2] Implement diff computation function `diff_playbook_versions(v1_data: dict, v2_data: dict) -> DiffResult` in `src/openreview_cli/review/playbook.py`
- [X] T024 [P] [US2] Implement `DiffResult` dataclass with structured change list (category-level, field-level) in `src/openreview_cli/review/playbook.py`
- [X] T025 [P] [US2] Implement human-readable diff formatter (Rich table output) for terminal display
- [X] T026 [US2] Register `openreview playbook diff <id> <v1> <v2>` subcommand in `src/openreview_cli/app.py` playbook group
- [X] T027 [US2] Wire diff command → storage layer → diff computation → formatted output with validation error handling

**Checkpoint**: `openreview playbook diff` works end-to-end with human-readable terminal output.

---

## Phase 5: User Story 3 — Set Current Version (Priority: P2)

**Goal**: Allow user to promote any existing version as the effective "current" version used by reviews.

**Independent Test**: Import playbook 3 times, set version 2 as current, verify `list` shows version 2 as current and version 3 as latest.

### Tests for User Story 3 (TDD: write first, ensure failure, then implement)

- [X] T028 [P] [US3] Write unit tests in `tests/unit/test_playbook_set_current.py` — set valid version, set non-existent version, set already-current version (idempotent), non-existent playbook
- [X] T029 [P] [US3] Write integration tests in `tests/integration/test_playbook_management.py` — set-current→list→verify current column, review with `--playbook <id>` uses current version

### Implementation for User Story 3

- [X] T030 [P] [US3] Implement `set_current_version` storage function (calls helper from T010) with validation
- [X] T031 [US3] Register `openreview playbook set-current <id> <version>` subcommand in `src/openreview_cli/app.py` playbook group
- [X] T032 [US3] Wire set-current command → storage → confirmation output with idempotent no-op handling

**Checkpoint**: `openreview playbook set-current` changes effective version. `list` reflects change.

---

## Phase 6: User Story 4 — Soft-Delete Playbook (Priority: P2)

**Goal**: Tombstone a playbook (all versions) — remove from default `list`, preserve data, allow restore via `set-current`.

**Independent Test**: Delete playbook, verify it disappears from `list`, appears in `list --include-deleted`, review with `--playbook <id>` still works.

### Tests for User Story 4 (TDD: write first, ensure failure, then implement)

- [X] T033 [P] [US4] Write unit tests in `tests/unit/test_playbook_delete.py` — soft-delete active playbook, delete non-existent, delete already-deleted (idempotent)
- [X] T034 [P] [US4] Write integration tests in `tests/integration/test_playbook_management.py` — delete→list→list --include-deleted→review with deleted playbook→restore via set-current

### Implementation for User Story 4

- [X] T035 [P] [US4] Implement `delete_playbook` storage function (calls soft_delete_playbook from T011) with validation
- [X] T036 [US4] Register `openreview playbook delete <id>` subcommand in `src/openreview_cli/app.py` playbook group
- [X] T037 [US4] Wire delete command → storage → confirmation output with idempotent handling
- [X] T038 [US4] Add `--include-deleted` flag to existing `playbook list` command in `src/openreview_cli/app.py`

**Checkpoint**: `openreview playbook delete` works. Deleted playbook hidden from default list, accessible with `--include-deleted`, restorable via `set-current`.

---

## Phase 7: User Story 5 — Version History (Priority: P2)

**Goal**: Display full version timeline of a playbook as a Rich table with version number, creation date, current marker, deletion status.

**Independent Test**: Import 3 versions, set version 2 as current, run `history`, verify 3 versions shown with version 2 marked "current".

### Tests for User Story 5 (TDD: write first, ensure failure, then implement)

- [X] T039 [P] [US5] Write unit tests in `tests/unit/test_playbook_history.py` — multi-version history, current marker, deleted marker, non-existent playbook
- [X] T040 [P] [US5] Write integration tests in `tests/integration/test_playbook_management.py` — import→set-current→delete→history→verify all markers

### Implementation for User Story 5

- [X] T041 [P] [US5] Implement history formatter (Rich Table with version, created_at, current flag, deleted flag) in `src/openreview_cli/app.py`
- [X] T042 [US5] Register `openreview playbook history <id>` subcommand in `src/openreview_cli/app.py` playbook group
- [X] T043 [US5] Wire history command → storage (get_playbook_history from T014) → formatted table with validation

**Checkpoint**: `openreview playbook history` displays complete version timeline with markers.

---

## Phase 8: User Story 6 — Precedence Warning Convergence (Priority: P1 — T055/T056)

**Goal**: Emit non-fatal warning to stderr when both `--playbook` and `--playbook-path` are provided to a review command. Resolves spec 017 convergence tasks T055/T056.

**Independent Test**: Run review with both flags → warning on stderr both flag names present. Run with one flag → no warning.

### Tests for User Story 6 (TDD: write first, ensure failure, then implement)

- [X] T044 [P] [US6] Write unit tests in `tests/unit/test_playbook_precedence.py` — both flags emit warning with both names, single flag no warning, warning is non-fatal (command proceeds)
- [X] T045 [P] [US6] Write integration tests in `tests/integration/test_playbook_management.py` (T056 convergence) — full-stack review command with both flags, verify warning on stderr, verify review completes

### Implementation for User Story 6

- [X] T046 [US6] Add precedence warning logic to review command handler(s) in `src/openreview_cli/app.py` or `src/openreview_cli/review/base.py` — detect both `--playbook` and `--playbook-path`, emit warning to stderr naming both flags, state which takes precedence, continue execution
- [X] T047 [US6] Update `specs/017-playbook-versioning/tasks.md` to mark T055 (unit) and T056 (integration) as done — do NOT add them as new tasks in this spec

**Checkpoint**: T055/T056 convergence complete. Both flags produce warning. Single flag silent.
All US6 tasks [X].

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Formatting, documentation, validation, integration sweep.

- [X] T048 [P] Run full pre-commit suite: `uvx pre-commit run --all-files` — fix any ruff/mypy/pytest issues
- [X] T049 [P] Run full test suite: `uv run pytest tests/unit/ tests/integration/ -q` — verify no regressions
- [X] T050 [P] Update `src/openreview_cli/__init__.py` version if feature bumps version
- [X] T051 [P] Run `uv run pytest -m memory` — verify peak memory stays under 110 MB
- [X] T052 [P] Verify `openreview --help` shows all new playbook subcommands with descriptions
- [X] T053 [P] Verify error messages match spec acceptance criteria (exact strings: "Playbook 'X' not found.", "Version N not found for playbook 'X' (latest: M).")

**Checkpoint**: Pre-commit green, tests green, memory budget OK, CLI help complete.
All polish tasks [X].

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 Export (Phase 3)**: Depends on Phase 2 — requires migration + storage helpers T009, T013
- **US2 Diff (Phase 4)**: Depends on Phase 2 — requires storage helper T013 for version data
- **US3 Set-Current (Phase 5)**: Depends on Phase 2 — requires helper T010
- **US4 Delete (Phase 6)**: Depends on Phase 2 — requires helpers T011, T012
- **US5 History (Phase 7)**: Depends on Phase 2 — requires helper T014
- **US6 Precedence Warning (Phase 8)**: Depends on Phase 2 — but does NOT depend on any other user story; targets review command code path
- **Polish (Phase 9)**: Depends on all user stories complete

### User Story Parallelism

Once Phase 2 completes, ALL six user stories can be implemented in parallel:
- **US1 (Export)**: independent — touches `export` path in app.py + YAML serialiser
- **US2 (Diff)**: independent — touches `diff` path in app.py + diff computation
- **US3 (Set-Current)**: independent — touches `set-current` path in app.py
- **US4 (Delete)**: independent — touches `delete` path + `list --include-deleted` in app.py
- **US5 (History)**: independent — touches `history` path in app.py
- **US6 (Precedence)**: independent — touches review command handler, no new subcommand

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD)
- Implementation tasks in dependency order within the story
- Story complete before moving to next (if doing sequential)

### Parallel Opportunities

- T007/T008 (migration + registry) — parallel
- T009–T014 (storage helpers) — all parallel, no file conflicts
- T015/T016, T021/T022, T028/T029, T033/T034, T039/T040, T044/T045 — test pairs within a story are parallel
- T017/T018 (YAML serialiser + app.py registration for export) — parallel
- T023/T024/T025 (diff computation + dataclass + formatter) — parallel
- T048–T053 — all parallel in polish phase

### Parallel Example: Phase 2 Foundational

```bash
# Launch all storage helpers in parallel:
Task: T007 Create migration SQL
Task: T008 Register migration
Task: T009 get_playbook_versions helper
Task: T010 set_playbook_current_version helper
Task: T011 soft_delete_playbook helper
Task: T012 restore_playbook helper
Task: T013 get_playbook_version_data helper
Task: T014 get_playbook_history helper
```

### Parallel Example: Phase 3 US1 (Export)

```bash
# Launch test files in parallel:
Task: T015 Write unit tests for export
Task: T016 Write integration tests for export

# Launch implementation in parallel:
Task: T017 YAML serialiser
Task: T018 Register CLI subcommand
```

---

## Implementation Strategy

### MVP First (Phase 3 Only — US1 Export)

1. Complete Phase 1: Setup (read existing patterns)
2. Complete Phase 2: Foundational (migration + storage helpers)
3. Complete Phase 3: US1 — Export (P1) — first shippable value
4. **STOP and VALIDATE**: Round-trip import→export→import works
5. Export is the MVP

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 Export → MVP (value: playbooks no longer trapped in SQLite)
3. US2 Diff → audit capability (value: see what changed between versions)
4. US3 Set-Current → version control (value: choose which version is active)
5. US4 Delete → cleanup (value: hide outdated playbooks, no data loss)
6. US5 History → visibility (value: see full timeline)
7. US6 Precedence → convergence (value: T055/T056 resolved)
8. Polish → full CI green

---

## Notes

- `[P]` tasks = different files, no dependencies
- `[Story]` label maps task to specific user story
- Each user story independently completable and testable
- ALL test tasks — write test first, verify failure, then implement
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Ban: `as any`, `@ts-ignore`, `@ts-expect-error` — this is Python, no type suppression
- Append-only invariant: no hard-delete, no version overwrite
- Zero new dependencies — use PyYAML (already in), Rich (already in), sqlite3 (stdlib)
