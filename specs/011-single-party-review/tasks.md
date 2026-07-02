---

description: "Task list for Spec 011 — Single-Party Review (PAKTON 3-Agent Pipeline)"
---

# Tasks: 011 — Single-Party Review

**Input**: Design documents from `specs/011-single-party-review/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-contract.md

**Tests**: Test tasks are included because this project uses TDD (tests written BEFORE implementation per AGENTS.md).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, etc.)
- Include exact file paths in descriptions

## Path Conventions

- Single project at repository root
- Source: `src/openreview_cli/review/`
- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- Fixtures: `tests/fixtures/playbooks/`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the review package structure, test fixtures directory, and CLI skeleton

- [X] T001 [P] Create `src/openreview_cli/review/` package with `__init__.py` (minimal, exports `run_review` stub)
- [X] T002 [P] Create `tests/fixtures/playbooks/` directory with bundled NDA playbook at `tests/fixtures/playbooks/precheck-nda-v1.yaml`
- [X] T003 Wire CLI command skeleton: add `review` subcommand under `precheck` group in `src/openreview_cli/app.py` (no-op, prints "Not yet implemented")

**Checkpoint**: Package structure and CLI skeleton exist. No functional review capability yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models, playbook loading, comparison agent, and prompt templates that ALL user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T004 [P] Unit test for review data models (`ClauseAssessment`, `Playbook`, `Category`, `PositionDef`, `ReviewReport`) in `tests/unit/test_review_models.py`
- [X] T005 [P] Unit test for playbook loader (YAML parsing, validation, bundled playbook loading) in `tests/unit/test_playbook.py`
- [X] T006 [P] Unit test for comparison agent (no-op placeholder) in `tests/unit/test_comparison_agent.py`

### Implementation for Foundational

- [X] T007 [P] Create data models (`ClauseAssessment`, `Playbook`, `Category`, `PositionDef`, `ReviewReport` dataclasses) in `src/openreview_cli/review/models.py`
- [X] T008 Create playbook loader (YAML parsing with `pyyaml`, validation, `load_bundled()` and `load_playbook(path)`) in `src/openreview_cli/review/playbook.py`
- [X] T009 Create bundled NDA playbook YAML at `src/openreview_cli/review/playbooks/precheck-nda-v1.yaml` (mirror of test fixture)
- [X] T010 Create comparison agent (structural no-op — passes extraction+QA results through unchanged) in `src/openreview_cli/review/comparison.py`
- [X] T011 Create prompt templates for extraction and QA agents in `src/openreview_cli/review/prompts.py`

**Checkpoint**: Models, playbook infrastructure, comparison agent, and templates exist. Extraction/QA agents and report formatting still TODO.

---

## Phase 3: User Story 1 — Single-Document NDA Review (Priority: P1) 🎯 MVP

**Goal**: User runs `openreview precheck review nda.docx` and receives a per-clause terminal report with position assessments, confidence scores, and citation grounding. The three-agent pipeline (extraction → QA → comparison no-op) runs end-to-end.

**Independent Test**: `pytest tests/integration/test_precheck_review.py` passes with a known NDA fixture; `pytest tests/unit/test_extraction_agent.py` and `tests/unit/test_qa_agent.py` pass.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T012 [P] [US1] Unit test for extraction agent (prompt building, confidence parsing, playbook matching orchestration) in `tests/unit/test_extraction_agent.py`
- [X] T013 [P] [US1] Unit test for QA agent (verification prompt construction, disagreement logic, position revision) in `tests/unit/test_qa_agent.py`
- [X] T014 [P] [US1] Unit test for terminal report formatting (table rendering, Amber highlighting, roll-up summary) in `tests/unit/test_review_report.py`
- [X] T015 [P] [US1] Unit test for `run_review()` public API in `tests/unit/test_review_pipeline.py`
- [X] T016 [US1] Integration test for end-to-end `precheck review` CLI flow with a known NDA fixture in `tests/integration/test_precheck_review.py`

### Implementation for User Story 1

- [X] T017 [P] [US1] Create extraction agent (prompt building via `prompts.py`, AI Gateway model slot routing, confidence extraction) in `src/openreview_cli/review/extraction.py`
- [X] T018 [P] [US1] Create QA agent (verification prompt, disagreement detection, position revision, Amber flagging) in `src/openreview_cli/review/qa.py`
- [X] T019 [P] [US1] Create terminal report formatter (Rich table, position badges, confidence bars, Amber highlight, roll-up summary) in `src/openreview_cli/review/report.py`
- [X] T020 [P] [US1] Implement `run_review()` public API orchestrating playback → extraction → QA → comparison → report in `src/openreview_cli/review/__init__.py`
- [X] T021 [US1] Wire complete `openreview precheck review <document>` command with `--extraction-model`, `--qa-model`, and `--no-pii` flags in `src/openreview_cli/app.py`; the `--no-pii` flag passes through to the PII stripping engine before clause extraction

**Checkpoint**: Single-document NDA review works end-to-end. Terminal report output. MVP deliverable.

---

## Phase 4: User Story 2 — Custom Playbook Override (Priority: P2)

**Goal**: User runs `openreview precheck review nda.docx --playbook my-terms.yaml` to review against a custom playbook instead of the bundled default.

**Independent Test**: `pytest tests/unit/test_playbook.py` includes a test for custom path loading; `pytest tests/integration/test_precheck_review.py` includes a `--playbook` scenario.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T022 [P] [US2] Unit test for playbook validation (malformed YAML, missing required fields, invalid positions) in `tests/unit/test_playbook.py`
- [X] T023 [P] [US2] Unit test for `--playbook` flag parsing and path resolution in `tests/unit/test_playbook.py`
- [X] T024 [US2] Integration test for `--playbook` flag with a custom playbook fixture in `tests/integration/test_precheck_review.py`

### Implementation for User Story 2

- [X] T025 [P] [US2] Extend `playbook.py` to support custom playbook path: `load_playbook(path)` method with validation (required fields: `id`, `categories`, each category has `favorable`/`neutral`/`unfavorable` position defs)
- [X] T026 [US2] Wire `--playbook` flag in CLI command in `src/openreview_cli/app.py`, pass through to `run_review()`

**Checkpoint**: Custom playbook loading works. Users can supply their own YAML playbook.

---

## Phase 5: User Story 3 — JSON Output / Export (Priority: P3)

**Goal**: User runs `openreview precheck review nda.docx --format json --output report.json` and receives a machine-readable JSON report.

**Independent Test**: `pytest tests/unit/test_review_report.py` includes JSON formatting tests; `pytest tests/integration/test_precheck_review.py` includes `--format json` scenario.

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T027 [P] [US3] Unit test for JSON report formatting (schema, serialization, per-clause + summary) in `tests/unit/test_review_report.py`
- [X] T028 [US3] Integration test for `--format json` and `--output` flag in `tests/integration/test_precheck_review.py`

### Implementation for User Story 3

- [X] T029 [P] [US3] Add JSON report output to `report.py`: `format_json(report)` returning a versioned JSON string with per-clause assessments and summary
- [X] T030 [US3] Wire `--format` (choices: `terminal`, `json`) and `--output` (optional file path) flags in CLI command in `src/openreview_cli/app.py`

**Checkpoint**: Users can export structured review results as JSON for downstream tooling.

---

## Phase 6: User Story 4 — Offline / SLM Mode (Priority: P4)

**Goal**: The `precheck review` command works identically with all-local SLM model slots (Ollama), producing the same output format with no network calls.

**Note**: This is already supported by the architecture (model routing defaults to local SLMs). The tasks in this phase add dedicated tests and verification.

**Independent Test**: Run `pytest tests/integration/test_precheck_review.py` with all model slots configured to local-only (simulated by mocking the AI Gateway with a local-only registry).

### Tests for User Story 4 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T031 [P] [US4] Unit test for extraction agent with local-only model slot config in `tests/unit/test_extraction_agent.py`
- [X] T032 [US4] Integration test for offline mode: mock AI Gateway with no cloud providers available, verify identical output format in `tests/integration/test_precheck_review.py`

### Implementation for User Story 4

- [X] T033 [P] [US4] Add offline-mode guard: if no model slot is configured (local or cloud), print clear error with setup instructions in `src/openreview_cli/review/extraction.py`

**Checkpoint**: Offline/SLM mode verified to produce identical output. No configuration change needed for all-local operation.

---

## Phase 7: User Story 5 — Batch Review (Priority: P5)

**Goal**: User runs `openreview precheck review *.docx` and receives per-document reports plus a batch summary showing aggregate risk posture.

**Independent Test**: `pytest tests/integration/test_precheck_review.py` includes a glob/batch scenario with 2+ documents.

### Tests for User Story 5 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T034 [P] [US5] Unit test for batch processing (sequential per-document, summary roll-up) in `tests/unit/test_review_report.py`
- [X] T035 [US5] Integration test for glob input and batch summary in `tests/integration/test_precheck_review.py`

### Implementation for User Story 5

- [X] T036 [P] [US5] Implement batch processing: detect glob/wildcard input, process each document sequentially, collect reports in `src/openreview_cli/review/__init__.py`
- [X] T037 [P] [US5] Create batch summary report (aggregate position distribution across all documents) in `src/openreview_cli/review/report.py`
- [X] T038 [US5] Wire batch support and batch summary output in `src/openreview_cli/app.py`

**Checkpoint**: Batch review works for multiple documents with aggregate summary.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Memory validation, constitution compliance, documentation, and quickstart verification.

- [X] T039 [P] Memory profile test: verify peak memory < 100 MB during a 50-page NDA review (NLP model exempt) in `tests/integration/test_memory.py` (or add to existing memory test file)
- [X] T040 [P] Run quickstart validation scenarios from `specs/011-single-party-review/quickstart.md` — verify all acceptance scenarios pass
- [X] T041 [P] Update `AGENTS.md` to reflect the new `review/` module and its deferred tasks (if any)
- [X] T042 [P] Add pre-commit hook or CI check for bundled playbook YAML validity (`ruff check`, `mypy` on new files)
- [X] T043 [P] Performance benchmark: run timed benchmark on 50-page NDA across all-local SLMs, verify <30s total, <5s/clause P95
- [X] T044 [P] Final review: verify no PII reaches extraction/QA agents (audit the `--no-pii` flag integration path)
- [X] T045 [P] Create accuracy benchmark test that measures extraction+QA F1 score against expert-labelled NDA corpus in `tests/integration/test_review_accuracy.py`
- [X] T046 Implement accuracy benchmark runner that reports F1, QA error-catch rate, and Amber-on-clear rate in `scripts/benchmark_review_accuracy.py`
- [-] T047 ⏭️ SKIPPED: `comparison.py` was intentionally deleted during ponytail-review (it was a no-op placeholder). Do NOT re-create.
- [-] T048 ⏭️ SKIPPED: `test_comparison_agent.py` was deleted alongside comparison.py. No re-creation needed.
- [X] T049 Create expert-labelled NDA clause corpus with ground-truth annotations in `tests/fixtures/review/nda-corpus-v1/nda-corpus-v1.json` (12 clauses covering all 6 categories)
- [X] T050 Add note to `scripts/benchmark_review_accuracy.py` docstring that it requires configured gateway slots for real model evaluation
- [X] T051 Update AGENTS.md with review module structure under "Where things live" tree
- [X] T052 Add `test_review_peak_memory` to `tests/integration/test_memory.py` asserting <100 MB peak via tracemalloc with mocked gateway calls
- [X] T053 Document `review/base.py` and `review/_gateway.py` in plan.md's project structure section
- [X] T054 Verify offline-mode test passes (test_precheck_review.py -k offline)

**Checkpoint**: All user stories complete, memory validated, quickstart scenarios pass, constitution compliance verified, accuracy benchmarks measure F1 ≥70%, error catch ≥80%, Amber rate ≤10%. T047/T048 intentionally skipped.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — **BLOCKS all user stories**
- **User Stories (Phase 3–7)**: All depend on Foundational completion
  - US1 (P1) → standalone, no story deps
  - US2 (P2) → depends on US1 (playbook override integrated into same pipeline)
  - US3 (P3) → depends on US1 (report formatting extension)
  - US4 (P4) → depends on US1 (cross-cutting verification)
  - US5 (P5) → depends on US1, US3 (batch uses report output)
- **Polish (Final Phase)**: All user stories complete

### User Story Dependencies

| Story | Depends On | Can Start After |
|-------|-----------|-----------------|
| US1 (P1) | Phase 1, Phase 2 | Phase 2 complete |
| US2 (P2) | Phase 2, US1 (partial) | Phase 2 complete, can parallel with US1 for non-overlapping files |
| US3 (P3) | Phase 2, US1 (report module) | After `report.py` exists (T019) |
| US4 (P4) | Phase 2, US1 | After extraction agent exists (T017) |
| US5 (P5) | Phase 2, US1, US3 | After batch report formatter (T037) |

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Services before CLI wiring
- Story complete before moving to next

### Parallel Opportunities

- **Phase 1**: T001, T002 are [P] (different files)
- **Phase 2**: T004, T005, T006 are [P] (test files are independent); T007 is [P]
- **Phase 3**: T012, T013, T014, T015 are [P] (independent unit tests); T017, T018, T019, T020 are [P] (independent source files)
- **Phase 4**: T022, T023 are [P]; T025 is [P]
- **Phase 5**: T027 is [P]; T029 is [P]
- **Phase 6**: T031 is [P]
- **Phase 7**: T034 is [P]; T036, T037 are [P]
- **Final Phase**: All tasks are [P]
- US2, US3 can start in parallel with each other after foundational is done

---

## Parallel Example: User Story 1

```bash
# Launch all unit tests for US1 together (must fail first):
pytest tests/unit/test_extraction_agent.py -v --no-header 2>&1 | head -5
pytest tests/unit/test_qa_agent.py -v --no-header 2>&1 | head -5
pytest tests/unit/test_review_report.py -v --no-header 2>&1 | head -5

# Launch all implementation files for US1 together:
# (T017) extraction.py — extraction agent
# (T018) qa.py — QA agent
# (T019) report.py — terminal report
# (T020) __init__.py — public API
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Single-Document NDA Review)
4. **STOP and VALIDATE**: `pytest tests/integration/test_precheck_review.py`, manual `openreview precheck review tests/fixtures/nda-sample.docx`
5. MVP is ready — user can review a single NDA with bundled playbook

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (Single NDA Review) → Test independently → **MVP SHIPPABLE**
3. Add US2 (Custom Playbook) → Test independently → Deploy
4. Add US3 (JSON Output) → Test independently → Deploy
5. Add US4 (Offline/SLM) → Test independently → Deploy
6. Add US5 (Batch) → Test independently → Deploy
7. Final: Polish, memory validation, benchmark

### Parallel Team Strategy

With multiple developers:

1. Team completes Phase 1 + Phase 2 together
2. Once Foundational is done:
   - Developer A: US1 (extraction + QA + report + CLI wiring)
   - Developer B: US2 (custom playbook) — needs playbook.py (T008) only
   - Developer C: US3 (JSON output) — needs report.py (T019) before full integration
3. US4 and US5 can be handled by any developer after US1 is stable

---

## Notes

- `[P]` tasks = different files, no dependencies
- `[Story]` label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Tests must fail before implementation (red-green-refactor)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- No new dependencies: reuse `stream_clauses()`, AI Gateway, `pyyaml`, `rich`, `httpx`
- Amber default for uncertain assessments per spec §3 (FR-1)
- Citation grounding on every claim per spec §3 (FR-1)
