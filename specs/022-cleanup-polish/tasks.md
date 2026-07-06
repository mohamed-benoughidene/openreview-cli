---

description: "Test coverage tasks for Cleanup & Polish — Close Remaining Test Gaps"

---

# Tasks: Cleanup & Polish — Close Remaining Test Gaps

**Input**: Design documents from `specs/022-cleanup-polish/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/CLI-interface.md, quickstart.md

**Organization**: Tasks grouped by user story. Each story independently testable. TDD ordering: test file before fixtures before integration.

**Scope**: Test-only. Zero production code changes. All features already shipped.

## Format

- `[P]`: Parallelizable (different files, no dependencies)
- `[Story]`: Which user story this task belongs to
- Include exact file paths in descriptions

---

## Phase 1: Setup & Verification

**Purpose**: Codebase orientation, verify existing production code state, confirm test infrastructure.

- [x] T001 Read existing review command base class at `src/openreview_cli/review/base.py` to confirm `--no-pii` flag definition and PII orchestration path
- [x] T002 [P] Read existing playbook loader at `src/openreview_cli/review/playbook.py` to confirm `--playbook` / `--playbook-path` flag handling and precedence logic
- [x] T003 [P] Read existing bilateral comparison subcommand in `src/openreview_cli/app.py` to confirm flag names, validators, error messages, and exit codes
- [x] T004 [P] Read existing integration test `tests/integration/test_precheck_pii.py` to extract mock patterns for gateway and PII engine
- [x] T005 [P] Read existing test fixtures directory at `tests/fixtures/` to confirm available sample documents for bilateral comparison tests
- [x] T006 [P] Read existing `tests/conftest.py` to confirm `memory_tracker` fixture and `fixtures_dir` helper signatures

**Checkpoint**: Codebase orientation complete. All production code paths verified. Mock patterns documented.

---

## Phase 2: User Story 1 — Playbook Precedence Warning (R1)

**Goal**: Unit test verifying that `--playbook` + `--playbook-path` conflict emits warning on stderr, names both flags, states `--playbook-path` wins, and command proceeds with exit code 0.

**Independent Test**: `uv run pytest tests/unit/test_playbook_precedence.py -v`

### Unit Tests (TDD — write failing test first)

- [x] T007 [US1] Write failing unit test for playbook precedence warning emission in `tests/unit/test_playbook_precedence.py` — verify warning on stderr when both flags supplied, contains both flag names, and states `--playbook-path` wins

- [x] T008 [US1] Write failing unit test for playbook precedence execution continuation in `tests/unit/test_playbook_precedence.py` — verify exit code 0 and no crash after conflict warning

- [x] T009 [US1] Write failing unit test for playbook precedence no-warning in `tests/unit/test_playbook_precedence.py` — verify no warning on stderr when only one flag is supplied

### Implementation (test-supporting helpers)

- [x] T010 [US1] Add test helper for invoking review command with dual playbook flags — create `_invoke_with_playbook_conflict()` fixture or helper in `tests/unit/test_playbook_precedence.py`
- [x] T011 [US1] Verify playbook precedence warning already exists in production code — confirm `warnings.warn()` call at `src/openreview_cli/review/__init__.py:102-107` emits message naming both flags and stating `--playbook-path` wins when both `--playbook` and `--playbook-path` are supplied (note: verification confirms no production code change needed)

### Integration Validation

- [x] T012 [US1] Run test and confirm green: `uv run pytest tests/unit/test_playbook_precedence.py -v`
- [x] T013 [US1] Run manual smoke test: `uv run openreview precheck --playbook precheck-nda-v1 --playbook-path /nonexistent/playbook.yaml tests/fixtures/sample-nda.pdf` — verify warning on stderr, execution proceeds

**Checkpoint**: Playbook precedence warning functional and tested. US1 complete.

---

## Phase 3: User Story 2 — Bilateral Comparison CLI (R2-R3)

**Goal**: Unit tests for bilateral comparison CLI input validation (missing file, unsupported format, unreadable, same file), flag parsing, help output, and successful comparison.

**Independent Test**: `uv run pytest tests/unit/test_bilateral_comparison.py -v`

### Unit Tests (TDD — write failing test first)

- [x] T014 [P] [US2] Write failing unit test for missing-file validation in `tests/unit/test_bilateral_comparison.py` — exit code != 0, stderr contains "not found" + path
- [x] T015 [P] [US2] Write failing unit test for unsupported-format validation in `tests/unit/test_bilateral_comparison.py` — exit code != 0, stderr names format (e.g. ".txt")
- [x] T016 [P] [US2] Write failing unit test for unreadable-file validation in `tests/unit/test_bilateral_comparison.py` — exit code != 0, stderr mentions "permission" or "unreadable"
- [x] T017 [P] [US2] Write failing unit test for same-file detection in `tests/unit/test_bilateral_comparison.py` — exit code != 0, stderr mentions "same" or "identical"
- [x] T018 [US2] Write failing unit test for valid comparison success in `tests/unit/test_bilateral_comparison.py` — exit code 0, comparison output on stdout
- [x] T019 [US2] Write failing unit test for flag parsing in `tests/unit/test_bilateral_comparison.py` — verify `--output`, `--format` flags accepted and parsed correctly
- [x] T020 [US2] Write failing unit test for help output in `tests/unit/test_bilateral_comparison.py` — verify `--help` contains subcommand name and all flags

### Fixture Creation

- [x] T021 [P] [US2] Create minimal sample DOCX fixture at `tests/fixtures/sample-compare-a.docx` for bilateral comparison tests (if not already present)
- [x] T022 [P] [US2] Create minimal sample PDF fixture at `tests/fixtures/sample-compare-b.pdf` for bilateral comparison tests (if not already present)

### Integration Validation

- [x] T023 [US2] Run test and confirm green: `uv run pytest tests/unit/test_bilateral_comparison.py -v`
- [x] T024 [US2] Run manual smoke test: `uv run openreview compare tests/fixtures/sample-nda.pdf tests/fixtures/sample-nda.pdf` — verify exit 0
- [x] T025 [US2] Run manual error test: `uv run openreview compare tests/fixtures/nonexistent.pdf tests/fixtures/sample-nda.pdf` — verify error on stderr, exit != 0
- [x] T026 [US2] Run help smoke test: `uv run openreview compare --help` — verify all flags documented

**Checkpoint**: Bilateral comparison CLI validation complete. US2 complete.

---

## Phase 4: User Story 3 — PII `--no-pii` Flag (R4-R5)

**Goal**: Integration test verifying `--no-pii` flag exists on all review subcommands, bypasses PII engine, and default behavior still strips PII. Integration test (previously skeleton T066) is fully populated.

**Independent Test**: `uv run pytest tests/integration/test_no_pii_flag.py -v`

### Integration Tests (TDD — write failing test first)

- [x] T060 [US3] Write failing integration test for `--no-pii` flag acceptance in `tests/integration/test_no_pii_flag.py` — invoke precheck (or equivalent review subcommand) with `--no-pii`, confirm no crash
- [x] T061 [US3] Write failing integration test for PII engine bypass in `tests/integration/test_no_pii_flag.py` — mock PiiEngine, invoke with `--no-pii`, assert mock call count = 0
- [x] T062 [US3] Write failing integration test for gateway receives raw text in `tests/integration/test_no_pii_flag.py` — mock gateway call, invoke with `--no-pii`, assert gateway receives unstripped text
- [x] T063 [US3] Write failing integration test for default PII stripping in `tests/integration/test_no_pii_flag.py` — invoke without `--no-pii`, assert PiiEngine call count > 0
- [x] T064 [US3] Write failing integration test for gateway receives stripped text in `tests/integration/test_no_pii_flag.py` — invoke without `--no-pii`, assert gateway receives stripped text
- [x] T065 [P] [US3] Write failing test for `--no-pii` flag in help output in `tests/unit/test_app.py` or dedicated test — verify `--help` on each review subcommand lists `--no-pii`
- [x] T066 [P] [US3] Write failing test for `--no-pii` acceptance across all review subcommands in `tests/integration/test_no_pii_flag.py` — parameterized test over precheck, hirecheck, dealcheck (or whatever subcommands exist)

### Mock Wiring

- [x] T067 [US3] Add mock fixture for `PiiEngine.detect_all_pages()` in `tests/integration/test_no_pii_flag.py` — returns `MockPiiEngineResult` with controlled return values
- [x] T068 [US3] Add mock fixture for `openreview_cli.review._gateway.call_gateway` in `tests/integration/test_no_pii_flag.py` — returns `MockGatewayResponse` with controlled content

### Integration Validation

- [x] T069 [US3] Run all test_no_pii_flag tests: `uv run pytest tests/integration/test_no_pii_flag.py -v`
- [x] T070 [US3] Run manual smoke test with flag: `uv run openreview precheck --no-pii tests/fixtures/sample-nda.pdf`
- [x] T071 [US3] Run manual smoke test without flag: `uv run openreview precheck tests/fixtures/sample-nda.pdf`

**Checkpoint**: `--no-pii` flag fully tested across all review commands. US3 complete.

---

## Phase 5: Validation & Cross-Cutting Checks

**Purpose**: Full-suite regression check, memory budget verification, pre-commit gate, quickstart validation.

- [x] T072 [P] Run full unit test suite: `uv run pytest tests/unit/ -q` — confirm no regressions
- [x] T073 [P] Run memory budget tests: `uv run pytest -m memory -v` — confirm peak < 110 MB with new tests
- [x] T074 [P] Run full integration suite: `uv run pytest tests/integration/ -q` — no regressions
- [x] T075 Run full pre-commit suite: `uv run pre-commit run --all-files` — pass lint, types, format, pytest-fast
- [x] T076 Run quickstart validation: execute all commands in `specs/022-cleanup-polish/quickstart.md` — confirm all pass
- [x] T077 Final check: full test suite `uv run pytest -q` — all green

**Checkpoint**: All tests green. Pre-commit clean. No regressions.

---

## Dependencies & Execution Order

### Phase Dependencies

| Phase | Depends On | Notes |
|-------|------------|-------|
| **P1** Setup | None | Can start immediately — codebase reads only |
| **P2** US1 (Playbook) | P1 | Read playbook.py before writing tests |
| **P3** US2 (Compare) | P1 | Read app.py before writing tests |
| **P4** US3 (No-PII) | P1 | Read base.py + test_precheck_pii.py for mock patterns |
| **P5** Validation | P2, P3, P4 | All US phases must complete |

### Within Each User Story

- Read existing code → Write failing test → Add helpers/fixtures → Make test pass → Integration validation

### Parallel Opportunities

- **Phase 1**: All T001-T006 can run in parallel (different files, no deps)
- **Phase 2**: T007 and T008 can be written in parallel (same file, different test functions)
- **Phase 3**: T014-T017 can be written in parallel (same file, different tests). T021-T022 (fixtures) parallel with tests
- **Phase 4**: T060-T066 can be written in parallel (same file, different tests). T067-T068 (mock fixtures) parallel with tests
- **Phase 5**: T072-T074 run in parallel (different test subsets)

### US-to-US Dependencies

- **US1 → US2**: None — independent. Different files, no shared state.
- **US1 → US3**: None — independent. Different files, no shared state.
- **US2 → US3**: None — independent. Different files, no shared state.

All three user stories can be implemented in any order or in parallel.

---

## Parallel Example: All Three User Stories

```bash
# US1 Terminal
uv run pytest tests/unit/test_playbook_precedence.py -v

# US2 Terminal
uv run pytest tests/unit/test_bilateral_comparison.py -v

# US3 Terminal
uv run pytest tests/integration/test_no_pii_flag.py -v
```

---

## Implementation Strategy

### MVP Scope (Phase 2 only — US1: Playbook Precedence Warning)

1. Complete Phase 1: Setup
2. Complete Phase 2: US1 — Playbook Precedence
3. **STOP and VALIDATE**: `uv run pytest tests/unit/test_playbook_precedence.py -v`
4. MVP delivers: playbook conflict warning functional and tested

### Full Delivery

1. Complete Phase 1: Setup
2. Complete US1 (Playbook Precedence)
3. Complete US2 (Bilateral Comparison CLI)
4. Complete US3 (PII --no-pii Flag)
5. Complete Phase 5: Validation

---

## Summary

| Metric | Count |
|--------|-------|
| **Total tasks** | 44 |
| **Phase 1 — Setup** | 6 |
| **Phase 2 — US1 (Playbook)** | 7 |
| **Phase 3 — US2 (Compare)** | 13 |
| **Phase 4 — US3 (No-PII)** | 12 |
| **Phase 5 — Validation** | 6 |
| **Parallelizable tasks** | 19 (marked [P]) |
| **New test files** | 3 |
| **Production code changes** | 0 |
| **MVP scope** | US1 only (T007-T013) |
