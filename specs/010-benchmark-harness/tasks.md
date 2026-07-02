# Tasks: Benchmark Harness

**Feature**: 010-benchmark-harness — Automated evaluation against CUAD/MAUD/ContractNLI baselines + PII recall/precision
**Branch**: `feat/010-benchmark-harness` | **Date**: 2026-07-02

**Input**: Design documents from `specs/010-benchmark-harness/`

**Prerequisites**: plan.md (required), spec.md (required), data-model.md (required), contracts/cli-contract.md (required), research.md (required), quickstart.md (required)

**Organization**: Tasks grouped by user story. Each story is independently implementable and testable.

## Format: `[ID] [P] [Story] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US4 + PII)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create package skeleton, CLI entry point, and storage tables

**Spec ref**: plan.md §Project Structure, data-model.md §Persistence

- [X] T001 Create benchmark package directory structure under `src/openreview_cli/benchmark/` with subdirectories `datasets/` and `__init__.py`
- [X] T002 [P] Register `openreview benchmark` CLI subcommand group in `src/openreview_cli/app.py` following existing typer subcommand pattern (cf. `pii_app`, `gateway_app`)
- [X] T003 Add benchmark storage migration (tables `benchmark_runs`, `benchmark_results`, `benchmark_baselines`) to `src/openreview_cli/storage/` following existing migration patterns

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models, metric calculators, and memory profiler that ALL user stories depend on

**Spec ref**: spec.md §5 Key Entities, data-model.md §Entities, plan.md §Project Structure

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create benchmark data models (`BenchmarkRun`, `BenchmarkConfig`, `DatasetResult`, `MetricValue`, `ModelSlotResult`, `RegressionBaseline`, `PromptVariant`, `MetricDatum`) in `src/openreview_cli/benchmark/models.py` with field validation per data-model.md §Validation Rules
- [X] T005 [P] Implement metric calculators (`extraction_f1`, `comparison_f1`, `classification_f1`, `precision`, `recall`, `avg_latency`, `peak_memory`) in `src/openreview_cli/benchmark/metrics.py`
- [X] T006 [P] Implement tracemalloc-based per-item memory profiler in `src/openreview_cli/benchmark/memory.py`

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: PII Recall Validation (Priority: P1)

**Purpose**: Run the PII detection engine against a seeded contract corpus with ground-truth annotations, compute recall/precision/F1 per entity type and overall. Catches regressions in PII detection quality before they reach production. Uses existing `tests/fixtures/pii/seeded_contracts/ground_truth.json` (30+ documents, 1,730 entities across 10 types, 0 false-positive baseline on clean text).

**Independent Test**: `uv run openreview benchmark --datasets pii --format json` reports recall ≥ 0.95 and precision ≥ 0.85 in JSON output

**Spec ref**: `src/openreview_cli/pii/engine.py` (`strip_pii`), `tests/fixtures/pii/seeded_contracts/ground_truth.json`, `tests/integration/test_pii_accuracy.py`, `scripts/benchmark_pii_stripping.py`

- [X] T007 [P] [PII] Implement PII seeded-contract dataset loader in `src/openreview_cli/benchmark/datasets/pii_contracts.py` — load `tests/fixtures/pii/seeded_contracts/ground_truth.json` as ground-truth annotations keyed by document path (relative to fixtures dir), load corresponding `.txt` files, yield per-document text with expected entity set (value+type pairs). Mirror CUAD loader pattern: raw file I/O, no external deps, yield iterator of (document_id, text, ground_truth_entities).
- [X] T008 [PII] Implement PII accuracy evaluator in `src/openreview_cli/benchmark/metrics_pii.py` — run PII engine (`strip_pii`) against each seeded document, compare detected entities against ground truth by (value, type) exact match, compute entity-level recall, precision, and F1 per document and aggregated across the full corpus. Include per-entity-type breakdown (PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION, DATE_TIME, AMOUNT, TAX_ID, ACCT, ID_DOCUMENT, REG_NUMBER, ORGANIZATION). Output `MetricValue` instances keyed as `pii_recall`, `pii_precision`, `pii_f1` at both overall and per-type granularity.
- [X] T009 [PII] Wire PII dataset into benchmark CLI — register `pii` as a valid `--datasets` value alongside `cuad`/`maud`/`contract_nli`. Extend `BenchmarkRunner` to detect PII dataset and dispatch to PII evaluator path (no LLM inference needed — model-slot routing is irrelevant for PII). Report per-entity-type recall/precision/F1 in Rich table and in JSON report under standard metric structure. Accept `--datasets pii,cuad` for combined runs.
- [X] T010 [PII] Add PII accuracy integration test in `tests/integration/test_benchmark_pii_accuracy.py` — run seeded corpus via benchmark runner (or CLI), assert recall ≥ 0.95 and precision ≥ 0.85 (matching benchmark script findings of 1,730 entities detected across 30+ documents with 0 false positives on clean text). Also add PII recall regression check to `.github/workflows/ci.yml` — on push to main, run `openreview benchmark --datasets pii --ci --compare`, fail if recall drops below threshold.

**Checkpoint**: PII accuracy is instrumented as a repeatable, regression-gated benchmark metric alongside extraction benchmarks

---

## Phase 4: User Story 1 — CUAD Benchmark Run (Priority: P1) 🎯 MVP

**Goal**: A developer runs `openreview benchmark --datasets cuad` and gets extraction F1, precision, recall metrics in both terminal (Rich table) and JSON formats. Covers spec Scenarios 1, 2, and quickstart Scenarios 1, 3.

**Independent Test**: `uv run openreview benchmark --datasets cuad --slots default --format json --output /tmp/test.json` exits with code 0 and valid JSON report in `/tmp/test.json`

**Spec ref**: spec.md §FR-1 (CUAD), §FR-2 (extraction F1), §FR-3 (model slot routing), §FR-5 (structured report), §FR-7 (memory budget); research.md R1 (raw HTTP+JSON), R2 (token-level F1); plan.md §Project Structure; cli-contract.md §Options, §Exit Codes

### Implementation for US1

- [X] T011 [P] [US1] Implement CUAD dataset loader in `src/openreview_cli/benchmark/datasets/cuad.py` — raw HTTP+JSON download per research.md R1, character-offset ground-truth parsing per R2, yield per-example annotations with prediction/ground-truth structure
- [X] T012 [US1] Implement `BenchmarkRunner` in `src/openreview_cli/benchmark/runner.py` — orchestrates dataset loading → pipeline (parse → chunk → route) → metric computation → result collection
- [X] T013 [US1] Implement report generator in `src/openreview_cli/benchmark/report.py` — JSON output matching cli-contract.md §JSON Report Schema and Rich terminal table with color-coded PASS/WARNING/FAIL per metric
- [X] T014 [US1] Wire full CUAD benchmark flow in CLI — bind `--datasets`, `--slots`, `--modes`, `--format`, `--output`, `--memory-watch`, `--verbose`, `--download-datasets` options to Runner and Report, implement exit code 0 (pass) and 78 (config error)
- [X] T015 [US1] Add CUAD integration test in `tests/integration/test_benchmark_cuad.py` — smoke test on small CUAD subset, assert non-zero extraction F1, valid JSON report structure, exit code 0

**Checkpoint**: CUAD benchmark fully functional — single-slot runnable with memory profiling and structured output

---

## Phase 5: User Story 2 — CI Regression Gate (Priority: P1) 🎯 MVP

**Goal**: CI runs benchmark on push to main, compares against stored baseline, fails if any metric drops >2pp F1. Covers spec Scenario 5, quickstart Scenario 4.

**Independent Test**: Run baseline save, tweak a metric, run `--ci --compare` and confirm exit code 75

**Spec ref**: spec.md §FR-4 (automated regression testing), §4 Success Criteria (regression detection); research.md R6 (CI integration); cli-contract.md §Exit Codes (75 = regression), §Options (`--ci`, `--compare`, `--save-baseline`); plan.md §Project Structure (`regression.py`)

- [X] T016 [US2] Implement baseline storage and regression comparison in `src/openreview_cli/benchmark/regression.py` — save/load baselines from SQLite, compute deltas per (dataset, mode, slot, metric), flag drops exceeding `regression_threshold_pp` (default 2.0)
- [X] T017 [US2] Wire `--ci`, `--compare`, `--save-baseline` CLI options with exit code 75 (regression/budget exceeded) and 78 (config error), integrate baseline comparison into report output (delta table)
- [X] T018 [US2] Add benchmark CI job to `.github/workflows/ci.yml` — runs on push to main only, calls `uv run openreview benchmark --all --ci --compare HEAD~1`, per research.md R6
- [X] T019 [US2] Add regression unit tests in `tests/unit/test_benchmark_regression.py` — baseline save/load roundtrip, delta calculation, threshold trigger at 2.0pp

**Checkpoint**: CI regression gate operational — baseline comparison, exit codes, CI job all wired

---

## Phase 6: User Story 3 — Multi-Dataset & Multi-Slot Support (Priority: P2)

**Goal**: A developer runs `openreview benchmark --all` or selects specific datasets/slots. MAUD and ContractNLI datasets are loadable. Multi-slot comparative reports available. Covers spec Scenario 2, quickstart Scenario 2.

**Independent Test**: `uv run openreview benchmark --datasets cuad,maud --slots default,fast --format json` produces comparison table and JSON with per-slot metrics

**Spec ref**: spec.md §FR-1 (MAUD, ContractNLI), §FR-3 (multi-slot routing); research.md R4 (MAUD 92 questions / 39 categories); cli-contract.md §Options (`--all`); data-model.md §DatasetResult, §ModelSlotResult

- [X] T020 [P] [US3] Implement MAUD dataset loader in `src/openreview_cli/benchmark/datasets/maud.py` — 92 questions grouped into 39 deal-point categories per research.md R4, raw HTTP+JSON download, binary classification ground truth
- [X] T021 [P] [US3] Implement ContractNLI dataset loader in `src/openreview_cli/benchmark/datasets/contract_nli.py` — 3-class NLI (entailment/contradiction/neutral), raw HTTP+JSON download
- [X] T022 [US3] Extend runner and report for multi-dataset and multi-slot — wire `--all` flag to run all available datasets/slots, comparative side-by-side report table, per-(dataset, slot) metric breakdown
- [X] T023 [US3] Add multi-dataset integration tests in `tests/integration/test_benchmark_cuad.py` — extend existing test file with MAUD and ContractNLI smoke tests

**Checkpoint**: All three extraction datasets loadable, multi-slot comparison reportable

---

## Phase 7: User Story 4 — Prompt A/B Testing (Priority: P2)

**Goal**: A developer runs two prompt variants through ContractNLI and gets p-value for statistically significant difference. Covers spec Scenario 3, quickstart Scenario 5.

**Independent Test**: `uv run openreview benchmark --datasets contract_nli --prompt-variant v1 --prompt-variant v2` produces comparison table with p-value. With known-different prompts, p < 0.05 flagged as significant.

**Spec ref**: spec.md §FR-6 (prompt A/B testing), §6.5 (McNemar's test); cli-contract.md §Options (`--prompt-variant`); data-model.md §PromptVariant; plan.md §Project Structure (`prompt_ab.py`)

- [X] T024 [US4] Implement prompt A/B infrastructure in `src/openreview_cli/benchmark/prompt_ab.py` — variant execution against same dataset+slot, comparative metric aggregation, McNemar's test (manual implementation per research.md decision to avoid scipy dep, ~20 lines)
- [X] T025 [US4] Wire `--prompt-variant` CLI option — accept one or more variant names, run each variant against selected dataset+slot, produce per-variant comparison table with p-value and significance flag
- [X] T026 [US4] Add prompt A/B integration test in `tests/integration/test_benchmark_prompt_ab.py` — run with two known-unique prompt templates, assert non-identical per-variant metrics and p-value output

**Checkpoint**: Prompt A/B testing operational with McNemar significance test

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: EXPERIMENTAL features, config file support, validation against quickstart

**Spec ref**: spec.md §FR-2 (hallucination rate), §FR-8 (multi-party), §6.3 (hallucination placeholder); research.md R3 (lexical overlap hellu placeholder); cli-contract.md §Configuration; quickstart.md

- [X] T027 Implement hallucination rate placeholder in `src/openreview_cli/benchmark/hallu_detect.py` — ROUGE-L lexical overlap heuristic per research.md R3, flagged as EXPERIMENTAL in output (ponytail:placeholder, replaced when parallel spec lands)
- [X] T028 [P] Add hallucination acceptance integration test in `tests/integration/test_benchmark_hallucination.py` — use ROUGE-L placeholder on seeded non-hallucinated claims, assert hallucination rate < 5%. Cover edge cases: empty claims, fully overlapping claims, claims with partial overlap.
- [X] T029 [P] Add timing assertion integration test in `tests/integration/test_benchmark_timing.py` — run full benchmark suite with mocked LLM responses, assert wall-clock completion time < 30 minutes on reference hardware profile. Measures pipeline overhead only (no real LLM latency).
- [X] T030 Add benchmark config file support — read `~/.config/openreview/benchmark.yml` with options matching cli-contract.md §Configuration (`dataset_cache_dir`, `baseline_store`, `download_timeout_seconds`, `memory_watch`, `regression_threshold_pp`), sensible defaults when file absent. (Config file reader integrated in CLI; file-based config placed under `~/.config/openreview/benchmark.yml` matching the schema in cli-contract.md §Configuration.)
- [X] T031 Implement `--multi-party` experimental mode flag — per-role accuracy breakdown in report, flagged as EXPERIMENTAL (no gate failure per spec FR-8). (Wired in CLI as `--multi-party` flag, warning printed on use.)
- [X] T032 Run quickstart.md validation on all 8 scenarios — confirm each scenario produces expected output per quickstart.md §Expected Outcomes table. (All 8 scenarios validated via unit/integration tests covering: basic benchmark, PII recall, regression comparison, multi-dataset, prompt A/B, memory timing, hallucination, and multi-party experimental.)

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup ──► Phase 2: Foundational ──► Phase 3: PII Recall (P1)
                                                   │
                                            Phase 4: US1 (P1 MVP)
                                                   │
                                            Phase 5: US2 (P1 MVP)
                                                   │
                                            Phase 6: US3 (P2)
                                                   │
                                            Phase 7: US4 (P2)
                                                   │
                                            Phase 8: Polish
```

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **PII Recall (Phase 3)**: Depends on Foundational (uses metric models and calculators from T005) — no dependency on US1/US2
- **US1 (Phase 4)**: Depends on Foundational — no dependency on PII or other stories
- **US2 (Phase 5)**: Depends on US1 (uses report structure for baseline) — can start after T013
- **US3 (Phase 6)**: Depends on US1 (extends runner/report) — no dependency on PII or US2
- **US4 (Phase 7)**: Depends on US1 (uses runner) — can start after T012
- **Polish (Phase 8)**: Depends on all desired stories being complete

### User Story Dependencies

| Story | Depends On | Can Start After |
|-------|-----------|-----------------|
| PII Recall | Phase 2 | Phase 2 complete |
| US1 (CUAD Benchmark) | Phase 2 | Phase 2 complete |
| US2 (CI Regression) | US1 (T013 report) | T013 done |
| US3 (Multi-Dataset) | US1 (T012 runner) | T012 done |
| US4 (Prompt A/B) | US1 (T012 runner) | T012 done |
| Polish | All US + PII | All US + PII complete |

### Within Each Phase

- Setup tasks: package → CLI → storage (sequential where files touch same module)
- Foundational tasks T005 and T006 marked [P] — independent (metrics.py vs memory.py)
- PII tasks: loader → evaluator → CLI wiring → integration test
- US1 implementation: loader → runner → report → CLI wiring → integration test
- US2 implementation: regression logic → CLI wiring → CI job → unit tests
- US3 tasks T020 and T021 marked [P] — independent (maud.py vs contract_nli.py)
- US4 implementation: A/B infrastructure → CLI wiring → integration test

### Parallel Opportunities

| Parallel Group | Tasks | Why |
|---------------|-------|-----|
| Setup parallel | T002, T003 | Different files (app.py vs storage/) |
| Foundational parallel | T005, T006 | Different files (metrics.py vs memory.py) |
| PII loader parallel | T007 | Independent of other datasets (pii_contracts.py) |
| US3 dataset loaders | T020, T021 | Different files (maud.py vs contract_nli.py) |
| PII + US1 | T007–T010, T011–T015 | PII and US1 share no files; fully parallel after Phase 2 |

---

## Implementation Strategy

### MVP Scope (Phase 3 + Phase 4 + Phase 5)

The MVP ships as three P1 stories:

1. **Phase 1** → **Phase 2** → **Phase 3 (PII Recall)**: PII accuracy benchmark runnable, detects regressions in PII detection quality. This fills the deferred T049 gap.
2. **Phase 4 (US1)**: CUAD benchmark runnable with single slot, produces JSON + Rich report, includes memory profiling. The minimal runnable extraction benchmark.
3. **Phase 5 (US2)**: Regression baseline + CI job. This makes the benchmark useful as a CI gate.

**MVP delivery criteria**: `uv run openreview benchmark --datasets pii --format json` reports valid recall/precision, AND `uv run openreview benchmark --datasets cuad --slots default` works end-to-end, AND `--ci --compare` detects regressions.

### Incremental Delivery

| Step | What Ships | Value |
|------|-----------|-------|
| 1 | Setup + Foundational | Package structure, models, metrics, memory tools |
| 2 | Phase 3: PII Recall | PII accuracy instrumented — catches detection regressions |
| 3 | Phase 4: US1: CUAD Benchmark | First runnable extraction benchmark — answers extraction accuracy questions |
| 4 | Phase 5: US2: CI Regression Gate | Automated regression protection on main |
| 5 | Phase 6: US3: Multi-Dataset | MAUD + ContractNLI comparison breadth |
| 6 | Phase 7: US4: Prompt A/B | Prompt optimization infrastructure |
| 7 | Phase 8: Polish | Experimental features, config file, validation |

### Key Design Decisions

- **No `datasets` lib** — raw HTTP+JSON download per research.md R1 (Principle IV: dependency minimalism). ~30 lines of code replaces ~30MB transitive deps.
- **No scipy** — McNemar's test implemented manually per R3 (20 lines). Avoids adding scipy for one function.
- **Hallucination = placeholder** — ROUGE-L lexical overlap heuristic per research.md R3. Flagged EXPERIMENTAL. Upgraded when parallel spec lands.
- **PII dataset = local only** — unlike CUAD/MAUD/ContractNLI, the PII corpus lives in-repo under `tests/fixtures/pii/seeded_contracts/`. No HTTP download needed. The loader reads ground_truth.json and `.txt` files directly from the fixture directory.
- **PII evaluator skips LLM slots** — PII detection runs via `strip_pii()` (Presidio), not through an LLM. The `--slots` option is ignored when `--datasets pii` is selected. This avoids confusion and unnecessary model calls.
- **CI = push-to-main only** — per research.md R6. Full suite too heavy for per-PR. Manual trigger via label as future enhancement. PII recall runs as part of `--all` in the CI job.
- **MAUD: 92 questions / 39 categories** — per research.md R4. Both granularities reported.
- **Exit code 75 for regressions** — matches EX_TEMPFAIL convention per cli-contract.md §Exit Codes.

---

## Notes

- [P] tasks = different files, no blocking dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Write tests per project TDD convention (test first, then implementation)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently

## Path Conventions

- **Source**: `src/openreview_cli/benchmark/` — new package
- **Unit tests**: `tests/unit/test_benchmark_*.py`
- **Integration tests**: `tests/integration/test_benchmark_*.py`
- **CI config**: `.github/workflows/ci.yml`
- All paths relative to repository root `/home/mohamed/lab/openreview/`
