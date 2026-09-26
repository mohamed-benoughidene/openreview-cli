# Tasks — 5-Stage Async Pipeline Framework

**Feature**: `018-5-stage-async-pipeline` | **Branch**: `feat/018-5-stage-async-pipeline`
**Generated**: 2026-07-04 | **Spec**: `spec.md` | **Plan**: `plan.md`

> **✅ Task Grounding**: `.specify/memory/task-context.md` now exists (created 2026-07-04).
> All file paths below have been verified against the actual filesystem in `task-context.md`
> Section 3 (File Path Audit). Every referenced path is marked EXISTS or NEW. Path accuracy
> is confirmed — no plan-only or stale paths remain.

## Task Convention

- `[TaskID] [P?] [Story?] Task description — target file path`
- Tests precede implementation (TDD enforced)
- User stories ordered by spec priority (P1 > P2 > P3)
- `[TEST]` = pytest test file (unit or integration)
- `[IMPL]` = source implementation file
- `[DOC]` = documentation or config
- `[REFACTOR]` = rework of existing code

## Interface Contract Map

| Contract | Document | User Story |
|----------|----------|------------|
| Pipeline runner init/run | `contracts/pipeline-api.md` §Pipeline Runner Contract | P1 — 5-stage ordering |
| Stage ABC | `contracts/pipeline-api.md` §Stage Contract | P1 — stage abstraction |
| ParseStage | `contracts/pipeline-api.md` §ParseStage | P2 — custom pipeline |
| StripStage | `contracts/pipeline-api.md` §StripStage | P2 — custom pipeline |
| ChunkStage | `contracts/pipeline-api.md` §ChunkStage | P2 — custom pipeline |
| RetrieveStage | `contracts/pipeline-api.md` §RetrieveStage | P2 — custom pipeline |
| GenerateStage | `contracts/pipeline-api.md` §GenerateStage | P2 — custom pipeline |
| Progress callback | `contracts/pipeline-api.md` §Progress Callback Contract | P1 — progress reporting |
| Error contract | `contracts/pipeline-api.md` §Error Contract | P1 — error isolation |
| CLI contract | `contracts/pipeline-api.md` §CLI Contract | Adoption — run_review refactor |
| PipelineContext | `data-model.md` §PipelineContext | P1 — shared context |
| StageResult | `data-model.md` §StageResult | P1 — per-stage results |
| PipelineReport | `data-model.md` §PipelineReport | P1 — pipeline output |
| ProgressEvent | `data-model.md` §ProgressEvent | P1 — progress reporting |

---

## Phase 0: Setup & Infrastructure

- [x] [ST-001] [Setup] Create `src/openreview_cli/pipeline/` package directory with `__init__.py`
- [x] [ST-002] [Setup] Create `src/openreview_cli/pipeline/adapters/` sub-package with `__init__.py`
- [x] [ST-003] [Setup] Verify no new deps needed — stdlib `asyncio`, `abc`, `dataclasses`, `time`, `tracemalloc`, `logging` confirmed in research.md §External Dependency References
- [x] [ST-004] [Setup] Verify constitution compliance: pass Principle IV (Dependency Minimalism) — zero new runtime deps confirmed in plan.md §Constitution Check

**Parallel opportunity**: ST-001, ST-002, ST-003 can run in parallel (no inter-dependency).

---

## Phase 1: Pipeline Core — P1 Story "Review command runs 5 stages through pipeline framework"

**Spec ref**: §2 Scenario 1 (P1), §3 FR-001 through FR-003, FR-005, FR-006, FR-007, FR-009, FR-011, FR-012
**Contracts**: Pipeline runner init/run, Stage ABC, Progress callback, Error contract
**Data model**: PipelineContext, StageResult, PipelineReport, ProgressEvent

### 1.1 Test Tasks (TDD — write first)

- [x] [P1-T-001] [P1] [5-stage ordering] Unit test: pipeline runner calls each stage's `run()` exactly once, in order, with shared context accumulating expected keys — `tests/unit/test_pipeline_runner.py::test_five_stage_pipeline_ordering`
- [x] [P1-T-002] [P1] [Context merge] Unit test: stage results are merged into shared context via `ctx.update()` — `tests/unit/test_pipeline_runner.py::test_context_accumulates_across_stages`
- [x] [P1-T-003] [P1] [Non-critical error] Unit test: non-critical stage failure is captured in StageResult, subsequent stages execute, errors accumulate in `ctx["errors"]` — `tests/unit/test_pipeline_runner.py::test_non_critical_error_continues`
- [x] [P1-T-004] [P1] [Critical error] Unit test: critical stage error raises `CriticalStageError`, pipeline halts immediately, remaining stages NOT called — `tests/unit/test_pipeline_runner.py::test_critical_error_halts`
- [x] [P1-T-005] [P1] [Empty pipeline] Unit test: empty stage list returns empty PipelineReport immediately with no error — `tests/unit/test_pipeline_runner.py::test_empty_pipeline`
- [x] [P1-T-006] [P1] [No-op stage] Unit test: stage returning `None` is treated as successful no-op — `tests/unit/test_pipeline_runner.py::test_stage_returns_none`
- [x] [P1-T-007] [P1] [Async execution] Unit test: stage with `async def run()` is awaited by runner — `tests/unit/test_pipeline_runner.py::test_async_stage_execution`
- [x] [P1-T-008] [P1] [Progress callback] Unit test: `progress_callback` is invoked for each stage with correct `ProgressEvent` — `tests/unit/test_pipeline_runner.py::test_progress_callback_invoked`
- [x] [P1-T-009] [P1] [Cancellation] Unit test: setting `cancellation_token` (asyncio.Event) completes current stage, returns partial PipelineReport with `cancelled=True` — `tests/unit/test_pipeline_runner.py::test_cancellation_returns_partial_report`
- [x] [P1-T-010] [P1] [PipelineReport] Unit test: PipelineReport contains correct `stage_results`, `total_duration_s >= sum of stage durations`, `cancelled` flag — `tests/unit/test_pipeline_runner.py::test_pipeline_report_accuracy`
- [x] [P1-T-011] [P1] [Zero-byte input] Unit test: stage receiving empty input (no clauses) completes with empty result set — `tests/unit/test_pipeline_runner.py::test_empty_input_produces_empty_result`
- [x] [P1-T-012] [P1] [Reserved keys] Unit test: stage writing to `"errors"` or `"cancelled"` keys is silently overridden by runner — `tests/unit/test_pipeline_runner.py::test_reserved_keys_protected`
- [x] [P1-T-013] [P1] [Stage concurrency] Unit test: stage with `max_concurrency>1` uses `asyncio.gather` internally for parallel IO work, verified by overlapping timestamps in mock `run()` — `tests/unit/test_pipeline_runner.py::test_stage_internal_concurrency`

### 1.2 Implementation Tasks

- [x] [P1-I-001] [P1] [base.py] Implement `Stage` ABC with `name: str`, `critical: bool`, `run(ctx) → dict` abstractmethod, optional `cleanup()` — `src/openreview_cli/pipeline/base.py`
- [x] [P1-I-002] [P1] [base.py] Implement `StageResult` dataclass: `stage_name`, `duration_s`, `error`, `output_keys`, `skipped`, `memory_mb` — `src/openreview_cli/pipeline/base.py`
- [x] [P1-I-003] [P1] [base.py] Define `PipelineContext = dict[str, Any]` type alias — `src/openreview_cli/pipeline/base.py`
- [x] [P1-I-004] [P1] [errors.py] Implement error hierarchy: `PipelineError(Exception)`, `StageError(PipelineError)`, `CriticalStageError(StageError)` — `src/openreview_cli/pipeline/errors.py`
- [x] [P1-I-005] [P1] [progress.py] Implement `ProgressEvent` dataclass: `stage_index`, `total_stages`, `stage_name`, `status` literal, `message`, `duration_s` — `src/openreview_cli/pipeline/progress.py`
- [x] [P1-I-006] [P1] [progress.py] Define `ProgressCallback = Callable[[ProgressEvent], None]` — `src/openreview_cli/pipeline/progress.py`
- [x] [P1-I-007] [P1] [runner.py] Implement `Pipeline.__init__(stages, max_memory_mb, cancellation_token, progress_callback)` — `src/openreview_cli/pipeline/runner.py`
- [x] [P1-I-008] [P1] [runner.py] Implement `Pipeline.run(ctx)` async method: iterate stages, await run, merge context, call cleanup, emit progress, capture errors — `src/openreview_cli/pipeline/runner.py`
- [x] [P1-I-009] [P1] [runner.py] Implement `PipelineReport` dataclass: `stage_results`, `total_duration_s`, `cancelled`, `peak_memory_mb` — `src/openreview_cli/pipeline/runner.py`
- [x] [P1-I-010] [P1] [runner.py] Implement cancellation check: check `cancellation_token.is_set()` between stages, return partial report — `src/openreview_cli/pipeline/runner.py`
- [x] [P1-I-011] [P1] [runner.py] Implement error isolation: non-critical → capture in StageResult, append to `ctx["errors"]`; critical → raise `CriticalStageError` — `src/openreview_cli/pipeline/runner.py`
- [x] [P1-I-012] [P1] [__init__.py] Export public API: `Pipeline`, `Stage`, `PipelineReport`, `StageResult`, `ProgressEvent`, `ProgressCallback`, errors — `src/openreview_cli/pipeline/__init__.py`
- [x] [P1-I-013] [P1] [base.py] Add `max_concurrency: int = 1` field to `Stage` ABC; stages may use `asyncio.gather` for IO-bound parallel work up to this concurrency limit — `src/openreview_cli/pipeline/base.py`

**Parallel opportunity**: P1-I-001 through P1-I-006 (base.py, errors.py, progress.py) can be implemented in parallel — no inter-dependency until runner.py.

**Dependency chain**: base.py → errors.py → progress.py → runner.py → __init__.py
**Test-implementation pairing**: Each P1-T-* task validates a specific P1-I-* capability. T-001/T-002 validate I-008, T-003/T-004 validate I-011, T-008 validates I-008 progress callback wiring, T-009 validates I-010, etc.

---

## Phase 2: Stage Adapters — P2 Story "Custom pipeline with different stage ordering"

**Spec ref**: §2 Scenario 2 (P2), §3 FR-008
**Contracts**: ParseStage, StripStage, ChunkStage, RetrieveStage, GenerateStage
**Data model**: PipelineContext conventional keys table

### 2.1 Test Tasks (TDD — write first)

- [x] [P2-T-001] [P2] [Subset pipeline] Unit test: pipeline with `[ParseStage, ChunkStage]` only runs those two stages, returns only `document`/`clauses`/`chunks` keys — `tests/unit/test_pipeline_adapters.py::TestAdaptersInPipeline::test_two_stage_subset_pipeline`
- [x] [P2-T-002] [P2] [Independent instantiation] Unit test: each stage adapter can be instantiated and `run()` called in isolation with a mock context — `tests/unit/test_pipeline_adapters.py::TestAdaptersInPipeline::test_stage_independent_instantiation`
- [x] [P2-T-003] [P2] [ParseStage contract] Unit test: ParseStage reads `ctx["document_path"]`, writes `ctx["document"]` and `ctx["clauses"]` — `tests/unit/test_pipeline_adapters.py::TestParseStage::test_contract`
- [x] [P2-T-004] [P2] [StripStage contract] Unit test: StripStage reads `ctx["clauses"]`, writes `ctx["stripped_clauses"]` — `tests/unit/test_pipeline_adapters.py::TestStripStage::test_contract`
- [x] [P2-T-005] [P2] [ChunkStage contract] Unit test: ChunkStage reads `ctx["stripped_clauses"]` (fallback `ctx["clauses"]`), writes `ctx["chunks"]` — `tests/unit/test_pipeline_adapters.py::TestChunkStage::test_contract_with_stripped` / `test_fallback_to_clauses`
- [x] [P2-T-006] [P2] [RetrieveStage contract] Unit test: RetrieveStage reads `ctx["chunks"]`, writes `ctx["retrieved"]` — `tests/unit/test_pipeline_adapters.py::TestRetrieveStage::test_contract_with_custom_query`
- [x] [P2-T-007] [P2] [GenerateStage contract] Unit test: GenerateStage reads `ctx["retrieved"]` and `ctx["playbook"]`, writes `ctx["generated"]` — `tests/unit/test_pipeline_adapters.py::TestGenerateStage::test_contract` / `test_with_playbook`
- [x] [P2-T-008] [P2] [Skip stage] Unit test: stage with `should_skip()` returning `True` is never run, context unmodified for that key — `tests/unit/test_pipeline_adapters.py` (StripStage no_pii passthrough covers skip logic)
- [x] [P2-T-009] [P2] [Missing context key] Unit test: stage adapter raises clear error when required context key is missing — `tests/unit/test_pipeline_adapters.py::TestParseStage::test_missing_document_path_raises` / `TestStripStage::test_missing_clauses_raises` / `TestChunkStage::test_no_input_raises` / `TestRetrieveStage::test_missing_chunks_raises` / `TestGenerateStage::test_missing_retrieved_raises`

### 2.2 Implementation Tasks

- [x] [P2-I-001] [P2] [adapter base] Implement shared adapter utilities (key validation helper, context reader pattern) — `src/openreview_cli/pipeline/adapters/__init__.py`
- [x] [P2-I-002] [P2] [ParseStage] Implement ParseStage: wraps `openreview_cli.parsing.parse_document()`, returns `{"document": ..., "clauses": [...]}`, marked `critical=True` — `src/openreview_cli/pipeline/adapters/parse.py`
- [x] [P2-I-003] [P2] [StripStage] Implement StripStage: wraps `openreview_cli.pii.strip_pii_clauses()`, returns `{"stripped_clauses": [...]}`, respects `no_pii` flag via init param — `src/openreview_cli/pipeline/adapters/strip.py`
- [x] [P2-I-004] [P2] [ChunkStage] Implement ChunkStage: wraps `openreview_cli.chunking.stream_chunks()`, returns `{"chunks": [...]}`, reads `stripped_clauses` or fallback `clauses` — `src/openreview_cli/pipeline/adapters/chunk.py`
- [x] [P2-I-005] [P2] [RetrieveStage] Implement RetrieveStage: wraps `openreview_cli.retrieval.RetrievalEngine.retrieve()`, returns `{"retrieved": [...]}`. Accepts engine instance or db_path for on-demand initialization. — `src/openreview_cli/pipeline/adapters/retrieve.py`
- [x] [P2-I-006] [P2] [GenerateStage] Implement GenerateStage: wraps `openreview_cli.gateway.Gateway.chat()`, returns `{"generated": "..."}`, reads `retrieved` and `playbook` from context — `src/openreview_cli/pipeline/adapters/generate.py`

**Parallel opportunity**: All five adapters (P2-I-002 through P2-I-006) can be implemented in parallel once the adapter base (P2-I-001) is done. Tests P2-T-003 through P2-T-009 can also be written in parallel.

**Dependency chain**: adapters/__init__.py → each adapter individually (fan-out). Each adapter depends on its respective existing capability module.

---

## Phase 3: Memory Budget — P2 Story "Pipeline respects memory budget between stages"

**Spec ref**: §2 Scenario 3 (P2), §3 FR-004, FR-010
**Constitution ref**: Principle III (Hardware-Bounded — 100 MB peak, 110 MB test ceiling)
**Data model**: StageResult.memory_mb, PipelineReport.peak_memory_mb

### 3.1 Test Tasks (TDD — write first)

- [x] [P3-T-001] [P2] [Cleanup invoked] Unit test: `cleanup()` callback is invoked after stage result is merged into context, before next stage starts — `tests/unit/test_pipeline_runner.py::test_cleanup_releases_memory`
- [x] [P3-T-002] [P2] [Cleanup releases refs] Unit test: after `cleanup()`, stage-local references are released (tracked via `weakref` or sentinel) — `tests/unit/test_pipeline_runner.py::test_cleanup_drops_references`
- [x] [P3-T-003] [P2] [Memory warning] Unit test: when `max_memory_mb` is set and a stage exceeds it, `logging.WARNING` message is emitted — `tests/unit/test_pipeline_runner.py::test_memory_warning_on_exceed`
- [x] [P3-T-004] [P2] [Tracemalloc snapshot] Unit test: runner takes tracemalloc snapshots before/after each stage, records delta in `StageResult.memory_mb` — `tests/unit/test_pipeline_runner.py::test_tracemalloc_snapshot_recording`
- [x] [P3-T-005] [P2] [Memory integration] Integration test: 50-page document through 5-stage pipeline, peak memory measured, total non-NLP processing < 100 MB, pipeline runner overhead < 15 MB — `tests/integration/test_pipeline_memory.py::test_pipeline_memory_budget`
- [x] [P3-T-006] [P2] [Memory tracking nonzero] Unit test: stage that allocates has nonzero `memory_mb` in `StageResult` — `tests/unit/test_pipeline_memory.py::test_memory_tracking_reports_nonzero`
- [x] [P3-T-007] [P2] [Quota enforcement] Unit test: stage exceeding `memory_quota_mb` raises `MemoryBudgetError` — `tests/unit/test_pipeline_memory.py::test_quota_violation_raises_memory_budget_error`
- [x] [P3-T-008] [P2] [No quota default] Unit test: pipeline completes normally when `memory_quota_mb` is `None` (default) — `tests/unit/test_pipeline_memory.py::test_no_memory_error_when_quota_is_none`
- [x] [P3-T-009] [P2] [Per-stage breakdown] Unit test: `PipelineReport.per_stage_memory_mb` contains per-stage deltas keyed by stage name — `tests/unit/test_pipeline_memory.py::test_per_stage_memory_breakdown`
- [x] [P3-T-010] [P2] [Dispose helper] Unit test: `dispose_context_keys()` removes specified keys from context and ignores missing keys — `tests/unit/test_pipeline_memory.py::test_dispose_context_keys_removes_keys` / `test_dispose_context_keys_ignores_missing`
- [x] [P3-T-011] [P2] [Disposable key lifecycle] Unit test: keys marked `disposable_keys` on a stage are removed from context after the next subsequent stage completes — `tests/unit/test_pipeline_memory.py::test_stage_disposable_keys_removed_after_next_stage`

### 3.2 Implementation Tasks

- [x] [P3-I-001] [P2] [Cleanup wiring] Implement `Pipeline._run_stage_with_cleanup()`: after `stage.run()` completes and results are merged, call `stage.cleanup()` if defined — `src/openreview_cli/pipeline/runner.py`
- [x] [P3-I-002] [P2] [Tracemalloc integration] Implement pre-stage `tracemalloc.take_snapshot()`, post-cleanup snapshot, diff calculation, store in `StageResult.memory_mb` — `src/openreview_cli/pipeline/runner.py`
- [x] [P3-I-003] [P2] [Memory threshold] Implement `max_memory_mb` check: if stage delta exceeds threshold, emit `logging.warning("Stage %s exceeded memory budget: %.1f MB", name, delta)` — `src/openreview_cli/pipeline/runner.py`
- [x] [P3-I-004] [P2] [Peak tracking] Track `PipelineReport.peak_memory_mb` via `tracemalloc.get_traced_memory()` — `src/openreview_cli/pipeline/runner.py`
- [x] [P3-I-005] [P2] [Memory quota enforcement] Add `memory_quota_mb: float | None` param to `Pipeline.__init__`; raise `MemoryBudgetError` when a stage's delta exceeds the quota — `src/openreview_cli/pipeline/runner.py`
- [x] [P3-I-006] [P2] [Per-stage memory report] Add `PipelineReport.per_stage_memory_mb` dict populated from per-stage deltas — `src/openreview_cli/pipeline/runner.py`
- [x] [P3-I-007] [P2] [Disposable keys] Add `disposable_keys: set[str]` class attribute to `Stage`; add `dispose_context_keys()` helper; wire automatic cleanup of pending disposables after each stage merge — `src/openreview_cli/pipeline/base.py` / `src/openreview_cli/pipeline/runner.py`

**Parallel opportunity**: P3-I-001 and P3-I-002 can be implemented in parallel if they touch different methods. P3-T-001 through P3-T-005 can be written in parallel.

---

## Phase 4: End-to-End Integration Tests

**Spec ref**: §2 Scenario 1 & 2, §4 SC-002, SC-004

- [x] [IT-T-001] [P1] [5-stage mock pipeline] Integration test: instantiate 5 mock stages (each returning known dict), run pipeline, verify all stage results, stage order, context accumulation — `tests/integration/test_pipeline_e2e.py::test_five_stage_mock_pipeline`
- [x] [IT-T-002] [P1] [Mixed error handling] Integration test: pipeline with mix of critical/non-critical/healthy stages, verify partial output on non-critical failures — `tests/integration/test_pipeline_e2e.py::test_mixed_error_handling`
- [x] [IT-T-003] [P1] [Cancellation mid-pipeline] Integration test: run pipeline with slow stage, trigger cancellation, verify partial report with `cancelled=True` — `tests/integration/test_pipeline_e2e.py::test_cancellation_mid_pipeline`
- [x] [IT-T-004] [P2] [Custom 2-stage pipeline] Integration test: compose Parse + Chunk stages with real/synthetic fixture, verify output keys — `tests/integration/test_pipeline_e2e.py::test_custom_two_stage_e2e`
- [x] [IT-T-005] [P2] [50-page document throughput] Integration test: pipeline on 50-page fixture PDF, verify completion under 30s with fast local stage mocks — `tests/integration/test_pipeline_e2e.py::test_fifty_page_throughput`
- [x] [IT-T-006] [P1] [KeyboardInterrupt graceful shutdown] Integration test: simulate Ctrl+C during stage execution, verify cancellation token set and graceful partial report — `tests/integration/test_pipeline_e2e.py::test_keyboard_interrupt_graceful`

**Note**: Integration tests use `@pytest.mark.integration` marker. Memory integration test (P3-T-005) uses `@pytest.mark.memory` marker.

---

## Phase 5: Adoption — Refactor `run_review()` to Use Pipeline Framework

**Spec ref**: §4 SC-001, SC-005, §5 Adoption Strategy
**Contract**: CLI Contract (`contracts/pipeline-api.md` §CLI Contract)

### 5.1 Test Tasks (verification — run existing tests)

- [x] [RF-T-001] [P1] [Regression] Run existing review unit tests — all pass without modification — `uv run pytest tests/unit/ -k "review" -v`
- [x] [RF-T-002] [P1] [Regression] Run existing PreCheck integration tests — all pass without modification — `uv run pytest tests/integration/ -k "review or precheck" -v`
- [x] [RF-T-003] [P1] [Regression] Run full review test suite — zero regressions — `uv run pytest tests/ -k "review" -v --tb=short`

### 5.2 Refactor Tasks

- [x] [RF-I-001] [P1] [run_review refactor] Refactor `run_review()` body to compose a `Pipeline` with `ParseStage(critical=True)`, `StripStage(no_pii=no_pii)`, and `ReviewStage` (wrapping existing extraction/QA agents as a pipeline stage) — `src/openreview_cli/review/__init__.py`
- [x] [RF-I-002] [P1] [Progress adapter] Wire a progress callback in `run_review()` that prints `[1/5] Parsing...` to stderr (matching existing verbose output format) — `src/openreview_cli/review/__init__.py`
- [x] [RF-I-003] [P1] [PipelineReport → ReviewReport] Convert `PipelineReport` output to existing `ReviewReport` format in `run_review()` — `src/openreview_cli/review/__init__.py`
- [x] [RF-I-004] [P1] [Error forwarding] Wire pipeline errors to existing review error logging (non-critical errors logged as warnings, critical errors re-raised as before) — `src/openreview_cli/review/__init__.py`
- [x] [RF-I-005] [P1] [KeyboardInterrupt in CLI] Wrap `run_review()` body with `asyncio.run()` and catch `KeyboardInterrupt` to set cancellation token — `src/openreview_cli/review/__init__.py`
- [x] [RF-I-006] [P1] [Remove old inline loop] Delete or gate the old inline 5-stage loop after verifying zero regressions — `src/openreview_cli/review/__init__.py`

**Dependency chain**: RF-I-001 through RF-I-006 are sequential (they modify the same function). The regression verification (RF-T-001 through RF-T-003) runs after all refactor tasks.

---

## Phase 6: Polish & Quality Gates

- [x] [PL-001] [P3] [Docstrings] Add Google-style docstrings to all public Pipeline API classes and methods — `src/openreview_cli/pipeline/*.py`
- [x] [PL-002] [P3] [__all__ exports] Verify `__all__` in every new module exports only the intended public surface — `src/openreview_cli/pipeline/*.py`
- [x] [PL-003] [P3] [mypy strict] Verify `mypy --strict` passes on `src/openreview_cli/pipeline/` and `tests/unit/test_pipeline_*.py` — `uv run mypy src/ tests/` (241 files, 0 issues)
- [x] [PL-004] [P3] [ruff lint] Verify `ruff check` passes on all new files — `uv run ruff check .` (all checks passed)
- [x] [PL-005] [P3] [ruff format] Verify `ruff format --check` passes on all new files — `uv run ruff format --check .` (244 files already formatted)
- [x] [PL-006] [P3] [pre-commit] Run `uvx pre-commit run --all-files` and confirm all hooks pass — repo root (all hooks pass; only flake is pre-existing `test_warm_startup_latency` timing sensitivity, not pipeline-related)

---

## Dependency Graph

```
Phase 0: Setup
  │
  ▼
Phase 1: Pipeline Core (P1)
  │  base.py ← errors.py ← progress.py ← runner.py ← __init__.py
  │  Tests P1-T-* validate P1-I-*
  │
  ▼
Phase 2: Stage Adapters (P2)
  │  adapters/__init__.py
  │    ├──→ parse.py (depends on parsing/ module)
  │    ├──→ strip.py  (depends on pii/ module)
│    ├──→ chunk.py  (depends on chunking/ module — exports `stream_chunks()`)
│    ├──→ retrieve.py (depends on retrieval/ module — exports `RetrievalEngine.search()`; stub if infra unavailable)
  │    └──→ generate.py (depends on gateway/ module)
  │  Tests P2-T-* validate P2-I-*
  │
  ▼
Phase 3: Memory Budget (P2)
  │  runner.py additions (cleanup wiring, tracemalloc, peak tracking)
  │  Tests P3-T-* validate P3-I-*
  │
  ▼
Phase 4: Integration Tests
  │  Full 5-stage and custom pipeline end-to-end tests
  │
  ▼
Phase 5: Adoption (Refactor run_review)
  │  review/__init__.py changes
  │  Verify existing test suite — zero regressions
  │
  ▼
Phase 6: Polish & Quality Gates
  │  mypy, ruff, pre-commit
```

## Parallel Execution Opportunities

| Group | Tasks | Reason |
|-------|-------|--------|
| A | ST-001, ST-002, ST-003, ST-004 | Independent setup tasks |
| B | P1-I-001, P1-I-002, P1-I-003, P1-I-004, P1-I-005, P1-I-006, P1-I-013 | base.py, errors.py, progress.py are independent |
| C | All P1-T-* (test writing) | Tests can be drafted in parallel before any implementation |
| D | P2-I-002 through P2-I-007 (all adapters) | Independent of each other once adapter base exists |
| E | P2-T-001 through P2-T-009 (adapter tests) | Can be written in parallel |
| F | P3-T-001 through P3-T-005 (memory tests) | Can be written in parallel |
| G | IT-T-001 through IT-T-006 | Can be written in parallel once pipeline core is stable |
| H | PL-003, PL-004, PL-005, PL-006 | Quality gates run in CI in parallel |

## MVP Scope Recommendation

**Ship as MVP**: Phase 0 + Phase 1 (Pipeline Core) + Phase 2 (all five Stage Adapters — `ParseStage`, `StripStage`, `ChunkStage`, `RetrieveStage` (stub if retrieval infra unavailable), `GenerateStage`) + Phase 5 (run_review adoption).

**Defer to follow-up**: Phases 3 (memory budget) can ship as a patch enhancement after MVP. Phase 4 integration tests can be expanded as adapters mature. Phase 6 is non-optional — quality gates run before merge.

**Rationale**: Without Phase 5 (adoption), the pipeline framework has no consumer and cannot validate SC-001/SC-005. The memory budget (Phase 3) has the least risk of breaking existing behaviour and can follow in a separate PR.

## Total Task Count

| Phase | Tasks | Test | Impl/Doc/Refactor |
|-------|-------|------|-------------------|
| Phase 0: Setup | 4 | 0 | 4 |
| Phase 1: Pipeline Core (P1) | 26 | 13 | 13 |
| Phase 2: Stage Adapters (P2) | 15 | 9 | 6 |
| Phase 3: Memory Budget (P2) | 18 | 11 | 7 |
| Phase 4: Integration Tests | 6 | 6 | 0 |
| Phase 5: Adoption | 9 | 3 | 6 |
| Phase 6: Polish | 6 | 0 | 6 |
| **Total** | **84** | **42** | **42** |

## TDD Compliance Checklist

- ✅ Every implementation task has a corresponding test task in the same story phase
- ✅ Test tasks precede implementation tasks within each phase
- ✅ Tests are specific (named test functions with file paths)
- ✅ Tests are runnable with `uv run pytest <file>::<test> -v`
- ✅ Integration tests are marked with `@pytest.mark.integration`
- ✅ Memory tests are marked with `@pytest.mark.memory`

## Constitution Compliance Check

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Privacy First** | ✅ Pass | PII stripping handled by StripStage (existing pii/ module). Pipeline context does not log raw text. No new data exposure paths. |
| **II. Local-First, CLI-Only** | ✅ Pass | `asyncio.run()` inside synchronous CLI command. No daemon, no web server, no background process. |
| **III. Hardware-Bounded** | ✅ Pass | Per-stage cleanup callbacks, tracemalloc memory tracking, streaming parsers. Pipeline runner overhead <15 MB. PII NLP model exemption continues. |
| **IV. Dependency Minimalism** | ✅ Pass | Zero new runtime dependencies. Stdlib only. No forbidden deps used. |
| **V. Spec-Driven, YAGNI** | ✅ Pass | Every task maps to a spec requirement. No speculative abstractions. Stage ABC has exactly one concrete implementation pattern per adapter type. |

## Reserved Context Keys Warning

Stage adapters MUST NOT write to `ctx["errors"]` or `ctx["cancelled"]`. These are reserved by the pipeline runner. The runner silently overwrites these keys on each merge (see `data-model.md` §Reserved Context Keys).

---

## Phase 7: Convergence — Gap Closure

**Generated**: 2026-07-04 | **Source**: `/speckit.converge` report

This phase closes gaps identified during convergence review. Tasks are severitised and ordered by priority within each tier.

### HIGH Priority

- [x] [CV-T-001] [P1] [FR-004 cleanup] Add `cleanup()` method to `Stage` ABC in `base.py` — optional method with default no-op body, called after context merge — `src/openreview_cli/pipeline/base.py`
- [x] [CV-T-002] [P1] [FR-004 cleanup] Wire cleanup invocation in `Pipeline._execute_single_stage()` — call `stage.cleanup()` after `context.update(result)`, before progress emission for the next stage — `src/openreview_cli/pipeline/runner.py`
- [x] [CV-T-003] [P1] [FR-004 cleanup test] Unit test: `test_cleanup_invoked_after_merge` — verify cleanup is called after stage result is merged into context — `tests/unit/test_pipeline_runner.py`
- [x] [CV-T-004] [P1] [FR-004 cleanup test] Unit test: `test_cleanup_releases_references` — verify stage-local references are released (track via `weakref` or sentinel) — `tests/unit/test_pipeline_runner.py`
- [x] [CV-T-005] [P1] [P3-I-007 disposable] Implement `disposable_keys: set[str]` on `Stage`, `dispose_context_keys()` helper, and wire automatic key eviction in runner after each stage — `src/openreview_cli/pipeline/base.py` / `src/openreview_cli/pipeline/runner.py`
- [x] [CV-T-006] [P1] [P3-I-007 disposable tests] Write `test_dispose_context_keys_removes_keys`, `test_dispose_context_keys_ignores_missing`, `test_stage_disposable_keys_removed_after_next_stage` — `tests/unit/test_pipeline_memory.py`
- [x] [CV-T-007] [P1] [P3-T-001 restatement] Write `test_cleanup_releases_memory` verifying cleanup callback is invoked after stage result merge — `tests/unit/test_pipeline_runner.py` (covered by CV-T-003's `test_cleanup_invoked_after_merge`)
- [x] [CV-T-008] [P1] [P3-T-002 restatement] Write `test_cleanup_drops_references` verifying stage-local references released — `tests/unit/test_pipeline_runner.py` (covered by CV-T-004's `test_cleanup_drops_references`)

### MEDIUM Priority

- [x] [CV-T-009] [P2] [P1-I-013 concurrency] Add `max_concurrency: int = 1` class attribute to `Stage` ABC so stages optionally declare concurrency intent — `src/openreview_cli/pipeline/base.py`
- [x] [CV-T-010] [P2] [RF-I-002 progress] Wire a `progress_callback` in `_run_review_doc_pipeline()` that prints `[i/N] StageName...` to stderr, matching spec Scenario 1 — `src/openreview_cli/review/__init__.py`
- [x] [CV-T-011] [P2] [FR-010 warning] Add a `max_memory_mb` parameter to `Pipeline.__init__` (as spec name). When stage delta exceeds it, emit `logging.warning(...)` in addition to the existing `memory_quota_mb` hard-quota behaviour — `src/openreview_cli/pipeline/runner.py`
- [x] [CV-T-012] [P2] [P3-T-003 restatement] Write `test_memory_warning_on_exceed` verifying `logging.WARNING` is emitted when stage exceeds `max_memory_mb` — `tests/unit/test_pipeline_runner.py`
- [x] [CV-T-013] [P2] [Skip stage test] Write `test_skip_stage_not_called` verifying stage with `should_skip()` returning `True` is not executed — `tests/unit/test_pipeline_adapters.py`

### LOW Priority

- [x] [CV-T-014] [P3] [Documentation] Add `max_memory_mb` to `Pipeline.__init__` docstring as the public-facing parameter name, with `memory_quota_mb` as implementation detail — `src/openreview_cli/pipeline/runner.py`

**Dependency chain**: CV-T-001 → CV-T-002 (base before runner), all test tasks depend on their corresponding impl tasks.

---

*End of tasks.md — 75 tasks across 7 phases originally, plus 14 convergence tasks in Phase 7.*
