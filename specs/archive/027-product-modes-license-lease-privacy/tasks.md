---
description: "Task list for LicenseCheck, LeaseCheck, PrivacyCheck product modes"
---

# Tasks: LicenseCheck, LeaseCheck, PrivacyCheck

**Input**: Design documents from `specs/027-product-modes-license-lease-privacy/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required per spec 027 FR1-FR7 and TDD requirement. Tests written FIRST, must FAIL before implementation.

**Organization**: Tasks grouped by user story (one per product mode). Each mode is independently implementable and testable.

## Format: `[ID] [P?] [US?] Description with file path`

- **[P]**: Parallelizable (different files, no dependencies)
- **[US]**: User story (US1=LicenseCheck, US2=LeaseCheck, US3=PrivacyCheck)
- File paths in description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Branch creation, verify existing pipeline is ready, prepare test fixtures

- [X] T001 Create `feat/027-product-modes-license-lease-privacy` branch from `main`
- [X] T002 [P] Verify existing review pipeline infra is ready — `run_review()` in `src/openreview_cli/review/__init__.py`, `ReviewCommand` in `src/openreview_cli/review/base.py`, `load_bundled()` in `src/openreview_cli/review/playbook.py`, prompt templates in `src/openreview_cli/review/prompts.py`
- [X] T003 [P] Create test fixture PDFs for all three modes in `tests/fixtures/`:
  - `tests/fixtures/saas-license-agreement.pdf`
  - `tests/fixtures/commercial-lease.pdf`
  - `tests/fixtures/dpa.pdf`

**Checkpoint**: Branch exists, infra verified, fixtures ready

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema and infrastructure changes that BLOCK all three user stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Update playbook loader to support new `positions`-based schema alongside existing `categories` schema in `src/openreview_cli/review/playbook.py` — add `BUNDLED_PLAYBOOKS` dict mapping modes to bundled playbook paths; add `load_bundled_for_mode()`; add unit tests in `tests/unit/test_playbook_schema.py`. (ponytail: used existing `categories` schema for new playbooks — no `_parse_playbook_v2()` needed since the existing schema handles all domain content)
- [X] T005 Add `load_bundled_for_mode(mode: str) -> Playbook` to `src/openreview_cli/review/playbook.py` — loads the default bundled playbook for a given mode string (e.g., `"licensecheck"` → `saas-license-v1.yaml`), with fallback to existing NDA playbook. Unit tests in `tests/unit/test_playbook_schema.py`
- [X] T006 [P] Add prompt registry mapping in `src/openreview_cli/review/prompts.py` — create `PROMPT_TEMPLATES: dict[str, Callable]` mapping mode names to prompt builder functions; add `get_prompt_template(mode: str) -> Callable` lookup; add unit test in `tests/unit/test_prompts.py`

**Checkpoint**: Foundation ready — prompt registry exists, mode-specific bundled load works

---

## Phase 3: User Story 1 — LicenseCheck (Priority: P1) 🎯 MVP

**Goal**: User can run `openreview licensecheck agreement.pdf` and get a SaaS license agreement review with Green/Amber/Red assessments

**Independent Test**: `uv run openreview licensecheck tests/fixtures/saas-license-agreement.pdf` produces a non-empty ReviewReport

### Tests for User Story 1 ⚠️

> **Write these FIRST — ensure they FAIL before implementation**

- [X] T007 [P] [US1] Unit test for `saas-license-v1.yaml` playbook schema validation in `tests/unit/test_playbook_schema.py` — validate YAML loads without error, has 9 categories, correct metadata
- [X] T008 [P] [US1] Unit test for `licensecheck` prompt template registration in `tests/unit/test_prompts.py` — verify `get_prompt_template("licensecheck")` returns a callable; verify system prompt contains domain vocabulary ("SaaS", "license grant", "royalty")
- [X] T009 [P] [US1] Unit test for `licensecheck` CLI command registration in `tests/unit/test_app.py` — verify `openreview licensecheck --help` shows mode-specific help text with "license" domain description

### Implementation for User Story 1

- [X] T010 [P] [US1] Create `src/openreview_cli/review/playbooks/saas-license-v1.yaml` — 9 categories covering SaaS license topics, per data-model.md spec
- [X] T011 [P] [US1] Register `licensecheck` prompt template in `src/openreview_cli/review/prompts.py` — add to `PROMPT_TEMPLATES` mapping; system prompt references "SaaS license agreement", domain vocabulary: SaaS, license grant, royalty, subscription, auto-renewal, liability cap, IP ownership, indemnification
- [X] T012 [US1] Wire `licensecheck` CLI subcommand in `src/openreview_cli/app.py` — add `@app.command()` def `licensecheck()` with `path`, `--no-pii`, `--playbook`, `--format`, `--output`, `--memo-format`, `--output-dir`, `--verbose`, `--confidence-threshold` parameters; delegates to `run_review()` with mode-specific bundled playbook
- [X] T013 [US1] Integration test for LicenseCheck E2E in `tests/integration/test_licensecheck.py` — CLI help, missing file, format flag tests

**Checkpoint**: LicenseCheck mode fully functional and independently testable

---

## Phase 4: User Story 2 — LeaseCheck (Priority: P2)

**Goal**: User can run `openreview leasecheck lease.pdf` and get a commercial lease review with Green/Amber/Red assessments

**Independent Test**: `uv run openreview leasecheck tests/fixtures/commercial-lease.pdf` produces a non-empty ReviewReport

### Tests for User Story 2 ⚠️

> **Write these FIRST — ensure they FAIL before implementation**

- [X] T014 [P] [US2] Unit test for `commercial-lease-v1.yaml` playbook schema validation in `tests/unit/test_playbook_schema.py` — validate YAML loads without error, has 9 categories
- [X] T015 [P] [US2] Unit test for `leasecheck` prompt template registration in `tests/unit/test_prompts.py` — verify `get_prompt_template("leasecheck")` returns callable; system prompt contains domain vocabulary ("commercial lease", "rent escalation", "CAM charges")
- [X] T016 [P] [US2] Unit test for `leasecheck` CLI command registration in `tests/unit/test_app.py` — verify `openreview leasecheck --help` shows mode-specific help text with "lease" domain description

### Implementation for User Story 2

- [X] T017 [P] [US2] Create `src/openreview_cli/review/playbooks/commercial-lease-v1.yaml` — 9 categories covering commercial lease topics, per data-model.md spec
- [X] T018 [P] [US2] Register `leasecheck` prompt template in `src/openreview_cli/review/prompts.py` — add to `PROMPT_TEMPLATES` mapping; system prompt references "commercial lease agreement", domain vocabulary: commercial lease, rent escalation, CAM charges, triple-net, subletting, security deposit, termination for convenience
- [X] T019 [US2] Wire `leasecheck` CLI subcommand in `src/openreview_cli/app.py` — add `@app.command()` def `leasecheck()` with same parameter signature as LicenseCheck; delegates to `run_review()` with mode-specific bundled playbook
- [X] T020 [US2] Integration test for LeaseCheck E2E in `tests/integration/test_leasecheck.py` — CLI help, missing file, format flag tests

**Checkpoint**: LicenseCheck AND LeaseCheck modes both functional and independently testable

---

## Phase 5: User Story 3 — PrivacyCheck (Priority: P3)

**Goal**: User can run `openreview privacycheck dpa.pdf` and get a DPA review with Green/Amber/Red assessments

**Independent Test**: `uv run openreview privacycheck tests/fixtures/dpa.pdf` produces a non-empty ReviewReport

### Tests for User Story 3 ⚠️

> **Write these FIRST — ensure they FAIL before implementation**

- [X] T021 [P] [US3] Unit test for `dpa-v1.yaml` playbook schema validation in `tests/unit/test_playbook_schema.py` — validate YAML loads without error, has 8 categories
- [X] T022 [P] [US3] Unit test for `privacycheck` prompt template registration in `tests/unit/test_prompts.py` — verify `get_prompt_template("privacycheck")` returns callable; system prompt contains domain vocabulary ("data controller", "data processor", "DPA")
- [X] T023 [P] [US3] Unit test for `privacycheck` CLI command registration in `tests/unit/test_app.py` — verify `openreview privacycheck --help` shows mode-specific help text with "data processing agreement" domain description

### Implementation for User Story 3

- [X] T024 [P] [US3] Create `src/openreview_cli/review/playbooks/dpa-v1.yaml` — 8 categories covering DPA topics, per data-model.md spec
- [X] T025 [P] [US3] Register `privacycheck` prompt template in `src/openreview_cli/review/prompts.py` — add to `PROMPT_TEMPLATES` mapping; system prompt references "data processing agreement", domain vocabulary: data controller, data processor, processing purpose, sub-processor, breach notification, data retention, DPA
- [X] T026 [US3] Wire `privacycheck` CLI subcommand in `src/openreview_cli/app.py` — add `@app.command()` def `privacycheck()` with same parameter signature as LicenseCheck/LeaseCheck; delegates to `run_review()` with mode-specific bundled playbook
- [X] T027 [US3] Integration test for PrivacyCheck E2E in `tests/integration/test_privacycheck.py` — CLI help, missing file, format flag tests

**Checkpoint**: All three modes functional and independently testable

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories — output consistency, memo export, accuracy, docs

- [X] T028 [P] Update `_export_memo_reports` in `src/openreview_cli/app.py` to accept `mode` parameter (dynamic prefix) — used by licensecheck/leasecheck/privacycheck commands — FR5, FR7
- [ ] T029 [P] Ensure JSON output envelope includes correct `mode` field matching invoked subcommand in `src/openreview_cli/review/report.py` — FR7, verify via unit test in `tests/unit/test_report.py`
- [ ] T030 Run accuracy benchmark per mode using existing benchmark harness — at least 10 test documents per mode, measure F1 against held-out corpus per spec Success Criteria
- [ ] T031 [P] Run quickstart.md validation — verify the 4-step pattern (playbook → prompt → CLI → tests) produces a working mode
- [ ] T032 [P] Documentation: update `README.md` with new CLI subcommands if user-facing docs section exists; update `src/openreview_cli/__init__.py` version if needed
- [X] T033 Run full test suite + pre-commit sweep — `uv run pytest` (55 new tests pass), `uv run ruff check .` (clean), `uv run ruff format --check` (clean), `uv run mypy src/ tests/` (clean); fix any failures

**Checkpoint**: All three modes complete, tested, benchmarked, documented

---

## Phase 7: Convergence

**Purpose**: Close remaining gaps identified by convergence analysis — JSON mode field, accuracy benchmarks, quickstart validation, and documentation updates. Closes out Phases 1-6.

### Gaps (from convergence)

| # | Finding | Severity | Source | Closure Task |
|---|---------|----------|--------|-------------|
| G1 | JSON `mode` field in output not verified | HIGH | FR7, SC6 | T034 |
| G2 | Accuracy benchmark per mode not run | MEDIUM | SC4 | T035 |
| G3 | Quickstart.md pattern not validated | MEDIUM | Plan decision | T036 |
| G4 | Docs/version not updated | LOW | Plan decision | T037 |

### Closure Tasks

- [X] T034 [P] Verify JSON output envelope includes correct `mode` field matching invoked subcommand in `src/openreview_cli/review/report.py` — add unit test in `tests/unit/test_report.py`. Closes G1, FR7, SC6.
- [X] T035 Run accuracy benchmark per mode using existing benchmark harness — at least 10 test documents per mode, measure F1 against held-out corpus. Closes G2, SC4.
- [X] T036 [P] Walk through quickstart.md 4-step pattern with LicenseCheck — verify each step produces expected output. Closes G3.
- [X] T037 [P] Update `README.md` with new CLI subcommands if user-facing docs section exists; update `src/openreview_cli/__init__.py` version if needed. Closes G4.

**Dependencies**: T034, T036, T037 are mutually independent (different files). T035 depends on fixture documents existing.

**Checkpoint**: All 4 convergence gaps closed. Spec 027 fully implemented.

---

## Dependencies & Execution Order

### Phase Dependencies

| Phase | Depends On | Blocks |
|-------|-----------|--------|
| Phase 1: Setup | Nothing | Phase 2 |
| Phase 2: Foundational | Phase 1 | Phase 3-5 (ALL user stories) |
| Phase 3: US1 LicenseCheck (P1) | Phase 2 | Nothing (independent) |
| Phase 4: US2 LeaseCheck (P2) | Phase 2 | Nothing (independent) |
| Phase 5: US3 PrivacyCheck (P3) | Phase 2 | Nothing (independent) |
| Phase 6: Polish | Phases 3-5 | Release |

### User Story Dependencies

- **US1 (LicenseCheck)**: Can start after Phase 2 — no dependencies on other stories
- **US2 (LeaseCheck)**: Can start after Phase 2 — no dependencies on other stories
- **US3 (PrivacyCheck)**: Can start after Phase 2 — no dependencies on other stories
- All three stories are MUTUALLY INDEPENDENT — they touch different files (different playbooks, different prompt entries, different CLI subcommands, different test files)

### Within Each User Story

1. Tests written FIRST — must FAIL before implementation (TDD)
2. Playbook YAML created (parallel)
3. Prompt template registered (parallel)
4. CLI subcommand wired (depends on playbook + prompt)
5. Integration test (depends on CLI wiring)
6. Story complete before moving to next priority

### Parallel Opportunities

| Group | Tasks | Rationale |
|-------|-------|-----------|
| Fixture creation | T003 | Different files, no deps |
| Schema + registry updates | T004, T005, T006 | Different files, foundational |
| Playbook YAML files | T010, T017, T024 | Independent files, identical schema |
| Prompt registrations | T011, T018, T025 | Independent entries in same dict |
| CLI subcommands | T012, T019, T026 | Independent functions in same file |
| Unit tests per mode | T007/T008/T009, T014/T015/T016, T021/T022/T023 | Per-mode isolation |
| Integration tests | T013, T020, T027 | Different test files |
| Polish tasks | T028, T029, T030, T031, T032 | Independent concerns |

---

## Implementation Strategy

### MVP First (US1 Only)

1. Phase 1 — Setup: branch + fixture docs (T001–T003)
2. Phase 2 — Foundational: schema update + prompt registry (T004–T006)
3. Phase 3 — LicenseCheck: all tasks T007–T013
4. **STOP and VALIDATE**: `uv run openreview licensecheck --help`, E2E integration test
5. ✅ MVP deliverable: LicenseCheck mode functional
6. Incrementally add LeaseCheck (Phase 4), PrivacyCheck (Phase 5)
7. Polish (Phase 6)

### Parallel Team Strategy

With multiple developers:
1. Team completes Phase 1 + 2 together
2. Once foundational is done:
   - Dev A: US1 LicenseCheck (Phase 3)
   - Dev B: US2 LeaseCheck (Phase 4)
   - Dev C: US3 PrivacyCheck (Phase 5)
3. All three stories are independently completable

### Blueprint Schema Note

The existing `precheck-nda-v1.yaml` uses `categories` with `preferred/acceptable/walkaway` positions. The data-model.md defines a new `positions`-based schema (3 positions × 3 questions = 9 total). Task T004 handles schema coexistence in `playbook.py`. New playbooks (T010, T017, T024) use the new `positions`-based schema per data-model.md.

---

## Task Summary

| ID | [P] | Story | Description | Key File |
|----|-----|-------|-------------|----------|
| T001 | | Setup | Create feature branch | `feat/027-product-modes-license-lease-privacy` |
| T002 | [P] | Setup | Verify existing pipeline infra | `src/openreview_cli/review/` |
| T003 | [P] | Setup | Create fixture PDFs | `tests/fixtures/*.pdf` |
| T004 | | Foundational | Update playbook loader for positions schema | `src/openreview_cli/review/playbook.py` |
| T005 | | Foundational | Add `load_bundled_for_mode()` | `src/openreview_cli/review/playbook.py` |
| T006 | [P] | Foundational | Add prompt registry | `src/openreview_cli/review/prompts.py` |
| T007 | [P] | US1 | Unit test: saas-license-v1.yaml schema | `tests/unit/test_playbook_schema.py` |
| T008 | [P] | US1 | Unit test: licensecheck prompt template | `tests/unit/test_prompts.py` |
| T009 | [P] | US1 | Unit test: licensecheck CLI registration | `tests/unit/test_app.py` |
| T010 | [P] | US1 | Create saas-license-v1.yaml playbook | `src/openreview_cli/review/playbooks/saas-license-v1.yaml` |
| T011 | [P] | US1 | Register licensecheck prompt template | `src/openreview_cli/review/prompts.py` |
| T012 | | US1 | Wire licensecheck CLI subcommand | `src/openreview_cli/app.py` |
| T013 | | US1 | Integration test: LicenseCheck E2E | `tests/integration/test_licensecheck.py` |
| T014 | [P] | US2 | Unit test: commercial-lease-v1.yaml schema | `tests/unit/test_playbook_schema.py` |
| T015 | [P] | US2 | Unit test: leasecheck prompt template | `tests/unit/test_prompts.py` |
| T016 | [P] | US2 | Unit test: leasecheck CLI registration | `tests/unit/test_app.py` |
| T017 | [P] | US2 | Create commercial-lease-v1.yaml playbook | `src/openreview_cli/review/playbooks/commercial-lease-v1.yaml` |
| T018 | [P] | US2 | Register leasecheck prompt template | `src/openreview_cli/review/prompts.py` |
| T019 | | US2 | Wire leasecheck CLI subcommand | `src/openreview_cli/app.py` |
| T020 | | US2 | Integration test: LeaseCheck E2E | `tests/integration/test_leasecheck.py` |
| T021 | [P] | US3 | Unit test: dpa-v1.yaml schema | `tests/unit/test_playbook_schema.py` |
| T022 | [P] | US3 | Unit test: privacycheck prompt template | `tests/unit/test_prompts.py` |
| T023 | [P] | US3 | Unit test: privacycheck CLI registration | `tests/unit/test_app.py` |
| T024 | [P] | US3 | Create dpa-v1.yaml playbook | `src/openreview_cli/review/playbooks/dpa-v1.yaml` |
| T025 | [P] | US3 | Register privacycheck prompt template | `src/openreview_cli/review/prompts.py` |
| T026 | | US3 | Wire privacycheck CLI subcommand | `src/openreview_cli/app.py` |
| T027 | | US3 | Integration test: PrivacyCheck E2E | `tests/integration/test_privacycheck.py` |
| T028 | [P] | Polish | MemoExporter mode prefix | `src/openreview_cli/review/memo/exporter.py` |
| T029 | [P] | Polish | JSON output mode field | `src/openreview_cli/review/report.py` |
| T030 | | Polish | Accuracy benchmark per mode | benchmark harness |
| T031 | [P] | Polish | Quickstart validation | `specs/027-product-modes-license-lease-privacy/quickstart.md` |
| T032 | [P] | Polish | Documentation updates | `README.md` |
| T033 | | Polish | Full test suite + pre-commit sweep | repo root |
| T034 | | Convergence | Verify JSON output includes correct `mode` field — closes T029 | `src/openreview_cli/review/report.py`, `tests/unit/test_report.py` |
| T035 | | Convergence | Run accuracy benchmark for all 3 modes (≥10 docs each) — closes T030 | benchmark harness |
| T036 | | Convergence | Walk through quickstart.md 4-step pattern with LicenseCheck — closes T031 | `specs/027-product-modes-license-lease-privacy/quickstart.md` |
| T037 | | Convergence | Update README.md with new subcommands + bump `__init__.py` version if needed — closes T032 | `README.md`, `src/openreview_cli/__init__.py` |
