# Pipeline-Recovery Contract

**Date**: 2026-07-05 | **Spec Reference**: spec.md §4 FR-04, FR-06, SC-06

---

## 1. Recovery wraps Pipeline stage execution

The recovery framework does not reimplement the pipeline runner. Instead, it wraps `Pipeline.run()` and `Pipeline._execute_single_stage()` at two levels:

### Level 1 — Pre-stage hook (before each stage runs)

The recovery coordinator checks `RecoveryContext` before each stage:
- If a previous stage failed non-critically and `StageIsolationStrategy` is active, skip remaining stages that depend on the failed stage's output.
- If memory pressure exceeds threshold, invoke `GracefulDegradationStrategy` before the stage starts.
- Completed-stage data from prior runs is available in `RecoveryContext.saved_results` — downstream stages read from this instead of re-running already-finished work. (FR-07: data preservation.)

Contract: Recovery coordinator recieves the stage name and `stage.critical` flag. Returns an action signal: `"proceed"`, `"skip"`, `"degrade"`, or `"halt"`.

### Level 2 — Post-stage error interceptor (when stage raises)

When a stage raises a `StageError` (non-critical) or other exception:
1. Recovery coordinator classifies the error via `ErrorClassification`.
2. Selects and executes the appropriate strategy.
3. Returns a decision: `"continue_with_partial"`, `"retry_stage"`, or `"halt"`.

For `"continue_with_partial"`: the recovery coordinator returns whatever partial output the stage produced before failing (if any) to be merged into shared context. The stage's error is recorded in `PipelineReport.stage_results` and in `RecoveryReport`.

---

## 2. Integration surface

### Inputs (from Pipeline → Recovery)

| Data | Source | When |
|------|--------|------|
| Stage name + critical flag | Pipeline._execute_single_stage | Before each stage |
| Current tracemalloc snapshot | Pipeline memory tracking | Before each stage |
| Stage exception (if any) | Pipeline catch block | After stage failure |
| Stage partial output | Stage.run() return value | After stage failure |
| Pipeline context | Pipeline.run() | Throughout |
| Completed-stage outputs | RecoveryContext.saved_results | After each stage success |

### Outputs (from Recovery → Pipeline)

| Decision | Meaning | Effect |
|----------|---------|--------|
| `"proceed"` | No recovery needed | Run stage normally |
| `"degrade"` | Apply degradation before stage | DegradationAction is set in context |
| `"skip"` | Skip this stage entirely | StageResult(skipped=True) |
| `"continue_with_partial"` | Use available data, continue | Merge partial output, record error |
| `"retry_stage"` | Re-run the stage | Pipeline re-invokes stage.run() |
| `"halt"` | Stop pipeline with error | Pipeline raises RecoveryHaltError with RecoveryReport |

---

## 3. Error type mapping

The existing pipeline error hierarchy is:

| Error | Existing Behavior | Recovery Intercept |
|-------|-------------------|--------------------|
| `StageError` | Caught, recorded, pipeline continues | StageIsolationStrategy evaluates partial data |
| `CriticalStageError` | Pipeline halts with report | UserGuidedRecoveryStrategy formats final error |
| `MemoryBudgetError` | Raised immediately | GracefulDegradationStrategy runs before quota check |
| Generic `Exception` | Caught as StageError | ErrorClassification decides transient vs permanent |

---

## 4. Progress visibility

Recovery events are emitted as `ProgressEvent` with status `"recovering"` or `"degraded"`. The pipeline's existing `progress_callback` forwards these to the CLI display. No new event channel needed.

(SC-05: every recovery action visible in progress output.)
