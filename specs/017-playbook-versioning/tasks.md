---

description: "Task list for Playbook Versioning — 3-Position Playbook with Version-Stamped Storage"

---

# Tasks: Playbook Versioning — 3-Position Playbook with Version-Stamped Storage

**Input**: Design documents from `/specs/017-playbook-versioning/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**TDD**: Tests are REQUIRED. Write tests FIRST, ensure they FAIL, then implement. Every user story phase follows this order.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions
- No [P] marker for sequential tasks

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database schema and migration for the two new playbook tables.

- [X] T001 Create SQL migration 006_playbook_versioning.sql with playbook and playbook_version tables in `src/openreview_cli/storage/migrations/006_playbook_versioning.sql`

**Checkpoint**: Migration registered. Tables can be created by running the migration pipeline.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared data models, content-hash utility, and position-name mapping — needed by every user story.

**⚠ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Add Position3 StrEnum (preferred, acceptable, walkaway, uncertain) alongside existing Position enum in `src/openreview_cli/review/models.py`
- [X] T003 [P] Add PlaybookRecord and PlaybookVersion dataclasses to `src/openreview_cli/review/models.py`
- [X] T004 [P] Add content_hash() utility (SHA-256 of raw YAML bytes) and map_position_name() function to `src/openreview_cli/review/playbook.py`

**Checkpoint**: Foundation ready — models and utilities exist and can be unit-tested.

---

## Phase 3: User Story 1 — First Review with Bundled Playbook (Priority: P1) 🎯 MVP

**Goal**: A user runs their first `openreview precheck review nda.docx`. The system loads the bundled playbook, detects its version, stores it in SQLite (or reuses an existing record), and produces a ReviewReport whose `playbook_id` is `<id>@<version>`.

**Independent Test**: A full run with the bundled playbook produces a `ReviewReport` whose `playbook_id` matches the expected `<id>@<version>` format. The SQLite database contains one `playbook_version` row. Running the same review again produces no duplicate row.

### Tests for User Story 1 (TDD — write FIRST, ensure FAIL)

- [X] T005 [P] [US1] Unit test for Position3 StrEnum values, mapping from old Position, and PlaybookRecord/PlaybookVersion dataclass validation in `tests/unit/test_playbook.py`
- [X] T006 [P] [US1] Unit test for content_hash() computation (SHA-256 raw bytes), map_position_name() bidirectional mapping, and version extraction in `tests/unit/test_playbook.py`
- [X] T007 [P] [US1] Unit test for playbook_version table CRUD operations (insert, lookup by id+version, lookup by content_hash) in `tests/unit/test_storage.py`
- [X] T008 [US1] Integration test for first review with bundled playbook: creates playbook_version row, playbook_id format, duplicate run reuses existing row in `tests/integration/test_playbook_versioning.py`
- [X] T009 [P] [US1] Unit test for DB-unavailable fallback: playbook loads from YAML with warning when SQLite connection fails in `tests/unit/test_playbook.py`

### Implementation for User Story 1

- [X] T010 [US1] Implement playbook_version table CRUD functions (insert_version, find_version, find_by_hash) and auto-create PlaybookRecord on first insert in `src/openreview_cli/storage/database.py`
- [X] T011 [P] [US1] Add version detection (extract metadata.version), content_hash computation (SHA-256 of raw bytes before YAML parse), and position name mapping in `src/openreview_cli/review/playbook.py`
- [X] T012 [US1] Implement unified playbook load with DB caching: load YAML → compute hash → query DB → reuse or insert → return Playbook with version context in `src/openreview_cli/review/playbook.py`
- [X] T013 [US1] Update ReviewReport.playbook_id format from bare `playbook.id` to `<id>@<version>` in `src/openreview_cli/review/__init__.py` (`_build_report` function, line 238)
- [X] T014 [US1] Wire version-stamped playbook loading into the review pipeline: load_bundled() and load_playbook() return versioned Playbook, pass version info into ReviewReport in `src/openreview_cli/review/__init__.py`
- [X] T015 [US1] Implement DB-unavailable fallback in playbook loader: catch DB connection errors, load playbook from YAML without persistence, emit warning to stderr, log failure in `src/openreview_cli/review/playbook.py`

**Checkpoint**: User Story 1 complete. A review run creates a versioned playbook record. The report carries `<id>@<version>`. Running again reuses the record. All tests pass.

---

## Phase 4: User Story 2 — Custom Playbook with Auto-Versioning (Priority: P1)

**Goal**: A user supplies a custom playbook YAML without a `metadata.version` field. The system auto-assigns `"0.1.0"`, stores it, and emits a warning on stderr. Loading the same custom playbook twice stores only one record.

**Independent Test**: A custom playbook YAML without a version field loads successfully, stores as `0.1.0`, and produces a warning on stderr. Loading it twice produces one DB row.

### Tests for User Story 2

- [X] T016 [P] [US2] Unit test for version-less playbook auto-assigning `0.1.0` and emitting warning in `tests/unit/test_playbook.py`
- [X] T017 [US2] Integration test for custom playbook with no version: loads, stores as 0.1.0, warning output, no duplicate on second load in `tests/integration/test_playbook_versioning.py`

### Implementation for User Story 2

- [X] T018 [US2] Implement auto-versioning: detect missing `metadata.version`, assign `"0.1.0"`, emit warning `Warning: Playbook "<id>" has no version — assigned 0.1.0` to stderr in `src/openreview_cli/review/playbook.py`

**Checkpoint**: User Stories 1 and 2 complete. Custom playbooks without versions load and store correctly. All tests pass.

---

## Phase 5: User Story 3 — Playbook Updated Between Reviews (Priority: P2)

**Goal**: A user edits a playbook YAML without changing the version string. The system detects the content hash mismatch, emits a warning, and stores a new row with a `+N` suffix (e.g., `1.0.0+1`). Old reviews still reference the old version.

**Independent Test**: Two reviews with different playbook versions produce reports with different `playbook_id` values. SQLite contains both version records. The old report's assessments are reproducible by reloading the old playbook version.

### Tests for User Story 3

- [X] T019 [P] [US3] Unit test for content-change detection: same id+version but different content_hash produces `+N` suffix emission and warning in `tests/unit/test_playbook.py`
- [X] T020 [US3] Integration test for playbook update between reviews: load playbook → modify content (same version) → reload creates `+1` row, old report still references original version in `tests/integration/test_playbook_versioning.py`

### Implementation for User Story 3

- [X] T021 [US3] Implement content-change detection and `+N` suffix logic: on hash mismatch during load, compute next `+N` suffix via SQL `MAX(SUBSTR(...))`, insert new row with suffixed version, emit warning `Playbook "<id>" content changed but version "<ver>" unchanged — storing as <ver>+<N>` in `src/openreview_cli/review/playbook.py`

**Checkpoint**: User Stories 1–3 complete. Content changes without version bumps create suffixed records. All tests pass.

---

## Phase 6: User Story 4 — First Three Product Modes Shipped (Priority: P2)

**Goal**: Three bundled playbooks ship with the tool: precheck-nda-v1 (existing), dealcheck-nda-v1 (new), hirecheck-terms-v1 (new). Each has its own ID, version, and stores independently.

**Independent Test**: Each mode's bundled playbook loads, versions, and stores independently. Cross-mode playbook interference is impossible because `id` + `version` is the primary key.

### Tests for User Story 4

- [X] T022 [P] [US4] Unit test for bundled playbook loading across modes: each playbook has valid YAML, correct metadata, and unique id in `tests/unit/test_playbook.py`
- [X] T023 [US4] Integration test for three modes storing independently: run review in each mode, verify three distinct playbook records exist with no cross-contamination in `tests/integration/test_playbook_versioning.py`

### Implementation for User Story 4

- [X] T024 [P] [US4] Verify precheck-nda-v1.yaml has `metadata.version: "1.0.0"` (already present) and update description field to match spec format in `src/openreview_cli/review/playbooks/precheck-nda-v1.yaml`
- [X] T025 [P] [US4] Create dealcheck-nda-v1.yaml bundled playbook with `id: "dealcheck-nda-v1"`, `mode: "dealcheck"`, `version: "1.0.0"`, and NDA-focused categories (adapted from precheck template) in `src/openreview_cli/review/playbooks/dealcheck-nda-v1.yaml`
- [X] T026 [P] [US4] Create hirecheck-terms-v1.yaml bundled playbook with `id: "hirecheck-terms-v1"`, `mode: "hirecheck"`, `version: "1.0.0"`, and employment-terms categories in `src/openreview_cli/review/playbooks/hirecheck-terms-v1.yaml`

**Checkpoint**: User Stories 1–4 complete. Three bundled playbooks version independently. All tests pass.

---

## Phase 7: User Story 5 — Explicit Playbook Version Pin (Priority: P3)

**Goal**: A power user pins a specific playbook version via `--playbook-version <semver>`. The system reuses a stored version if available, or validates the YAML's version against the pin. Mismatch produces a clear error.

**Independent Test**: `--playbook-version` with a stored version loads that version without re-parsing. `--playbook-version` that doesn't match the YAML produces an error. Standalone `--playbook-version` without `--playbook` errors.

### Tests for User Story 5

- [X] T027 [P] [US5] Unit test for --playbook-version resolution logic: stored version reused, version mismatch error, standalone flag error in `tests/unit/test_playbook.py`
- [X] T028 [P] [US5] Integration test for version pin reuse (no new row created) and version mismatch error (clear error message) in `tests/integration/test_playbook_versioning.py`

### Implementation for User Story 5

- [X] T029 [US5] Add `--playbook-version` optional string CLI flag to precheck review command definition, with validation that it requires `--playbook`, in `src/openreview_cli/app.py` (around line 441)
- [X] T030 [US5] Implement version pin resolution in playbook loader: load YAML → extract id → query DB by (id, pin) → reuse stored content if found → validate embedded version if not found → error on mismatch in `src/openreview_cli/review/playbook.py`
- [X] T031 [US5] Wire --playbook-version through run_review() signature and pass to playbook loader in `src/openreview_cli/review/__init__.py`

**Checkpoint**: All user stories complete. Version pinning works end-to-end. All tests pass.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Validation, documentation, and cleanup touching all stories.

- [X] T032 [P] Run quickstart.md validation scenarios (Scenarios 1–10) from `specs/017-playbook-versioning/quickstart.md` and verify all pass
- [X] T033 [P] Add docstrings to all new functions (map_position_name, content_hash, CRUD functions), update module-level docs in `src/openreview_cli/review/playbook.py` and `src/openreview_cli/storage/database.py`
- [X] T034 Run full test suite (`pytest tests/unit/ -q`), mypy strict, ruff check, and pre-commit to verify no regressions

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ──► Phase 2 (Foundational) ──► Phase 3 (US1 — MVP)
                                                       │
                                                       ├──► Phase 4 (US2 — P1)
                                                       │
                                                       ├──► Phase 5 (US3 — P2)
                                                       │
                                                       ├──► Phase 6 (US4 — P2)
                                                       │
                                                       └──► Phase 7 (US5 — P3)
                                                               │
                                                               └──► Phase 8 (Polish)
```

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Stories (3–7)**: All depend on Foundational. US1 must be complete before US2–5 because they build on the version-stamped loading mechanism. US2, US3, US4 can proceed in any order after US1. US5 depends on US1 (version storage exists) and US3 (content-change detection).
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Core loader before CLI wiring
- Story complete before moving to next priority

### User Story Dependency Details

| Story | Depends On | Why |
|-------|-----------|-----|
| US1 | Phase 1, Phase 2 | Needs DB schema and Position3 models |
| US2 | US1 | Needs version-stamped loader; adds auto-versioning on top |
| US3 | US1 | Needs version-stamped loader; adds content-change detection |
| US4 | US1 | Needs version-stamped loader; adds two new playbook files |
| US5 | US1, US3 | Needs version storage and content-hash detection for pin resolution |

### Parallel Opportunities

- **Phase 2**: T002 (Position3), T003 (dataclasses), T004 (hash + mapping) can run in parallel
- **US1 Tests**: T005, T006, T007 can run in parallel
- **US1 Implementation**: T011 (version detection) and T013 (review pipeline changes) can run in parallel with T010 (DB CRUD)
- **US4 Implementation**: T024, T025, T026 (three playbook files) can run in parallel
- **US5 Tests**: T027, T028 can run in parallel
- **Phase 8**: T032, T033 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Unit test for Position3 / dataclasses in tests/unit/test_playbook.py"
Task: "Unit test for content_hash / mapping in tests/unit/test_playbook.py"
Task: "Unit test for storage CRUD in tests/unit/test_storage.py"

# Launch DB CRUD and playbook version-detection together (different files):
Task: "Implement playbook_version CRUD in src/openreview_cli/storage/database.py"
Task: "Add version detection + hash in src/openreview_cli/review/playbook.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (migration script)
2. Complete Phase 2: Foundational (models, hash, mapping)
3. Complete Phase 3: User Story 1 (bundled playbook versioning)
4. **STOP and VALIDATE**: Test US1 independently
5. All 8 tests + integration tests pass

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → **MVP complete** (playbook versioning works for bundled playbook)
3. Add User Story 2 → Test independently → Custom playbook auto-versioning works
4. Add User Story 3 → Test independently → Content-change detection works
5. Add User Story 4 → Test independently → Three modes ship
6. Add User Story 5 → Test independently → Version pinning works
7. Final polish → Full feature complete

### Parallel Team Strategy

With multiple developers:

1. Team completes Phase 1 + Phase 2 together
2. Developer A: US1 (core loader) + US5 (version pin — depends on US1 loader)
3. Developer B: US2 (auto-versioning) + US4 (playbook files) — build on US1 foundation
4. Developer C: US3 (content-change detection) — build on US1 foundation
5. All converge for Phase 8 (Polish)

---

## Notes

- **[P] tasks** = different files, no dependencies — can run in parallel
- **[Story] label** = maps task to specific user story for traceability
- Each user story is independently completable and testable
- Within each story: write tests FIRST (TDD), ensure they FAIL, then implement
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- No new third-party dependencies — stdlib (`hashlib`, `sqlite3`) + existing `pyyaml` only
- No scope creep — single-party review only (R-7), no bilateral comparison

## Task Count

| Phase | Tasks | Story |
|-------|-------|-------|
| Phase 1: Setup | 1 | — |
| Phase 2: Foundational | 3 | — |
| Phase 3: US1 (P1 — MVP) | 11 | 5 tests + 6 implementation |
| Phase 4: US2 (P1) | 3 | 2 tests + 1 implementation |
| Phase 5: US3 (P2) | 3 | 2 tests + 1 implementation |
| Phase 6: US4 (P2) | 5 | 2 tests + 3 implementation |
| Phase 7: US5 (P3) | 5 | 2 tests + 3 implementation |
| Phase 8: Polish | 3 | — |
| **Total** | **34** | **13 tests + 20 implementation + 2 polish** |

---



## Phase 9: Convergence

**Purpose**: Close gaps identified during convergence analysis between the spec/data-model and the implemented codebase.

- [X] T035 Add `mode`, `description`, `author` columns to `playbook` table and `category_count` column to `playbook_version` table in `src/openreview_cli/storage/migrations/006_playbook_versioning.sql`; add `ON DELETE CASCADE` to the `playbook_version` FK per `data-model.md` (FR-2, partial)
- [X] T036 Update `ensure_playbook_record()` in `src/openreview_cli/storage/database.py` to store `mode`, `description`, and `author` from the parsed playbook metadata per `data-model.md` PlaybookRecord entity (FR-2, partial)
