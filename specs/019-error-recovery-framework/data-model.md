# Data Model — Error Recovery Framework

**Date**: 2026-07-05 | **Spec Reference**: [spec.md](../spec.md) §8, spec.md §6 for SC mappings

---

## Entity Overview

The recovery framework defines six core entities. Every entity maps to one or more spec functional requirements and success criteria.

| Entity | Source | Key SC |
|--------|--------|--------|
| `ErrorCategory` | spec §8 ErrorClassification | SC-01, SC-02 |
| `RecoveryContext` | spec §8 RecoveryContext | SC-05 |
| `RecoveryStrategy` | spec §8 RecoveryStrategy | SC-01–SC-07 |
| `RecoveryEvent` | derived from RecoveryReport | SC-05 |
| `RecoveryReport` | spec §8 RecoveryReport | SC-05, SC-06, SC-07 |
| `DegradationAction` | spec FR-03 | SC-03 |
| `PrivacyTier` | spec SC-04 | SC-04 |

---

## ErrorCategory

Describes the nature of a failure. Determines which recovery strategy applies.

**Values** (enum):

| Value | Trigger | Strategy |
|-------|---------|----------|
| `transient` | HTTP 503, 429, timeout, connection reset | Auto-retry (FR-01) |
| `permanent` | HTTP 400, 401, 403, 404, 500 | Provider fallback (FR-02) |
| `resource` | Memory over threshold, CPU budget exceeded | Graceful degradation (FR-03) |
| `stage_failure` | Non-critical stage exception | Stage isolation (FR-04) |
| `stage_failure_critical` | Critical stage exception | Halt + user-guided recovery (FR-05) |
| `unknown` | Unrecognized error type | User-guided recovery (FR-05) |

**Validation**: Classification is pure function of error metadata (HTTP status, exception type, memory delta). No mutable state involved. (SC-01: correct classification drives 90% auto-recovery target.)

---

## RecoveryContext

Per-pipeline-invocation state bag. Carries cumulative recovery state between strategy evaluations.

**Fields**:

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `provider_list` | `list[str]` | user-configured | Ordered provider names for fallback (FR-02) |
| `attempted_strategies` | `list[str]` | `[]` | Names of strategies already applied (SC-05) |
| `current_provider_index` | `int` | `0` | Index into provider_list for fallback ordering |
| `retry_counts` | `dict[str, int]` | `{}` | Per-provider retry attempt counts (FR-01) |
| `memory_threshold_bytes` | `int` | 80% of budget | Bytes at which degradation triggers (FR-03, FR-08) |
| `memory_budget_bytes` | `int` | 100 MB | Hard budget from constitution §III |
| `failed_stages` | `list[str]` | `[]` | Names of stages that failed (FR-04) |
| `completed_stages` | `list[str]` | `[]` | Names of stages that completed (FR-04) |
| `partial_data` | `dict[str, Any]` | `{}` | Available data from partially-failed stages (FR-04) |
| `saved_results` | `dict[str, Any] | None` | `None` | Completed-stage outputs preserved before failure, keyed by stage name (FR-07) |
| `events` | `list` | `[]` | Accumulated RecoveryEvent list |
| `user_privacy_tier` | `PrivacyTier` | `"strict"` | Controls cloud fallback allowance (SC-04) |

**Lifecycle**: Created at pipeline start. Passed between strategy evaluations. Discarded after pipeline finishes. (Per spec §5: no persistence across invocations.)

---

## RecoveryStrategy

Base representation of one of the five recovery approaches. Each strategy implements a common lifecycle.

**Lifecycle states**: `initiate → [execute → succeed|exhaust]`

**Five concrete strategies**:

### AutoRetryStrategy (FR-01)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `max_attempts` | `int` | 4 | Per-provider retry limit (FR-08). 4 retries × 1.0s base = 30s max wall time, within SC-02 budget. |
| `base_interval_s` | `float` | 1.0 | Backoff base in seconds (FR-08) |
| `jitter` | `float` | 0.2 | ±jitter ratio to avoid thundering-herd |
| `provider_name` | `str` | — | Which provider is being retried |

**Backoff formula**: `base_interval_s * attempt^2 * (1 + uniform(-jitter, jitter))`

**Succeeds when**: Provider responds with success within max_attempts.
**Exhausted when**: All attempts fail → escalate to ProviderFallback.

### ProviderFallbackStrategy (FR-02)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `provider_list` | `list[str]` | — | Remaining untried providers |
| `current_index` | `int` | 0 | Current position in fallback list |
| `privacy_tier` | `PrivacyTier` | — | Prevents cloud fallback when local-only |

**Succeeds when**: A fallback provider responds successfully.
**Exhausted when**: All providers attempted → escalate to UserGuidedRecovery.

**Privacy guard**: Before attempting a cloud provider, check `privacy_tier`. If tier is `"strict"` (local-only) and fallback provider is cloud, stop and report error. (SC-04: no silent cloud fallback.)

### GracefulDegradationStrategy (FR-03)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `memory_threshold_bytes` | `int` | 80% of budget | Trigger threshold |
| `degradation_actions` | `list` | — | Actions to apply (see DegradationAction) |
| `active` | `bool` | `False` | Whether degradation is currently applied |
| `action_index` | `int` | `0` | Current degradation level |

**Triggers**: Pre-stage tracemalloc check shows current > threshold.
**Succeeds when**: Stage completes within budget after degradation.
**Exhausted when**: Degradation applied but memory still exceeds budget → stop with memory error.

### StageIsolationStrategy (FR-04)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `failed_stages` | `list[str]` | `[]` | Stages marked as failed |
| `partial_data` | `dict` | `{}` | Data salvaged from partial stage output |

**Triggers**: Stage raises non-critical exception.
**Succeeds when**: Pipeline continues with available data, completes with partial results.
**Exhausted when**: Critical stage failure → halt pipeline, escalate to UserGuidedRecovery.

### UserGuidedRecoveryStrategy (FR-05)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `failure_description` | `str` | — | What went wrong |
| `attempted_strategies` | `list` | — | What was tried |
| `suggestions` | `list[str]` | — | 2+ actionable suggestions |

**Always terminal**: This strategy never auto-recovers. It produces the final user-facing error message. (SC-07: ≥2 actionable suggestions.)

---

## RecoveryEvent

Record of a single recovery action taken during pipeline execution.

**Fields**:

| Field | Type | Purpose |
|-------|------|---------|
| `strategy_name` | `str` | Which strategy ran |
| `stage_name` | `str` | Stage where failure occurred |
| `provider_name` | `str | None` | Provider involved (if provider call) |
| `attempt` | `int | None` | Attempt number (for retries) |
| `outcome` | `str` | `"resolved"`, `"escalated"`, `"exhausted"`, `"degraded"` |
| `message` | `str` | Human-readable description for progress output |
| `timestamp` | `float` | When the event was recorded |

**Usage**: Appended to `RecoveryContext.events` in order. Drained into RecoveryReport at pipeline end. Displayed in real time via ProgressEvent with relevant message. (SC-05: every recovery action visible.)

**PII rule**: Only strategy names, error codes, and provider names appear in messages. No contract text or user data. (Spec §Edge Cases.)

---

## RecoveryReport

Final output structure attached to the pipeline's result. Summarizes all recovery actions and their outcomes.

**Fields**:

| Field | Type | Purpose |
|-------|------|---------|
| `events` | `list[RecoveryEvent]` | Chronological recovery log |
| `final_status` | `str` | `"resolved"`, `"degraded"`, `"unrecoverable"` |
| `summary` | `str` | One-line summary for pipeline report banner |
| `degradation_notices` | `list[str]` | Per-stage degradation warnings |
| `partial_results` | `bool` | True if pipeline completed with partial data |
| `actionable_error` | `str | None` | Final error message if unrecoverable |

**Output flow**:

```
Pipeline completes → RecoveryReport attached to PipelineReport
                           ↓
              Progress display renders real-time events
                           ↓
              Final user report includes recovery summary banner
```

---

## DegradationAction

Describes a single degradation measure applied to a pipeline stage.

**Values** (enum):

| Value | Effect |
|-------|--------|
| `reduce_batch_size` | Halve chunk batch size in chunking stage |
| `switch_to_lightweight_model` | Use cheaper/faster model for generation |
| `simplify_processing` | Skip optional enrichment (e.g., clause hierarchy) |
| `reduce_context_window` | Truncate context sent to generation |

**Order of application**: Least-disruptive first (reduce batch size → switch model → simplify processing → reduce context). (SC-03: maximize functional output under pressure.)

---

## PrivacyTier

Controls cloud provider fallback behavior. Used by `ProviderFallbackStrategy` to enforce privacy constraints (SC-04).

**Values** (enum):

| Value | Meaning |
|-------|---------|
| `strict` | Local-only. Cloud fallback blocked. (Default) |
| `standard` | Cloud fallback allowed if provider is user-configured. |
| `none` | No privacy restrictions on fallback. |

**Validation**: Set at pipeline start from user config. Never changes mid-pipeline.

---

## Entity Relationships

```
Pipeline start
  │
  ▼
RecoveryContext (created)
  │
  ├── ErrorClassification (per failure)
  │     ▼
  │   RecoveryStrategy selected
  │     ├── AutoRetryStrategy
  │     ├── ProviderFallbackStrategy
  │     ├── GracefulDegradationStrategy
  │     ├── StageIsolationStrategy
  │     └── UserGuidedRecoveryStrategy
  │     │
  │     ▼
  │   RecoveryEvent (recorded)
  │     │
  │     ├── ProgressEvent (real-time display)
  │     └── RecoveryContext.events (accumulated)
  │
  ▼
RecoveryReport (produced at pipeline end)
  │
  ├── Attached to PipelineReport
  └── Rendered in final user output
```

---

## State Transitions

```
                    ┌─────────────────────────┐
                    │    Failure Detected     │
                    │  (ErrorClassification)  │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │  Strategy Selection     │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
              ┌─────│   Strategy Execute      │─────┐
              │     └───────────┬─────────────┘     │
              ▼                 ▼                    ▼
     ┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
     │    Succeeded    │ │  Exhausted   │ │  Escalated       │
     │ → resolved      │ │ → next strat │ │ → user-guided    │
     │ → continue      │ │ → escalate   │ │ → terminal       │
     └─────────────────┘ └──────────────┘ └──────────────────┘
```

**Key transitions**:
1. transient → AutoRetry → succeed → resolved → continue
2. transient → AutoRetry → exhaust → ProviderFallback → succeed → resolved
3. permanent → ProviderFallback → all exhausted → UserGuidedRecovery → terminal
4. resource → GracefulDegradation → succeed → degraded → continue with banner
5. resource → GracefulDegradation → exhaust → terminal with memory error
6. stage_failure → StageIsolation → continue with partial data
7. stage_failure_critical → halt → UserGuidedRecovery → terminal
