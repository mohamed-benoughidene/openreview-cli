# Stage-Recovery Contract

**Date**: 2026-07-05 | **Spec Reference**: spec.md §4 FR-03, FR-04, SC-03, SC-06

---

## 1. Stages signal degradation capability

A stage MAY declare that it supports graceful degradation by implementing an optional method:

```python
class Stage(ABC):
    ...
    def supports_degradation(self) -> bool:
        """Return True if this stage can run in degraded mode."""
        return False

    def apply_degradation(self, action: DegradationAction) -> None:
        """Reduce resource usage for this invocation.

        Called by the recovery coordinator before stage.run() when
        memory pressure is detected. The stage adjusts its internal
        parameters (batch size, model choice, etc.) accordingly.
        """
```

Stages that do not implement these methods are treated as degradation-agnostic — they still benefit from stage-isolation recovery if they fail.

---

## 2. Degradation action contract

When `GracefulDegradationStrategy` triggers, the coordinator calls `stage.apply_degradation(action)` with one of these actions:

| Action | Expected Stage Behavior |
|--------|------------------------|
| `reduce_batch_size` | Halve internal batch size. If already 1, this is a no-op. |
| `switch_to_lightweight_model` | Use a cheaper model for generation tasks (e.g., ollama/llama3.1:8b instead of ollama/llama3.1:70b). |
| `simplify_processing` | Skip optional enrichment (clause hierarchy building, cross-referencing). |
| `reduce_context_window` | Truncate context sent to generation stage. |

Stage implementations are responsible for handling partially degraded state. If a stage cannot honor a degradation action, it ignores the action silently.

---

## 3. Partial output contract

When a non-critical stage fails, the recovery coordinator examines the stage's partial output:

**Rules**:
- If the stage produced ANY output before failure (e.g., parsed N out of M pages), that output is merged into `RecoveryContext.partial_data`.
- Before failure, completed stages' outputs are preserved in `RecoveryContext.saved_results` (keyed by stage name). This satisfies FR-07: user data preservation across recovery attempts.
- The stage's error is recorded in `StageResult.error` and `RecoveryReport`.
- If the stage produced NO output before failure, the coordinator treats it as fully failed.

**Dependent stage behavior**:
- A stage MAY check `ctx.get("errors")` to see if prior stages failed.
- A stage MAY skip processing of data that depends on a failed stage's output.
- A stage MUST NOT crash when partial data is missing keys it expects — it processes what is available.

---

## 4. Critical vs non-critical

The distinction lives in `Stage.critical` (boolean):

| `critical` | Failure Behavior |
|------------|-----------------|
| `False` | StageIsolationStrategy handles it. Pipeline continues with partial data. |
| `True` | Pipeline halts immediately. UserGuidedRecoveryStrategy formats final error. |

The list of critical stages from the 5-stage pipeline (spec-018):
- **ParseStage**: critical — all downstream stages depend on parsed document.
- All other stages: non-critical — chunking, retrieval, generation, and reporting can produce partial results with available data.

---

## 5. Memory monitoring contract

Memory monitoring happens at the recovery coordinator level, not inside stages:

- **Before stage**: Coordinator checks `RecoveryContext.memory_threshold_bytes` against current allocated bytes.
- **If threshold exceeded**: Coordinator calls `stage.apply_degradation(action)` and sets `context["_recovery_degraded"] = True` so the stage knows to run in degraded mode.
- **After stage**: The pipeline's existing pre/post snapshot delta is recorded. If it exceeds budget despite degradation, the coordinator halts with a memory error.

This separation keeps stages free of memory-management concerns while letting the coordinator apply uniform pressure handling.
