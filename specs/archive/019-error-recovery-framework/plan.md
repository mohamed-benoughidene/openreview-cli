# Implementation Plan — Error Recovery Framework

**Feature ID**: 019-error-recovery-framework
**Date**: 2026-07-05
**Spec**: [spec.md](./spec.md)
**Previous**: clarifications.md (no changes needed)

---

## Technical Context

### What exists today

- **Pipeline runner** (`src/openreview_cli/pipeline/runner.py`): Sequential stage execution with `Stage.critical` flag, `StageResult` per stage, `PipelineReport` final output. Progress events emitted via callback. Memory tracking via `tracemalloc` snapshots (pre/post per stage). Catches `StageError` (non-critical, continue) and `CriticalStageError` (halt).
- **Stage ABC** (`src/openreview_cli/pipeline/base.py`): `Stage.name`, `Stage.critical`, `Stage.run()`, `Stage.cleanup()`. No degradation support yet.
- **Error hierarchy** (`src/openreview_cli/pipeline/errors.py`): `PipelineError` → `StageError` → `CriticalStageError`; `MemoryBudgetError`.
- **Progress events** (`src/openreview_cli/pipeline/progress.py`): `ProgressEvent` with status `running|completed|failed|skipped`. No recovering/degraded status yet.
- **AI Gateway** (`src/openreview_cli/gateway/`): `Gateway.chat()/embed()/rerank()`, `ModelRegistry`, cost tracking. No retry or fallback wrapping at call level today.
- **Review pipeline** (spec-011): 3-agent (extraction→QA→report). Runs on top of the 5-stage pipeline runner.

### What needs to be built

A thin recovery coordinator that sits between the pipeline runner and the stage/gateway boundaries. It adds:

1. `RecoveryCoordinator` — intercepts failures, classifies them, selects/applies strategies
2. Five concrete strategy classes (see data-model.md)
3. Progress event extensions for recovery visibility
4. Gateway call wrapper with retry + fallback
5. Config section for recovery thresholds
6. RecoveryReport attached to PipelineReport at output

### Key unknowns (all resolved by spec/clarifications)

- **Strategy selection order**: Auto-retry first, then fallback, then degradation, then isolation, then user-guided. (Spec scenarios 1→2→3→4→5.)
- **Memory monitoring**: Stage-boundary check, not continuous. (Spec §7 Assumptions.)
- **Provider list source**: User config, ordered by preference. Gateway `ModelRegistry`. (Spec FR-02.)
- **Fallback privacy guard**: Check privacy tier before cloud fallback. (Spec FR-05, SC-04.)
- **Recovery state lifetime**: Single pipeline invocation only. (Spec §5 Non-Goals.)

---

## Constitution Check

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Privacy First** | Pass | Recovery events log only strategy names, error codes, provider names — never PII or contract text. Fallback privacy guard prevents silent cloud fallback (SC-04). |
| **II. Local-First, CLI-Only** | Pass | All recovery logic runs locally in-process. No server, no daemon, no telemetry. Framework works fully offline when all provider slots are local. |
| **III. Hardware-Bounded** | Pass | Graceful degradation reduces resource use under pressure. Memory monitoring reuses existing tracemalloc — no additional overhead. Peak budget unaffected: recovery coordinator is a thin decision layer (~KB memory). |
| **IV. Dependency Minimalism** | Pass | Zero new runtime dependencies. All strategies use stdlib (`asyncio`, `time`, `dataclasses`, `enum`, `logging`) or already-installed packages (pipeline internals, gateway types). |
| **V. Spec-Driven, YAGNI** | Pass | Every strategy maps to a spec FR. No speculative abstractions. Five strategies, no more. No interface for one implementation — each strategy is a concrete class. |

---

## Gates

| Gate | Status | Notes |
|------|--------|-------|
| Spec complete | ✅ Pass | clarifications.md confirms zero changes needed |
| No NEEDS CLARIFICATION | ✅ Pass | All 8 FRs, 7 SCs clear |
| No forbidden deps proposed | ✅ Pass | Zero new deps |
| Constitution compliance | ✅ Pass | All 5 principles pass |
| Memory budget respected | ✅ Pass | Existing tracemalloc reused; coordinator is thin |
| TDD compatible | ✅ Pass | Each phase writes failing test before implementation |

---

## Implementation Phases

### Phase 1 — Core Data Models + ErrorClassification

**Goal**: Define all data model types in a new module `src/openreview_cli/recovery/models.py`.

**Files to create**:
- `src/openreview_cli/recovery/__init__.py` — public exports
- `src/openreview_cli/recovery/models.py` — ErrorCategory enum, RecoveryStrategy ABC, RecoveryContext dataclass, RecoveryEvent dataclass, RecoveryReport dataclass, DegradationAction enum

**Tests** (written first per TDD):
- `tests/unit/test_recovery_models.py` — dataclass instantiation, enum values, default field assertions, error classification pure function tests

**SC mapping**: SC-01 (classification drives recovery rate)

---

### Phase 2 — AutoRetryStrategy

**Goal**: Implement retry loop with exponential backoff in `src/openreview_cli/recovery/strategies/auto_retry.py`.

**Files to create**:
- `src/openreview_cli/recovery/strategies/__init__.py`
- `src/openreview_cli/recovery/strategies/auto_retry.py` — backoff formula, retry loop, jitter, attempt counting

**Tests**:
- `tests/unit/test_recovery_auto_retry.py` — backoff timing (±20%), exhaustion after N attempts, success on attempt M < N, jitter randomness

**SC mapping**: SC-02 (transient failure tolerance, 30 s window)

---

### Phase 3 — ProviderFallbackStrategy

**Goal**: Implement fallback to next configured provider after retry exhaustion.

**Files to create**:
- `src/openreview_cli/recovery/strategies/provider_fallback.py` — provider list iteration, privacy tier guard, fallback retry

**Tests**:
- `tests/unit/test_recovery_provider_fallback.py` — fallback succeeds, all providers exhausted, privacy tier blocks cloud fallback, no providers configured case

**SC mapping**: SC-04 (no silent cloud fallback)

---

### Phase 4 — GracefulDegradationStrategy

**Goal**: Implement memory-pressure degradation that triggers before stage execution.

**Files to create**:
- `src/openreview_cli/recovery/strategies/graceful_degradation.py` — memory threshold check, degradation action ordering (batch size → model → simplify → context)

**Modifications**:
- `src/openreview_cli/pipeline/base.py` — add `supports_degradation()` and `apply_degradation()` to `Stage` ABC (optional methods with default no-op)
- `src/openreview_cli/pipeline/progress.py` — add `"recovering"` and `"degraded"` to `StageStatus` literal

**Tests**:
- `tests/unit/test_recovery_graceful_degradation.py` — threshold triggers, actions applied in order, stage completes under budget, exhaustion when degradation insufficient

**SC mapping**: SC-03 (memory pressure handling)

---

### Phase 5 — StageIsolationStrategy

**Goal**: Capture non-critical stage failures and continue with partial data.

**Files to create**:
- `src/openreview_cli/recovery/strategies/stage_isolation.py` — partial data salvage, critical vs non-critical dispatch, dependent stage skip logic

**Tests**:
- `tests/unit/test_recovery_stage_isolation.py` — non-critical failure continues, critical failure halts, partial data merged, dependent stage produces available results

**SC mapping**: SC-06 (stage failure isolation)

---

### Phase 6 — UserGuidedRecoveryStrategy

**Goal**: Format terminal error with actionable suggestions when all strategies exhausted.

**Files to create**:
- `src/openreview_cli/recovery/strategies/user_guided_recovery.py` — suggestion templates keyed to error type, strategy-attempt log formatting

**Tests**:
- `tests/unit/test_recovery_user_guided.py` — ≥2 suggestions present, no provider configured case, local-only unreachable case, cloud-only unreachable case

**SC mapping**: SC-07 (actionable final error messages)

---

### Phase 7 — RecoveryCoordinator

**Goal**: Wire all strategies into a single coordinator that the pipeline runner calls.

**Files to create**:
- `src/openreview_cli/recovery/coordinator.py` — strategy selection, execution, event recording, RecoveryReport assembly

**Integration**:
- Modify `Pipeline.run()` in `src/openreview_cli/pipeline/runner.py` to call coordinator pre/post each stage.
- Add `RecoveryReport` to `PipelineReport` dataclass.
- Modify `Pipeline.__init__()` to accept optional `RecoveryConfig`.

**Tests**:
- `tests/unit/test_recovery_coordinator.py` — full strategy selection flow, coordinator calls correct strategy for each ErrorCategory, event accumulation
- `tests/integration/test_pipeline_with_recovery.py` — end-to-end: inject transient failure, assert retry; inject memory pressure, assert degradation

**SC mapping**: SC-01 (90% auto-recovery rate verification)

---

### Phase 8 — Configuration Integration

**Goal**: Add recovery config section to existing config loading.

**Files to modify**:
- `src/openreview_cli/config/` — add `recovery` section with `max_retries`, `base_interval_s`, `memory_threshold_pct`, `enabled_strategies`

**Tests**:
- `tests/unit/test_recovery_config.py` — default values, custom values, validation of invalid values

**SC mapping**: FR-08 (configurable thresholds)

---

## File Map

```
src/openreview_cli/recovery/
├── __init__.py                  # Public API exports
├── models.py                    # ErrorCategory, RecoveryContext, RecoveryEvent,
│                                # RecoveryReport, DegradationAction, RecoveryStrategy ABC
├── coordinator.py               # RecoveryCoordinator — orchestrates strategy selection
└── strategies/
    ├── __init__.py              # Strategy exports
    ├── auto_retry.py            # AutoRetryStrategy — FR-01
    ├── provider_fallback.py     # ProviderFallbackStrategy — FR-02
    ├── graceful_degradation.py  # GracefulDegradationStrategy — FR-03
    ├── stage_isolation.py       # StageIsolationStrategy — FR-04
    └── user_guided_recovery.py  # UserGuidedRecoveryStrategy — FR-05

Modified files:
  src/openreview_cli/pipeline/base.py     # Add supports_degradation(), apply_degradation()
  src/openreview_cli/pipeline/progress.py # Extend StageStatus literal
  src/openreview_cli/pipeline/runner.py   # Wire RecoveryCoordinator, add RecoveryReport to PipelineReport
  src/openreview_cli/pipeline/errors.py   # Add RecoveryHaltError (optional)
  src/openreview_cli/config/              # Add recovery section

Tests:
  tests/unit/test_recovery_models.py
  tests/unit/test_recovery_auto_retry.py
  tests/unit/test_recovery_provider_fallback.py
  tests/unit/test_recovery_graceful_degradation.py
  tests/unit/test_recovery_stage_isolation.py
  tests/unit/test_recovery_user_guided.py
  tests/unit/test_recovery_coordinator.py
  tests/unit/test_recovery_config.py
  tests/integration/test_pipeline_with_recovery.py
```

---

## Appendix: Strategy Selection Logic

```text
failure occurs
  → classify error
  → if transient:
      → AutoRetryStrategy
        → if succeed: resolved
        → if exhaust: → ProviderFallbackStrategy
  → if permanent:
      → ProviderFallbackStrategy
        → if succeed: resolved
        → if exhaust: → UserGuidedRecoveryStrategy
  → if resource:
      → GracefulDegradationStrategy
        → if succeed: degraded (continue with banner)
        → if exhaust: halt with memory error
  → if stage_failure (non-critical):
      → StageIsolationStrategy
        → continue with partial data
  → if stage_failure_critical:
      → halt
      → UserGuidedRecoveryStrategy (terminal error)
  → if unknown:
      → UserGuidedRecoveryStrategy (terminal error)
```
