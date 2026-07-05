# Quickstart — Error Recovery Framework

**Date**: 2026-07-05 | **Spec Reference**: [spec.md](./spec.md)

---

## What this gives you

Five automatic recovery strategies for pipeline failures. When a stage or provider call fails, the framework retries, falls back, degrades, isolates, or reports — without your code managing any of it.

---

## Using recovery in a pipeline

### Step 1: Create a recovery config

```python
from openreview_cli.recovery.models import RecoveryConfig

config = RecoveryConfig(
    max_retries=5,              # Per-provider retry limit (FR-08)
    base_interval_s=1.0,        # Backoff base in seconds
    memory_threshold_pct=80.0,  # Degradation trigger (% of 100 MB)
)
```

Or let the framework read from the user's config file (TOML/YAML via existing config loader).

### Step 2: Pass config to Pipeline

```python
from openreview_cli.pipeline import Pipeline
from openreview_cli.recovery import make_coordinator

coordinator = make_coordinator(config)

pipeline = Pipeline(
    stages=[parse, chunk, retrieve, generate, report],
    progress_callback=display_progress,
    recovery=coordinator,  # ← new parameter
)
```

### Step 3: Run normally

```python
report = await pipeline.run(ctx)
# If recovery occurred, report.recovery contains RecoveryReport
# with events, final_status, and any degradation_notices
```

That is the entire integration surface. Stages do not change (except optional degradation support — see contracts/stage-recovery-contract.md).

---

## Validation scenarios

Run these to verify the framework works end-to-end:

### Scenario 1 — Transient provider failure auto-recovers

1. Configure two providers: a primary that can be made to fail temporarily, and a fallback.
2. Run a pipeline that calls the AI Gateway.
3. Inject two HTTP 503 responses before a successful response from the primary.

Expected: Pipeline completes. Progress output shows retry messages. RecoveryReport shows `final_status="resolved"`.

### Scenario 2 — Provider fallback on permanent failure

1. Configure two providers: primary that always fails (500), fallback that works.
2. Run a pipeline.

Expected: After retries exhaust on primary, progress shows "Falling back to {fallback}". Pipeline completes via fallback.

### Scenario 3 — Memory degradation

1. Set `memory_threshold_pct=10` (aggressive).
2. Run a pipeline whose stage allocates >10 MB.
3. The stage should implement `supports_degradation()` that reduces memory usage.

Expected: Progress shows "Memory pressure detected". Pipeline completes with `final_status="degraded"` and a degradation notice in the report.

### Scenario 4 — Stage isolation preserves partial results

1. Configure a pipeline with two non-critical stages. The first produces some output but raises a `StageError` before finishing.
2. Run.

Expected: Pipeline continues. Second stage receives partial data. Report includes `partial_results=True` and error recorded in results.

### Scenario 5 — Actionable error when all strategies exhausted

1. Configure a single provider that always fails.
2. Set retries to 0 (or let them exhaust).
3. Run a pipeline that calls the Gateway.

Expected: Pipeline stops with an error message containing ≥2 actionable suggestions. No silent fallback.

---

## Verifying the 90% auto-recovery target (SC-01)

The test suite includes a parameterized injection test:

```
tests/integration/test_pipeline_with_recovery.py
  test_ninety_percent_auto_recovery()
```

This test injects 100 representative failure scenarios:
- 40 transient provider errors (varying by status code)
- 20 permanent provider errors (with fallback configured)
- 20 memory-pressure scenarios (with degradation-capable stages)
- 20 non-critical stage failures

**Pass condition**: ≥90 scenarios complete without user-facing error prompt.

---

## Config file reference

```yaml
# ~/.config/openreview/config.yaml or equivalent
recovery:
  max_retries: 5              # int, default 5
  base_interval_s: 1.0        # float, default 1.0
  memory_threshold_pct: 80.0  # float, default 80.0 (percentage of 100 MB budget)
  enabled_strategies:          # list, default all
    - auto_retry
    - provider_fallback
    - graceful_degradation
    - stage_isolation
    - user_guided_recovery
```
