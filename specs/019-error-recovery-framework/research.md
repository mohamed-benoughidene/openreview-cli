# Research Notes — Error Recovery Framework

**Date**: 2026-07-05 | **Spec Reference**: [spec.md](../spec.md)

---

## 1. Exponential Backoff Patterns in Python Asyncio

### Decision
Use `asyncio.sleep()` with computed backoff interval inside a retry loop wrapping the provider call. Base interval 1 s, multiplier squared (1, 4, 9, 16, 25 s for attempts 1–5). Jitter (random offset ±20%) to avoid thundering-herd when multiple calls retry simultaneously.

### Rationale
- The spec (FR-01) defines exponential backoff with configurable base interval and max attempts.
- `asyncio.sleep` is non-blocking — the event loop continues processing other tasks during the wait (SC-02: 30 s recovery window).
- Squared multiplier keeps early retries fast and later ones sparse without requiring a separate jitter library.
- Stdlib only — no new dependencies (constitution §IV, Dependency Minimalism).

### Alternatives Considered
- **tenacity library**: Full-featured retry library. Rejected because it adds a dependency for what a 5-line loop does. Spec forbids unnecessary dependencies.
- **stamina library**: Thin wrapper over tenacity. Same rejection reason.
- **Fixed-interval retry**: Simpler but violates FR-01 which specifies exponential backoff.

---

## 2. Memory Monitoring at Stage Boundaries

### Decision
Reuse the existing `tracemalloc` snapshot mechanism already in `Pipeline._execute_single_stage()`. Add a pre-stage memory check: if current allocated bytes exceeds `budget * threshold_ratio` (default 80% of 100 MB), emit a degradation signal before the stage runs.

### Rationale
- The existing runner already takes pre/post snapshots for each stage (runner.py lines 193, 213).
- A pre-stage check adds zero additional overhead — just compare `tracemalloc.get_traced_memory()` current value against threshold.
- Stage-boundary monitoring is acceptable per spec §7 Assumptions: "Memory pressure is monitored at stage boundaries, not continuously."
- Continuous monitoring would add complexity and overhead for minimal benefit on a CLI tool (SC-03: memory pressure handling).

### Alternatives Considered
- **psutil for RSS monitoring**: Would work but adds a dependency. tracemalloc is already wired and gives us per-stage deltas.
- **Continuous monitoring thread**: Overkill for a CLI with <100 MB budget. The spec explicitly permits stage-boundary checks.

---

## 3. Provider Fallback Pattern

### Decision
After retry exhaustion on primary provider, iterate the user's provider list (ordered by preference) and attempt each sequentially. If the fallback provider also fails, retry it with the same backoff schedule before trying the next. If all providers exhausted, escalate to UserGuidedRecovery.

### Rationale
- FR-02 requires sequential fallback in user-specified order. No parallel execution (per spec §5 Non-Goals).
- SC-04 mandates no silent cloud fallback — framework must check if remaining providers violate the user's privacy tier before attempting.
- Reusing the existing Gateway registry (spec-005 `ModelRegistry`) for provider enumeration avoids duplicating provider state.
- Fallback notification must appear in progress output per FR-06 and SC-05.

### Alternatives Considered
- **Parallel fallback**: Call all remaining providers simultaneously, use first to respond. Rejected — spec §5 explicitly excludes dual-path/parallel execution.
- **Hardcoded fallback order**: Rejected — FR-08 requires user-configurable provider order.

---

## 4. Stage Error Isolation Pattern

### Decision
Wrap each `stage.run()` call in a try/except that catches non-critical stage failures, records the error in `RecoveryContext`, and returns empty results rather than propagating the exception. Critical stages (`Stage.critical = True`) still propagate per the existing pipeline behavior.

### Rationale
- FR-04 distinguishes critical vs. non-critical stages. The Stage ABC already has a `critical` attribute (base.py line 47).
- The existing `Pipeline._execute_single_stage()` already catches `StageError` and `CriticalStageError` separately. The recovery framework wraps this at a higher level — before the pipeline catches it, the recovery coordinator decides whether isolation is possible.
- For critical stage failure, stop pipeline with clear error (SC-06).
- For non-critical failure, provide partial results (SC-06).
- Stage output keys already track which data is available for later stages.

### Alternatives Considered
- **Skip stage entirely on failure**: Simpler but loses partial data. Spec requires partial results when possible.
- **Rerun the failed stage**: May work for transient failures, but spec explicitly excludes retrying document-parsing failures ($5 Non-Goals).

---

## 5. User-Guided Recovery Pattern

### Decision
When all automated strategies exhausted, produce a structured error containing: (a) failure description, (b) strategy attempt log, (c) 2+ actionable suggestions. Suggestions are template-based, keyed to error type (provider down → start/configure/check connectivity; memory exceeded → reduce document size/free RAM; no provider configured → run setup wizard).

### Rationale
- FR-05 and SC-07 require actionable final error messages with ≥2 suggestions.
- Template-based messages ensure consistency and testability (SC-07 verification: test asserts ≥2 expected patterns).
- Never silent fallback (SC-04) — the error explicitly says what was attempted and what the user should do.
- No PII in error messages per spec Edge Cases.

### Alternatives Considered
- **LLM-generated suggestions**: Over-engineered for a CLI error message. Template + variable interpolation is sufficient and testable.
- **Generic "try again later"**: Rejected by SC-07.

---

## 6. Recovery Visibility via Progress Events

### Decision
Add recovery-specific status values to the existing `ProgressEvent` model: extend `StageStatus` type to include `"recovering"` and `"degraded"`. Each recovery action emits a `ProgressEvent` with `message` describing what happened (e.g., "Retrying provider call (attempt 2/5)...").

### Rationale
- FR-06 and SC-05 require recovery actions visible in pipeline progress output.
- The existing `ProgressCallback` mechanism already streams events to the CLI display.
- Adding status values is backward-compatible: existing consumers see `"recovering"` as unrecognized but still render the message field.
- No need for a separate recovery channel — reuse the established progress pipeline.

### Alternatives Considered
- **Separate recovery callback**: Adds complexity for no benefit when the existing callback already works.
- **Stdout logging**: Would mix with progress display and be harder to test.

---

## 7. Configuration Schema for Recovery Thresholds

### Decision
Add a `recovery` section to the existing config schema (likely YAML/TOML in the config loader). Keys: `max_retries` (int, default 5), `base_interval_s` (float, default 1.0), `memory_threshold_pct` (float, default 80.0), `enabled_strategies` (list of strategy names, default all). Validate at load time.

### Rationale
- FR-08 requires configurable recovery thresholds.
- Using existing config loader avoids a new configuration mechanism.
- Defaults match spec acceptance scenarios (retry 5 times, 1 s base, 80% memory threshold).
- Validation at load time prevents runtime misconfiguration (SC-03).

### Alternatives Considered
- **Env vars only**: Less discoverable than config file. Config file is the established pattern.
- **CLI flags only**: Would clutter every command. Config file is appropriate for operational parameters.

---

## 8. No Persistent Recovery State

### Decision
RecoveryContext lives only for the duration of a single pipeline invocation. No recovery state written to disk. If the CLI restarts, recovery starts fresh.

### Rationale
- Explicitly specified in §5 Non-Goals: "No persistent recovery state across CLI invocations."
- Avoids complex serialization/deserialization of recovery state.
- Avoids potential privacy leak from recovery logs (constitution §I).

### Alternatives Considered
- **SQLite recovery log**: Spec says no. Avoids complexity.
- **JSON state file**: Spec says no. Avoids stale state issues.

---

## 9. Dependency Verdict

| Item | Source | Status |
|------|--------|--------|
| Python 3.12 asyncio | CPython docs | CONFIRMED — built-in |
| tracemalloc | CPython docs | CONFIRMED — already used in pipeline |
| AI Gateway registry | spec-005 / code | CONFIRMED — exists at `src/openreview_cli/gateway/registry.py` |
| Pipeline runner | spec-018 / code | CONFIRMED — exists at `src/openreview_cli/pipeline/runner.py` |
| httpx (HTTP calls to providers) | LiteLLM integration | CONFIRMED — existing dep |

No new external dependencies required for the recovery framework. All strategies use stdlib or already-installed packages.
