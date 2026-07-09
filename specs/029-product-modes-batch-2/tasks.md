---

description: "Task list for Product Modes Batch 2 — 5 new L-4b modes + 9 orphan mode CLI wiring + tests"
---

# Tasks: Product Modes Batch 2 (AssetCheck, BuyCheck, EngageCheck, GuaranteeCheck, LoanCheck + 9 Orphan Modes)

**Input**: `specs/029-product-modes-batch-2/`

**Branch**: `feat/029-product-modes-batch-2`

**Design artifacts**: spec.md (6 user stories, all P1), plan.md, research.md, data-model.md, quickstart.md, contracts/ (14 interface contracts)

**TDD enforcement**: Tests MUST be written BEFORE implementation code in every user story phase (constitutional Principle V). Each user story has test tasks physically preceding implementation tasks.

## Format: `[ID] [P?] [Story] Description with file path`

- `[P]`: Parallelizable — different files, no dependencies on incomplete tasks
- `[Story]`: Maps task to user story (US1–US6). Setup/Foundational/Polish have no story label.

---

## Phase 1: Setup

**Purpose**: Branch validation, dependency verification, build smoke test

- [X] T001 Verify branch `feat/029-product-modes-batch-2` exists, run `uv sync`, verify `uv run openreview --version` exits 0

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Verify orphan-mode prerequisites already on disk. Extend shared test infrastructure for CLI routing tests across all 14 modes.

**⚠️ CRITICAL**: Must complete before ANY user story. Required for all 5 new modes and all 9 orphan modes.

- [X] T002 Verify prerequisites for all 9 orphan modes: confirm each has playbook YAML in `src/openreview_cli/review/playbooks/`, entry in `BUNDLED_PLAYBOOKS` in `src/openreview_cli/review/playbook.py`, and entry in `MODE_VOCABULARY` in `src/openreview_cli/review/prompts.py`. List: licensecheck, leasecheck, privacycheck, indemnitycheck, consultcheck, workcheck, loicheck, subcheck, settlementcheck.
- [X] T003 [P] Extend parametrize decorators in `tests/unit/test_app.py` — add all 14 modes (5 new + 9 orphan) to `test_product_mode_help_contains_mode` and `test_product_mode_shows_confidence_threshold` parametrize lists. Orphan modes that are already registered get test coverage; new modes get test coverage after their CLI registration task completes.
- [X] T004 [P] Create shared test helper `_assert_subcommand_registers(mode_name, help_keyword)` in `tests/unit/test_app.py` for reuse across orphan mode CLI routing tests. Helper must: invoke `--help`, assert exit 0, assert help text contains keyword.

---

## Phase 3: User Story 1 — AssetCheck (Priority: P1)

**Goal**: AssetCheck — review asset transfer/assignment agreements. New playbook YAML, MODE_VOCABULARY entry, BUNDLED_PLAYBOOKS entry, CLI subcommand, full smoke test.

**Independent Test**: `uv run pytest tests/integration/test_assetcheck.py -v`

### Tests for US1 (write FIRST, ensure FAIL before impl)

- [X] T005 [P] [US1] Create fixture document at `tests/fixtures/asset-transfer.pdf` — minimal valid PDF covering asset identification, exclusions, representations, price/title, as-is condition (1-3 pages)
- [X] T006 [P] [US1] Add AssetCheck playbook schema validation test in `tests/unit/test_playbook_schema.py` — assert `load_playbook()` succeeds for `asset-transfer-v1.yaml`
- [X] T007 [US1] Create AssetCheck integration smoke test at `tests/integration/test_assetcheck.py` — validates: `--help` shows mode-specific text, default playbook loads, `run_review()` returns non-empty `ReviewReport` with at least one clause assessment

### Implementation for US1

- [X] T008 [P] [US1] Create playbook YAML at `src/openreview_cli/review/playbooks/asset-transfer-v1.yaml` — 5 categories following 3-position schema (asset description/exclusions/representations/price-title/as-is-regulatory)
- [X] T009 [P] [US1] Add `"assetcheck"` entry to `MODE_VOCABULARY` in `src/openreview_cli/review/prompts.py` — specialization, domain, vocabulary for asset transfer agreements
- [X] T010 [P] [US1] Add `"assetcheck"` entry to `BUNDLED_PLAYBOOKS` in `src/openreview_cli/review/playbook.py` — maps to `asset-transfer-v1.yaml`
- [X] T011 [US1] Register `assetcheck` CLI subcommand in `src/openreview_cli/app.py` via `_register_product_mode(app, name="assetcheck", ...)` — help text: "Review an asset transfer/assignment agreement with AssetCheck."

---

## Phase 4: User Story 2 — BuyCheck (Priority: P1)

**Goal**: BuyCheck — review asset purchase/business acquisition agreements. New playbook YAML, MODE_VOCABULARY entry, BUNDLED_PLAYBOOKS entry, CLI subcommand, full smoke test.

**Independent Test**: `uv run pytest tests/integration/test_buycheck.py -v`

### Tests for US2 (write FIRST, ensure FAIL before impl)

- [X] T012 [P] [US2] Create fixture document at `tests/fixtures/asset-purchase.pdf` — minimal PDF covering price, asset list, liabilities, reps, closing conditions
- [X] T013 [P] [US2] Add BuyCheck playbook schema validation test in `tests/unit/test_playbook_schema.py` — assert `load_playbook()` succeeds for `asset-purchase-v1.yaml`
- [X] T014 [US2] Create BuyCheck integration smoke test at `tests/integration/test_buycheck.py` — validates: `--help`, playbook schema, `run_review()` non-empty

### Implementation for US2

- [X] T015 [P] [US2] Create playbook YAML at `src/openreview_cli/review/playbooks/asset-purchase-v1.yaml` — 5 categories (price, asset list, liabilities, reps, closing)
- [X] T016 [P] [US2] Add `"buycheck"` entry to `MODE_VOCABULARY` in `src/openreview_cli/review/prompts.py`
- [X] T017 [P] [US2] Add `"buycheck"` entry to `BUNDLED_PLAYBOOKS` in `src/openreview_cli/review/playbook.py` — maps to `asset-purchase-v1.yaml`
- [X] T018 [US2] Register `buycheck` CLI subcommand in `src/openreview_cli/app.py` via `_register_product_mode(app, name="buycheck", ...)` — help text: "Review an asset purchase/business acquisition agreement with BuyCheck."

---

## Phase 5: User Story 3 — EngageCheck (Priority: P1)

**Goal**: EngageCheck — review professional services engagement letters. New playbook YAML, MODE_VOCABULARY entry, BUNDLED_PLAYBOOKS entry, CLI subcommand, full smoke test.

**Independent Test**: `uv run pytest tests/integration/test_engagecheck.py -v`

### Tests for US3 (write FIRST, ensure FAIL before impl)

- [X] T019 [P] [US3] Create fixture document at `tests/fixtures/engagement-letter.pdf` — minimal PDF covering SOW, fees, IP, confidentiality, termination
- [X] T020 [P] [US3] Add EngageCheck playbook schema validation test in `tests/unit/test_playbook_schema.py` — assert `load_playbook()` succeeds for `engagement-letter-v1.yaml`
- [X] T021 [US3] Create EngageCheck integration smoke test at `tests/integration/test_engagecheck.py` — validates: `--help`, playbook schema, `run_review()` non-empty

### Implementation for US3

- [X] T022 [P] [US3] Create playbook YAML at `src/openreview_cli/review/playbooks/engagement-letter-v1.yaml` — 5 categories (SOW, fees, IP, confidentiality, termination)
- [X] T023 [P] [US3] Add `"engagecheck"` entry to `MODE_VOCABULARY` in `src/openreview_cli/review/prompts.py`
- [X] T024 [P] [US3] Add `"engagecheck"` entry to `BUNDLED_PLAYBOOKS` in `src/openreview_cli/review/playbook.py` — maps to `engagement-letter-v1.yaml`
- [X] T025 [US3] Register `engagecheck` CLI subcommand in `src/openreview_cli/app.py` via `_register_product_mode(app, name="engagecheck", ...)` — help text: "Review a professional services engagement letter with EngageCheck."

---

## Phase 6: User Story 4 — GuaranteeCheck (Priority: P1)

**Goal**: GuaranteeCheck — review personal guarantees and suretyship agreements. New playbook YAML, MODE_VOCABULARY entry, BUNDLED_PLAYBOOKS entry, CLI subcommand, full smoke test.

**Independent Test**: `uv run pytest tests/integration/test_guaranteecheck.py -v`

### Tests for US4 (write FIRST, ensure FAIL before impl)

- [X] T026 [P] [US4] Create fixture document at `tests/fixtures/personal-guarantee.pdf` — minimal PDF covering guarantee type, liability scope, waivers, confession, release
- [X] T027 [P] [US4] Add GuaranteeCheck playbook schema validation test in `tests/unit/test_playbook_schema.py` — assert `load_playbook()` succeeds for `personal-guarantee-v1.yaml`
- [X] T028 [US4] Create GuaranteeCheck integration smoke test at `tests/integration/test_guaranteecheck.py` — validates: `--help`, playbook schema, `run_review()` non-empty

### Implementation for US4

- [X] T029 [P] [US4] Create playbook YAML at `src/openreview_cli/review/playbooks/personal-guarantee-v1.yaml` — 5 categories (guarantee type, liability scope, waiver, confession, release)
- [X] T030 [P] [US4] Add `"guaranteecheck"` entry to `MODE_VOCABULARY` in `src/openreview_cli/review/prompts.py`
- [X] T031 [P] [US4] Add `"guaranteecheck"` entry to `BUNDLED_PLAYBOOKS` in `src/openreview_cli/review/playbook.py` — maps to `personal-guarantee-v1.yaml`
- [X] T032 [US4] Register `guaranteecheck` CLI subcommand in `src/openreview_cli/app.py` via `_register_product_mode(app, name="guaranteecheck", ...)` — help text: "Review a personal guarantee/suretyship agreement with GuaranteeCheck."

---

## Phase 7: User Story 5 — LoanCheck (Priority: P1)

**Goal**: LoanCheck — review loan agreements and promissory notes. New playbook YAML, MODE_VOCABULARY entry, BUNDLED_PLAYBOOKS entry, CLI subcommand, full smoke test.

**Independent Test**: `uv run pytest tests/integration/test_loancheck.py -v`

### Tests for US5 (write FIRST, ensure FAIL before impl)

- [X] T033 [P] [US5] Create fixture document at `tests/fixtures/loan-agreement.pdf` — minimal PDF covering loan terms, default, collateral, covenants, cross-default
- [X] T034 [P] [US5] Add LoanCheck playbook schema validation test in `tests/unit/test_playbook_schema.py` — assert `load_playbook()` succeeds for `loan-agreement-v1.yaml`
- [X] T035 [US5] Create LoanCheck integration smoke test at `tests/integration/test_loancheck.py` — validates: `--help`, playbook schema, `run_review()` non-empty

### Implementation for US5

- [X] T036 [P] [US5] Create playbook YAML at `src/openreview_cli/review/playbooks/loan-agreement-v1.yaml` — 5 categories (loan terms, default, collateral, covenants, cross-default)
- [X] T037 [P] [US5] Add `"loancheck"` entry to `MODE_VOCABULARY` in `src/openreview_cli/review/prompts.py`
- [X] T038 [P] [US5] Add `"loancheck"` entry to `BUNDLED_PLAYBOOKS` in `src/openreview_cli/review/playbook.py` — maps to `loan-agreement-v1.yaml`
- [X] T039 [US5] Register `loancheck` CLI subcommand in `src/openreview_cli/app.py` via `_register_product_mode(app, name="loancheck", ...)` — help text: "Review a loan agreement/promissory note with LoanCheck."

---

## Phase 8: User Story 6 — 9 Orphan Modes CLI Wiring (Priority: P1)

**Goal**: Verify and test CLI wiring for 9 orphan modes. Playbook YAMLs, BUNDLED_PLAYBOOKS entries, and MODE_VOCABULARY entries already exist from prior specs. Add CLI routing smoke test to confirm subcommand registers, `--help` displays mode-specific text, invokes correct playbook, exits cleanly.

**Per spec clarification**: CLI routing test only — no fixture documents or `run_review()` assertions required.

**Independent Test**: `uv run pytest tests/integration/test_orphan_modes.py -v`

### Tests for US6 (write FIRST, ensure FAIL before impl)

- [X] T040 [US6] Create orphan modes CLI routing test at `tests/integration/test_orphan_modes.py` — 9 parametrized test cases, one per orphan mode. Each case: invoke `--help`, assert exit 0, assert mode-specific help text contains expected keyword. Modes: licensecheck, leasecheck, privacycheck, indemnitycheck, consultcheck, workcheck, loicheck, subcheck, settlementcheck.

### Implementation for US6

- [X] T041 [P] [US6] Add `_register_product_mode()` calls for orphan modes from spec 027 in `src/openreview_cli/app.py` — verify licensecheck, leasecheck, privacycheck are registered. Add if missing (3 × 3 lines).
- [X] T042 [P] [US6] Add `_register_product_mode()` calls for orphan modes from spec 028 (batch 1) in `src/openreview_cli/app.py` — verify indemnitycheck, consultcheck, workcheck are registered. Add if missing (3 × 3 lines).
- [X] T043 [P] [US6] Add `_register_product_mode()` calls for orphan modes from spec 028 (batch 2) in `src/openreview_cli/app.py` — verify loicheck, subcheck, settlementcheck are registered. Add if missing (3 × 3 lines).

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final verification — full test suite, code quality checks, quickstart validation.

- [X] T044 Run `uv run pytest tests/unit/ tests/integration/ -k 'not memory' -q` — all existing + new tests pass
- [X] T045 [P] Run `uv run ruff check src/openreview_cli/` — no new lint errors
- [X] T046 [P] Run `uv run mypy src/openreview_cli/ --strict` — no new type errors
- [X] T047 Run `uv run openreview --help` — verify all 14 new subcommands appear in product-modes section. Check each individual `--help`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1–US5 (Phases 3–7)**: Depend on Foundational phase. Independent of each other — can proceed in parallel across implementers.
- **US6 (Phase 8)**: Depends on Foundational phase. Independent of US1–US5 — orphan wiring touches app.py only, no new playbooks/prompts.
- **Polish (Phase 9)**: Depends on all user story phases.

### Within Each User Story

| Step | Rule |
|------|------|
| Tests | MUST be written and FAIL before implementation |
| Playbook YAML | Independent — [P] with other file tasks |
| MODE_VOCABULARY | Independent — [P] with other file tasks |
| BUNDLED_PLAYBOOKS | Independent — [P] with other file tasks |
| CLI registration | Depends on BUNDLED_PLAYBOOKS entry existing |

### Parallel Opportunities

| Tasks | Why parallel |
|-------|-------------|
| T003 and T004 | Different functions in same file; helper can be created before decorator updates |
| T005 and T006 | Fixture creation and test addition touch different files |
| T008, T009, T010 | Three different files (playbook YAML, prompts.py, playbook.py) |
| US1–US5 across different implementers | Different playbook YAMLs, different dict keys, different _register_product_mode calls |
| T044, T045, T046 | Independent tools (pytest, ruff, mypy) |
| T041, T042, T043 | Three call blocks in same file can be added independently |

### Parallel Example: US1 — AssetCheck

```bash
# Launch all test preparations together:
# Task T005: Create fixture tests/fixtures/asset-transfer.pdf
# Task T006: Add schema test in test_playbook_schema.py

# Launch all file creations together (after tests):
# Task T008: Create playbook YAML playbooks/asset-transfer-v1.yaml
# Task T009: Add MODE_VOCABULARY entry in prompts.py
# Task T010: Add BUNDLED_PLAYBOOKS entry in playbook.py

# Then:
# Task T007: Create integration smoke test (needs fixture)
# Task T011: Register CLI subcommand in app.py (needs BUNDLED_PLAYBOOKS entry)
```

---

## Implementation Strategy

### MVP First (US1 — AssetCheck)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 — AssetCheck (playbook YAML + MODE_VOCABULARY + BUNDLED_PLAYBOOKS + CLI + tests)
4. **STOP and VALIDATE**: `uv run pytest tests/integration/test_assetcheck.py -v`
5. Each subsequent mode adds independently — no regressions between modes

### Incremental Delivery (recommended)

1. Phase 1 + 2 → Foundation verified
2. Phase 3 → US1 (AssetCheck) tested independently ✅
3. Phase 4 → US2 (BuyCheck) tested independently ✅
4. Phase 5 → US3 (EngageCheck) tested independently ✅
5. Phase 6 → US4 (GuaranteeCheck) tested independently ✅
6. Phase 7 → US5 (LoanCheck) tested independently ✅
7. Phase 8 → US6 (orphan modes) all wired and tested ✅
8. Phase 9 → All green, lint clean, types clean ✅

---

## Notes

- `[P]` tasks = different files, no dependencies — safe to execute in parallel
- Some orphan modes may already be registered in `app.py` (wired during prior specs). T041–T043 verify first, add only if missing.
- 5 new modes each create 7 files: test fixture PDF, unit test entry, integration test file, playbook YAML, 2 dict entries, 1 CLI registration
- Orphan modes create 1 test file + verify/add 9 CLI registrations
- Total new files: 5 fixture PDFs, 5 playbook YAMLs, 6 test files (5 smoke + 1 orphan routing)
- Total modified files: test_playbook_schema.py, test_app.py, prompts.py, playbook.py, app.py

---

## Phase 10: Convergence

**Purpose**: Close gaps between spec/plan/tasks and current implementation. Findings from `/speckit.converge` run.

**Blocked items** (not independently actionable): Memo export and JSON mode-field verification (SC items) depend on `run_review()` execution. Once F1 resolved, these become testable and should be added as follow-up tasks.

- [X] T048 Add mock-gateway `run_review()` non-empty smoke test to all 5 new-mode integration tests (`test_assetcheck.py`, `test_buycheck.py`, `test_engagecheck.py`, `test_guaranteecheck.py`, `test_loancheck.py`). Each must assert at least one clause assessment returned. per spec §Per-mode smoke test requirements, SC row 3 (partial)
- [X] T049 Add playbook-override smoke tests for 5 new modes (AssetCheck, BuyCheck, EngageCheck, GuaranteeCheck, LoanCheck). Each must invoke `--playbook custom.yaml` and confirm different assessment output. per SC "Playbook override works for each new mode" (missing)
