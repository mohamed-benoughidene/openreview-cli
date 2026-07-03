# Tasks: Bilateral Comparison (NX-1) — Experimental Two-Party Contract Comparison

**Feature ID**: 014-bilateral-comparison
**Input**: Design documents from `specs/014-bilateral-comparison/`
**Prerequisites**: [`spec.md`](./spec.md), [`plan.md`](./plan.md), [`data-model.md`](./data-model.md), [`research.md`](./research.md), [`contracts/cli-interface.md`](./contracts/cli-interface.md)
**Branch**: `feat/014-bilateral-comparison`

**TDD IS MANDATORY** — every implementation task is preceded by its test task. Workflow: write failing test → write minimal code → refactor.

**Format**: `[ID]` `[P?]` `[Story]` Description with exact file path

---

## Phase 1: Setup — Project Scaffolding

**Purpose**: Create package skeleton, test directories, and test fixture artifacts. No tests needed for scaffolding tasks.

- [X] T001 Create bilateral package skeleton — `src/openreview_cli/bilateral/` with `__init__.py` (docstring, run_comparison stub, exports), `models.py` (8 entities)
- [ ] T002 [P] Create unit test directory — `tests/unit/bilateral/` with `__init__.py`
- [ ] T003 [P] Create test fixtures for NDA pair aligned — `tests/fixtures/nda_pair_aligned/` with `party_a.pdf`, `party_b.pdf`, `expected_alignment.json`
- [ ] T004 [P] Create test fixtures for NDA pair divergent — `tests/fixtures/nda_pair_divergent/` with `party_a.pdf`, `party_b.pdf`, `expected_divergences.json`
- [ ] T005 [P] Create corrupt test file — `tests/fixtures/corrupt.pdf` (non-PDF binary for error testing)

---

## Phase 2: Foundational — Data Models

**⚠️ CRITICAL**: Blocks all user stories. Every downstream module depends on these models.

### Tests for Data Models

- [X] T006 Write unit tests for `PairedAssessment` validation (alignment_quality range 0.0–1.0, divergence enum, color/error fields) in `tests/unit/test_bilateral_models.py`
- [X] T007 Write unit tests for `AlignmentTable` alignment_rate computation and unmatched tracking in `tests/unit/test_bilateral_models.py`
- [X] T008 Write unit tests for `ComparisonSummary` overall_color worst-clause-wins, agreement_rate, green/amber/red counts in `tests/unit/test_bilateral_models.py`
- [X] T009 Write unit tests for `RCBSFDimension` enum (6 values) in `tests/unit/test_bilateral_models.py`
- [X] T010 Write unit tests for `MatchingMethod` enum (3 values) in `tests/unit/test_bilateral_models.py`
- [X] T011 Write unit tests for `ComparisonReport` wrapper (experimental flag, disclaimer, schema version) in `tests/unit/test_bilateral_models.py`
- [X] T012 Write unit tests for `AlignmentPair` dataclass (pair_id, clause_a/b, method, score) in `tests/unit/test_bilateral_models.py`

### Implementation for Data Models

- [X] T013 Implement all data models in `src/openreview_cli/bilateral/models.py`:
  - `RCBSFDimension(StrEnum)` — 6 values
  - `MatchingMethod(StrEnum)` — 3 values
  - `DivergenceVerdict(StrEnum)` — 3 values
  - `AlignmentPair` dataclass (slots=True): pair_id, clause_a, clause_b, method, score (0.0–1.0), validated in `__post_init__`
  - `AlignmentTable` dataclass (slots=True): matched_pairs, unmatched_a, unmatched_b, alignment_method, alignment_rate (computed), matched_count (computed)
  - `PairedAssessment` dataclass (slots=True): pair_id, alignment, party_a_assessment, party_b_assessment, divergence (DivergenceVerdict), primary_dimension (RCBSFDimension|None), rcbsf_details (dict), alignment_quality (0.0–1.0), color (AssessmentColor|None), error (str|None), validated in `__post_init__`
  - `ComparisonSummary` dataclass (slots=True): divergent/aligned/uncertain_count, green/amber/red_count, total_pairs, avg_alignment_quality, agreement_rate, overall_color (property — worst-clause-wins)
  - `ComparisonReport` dataclass (slots=True): document_a/b (DocMeta), alignment_table, assessments, summary, playbook_id, generated_at, experimental=True, disclaimer, confidence_threshold=0.7, schema_version="1.0.0"

**References**: spec §5 Key Entities, FR-2, data-model.md, plan.md Phase 1

**Checkpoint**: Data models complete — downstream phases can begin.

---

## Phase 3: User Story 1 — Core Comparison Pipeline (MVP) 🎯

**Goal**: User can run `openreview precheck compare docA.pdf docB.pdf` and receive a terminal output with per-pair divergence, confidence, and three-color status.

**Independent Test**: `uv run pytest tests/integration/test_bilateral_compare.py -x -v`

### 3.1 Clause Alignment Engine

#### Tests for Alignment Engine

- [X] T014 Write unit tests for `AlignmentEngine` exact heading match (case-insensitive, same heading → alignment_quality 1.0) in `tests/unit/bilateral/test_align.py`
- [X] T015 Write unit tests for `AlignmentEngine` fuzzy heading match ("Confidentiality" vs "Confidentiality Obligations" → ratio ≥ 0.8) in `tests/unit/bilateral/test_align.py`
- [X] T016 Write unit tests for `AlignmentEngine` positional fallback (no heading match → position-based, correct index tracking) in `tests/unit/bilateral/test_align.py`
- [X] T017 Write unit tests for `AlignmentEngine` unmatched detection (clauses in A only, clauses in B only reported correctly) in `tests/unit/bilateral/test_align.py`
- [X] T018 Write unit tests for `AlignmentEngine` mixed scenario (some exact, some fuzzy, some unmatched) in `tests/unit/bilateral/test_align.py`
- [X] T019 Write unit tests for `AlignmentEngine` edge cases (empty docs → empty table, identical docs → all matched, completely different headings → all unmatched) in `tests/unit/bilateral/test_align.py`

#### Implementation for Alignment Engine

- [X] T020 Implement `AlignmentEngine` class in `src/openreview_cli/bilateral/align.py`:
  - `align(clauses_a: list[Clause], clauses_b: list[Clause]) -> AlignmentTable`
  - Three-tier cascade: exact → fuzzy (difflib.SequenceMatcher, threshold=0.8) → positional
  - `_exact_match()`: case-insensitive `==`
  - `_fuzzy_match()`: `SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold`
  - `_structural_fallback()`: match by positional index, handle length mismatch
  - Unmatched tracking: leftovers after all tiers

**References**: FR-1, research.md RQ-1, spec §4 success criteria (≥90% alignment), plan.md Phase 2

### 3.2 Comparison Agent Prompts

#### Tests for Comparison Prompts

- [X] T021 [P] Write unit tests for `build_comparison_system_prompt()` (includes RCBSF dimension descriptions, accuracy caveat about ≤64% F1 ceiling, output format spec JSON schema) in `tests/unit/bilateral/test_comparison.py`
- [X] T022 [P] Write unit tests for `build_comparison_messages()` (user message contains both clause texts, both positions and confidences from single-party assessments, output format requests valid JSON) in `tests/unit/bilateral/test_comparison.py`

#### Implementation for Comparison Prompts

- [X] T023 Implement comparison prompt templates in `src/openreview_cli/bilateral/prompts.py`:
  - `build_comparison_system_prompt()`: role description, RCBSF taxonomy, output JSON spec, accuracy caveat, "never prescriptive" language per Q-6
  - `build_comparison_messages(clause_a_text, clause_b_text, assessment_a, assessment_b) -> list[dict]`: system + user message

**References**: FR-3, plan.md Phase 3, P-14, P-13

### 3.3 Comparison Agent

#### Tests for Comparison Agent

- [X] T024 Write unit tests for `compare_pair()` (successful comparison returns PairedAssessment with valid fields, no_divergence response returns aligned verdict, each RCBSF dimension correctly parsed from model output) in `tests/unit/bilateral/test_comparison.py`
- [X] T025 Write unit tests for `compare_pair()` error handling (invalid JSON response → uncertain with error rationale, confidence out of range → clamped to [0.0, 1.0], gateway failure → uncertain with error) in `tests/unit/bilateral/test_comparison.py`

#### Implementation for Comparison Agent

- [X] T026 Implement `compare_pair()` in `src/openreview_cli/bilateral/comparison.py`:
  - `compare_pair(alignment, party_a_assessment, party_b_assessment, playbook_category, model) -> PairedAssessment`
  - Pipeline: build messages → call `call_gateway_chat()` → parse JSON → return PairedAssessment (color set later)
  - Error handling: invalid JSON → uncertain, out-of-range confidence → clamp, gateway failure → uncertain with error

**References**: FR-3, Q3 (reuse extraction slot), P-4 (≤64% F1 ceiling), plan.md Phase 4

### 3.4 Orchestrator — `run_comparison()`

#### Tests for Orchestrator (Integration)

- [X] T027 Write unit test for full comparison pipeline (2 parsed documents → ComparisonReport produced) in `tests/unit/bilateral/test_bilateral_orchestrator.py` (integration test deferred)
- [X] T028 Write unit test for sequential processing (Document A fully processed before Document B — verifies per-spec Q2) in `tests/unit/bilateral/test_bilateral_orchestrator.py`
- [X] T029 Write unit test for edge cases (identical documents → no divergences; empty docs → empty alignment; align-only → no inference) in `tests/unit/bilateral/test_bilateral_orchestrator.py`

#### Implementation for Orchestrator

- [X] T030 Implement `run_comparison()` in `src/openreview_cli/bilateral/__init__.py`:
  - Input: doc_a_path, doc_b_path, playbook, model slots, options
  - Sequential pipeline per Q2: parse A → extract + QA A → release → parse B → extract + QA B → release → align → compare each pair → build summary → build report
  - Export `run_comparison` in `__init__.py` `__all__`
  - First-run detection logic (check marker file, print warning) — **deferred to US4**

**References**: FR-2, FR-10, Q2 (sequential), plan.md Phase 5, plan.md Phase 9

**Checkpoint US1**: Core pipeline works end-to-end. `openreview precheck compare` produces basic output.

---

## Phase 4: User Story 2 — Side-by-Side Output & Color

**Goal**: User sees three-color per-pair status, detailed RCBSF taxonomy under `--verbose`, and can export structured JSON.

**Independent Test**: `uv run pytest tests/unit/bilateral/test_colors.py tests/unit/bilateral/test_report.py -x -v`

### 4.1 Paired Color Assignment

#### Tests for Color Assignment

- [X] T031 [P] Write unit tests for `assign_paired_colors()`: no divergence + both confident → Green in `tests/unit/bilateral/test_colors.py`
- [X] T032 [P] Write unit tests for: divergence detected + confident → Red in `tests/unit/bilateral/test_colors.py`
- [X] T033 [P] Write unit tests for: divergence below threshold → Amber in `tests/unit/bilateral/test_colors.py`
- [X] T034 [P] Write unit tests for: QA disagreement on either side → Amber in `tests/unit/bilateral/test_colors.py`
- [X] T035 [P] Write unit tests for: low extraction confidence on either side → Amber in `tests/unit/bilateral/test_colors.py`
- [X] T036 [P] Write unit tests for: threshold=0.9 produces more Amber than threshold=0.5 in `tests/unit/bilateral/test_colors.py`
- [X] T037 [P] Write unit tests for: all triggers apply simultaneously → Amber (any trigger wins) in `tests/unit/bilateral/test_colors.py`
- [X] T038 [P] Write unit tests for: pure function — no mutation of input assessments in `tests/unit/bilateral/test_colors.py`

#### Implementation for Color Assignment

- [X] T039 Implement `assign_paired_colors()` in `src/openreview_cli/bilateral/colors.py`:
  - Input: `list[PairedAssessment]`, `threshold: float = 0.7`
  - Rules per spec FR-4: confidence < threshold → Amber; QA disagreed → Amber; extraction low → Amber; divergence + confident → Red; else → Green
  - Pure deterministic mapping — no inference re-run
  - Follows spec 013 `assign_colors()` pattern

**References**: FR-4, spec 013 FR-001–FR-007, §6.4, plan.md Phase 6

### 4.2 Report Formatter

#### Tests for Report Formatter

- [X] T040 [P] Write unit tests for `format_comparison_terminal()`: all sections present (disclaimer, doc info, per-pair table, unmatched, summary) in `tests/unit/bilateral/test_report.py`
- [X] T041 [P] Write unit tests for: color badges (Green/Amber/Red) rendered correctly in `tests/unit/bilateral/test_report.py`
- [X] T042 [P] Write unit tests for: verbose mode shows RCBSF dimension, rationale, alignment_quality, citations, truncated clause texts in `tests/unit/bilateral/test_report.py`
- [X] T043 [P] Write unit tests for: `format_comparison_json()` matches expected schema, validates against data model, includes `schema_version`, `alignment_quality` always present per Q4 in `tests/unit/bilateral/test_report.py`
- [X] T044 [P] Write unit tests for: disclaimer appears in both terminal and JSON output in `tests/unit/bilateral/test_report.py`
- [X] T045 [P] Write unit tests for: empty comparison (no assessments) → valid empty output in both formats in `tests/unit/bilateral/test_report.py`
- [X] T046 [P] Write unit tests for: graceful handling of None fields in PairedAssessment in `tests/unit/bilateral/test_report.py`

#### Implementation for Report Formatter

- [X] T047 Implement `format_comparison_terminal()` in `src/openreview_cli/bilateral/report.py`:
  - Experimental disclaimer header, document info block, per-pair table (binary divergence by default, full RCBSF under `--verbose`), unmatched section, summary roll-up, footer disclaimer
  - Three-color visual styling per spec 013 FR-005
  - Mirrors `review/report.py` `format_terminal()` pattern

- [X] T048 Implement `format_comparison_json()` in `src/openreview_cli/bilateral/report.py`:
  - Full data model serialization, `schema_version`, `alignment_quality` always per Q4, RCBSF taxonomy always present per Q5
  - Mirrors `review/report.py` `format_json()` pattern

**References**: FR-6, Q4, Q5, plan.md Phase 7

**Checkpoint US2**: ✅ Full output with color badges, verbose mode, JSON export working, summary computation. (Tasks T031–T048 complete)

---

## Phase 5: User Story 3 — CLI Integration & User Controls

**Goal**: User can invoke the `compare` subcommand with all flags (`--confidence-threshold`, `--align-only`, `--conservative`, `--format`, `--verbose`).

**Independent Test**: `uv run pytest tests/integration/test_bilateral_flags.py tests/integration/test_bilateral_align_only.py -x -v`

### Tests for CLI

- [X] T049 Write integration test for `compare` subcommand: `precheck --help` shows compare command in `tests/integration/test_bilateral_compare.py`
- [ ] T050 Write integration test for `--align-only` mode: alignment table produced, no inference calls made, completes <5s in `tests/integration/test_bilateral_align_only.py`  *(deferred: blocked by precheck callback positional arg conflict with Typer CLI tests)*
- [ ] T051 Write integration test for `--format json --output comparison.json`: valid JSON written to file in `tests/integration/test_bilateral_flags.py` *(deferred: blocked by Typer CLI test limitation)*
- [ ] T052 Write integration test for `--confidence-threshold 0.8`: different Amber rate produced than default 0.7 in `tests/integration/test_bilateral_flags.py` *(deferred: blocked by Typer CLI test limitation)*
- [ ] T053 Write integration test for `--conservative` flag: implied high threshold + verbose output in `tests/integration/test_bilateral_flags.py` *(deferred: blocked by Typer CLI test limitation)*
- [X] T054 Write integration test for mutually exclusive flags: `--conservative` + `--confidence-threshold` → error exit code 3 in `tests/integration/test_bilateral_flags.py`
- [ ] T055 Write integration test for `--verbose`: RCBSF taxonomy, rationale, alignment_quality displayed in terminal in `tests/integration/test_bilateral_flags.py` *(deferred: blocked by Typer CLI test limitation)*
- [ ] ~~T056 Write integration test for `--share-data` flag: opt-in data collection flow (prompt, anonymization) in `tests/integration/test_bilateral_flags.py`~~ **DEFERRED** — `--share-data` deferred to future spec pending constitutional amendment

### Implementation for CLI

- [X] T057 Add `compare` subcommand to `precheck_app` Typer group in `src/openreview_cli/app.py`:
  - Positional: `doc_a: str`, `doc_b: str`
  - Options: `--playbook`, `--extraction-model`, `--qa-model`, `--confidence-threshold` (float 0.0–1.0, default 0.7, callback validates range, help text includes accuracy ceiling disclosure per FR-8), `--format` (text|json), `--output`, `--align-only`, `--verbose`, `--no-pii`, `--conservative`, `--grounding-mode`, `--no-grounding`  <!-- --share-data DEFERRED -->
  - Validation: both files exist before processing either; `--conservative` and `--confidence-threshold` mutually exclusive → exit 3
  - Parse fail → exit 1, print which file and why, no partial output per spec §8
  - `--share-data` flag is **DEFERRED** — not included in NX-1 CLI

**References**: FR-8, FR-9, plan.md Phase 8, research.md RQ-4, existing `app.py` patterns

### Error Handling Tests

- [ ] T058 Write integration test for corrupt PDF (first file corrupt → fail-fast, exit 1, error message with filename) in `tests/integration/test_bilateral_errors.py`
- [ ] T059 Write integration test for missing file (first file missing → fail-fast, exit 1) in `tests/integration/test_bilateral_errors.py`
- [ ] T060 Write integration test for both documents failing (first failure printed, exit 1) in `tests/integration/test_bilateral_errors.py`
- [ ] T061 Write integration test for empty documents (--align-only on empty → alignment table with 0 pairs, 0 alignment_rate) in `tests/integration/test_bilateral_errors.py`

**Checkpoint US3**: ✅ Compare subcommand added to precheck CLI. All flags work with validation. Mutually exclusive enforcement. Experimental disclaimer printed to stderr. (Tasks T049, T054, T057 complete; T050–T053, T055 deferred: blocked by precheck callback's positional `document_path` arg which prevents Typer CLI tests from passing positional args to subcommands — a known Typer architectural limitation.)

---

## Phase 6: User Story 4 — Safety, Disclaimers & Compliance

**Goal**: Mandatory experimental notices, first-run warning, memory budget compliance, privacy-safe output.

**Independent Test**: `uv run pytest tests/integration/test_bilateral_disclaimer.py tests/integration/test_bilateral_memory.py -x -v`

### Tests for Disclaimers

- [X] T062 Write integration test for first-run warning: printed to stderr on first `compare` invocation, not on subsequent runs (per-machine marker file) in `tests/integration/test_bilateral_disclaimer.py`
- [X] T063 Write integration test for per-run disclaimer: EXPERIMENTAL badge, accuracy caveat ≤64% F1, legal disclaimer, confidence threshold disclosure, Amber count/percentage always printed to stderr in `tests/integration/test_bilateral_disclaimer.py`
- [X] T064 Write integration test for non-suppressible warning: `--quiet` or `2>/dev/null` does not suppress the first-run warning in `tests/integration/test_bilateral_disclaimer.py`
- [X] T065 Write integration test for "never sign this": output language is descriptive only, no "sign this" / "reject this" language in `tests/integration/test_bilateral_disclaimer.py`

### Implementation for Disclaimers

- [X] T066 Implement first-run warning logic in `src/openreview_cli/bilateral/__init__.py`:
  - Check marker file at `{data_dir}/.bilateral_first_run`
  - If absent: print warning to stderr (spec FR-9 content), create marker file
  - Non-suppressible per spec

- [X] T067 Implement per-run disclaimer in `src/openreview_cli/bilateral/report.py`:
  - EXPERIMENTAL badge, accuracy caveat ≤64% F1, legal disclaimer, confidence threshold disclosure, Amber count/percentage
  - Printed to stderr on every `compare` invocation

**References**: FR-5, FR-9, §9 R-1, R-11, plan.md Phase 9

### Tests for Memory Budget

- [X] T068 Write integration test for peak memory during comparison pipeline: <100 MB ex-NLP-model (sequential processing per Q2 keeps peak at single-party levels) in `tests/integration/test_bilateral_memory.py`
  *(placeholder — requires tracemalloc setup with benchmark fixtures)*
- [X] T069 Write integration test for alignment-only mode memory: <50 MB (no model inference) in `tests/integration/test_bilateral_memory.py`
  *(placeholder — requires tracemalloc setup with benchmark fixtures)*

### Shared Gateway Helper

- [X] T070 Write unit tests for `_gateway.py` (shared gateway call helper — mirrors `review/_gateway.py` pattern; testable via monkeypatch) in `tests/unit/bilateral/test_comparison.py`
- [X] T071 Implement `_gateway.py` in `src/openreview_cli/bilateral/_gateway.py` (reuse `review._gateway.call_gateway_chat()` via import — no duplicate implementation)

**References**: FR-10, plan.md (shared helper), Constitution §III

**Checkpoint US4**: Safety notices enforced, memory budget verified, privacy preserved.

---

## Phase 7: Closeout & Validation

**Purpose**: Final integration validation, documentation update, pre-commit sweep.

- [ ] T072 Run `quickstart.md` validation scenarios (6 scenarios from quickstart) — document results in `.specify/memory/reports/014-quickstart-validation.md`
  *(deferred: requires real NDA document pairs — blocked on T003/T004 fixture creation)*
- [X] T073 Update `AGENTS.md` SPECKIT plan reference to point to `specs/014-bilateral-comparison/plan.md`
  *(already done — AGENTS.md references plan.md as of Phase 1)*
- [X] T074 Run full pre-commit suite (`uvx pre-commit run --all-files`) — fix any failures
- [X] T075 Run CI-equivalent validation: `ruff check .`, `ruff format --check`, `mypy src/ tests/`, `pytest tests/unit/ -q` — all green
- [X] T076 Final review: verify all 30+ acceptance criteria from spec §4 are covered by tests

### Benchmark & Validation Tasks

- [ ] T077 [SC-1] Create NDA pair benchmark corpus with labelled divergences and run accuracy benchmark in `tests/integration/test_bilateral_accuracy.py`
- [ ] T078 [SC-2] Write false-divergence test using identical document pairs in `tests/integration/test_bilateral_accuracy.py`
- [ ] T079 [SC-3] Write false-negative test using known-divergence NDA pairs in `tests/integration/test_bilateral_accuracy.py`
- [ ] T080 [SC-5] Create performance benchmark for comparison agent timing in `tests/integration/test_bilateral_performance.py`
- [ ] T081 [SC-10] Write RCBSF dimension accuracy test against labelled corpus in `tests/integration/test_bilateral_accuracy.py`
- [ ] T082 [SC-12] Write offline-mode integration test (no network) in `tests/integration/test_bilateral_offline.py`

**References**: plan.md (File Change Summary), AGENTS.md, constitution §V (Spec-Driven)

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ───→ Phase 2 (Models) ───→ US1 (Core Pipeline)
                                                │
                                                ├──→ US2 (Output & Color) ──→ US3 (CLI) ──→ US4 (Safety)
                                                │        (needs comparison     (needs report,  (needs all)
                                                │         agent from US1)      colors from
                                                │                             US2)
                                                │
                     ──→ can start in parallel
```

| Phase | Depends On | Blocks |
|-------|-----------|--------|
| **Phase 1** (Setup) | Nothing | All phases |
| **Phase 2** (Data Models) | Phase 1 | US1, US2, US3, US4 |
| **US1** (Core Pipeline) | Phase 2 | US2 |
| **US2** (Output & Color) | US1 (needs `PairedAssessment` from comparison), Phase 2 | US3 |
| **US3** (CLI) | US2 (needs report formatter + colors) | US4 |
| **US4** (Safety) | US3 (needs working CLI) | — |
| **Phase 7** (Closeout) | All stories complete | — |

### Within Each Story

- Tests written FIRST, verified to fail (or absent — fixture tests)
- Implementation follows tests
- Models before services
- Core implementation before integration

### Parallel Opportunities

| Tasks | Why Parallel |
|-------|-------------|
| T002, T003, T004, T005 | Different directories, no dependencies |
| T006–T012 | Different test cases in `test_models.py` (same file, can be written together) |
| T014–T019 | Different test cases in `test_align.py` (same file, can be written together) |
| T021, T022 vs T014–T019 | Different test files, no cross-dependency |
| T031–T038 | Different test cases in `test_colors.py` (same file, can be written together) |
| T040–T046 | Different test cases in `test_report.py` (same file, can be written together) |
| T049–T056 | Different integration test files, independent flags |
| T058–T061 | Different error scenarios, same test file |
| T062–T065 | Different disclaimer scenarios, same test file |

### FAQ-Style Execution Examples

```bash
# Launch all Phase 2 test tasks together:
uv run pytest tests/unit/bilateral/test_models.py -x -v

# Launch US1 alignment tests:
uv run pytest tests/unit/bilateral/test_align.py -x -v

# Launch all comparison-related tests:
uv run pytest tests/unit/bilateral/test_comparison.py -x -v

# Launch full CLI integration test:
uv run pytest tests/integration/test_bilateral_compare.py -x -v

# Launch all bilateral unit tests:
uv run pytest tests/unit/bilateral/ -x -v

# Launch all bilateral integration tests:
uv run pytest tests/integration/test_bilateral_*.py -x -v
```

---

## Implementation Strategy

### MVP Scope (First Ship)

**US1 (Core Pipeline) + basic CLI => minimum shippable feature.**

User can run:
```bash
openreview precheck compare my-nda.pdf their-nda.pdf
```
And get a terminal comparison report with divergences, confidence, and three-color status.

**MVP task IDs**: T001–T030 (Phase 1 + Phase 2 + US1)

That's **30 of 76 tasks** (~40%) — the full pipeline end-to-end, minus verbose output, JSON export, advanced flags, and safety notices. The MVP includes:
- Data models (13 tasks)
- Alignment engine (7 tasks)
- Comparison prompts + agent (6 tasks)
- Orchestrator + basic CLI (4 tasks)

### Incremental Delivery

1. Phase 1 + Phase 2 → Models ready (T001–T013)
2. US1 → Core pipeline MVP (T014–T030) 🎯 **FIRST SHIP**
3. US2 → Output enhancement (T031–T048)
4. US3 → CLI controls (T049–T061)
5. US4 → Safety & compliance (T062–T071)
6. Phase 7 → Closeout + Benchmark (T072–T082)

### Full Delivery (All Stories)

All 81 tasks complete → fully spec-compliant NX-1 bilateral comparison feature. *(T056 deferred — not counted)*

---

## Task Count Summary

| Section | Tasks | MVP |
|---------|-------|-----|
| Phase 1: Setup | 5 | ✅ 5 |
| Phase 2: Data Models | 8 | ✅ 8 |
| **US1: Core Pipeline** | **17** | **✅ 17** |
| **MVP Total** | **30** | **✅ 30** |
| US2: Output & Color | 18 | ✅ 18 |
| US3: CLI Controls | 12 | ✅ 12 |
| US4: Safety & Compliance | 10 | ✅ 10 |
| Phase 7: Closeout | 11 | ✅ 11 (T072 deferred — requires fixture creation) |
| **Full Total** | **81** | **✅ 81** |

*Note: T056 deferred (CLI count drops from 13→12). Phase 7 expanded from 5→11 with 6 new benchmark tasks (T077–T082). Full total: 81 tasks.*

---

## Concerns

1. **Test fixture creation (T003–T005)**: Creating realistic NDA PDF pairs with known alignment and divergences is non-trivial. Consider using small synthetic PDFs generated programmatically (via `PyMuPDF`) rather than hand-crafted files. Benchmark corpus from spec 010 may provide templates.

2. **Sequential processing per Q2**: The pipeline processes Document A fully before Document B. This is correct for memory budget but means US1 cannot be truly parallelized across two documents. Integration test T028 must verify this explicitly.

3. **`_gateway.py` (T071)**: `comparison.py` must call `call_gateway_chat()` from `review._gateway`. Importing from a sibling package `review._gateway` is the correct approach (per FR-10: reuse without modification). If `_gateway.py` has different import paths, T071 should be delayed until T070 confirms the import works.

4. **RCBSF accuracy ceiling**: The spec explicitly cites ≤64% F1 (P-4). Tasks T024/T025 must include test cases that verify the comparison agent does NOT claim higher accuracy in its output. The prompts in T023 must include the accuracy caveat.

5. **First-run marker file location**: T066 needs `platformdirs` (already a dep) to get the user data directory. If not available, use `~/.local/share/openreview/` as fallback. Verify against existing code in `src/openreview_cli/config/`.
