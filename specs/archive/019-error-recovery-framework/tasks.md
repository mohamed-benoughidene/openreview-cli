# Tasks: Error Recovery Framework

**Input**: Design documents from `/specs/019-error-recovery-framework/`

**Prerequisites**: plan.md (complete), spec.md (complete with 5 user stories), data-model.md (6 entities), contracts/ (3 contracts), research.md (3 research decisions), quickstart.md (usage examples)

**Organization**: Tasks grouped by user story. Each story independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to user story from spec.md
- File paths in descriptions

---

## Phase 1: Setup

**Purpose**: Create the recovery package directory structure and public API surface.

- [X] T001 Create `src/openreview_cli/recovery/__init__.py` with public exports (initially empty, populated per phase)
- [X] T002 [P] Create `src/openreview_cli/recovery/strategies/__init__.py` with strategy exports (initially empty, populated per phase)

**Checkpoint**: Package structure exists. `from openreview_cli.recovery` imports without error.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models, error classification, and pipeline extensions that ALL strategies depend on.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Define `ErrorCategory` enum (`transient`, `permanent`, `resource`, `stage_failure`, `stage_failure_critical`, `unknown`) in `src/openreview_cli/recovery/models.py`
- [X] T004 [P] Define `DegradationAction` enum (`reduce_batch_size`, `switch_to_lightweight_model`, `simplify_processing`, `reduce_context_window`) in `src/openreview_cli/recovery/models.py`
- [X] T005 [P] Define `RecoveryEvent` dataclass (strategy_name, stage_name, provider_name, attempt, outcome, message, timestamp) in `src/openreview_cli/recovery/models.py`
- [X] T006 [P] Define `RecoveryContext` dataclass (provider_list, attempted_strategies, current_provider_index, retry_counts, memory_threshold_bytes, memory_budget_bytes, failed_stages, completed_stages, partial_data, saved_results, events, user_privacy_tier) in `src/openreview_cli/recovery/models.py`
- [X] T007 [P] Define `RecoveryReport` dataclass (events, final_status, summary, degradation_notices, partial_results, actionable_error) in `src/openreview_cli/recovery/models.py`
- [X] T007b [P] Define `PrivacyTier` enum (`strict`, `standard`, `none`) in `src/openreview_cli/recovery/models.py`
- [X] T008 [P] Define `RecoveryStrategy` ABC with lifecycle methods (`initiate`, `execute`, `succeed`, `exhaust`) in `src/openreview_cli/recovery/models.py`
- [X] T009 [P] Implement `classify_error()` pure function — maps HTTP status codes, error types, and exception types to `ErrorCategory` values in `src/openreview_cli/recovery/models.py`
- [X] T010 [P] Extend `StageStatus` literal in `src/openreview_cli/pipeline/progress.py` — add `"recovering"` and `"degraded"` values
- [X] T011 [P] Add `supports_degradation()` (returns bool, default False) and `apply_degradation(action: DegradationAction)` (default no-op) methods to `Stage` ABC in `src/openreview_cli/pipeline/base.py`
- [X] T012 Write unit tests for all data models, enums, and `classify_error()` in `tests/unit/test_recovery_models.py` — covering all 6 `ErrorCategory` values, all 4 `DegradationAction` values, `RecoveryEvent`/`RecoveryContext`/`RecoveryReport` instantiation with defaults, and classification of HTTP 503/429/timeout → transient, HTTP 400/401/403/404/500 → permanent, unknown → unknown

**FR/SC mapping**: FR-01 (classification triggers auto-retry), FR-02 (classification triggers fallback), FR-03 (classification triggers degradation), FR-04 (classification triggers isolation), FR-05 (unknown→user-guided), SC-01 (correct classification drives 90% auto-recovery), SC-05 (RecoveryEvent enables visibility), SC-06 (StageIsolation depends on ErrorCategory), SC-07 (UserGuidedRecovery triggered by classification)

**Checkpoint**: `models.py` exports all 6 types, `classify_error()` returns correct `ErrorCategory` for 8+ status codes, `pipeline/progress.py` accepts `"recovering"` status, `pipeline/base.py` Stage has degradation hooks.

---

## Phase 3: User Story 1 — Auto-Retry with Backoff (Priority: P1) 🎯 MVP

**Goal**: Transient provider failures (HTTP 503, 429, timeout, connection reset) are automatically retried with exponential backoff (1s, 4s, 9s, 16s) up to 4 attempts. If a retry succeeds, pipeline continues normally. If all retries exhaust, escalation to ProviderFallbackStrategy.

**FR/SC**: FR-01 (auto-retry with backoff), SC-02 (transient failure tolerance within 30s)

**Independent Test**: Inject 2 consecutive HTTP 503 responses before a success response. Assert pipeline completes with retry count (attempts 2/4, 3/4) visible in progress output and total recovery time ≤30s from initial failure.

**Gateway contract**: `src/openreview_cli/recovery/strategies/auto_retry.py` wraps `Gateway.chat()` per `contracts/gateway-recovery-contract.md` §3

### Tests for US1

- [X] T013 [US1] Write unit tests for AutoRetryStrategy in `tests/unit/test_recovery_auto_retry.py`:
  - Backoff timing within ±20% of `base * attempt^2` for attempts 1-4
  - Exhaustion after `max_attempts` (default 4) when all fail
  - Success on attempt M < max_attempts (test M=2 and M=3)
  - Jitter randomness produces different values (±20% range)
  - RecoveryEvent recorded per attempt with correct outcome

### Implementation for US1

- [X] T014 [US1] Implement `AutoRetryStrategy` class in `src/openreview_cli/recovery/strategies/auto_retry.py`:
  - Exponential backoff formula: `base_interval_s * attempt^2 * (1 + uniform(-jitter, jitter))`
  - `execute()`: retry loop wrapping async provider call, returns on first success, raises on exhaust
  - Emits RecoveryEvent per attempt with attempt count and outcome
  - Configurable `max_attempts`, `base_interval_s`, `jitter` (defaults: 4, 1.0, 0.2)
  - Escalates to "provider_fallback" signal when exhausted

**Checkpoint**: `AutoRetryStrategy` retries N-1 times, succeeds on Nth attempt, exhausts after max_attempts. All tests pass. Progress output shows retry count per attempt.

---

## Phase 4: User Story 2 — Provider Fallback (Priority: P1)

**Goal**: When auto-retry on the primary provider exhausts, fall back to the next configured provider in the user's ordered list. When all providers exhaust, escalate to UserGuidedRecoveryStrategy. Silent cloud fallback is forbidden — if user privacy tier is "strict" (local-only) and remaining providers are cloud, stop with error.

**FR/SC**: FR-02 (provider fallback), SC-04 (no silent cloud fallback)

**Independent Test**: Configure 2 providers (primary + fallback). Permanently fail the primary. Assert the call routes to the fallback with a fallback notification in the output. When only a local provider is configured and unreachable, assert error message contains actionable suggestions without any cloud-provider call.

**Gateway contract**: `contracts/gateway-recovery-contract.md` §4 (fallback flow), §5 (provider enumeration via ModelRegistry), §6 (cost tracking)

### Tests for US2

- [X] T015 [US2] Write unit tests for ProviderFallbackStrategy in `tests/unit/test_recovery_provider_fallback.py`:
  - Fallback succeeds — primary fails, secondary succeeds, pipeline continues
  - All providers exhausted — all providers fail, escalates to UserGuidedRecovery signal
  - Privacy tier blocks cloud fallback — local-only tier, remaining providers are cloud, assert error
  - No providers configured — returns error with setup wizard suggestion
  - RecoveryEvent recorded with correct provider name and outcome

### Implementation for US2

- [X] T016 [US2] Implement `ProviderFallbackStrategy` class in `src/openreview_cli/recovery/strategies/provider_fallback.py`:
  - Iterates `RecoveryContext.provider_list` from current index
  - Before attempting cloud provider, checks `RecoveryContext.user_privacy_tier` (SC-04 guard)
  - Applies auto-retry on each fallback provider (reuses AutoRetryStrategy backoff)
  - Emits RecoveryEvent per fallback attempt with provider name and outcome
  - Escalates to "user_guided" signal when all providers exhausted
  - Reads provider list via Gateway's `get_configured_providers()` (contract §5)

**Checkpoint**: `ProviderFallbackStrategy` correctly iterates fallback list, respects privacy tier, exhausts correctly. All tests pass.

---

## Phase 5: User Story 3 — Graceful Degradation Under Memory Pressure (Priority: P2)

**Goal**: When a pipeline stage approaches the memory budget threshold (default 80% of 100 MB), the framework applies degradation measures before the stage runs: reduce batch size → switch to lightweight model → simplify processing → reduce context window. If degradation is insufficient and memory still exceeds budget, halt with a clear memory error preserving prior-stage data.

**FR/SC**: FR-03 (graceful degradation), SC-03 (memory pressure handling)

**Independent Test**: Set artificially low memory threshold (10 MB). Run a pipeline that would allocate 20 MB. Assert degradation triggers (batch size reduced or model switched), pipeline completes with degradation warning banner. When degradation is insufficient, assert pipeline halts with memory error and prior-stage data intact.

**Stage contract**: `contracts/stage-recovery-contract.md` §1 (degradation capability), §2 (degradation action contract), §5 (memory monitoring contract)

### Tests for US3

- [X] T017 [US3] Write unit tests for GracefulDegradationStrategy in `tests/unit/test_recovery_graceful_degradation.py`:
  - Threshold triggers — current memory > threshold triggers pre-stage degradation
  - Actions applied in order (batch_size → lightweight_model → simplify → context_window)
  - Stage completes within budget after degradation (mocked)
  - Exhaustion when degradation applied but budget still exceeded → halt signal
  - RecoveryEvent recorded with degradation action and outcome

### Implementation for US3

- [X] T018 [US3] Implement `GracefulDegradationStrategy` class in `src/openreview_cli/recovery/strategies/graceful_degradation.py`:
  - Pre-stage check: compare `tracemalloc.get_traced_memory()` current against `RecoveryContext.memory_threshold_bytes`
  - Applies `DegradationAction` values in least-disruptive order (contract §2)
  - Calls `stage.apply_degradation(action)` for each action
  - Emits RecoveryEvent per degradation action
  - If degradation stack exhausted and budget still exceeded → emits halt signal with memory error
  - Post-stage: Records final memory delta in context

**Checkpoint**: `GracefulDegradationStrategy` triggers at threshold, applies actions in order, exhausts when insufficient. All tests pass.

---

## Phase 6: User Story 4 — Stage Error Isolation (Priority: P2)

**Goal**: Non-critical stage failures are captured and isolated — pipeline continues with whatever data was produced before the failure. Critical stage failures (parsing) halt the pipeline with a clear error. Partial data from a failed stage is merged into shared context for downstream stages.

**FR/SC**: FR-04 (stage error isolation), SC-06 (stage failure isolation), FR-07 (user data preservation)

**Independent Test**: Inject a failure in a non-critical generation stage. Assert pipeline completes, report includes results from prior stages, and a failure notice appears. Inject a failure in a critical parsing stage. Assert pipeline halts with clear error identifying the failed stage.

**Stage contract**: `contracts/stage-recovery-contract.md` §3 (partial output contract), §4 (critical vs non-critical)

### Tests for US4

- [X] T019 [US4] Write unit tests for StageIsolationStrategy in `tests/unit/test_recovery_stage_isolation.py`:
  - Non-critical failure — pipeline continues, partial data merged into context
  - Critical failure — pipeline halts, error recorded
  - Partial data salvage — stage produced 3/10 items before failure, those 3 items available
  - Dependent stage produces results from available data
  - RecoveryEvent recorded with stage name, partial/full failure, and outcome

### Implementation for US4

- [X] T020 [US4] Implement `StageIsolationStrategy` class in `src/openreview_cli/recovery/strategies/stage_isolation.py`:
  - Checks `RecoveryContext.failed_stages` and stage `critical` flag
  - Non-critical: merges stage's partial output into `RecoveryContext.partial_data`, records error
  - Critical: emits halt signal with error identifying stage name and reason
  - Updates `RecoveryContext.failed_stages` and `RecoveryContext.completed_stages`
  - Skips dependent stages when upstream non-critical failure makes their input unavailable
  - Emits RecoveryEvent per isolated failure

**Checkpoint**: `StageIsolationStrategy` correctly distinguishes critical vs non-critical, preserves partial data, records errors. All tests pass.

---

## Phase 7: User Story 5 — User-Guided Recovery (Priority: P3)

**Goal**: When all automated strategies exhaust, produce a terminal error message with the specific failure, attempted strategies and their outcomes, and at least 2 actionable suggestions. Never a silent fallback. No generic crash message.

**FR/SC**: FR-05 (user-guided recovery), SC-07 (actionable final error messages), SC-04 (no silent cloud fallback)

**Independent Test**: Configure a single unreachable local provider (Ollama not running). Assert error message: (a) does not include any cloud-provider call, (b) includes ≥2 of "Start", "Configure", "Check", "Install" patterns or a direct CLI command, (c) lists attempted strategies and their outcomes.

### Tests for US5

- [X] T021 [US5] Write unit tests for UserGuidedRecoveryStrategy in `tests/unit/test_recovery_user_guided.py`:
  - Error message contains ≥2 actionable suggestions (test "Start", "Configure", "Check" patterns)
  - No provider configured case — error directs to `openreview gateway setup`
  - Local-only unreachable case — error suggests local-repair options, no cloud mention
  - Cloud-only unreachable case — error suggests connectivity-check options
  - Strategy-attempt log includes all previously attempted strategies

### Implementation for US5

- [X] T022 [US5] Implement `UserGuidedRecoveryStrategy` class in `src/openreview_cli/recovery/strategies/user_guided_recovery.py`:
  - Accepts `RecoveryContext.attempted_strategies` and last failure description
  - Selects suggestion templates based on error type and provider configuration:
    - Local provider unreachable → "Start Ollama: `openreview gateway start ollama`"
    - Cloud provider unreachable → "Check connectivity" + "Configure a different provider"
    - No providers → "Run `openreview gateway setup`"
    - Memory exhaustion → "Reduce document size" + "Increase memory budget in config"
    - Stage failure → "Check document format" + "Run with --verbose for details"
  - Formats terminal error with: failure description, attempted strategies table, suggestions list
  - Always terminal — never auto-recovers
  - Emits final RecoveryEvent with outcome "unrecoverable"

**Checkpoint**: `UserGuidedRecoveryStrategy` produces ≥2 suggestions, no silent cloud fallback, lists attempted strategies. All tests pass.

---

## Phase 8: RecoveryCoordinator + Pipeline Integration

**Purpose**: Wire all five strategies into a single `RecoveryCoordinator` that the pipeline runner calls pre-stage and post-stage. Connect recovery events to progress reporting. Attach `RecoveryReport` to `PipelineReport`.

**FR/SC**: FR-06 (recovery visibility), FR-07 (user data preservation), SC-01 (90% auto-recovery), SC-05 (recovery visibility)

**Pipeline contract**: `contracts/pipeline-recovery-contract.md` §1 (pre-stage/post-stage hooks), §2 (integration surface: decisions as signals), §3 (error type mapping), §4 (progress visibility)

**Depends on**: All 5 strategies implemented (Phases 3-7 complete)

### Tests for Coordinator

- [X] T023 Write unit tests for RecoveryCoordinator in `tests/unit/test_recovery_coordinator.py`:
  - Strategy selection maps each ErrorCategory to correct strategy
  - Coordinator calls correct strategy for transient, permanent, resource, stage_failure, stage_failure_critical, unknown
  - Event accumulation — RecoveryContext.events populated correctly after each strategy
  - Decision signal returned correctly (proceed, skip, degrade, continue_with_partial, retry_stage, halt)
  - Full strategy selection flow: transient → auto_retry → exhaust → provider_fallback → succeed → resolved

### Implementation for Coordinator

- [X] T024 Implement `RecoveryCoordinator` class in `src/openreview_cli/recovery/coordinator.py`:
  - `evaluate_pre_stage(stage_name, critical, memory_bytes)` → returns decision signal
  - `handle_stage_failure(stage, exception, partial_output, ctx)` → classifies error, selects strategy, returns decision
  - `handle_gateway_failure(provider_name, error_metadata, ctx)` → classifies, selects strategy, returns decision or result
  - Strategy selection logic per plan.md Appendix (transient→auto_retry→fallback, permanent→fallback→user_guided, resource→degradation, stage_failure→isolation, stage_failure_critical→user_guided, unknown→user_guided)
  - Calls each strategy's `execute()` and processes outcome (resolved→continue, exhausted→next strategy, escalated→user_guided)
  - `build_report()` → assembles RecoveryReport from RecoveryContext.events
  - Emits recovery events as ProgressEvent with status `"recovering"` or `"degraded"`

- [X] T025 Modify `PipelineReport` dataclass in `src/openreview_cli/pipeline/runner.py` — add optional `recovery_report: RecoveryReport | None = None` field

- [X] T026 Modify `Pipeline.__init__()` in `src/openreview_cli/pipeline/runner.py` — accept optional `RecoveryCoordinator` parameter; if provided, wire pre-stage and post-stage hooks

- [X] T027 Modify `Pipeline.run()` in `src/openreview_cli/pipeline/runner.py`:
  - Before each stage: call `coordinator.evaluate_pre_stage()` — if signal is "skip" or "degrade", act accordingly
  - After stage failure: catch exceptions, call `coordinator.handle_stage_failure()` — route decision signal
  - After success: update `RecoveryContext.completed_stages`
  - Final: `coordinator.build_report()` → attach to PipelineReport

**Checkpoint**: `RecoveryCoordinator` selects correct strategy per error category. `Pipeline.run()` integrates recovery hooks. PipelineReport includes RecoveryReport. All coordinator tests pass.

---

## Phase 9: Configuration Integration

**Purpose**: Add recovery configuration section to the existing config loader. Users can configure retry limits, backoff interval, memory threshold, and enabled strategies.

**FR/SC**: FR-08 (configurable recovery thresholds)

**Depends on**: Phase 2 (RecoveryContext uses config values), but config loading can be implemented in parallel with Phases 3-7.

- [X] T028 [P] Write unit tests for recovery config in `tests/unit/test_recovery_config.py`:
  - Default values (max_retries=4, base_interval_s=1.0, memory_threshold_pct=80.0, all strategies enabled)
  - Custom values override defaults correctly
  - Invalid values rejected (max_retries < 1, base_interval_s ≤ 0, memory_threshold_pct outside [10, 100])
  - Partial config merges with defaults

- [X] T029 [P] Add `recovery` section to config model in `src/openreview_cli/config/`:
  - `max_retries`: int (default 4)
  - `base_interval_s`: float (default 1.0)
  - `memory_threshold_pct`: float (default 80.0)
  - `enabled_strategies`: list[str] | None (default None = all enabled)
  - Validation: `max_retries` ≥ 1, `base_interval_s` > 0, `memory_threshold_pct` in [10.0, 100.0]

- [X] T030 Wire recovery config into `RecoveryCoordinator.__init__()` so coordinator reads thresholds from config

**Checkpoint**: Config loader accepts recovery section with defaults and custom values. Invalid values raise validation errors. Coordinator reads thresholds from config.

---

## Phase 10: Integration Tests

**Purpose**: End-to-end tests that verify the full recovery framework integrates with the pipeline runner and AI Gateway.

**FR/SC**: SC-01 (90% auto-recovery rate), SC-02 (transient failure tolerance), SC-03 (memory pressure handling), SC-04 (no silent cloud fallback), SC-05 (recovery visibility), SC-06 (stage failure isolation), SC-07 (actionable final error messages)

- [X] T031 Write integration tests in `tests/integration/test_pipeline_with_recovery.py`:
  - **Transient recovery** — mock Gateway to return 503 then success. Assert pipeline completes, progress output shows retry counts, total recovery time ≤30s
  - **Fallback recovery** — mock two providers, primary returns 500 permanently, fallback succeeds. Assert fallback notification in output
  - **Memory degradation** — set low threshold, mock stage with memory-heavy allocation. Assert degradation triggers, pipeline completes with warning
  - **Stage isolation** — inject non-critical stage error. Assert pipeline produces partial results, failure notice in report
  - **User-guided terminal error** — configure single unreachable provider. Assert error message with ≥2 suggestions
  - **No silent cloud fallback** — configure local-only provider, make it unreachable. Assert error has local-repair options, no cloud call
  - **SC-01 verification** — inject 10 representative failure scenarios (transient, permanent, resource, stage_failure mix), assert ≥9 resolve without user intervention (90% pass threshold)

- [X] T032 Final validation — run full test suite (`pytest tests/unit/ tests/integration/`), run `ruff check`, `mypy src/ tests/` on recovery-related files. All pass.

**Checkpoint**: All integration tests pass. Recovery framework end-to-end verified against all 7 success criteria.

---

## Dependencies & Execution Order

### Phase Dependencies

| Phase | Depends On | Blocks |
|-------|-----------|--------|
| Phase 1 (Setup) | None | Phase 2 |
| Phase 2 (Foundational) | Phase 1 | Phases 3-7 |
| Phase 3 (US1 - Auto-Retry) | Phase 2 | Phase 8 |
| Phase 4 (US2 - Fallback) | Phase 2 | Phase 8 |
| Phase 5 (US3 - Degradation) | Phase 2 | Phase 8 |
| Phase 6 (US4 - Isolation) | Phase 2 | Phase 8 |
| Phase 7 (US5 - User-Guided) | Phase 2 | Phase 8 |
| Phase 8 (Coordinator) | Phases 3-7 | Phase 10 |
| Phase 9 (Config) | Phase 2 | Phase 10 |
| Phase 10 (Integration) | Phases 8, 9 | — |

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2. No dependency on other stories.
- **US2 (P1)**: Can start after Phase 2. Independent of US1 (different strategy, different file).
- **US3 (P2)**: Can start after Phase 2. Independent of US1, US2, US4, US5.
- **US4 (P2)**: Can start after Phase 2. Independent of US1, US2, US3, US5.
- **US5 (P3)**: Can start after Phase 2. Independent of US1-US4.
- **Coordinator (Phase 8)**: Depends on ALL US1-US5.

### Within Each Phase

- Test tasks written first (TDD per plan.md gate)
- Models before services
- Core implementation before integration
- Phase complete before moving to next

---

## Parallel Opportunities

- **Phase 2**: T003-T011 all [P] — 9 tasks on different files, no dependencies between them
- **Phases 3-7**: Can run in parallel — 5 teams could implement 5 strategies simultaneously
- **Phase 9** (Config): Can run in parallel with Phases 3-7 (no dependency on strategy implementations)
- **Within each US phase**: Test task and implementation task are sequential (test first, then implement)

### Parallel Example: US1 + US2 + US3 (3 teams)

```bash
# Team A: US1 Auto-Retry
Task: T013 [US1] Write unit tests for AutoRetryStrategy
Task: T014 [US1] Implement AutoRetryStrategy

# Team B: US2 Provider Fallback
Task: T015 [US2] Write unit tests for ProviderFallbackStrategy
Task: T016 [US2] Implement ProviderFallbackStrategy

# Team C: US3 Graceful Degradation
Task: T017 [US3] Write unit tests for GracefulDegradationStrategy
Task: T018 [US3] Implement GracefulDegradationStrategy
```

---

## Implementation Strategy

### MVP First (US1 + US2 — both P1)

1. Complete Phase 1: Setup → `recovery/` package
2. Complete Phase 2: Foundational → models, classification, pipeline extensions
3. Complete Phase 3: US1 Auto-Retry (P1) → auto-retry works end-to-end
4. Complete Phase 4: US2 Provider Fallback (P1) → provider fallback works end-to-end
5. **MVP STOP**: Auto-retry + provider fallback cover the 2 most common failure modes (P1)
   - Deploy/demo: `openreview precheck review nda.pdf` recovers from transient failures
   - Integration test: inject 503 → retry succeeds; inject 500 → fallback

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 + US2 → Auto-recovery for P1 failures (MVP)
3. US3 (Graceful Degradation, P2) → Memory pressure handling
4. US4 (Stage Isolation, P2) → Partial results from stage failures
5. US5 (User-Guided Recovery, P3) → Clear terminal errors
6. Coordinator + Pipeline Integration → All strategies wired together
7. Config → User-tunable thresholds
8. Integration tests → Full verification against SC-01 through SC-07

### Parallel Team Strategy

With multiple developers:
1. Team completes Phase 1 + Phase 2 together
2. Once Phase 2 done:
   - Developer A: US1 (Auto-Retry)
   - Developer B: US2 (Provider Fallback)
   - Developer C: US3 (Graceful Degradation)
   - Developer D: US4 (Stage Isolation) + US5 (User-Guided)
   - Developer E: Phase 9 (Config) — parallel with strategies
3. All converge on Phase 8 (Coordinator) + Phase 10 (Integration)

---

## Summary

| Metric | Count |
|--------|-------|
| Total tasks | 32 |
| Phase 1 (Setup) | 2 |
| Phase 2 (Foundational) | 10 |
| Phase 3 (US1 - Auto-Retry) | 2 |
| Phase 4 (US2 - Provider Fallback) | 2 |
| Phase 5 (US3 - Graceful Degradation) | 2 |
| Phase 6 (US4 - Stage Isolation) | 2 |
| Phase 7 (US5 - User-Guided Recovery) | 2 |
| Phase 8 (Coordinator + Pipeline) | 5 |
| Phase 9 (Config) | 3 |
| Phase 10 (Integration) | 2 |
| User stories | 5 |
| [P] parallelizable tasks | 12 |
| MVP scope | Phases 1-4 (US1 + US2, both P1) |

---

## Phase 11: Convergence

**Purpose**: Close remaining gaps identified by converge assessment (spec 019).

- [X] T033 Add `"recovering"` and `"degraded"` to `StageStatus` literal in `src/openreview_cli/pipeline/progress.py`; wire coordinator to emit progress events with these statuses per FR-06 and SC-05 (partial)
- [X] T034 Add `supports_degradation()` (returns bool, default False) and `apply_degradation(action: str)` (default no-op) to `Stage` ABC in `src/openreview_cli/pipeline/base.py` per T011 and FR-03 (partial)
- [X] T035 Add `RecoveryConfig` dataclass to `src/openreview_cli/config/` with fields `max_retries`, `base_interval_s`, `memory_threshold_pct`, `enabled_strategies`; wire into `RecoveryCoordinator.__init__()`; update test to import from production module per FR-08 (partial)
- [X] T036 Add `saved_results: dict[str, Any] | None = None` field to `RecoveryContext` in `src/openreview_cli/recovery/models.py`; populate from pipeline runner post-stage; add assertions to integration test per FR-07 and data-model.md (partial)
- [X] T037 Add test that confirms `RecoveryContext` state is discarded after pipeline completes — assert no external state file or residual data per spec §5 non-goals (missing)
- [X] T038 Optional: Migrate `RecoveryEvent.outcome` from `str` to a `StrEnum` for type safety per analyze-report D2 (partial)
