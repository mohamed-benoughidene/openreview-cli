# Tasks: PII-to-Chunk Pipeline Bridge

**Input**: Design documents from `/specs/008-pii-chunk-bridge/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md

**Tests**: TDD approach — tests written before implementation per project convention

**Organization**: Tasks grouped by user story for independent implementation and testing

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No setup needed — project structure and dependencies already exist

*No tasks required — skip to Phase 2*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No foundational work needed — all infrastructure (PII engine, chunking module, test framework) already exists

*No tasks required — skip to Phase 3*

---

## Phase 3: User Story 1 - Per-Clause PII Stripping with Clause Preservation (Priority: P1) 🎯 MVP

**Goal**: Implement `strip_pii_clauses()` that strips PII from each clause's text individually while preserving clause metadata (id, title, level, parent_id, source_page, source_paragraph, source_span).

**Independent Test**: Pass a list of clauses with known PII → verify each output clause has same metadata and text contains placeholders instead of raw PII.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T001 [P] [US1] Add unit test `test_strip_pii_clauses_preserves_metadata` in `tests/unit/test_pii_engine.py` — verify all clause metadata fields unchanged after stripping
- [X] T002 [P] [US1] Add unit test `test_strip_pii_clauses_replaces_pii` in `tests/unit/test_pii_engine.py` — verify clause text contains placeholders (e.g., `[PARTY_1]`) instead of raw PII
- [X] T003 [P] [US1] Add unit test `test_strip_pii_clauses_empty_input` in `tests/unit/test_pii_engine.py` — verify empty list returns `([], PiiResult)` with empty mapping
- [X] T004 [P] [US1] Add unit test `test_strip_pii_clauses_no_pii_unchanged` in `tests/unit/test_pii_engine.py` — verify clause with no PII has unchanged text and no mapping entries
- [X] T005 [P] [US1] Add unit test `test_strip_pii_clauses_metadata_entities` in `tests/unit/test_pii_engine.py` — verify metadata placeholders (FILENAME, AUTHOR, TITLE, COMPANY) are appended to last clause when not found in clause text
- [X] T006 [P] [US1] Add performance test `test_strip_pii_clauses_performance` in `tests/unit/test_pii_engine.py` — verify `strip_pii_clauses()` execution time is within 10% of `strip_pii()` for the same document (wall-clock time averaged over 3 runs using `time.perf_counter()`)

### Implementation for User Story 1

- [X] T007 [US1] Implement `strip_pii_clauses(clauses, document, **kwargs) -> tuple[list[Clause], PiiResult]` in `src/openreview_cli/pii/engine.py` — reuse `detect_all_pages()` for detection, do per-clause text replacement using mapping, preserve all clause metadata fields
- [X] T008 [US1] Add metadata entity handling in `strip_pii_clauses()` in `src/openreview_cli/pii/engine.py` — append metadata placeholders (FILENAME, AUTHOR, TITLE, COMPANY) to last clause if not found in any clause text
- [X] T009 [US1] Add partial failure handling in `strip_pii_clauses()` in `src/openreview_cli/pii/engine.py` — return stripped clauses for successes with warning if some clauses fail PII detection (match existing `strip_pii()` behavior)
- [X] T010 [US1] Export `strip_pii_clauses` in `src/openreview_cli/pii/__init__.py` — add to `__all__` list

**Checkpoint**: User Story 1 complete — `strip_pii_clauses()` function works, all unit tests pass

---

## Phase 4: User Story 2 - End-to-End PII-Safe Chunking (Priority: P1)

**Goal**: Integration test that proves the full pipeline (parse → strip_pii_clauses → stream_chunks) produces chunks with no raw PII. Delivers T014 from spec 007.

**Independent Test**: Parse a PDF with known PII → strip_pii_clauses → stream_chunks → verify no chunk text contains raw PII strings.

### Tests for User Story 2 ⚠️

- [X] T011 [US2] Add integration test `test_pii_safe_chunking` in `tests/integration/test_chunking_cli.py` — parse PDF fixture with PII, run strip_pii_clauses, chunk result, assert no raw PII in any chunk text

### Implementation for User Story 2

- [X] T012 [US2] Verify integration test fixture exists in `tests/fixtures/` — ensure a PDF with known PII patterns (emails, phone numbers, party names) is available for T014 test. If no suitable fixture exists, create `tests/fixtures/nda_with_pii.pdf` with seeded PII: at least 2 party names, 1 email, 1 phone number, and 1 date.

**Checkpoint**: User Story 2 complete — T014 integration test passes, full pipeline verified

---

## Phase 5: User Story 3 - No Regression on Existing PII Pipeline (Priority: P2)

**Goal**: Verify that existing `strip_pii()` and `strip_and_persist()` functions behave identically after adding the bridge. Zero regressions in existing PII test suite.

**Independent Test**: Run all existing `test_pii_*` and `test_precheck_pii` tests — all must pass with zero changes.

### Tests for User Story 3 ⚠️

- [X] T013 [US3] Run full PII test suite in `tests/unit/test_pii_*.py` — verify all existing tests pass with zero changes
- [X] T014 [US3] Run precheck PII tests in `tests/integration/test_precheck_pii.py` — verify all precheck tests pass with zero changes

### Implementation for User Story 3

*No implementation tasks — this story is verification only*

**Checkpoint**: User Story 3 complete — zero regressions confirmed

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [X] T015 [P] Run quickstart.md validation scenarios in `specs/008-pii-chunk-bridge/quickstart.md` — verify all 5 scenarios pass
- [X] T016 [P] Run full test suite `uv run pytest tests/unit/ tests/integration/` — verify all tests pass
- [X] T017 [P] Run linting and type checking `uv run ruff check . && uv run mypy src/` — verify no lint or type errors

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No setup needed
- **Foundational (Phase 2)**: No foundational work needed
- **User Story 1 (Phase 3)**: Can start immediately
- **User Story 2 (Phase 4)**: Depends on US1 completion (needs `strip_pii_clauses()` function)
- **User Story 3 (Phase 5)**: Can run in parallel with US2 (verification only)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies — can start immediately
- **User Story 2 (P1)**: Depends on US1 (needs `strip_pii_clauses()` function)
- **User Story 3 (P2)**: No dependencies — can run in parallel with US2

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD)
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- T001-T006 (US1 tests) can run in parallel
- T013-T014 (US3 verification) can run in parallel
- T015-T017 (Polish tasks) can run in parallel
- US2 and US3 can run in parallel after US1 completes

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Add unit test test_strip_pii_clauses_preserves_metadata in tests/unit/test_pii_engine.py"
Task: "Add unit test test_strip_pii_clauses_replaces_pii in tests/unit/test_pii_engine.py"
Task: "Add unit test test_strip_pii_clauses_empty_input in tests/unit/test_pii_engine.py"
Task: "Add unit test test_strip_pii_clauses_no_pii_unchanged in tests/unit/test_pii_engine.py"
Task: "Add unit test test_strip_pii_clauses_metadata_entities in tests/unit/test_pii_engine.py"
Task: "Add performance test test_strip_pii_clauses_performance in tests/unit/test_pii_engine.py"

# Then implement:
Task: "Implement strip_pii_clauses() in src/openreview_cli/pii/engine.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 3: User Story 1 (T001-T010)
2. **STOP and VALIDATE**: Run `uv run pytest tests/unit/test_pii_engine.py -v`
3. All US1 tests should pass
4. Deploy/demo if ready

### Incremental Delivery

1. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
2. Add User Story 2 → Test independently → Deploy/Demo
3. Add User Story 3 → Verify no regressions → Final release

### Parallel Team Strategy

With multiple developers:

1. Developer A: User Story 1 (T001-T010)
2. After US1 completes:
   - Developer A: User Story 2 (T011-T012)
   - Developer B: User Story 3 (T013-T014)
3. Polish phase (T015-T017) can be split across developers

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Verify tests fail before implementing (TDD)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
