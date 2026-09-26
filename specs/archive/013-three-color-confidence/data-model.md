# Data Model: Three-Color Output with Confidence Scores

**Spec**: 013 — Three-Color Output with Confidence Scores
**Date**: 2026-07-03

---

## New Entities

### `AssessmentColor(StrEnum)`

```python
class AssessmentColor(StrEnum):
    """First-class three-color status for a clause assessment."""
    green = "green"
    amber = "amber"
    red = "red"
```

Replaces boolean `is_amber` as the primary color signal. Represents the final color-assigned verdict for one clause assessment. Derived deterministically from position, confidence, QA verdict, grounding verdict, error state, and user-configured threshold.

### `AmberReason(StrEnum)`

```python
class AmberReason(StrEnum):
    """Specific reason why an assessment is marked Amber."""
    low_confidence = "low_confidence"
    qa_disagreement = "qa_disagreement"
    qa_uncertain = "qa_uncertain"
    error = "error"
    grounding_failure = "grounding_failure"
    grounding_uncertain = "grounding_uncertain"
```

Each reason corresponds to a specific Amber trigger defined in FR-004. Multiple reasons may be active for a single assessment (e.g., low confidence AND QA disagreement).

---

## Modified Entities

### `ClauseAssessment` — additions

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `color` | `AssessmentColor \| None` | `None` | Derived color status. Set at output time by `assign_colors()`. |
| `amber_reasons` | `list[AmberReason] \| None` | `None` | Specific reasons this assessment is Amber. Empty list or None when color is Green or Red. |
| `effective_confidence` | `float \| None` | `None` | Aggregated confidence score from extraction, QA, and grounding stages. Computed as `min(extraction, qa, grounding)` with missing stages defaulting to 1.0. |

#### `is_amber` property (backward compat)

```python
@property
def is_amber(self) -> bool:
    """Backward-compat property — derives from color if set, otherwise falls back to stored bool."""
    if self.color is not None:
        return self.color == AssessmentColor.amber
    return self._is_amber  # stored field from __post_init__ for pre-color consumers
```

The stored `is_amber` field in `__post_init__` is kept but renamed to `_is_amber` (private). The public `is_amber` becomes a property that:
1. Returns `(color == amber)` if color is set (post-`assign_colors()`)
2. Falls back to the stored `_is_amber` value for consumers that haven't called `assign_colors()` yet

This ensures backward compatibility without breaking existing code that reads `ca.is_amber` before the color pipeline runs.

### `ReviewSummary` — additions

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `green_count` | `int` | `0` | Count of Green assessments |
| `red_count` | `int` | `0` | Count of Red assessments |
| `avg_effective_confidence` | `float` | `0.0` | Average of `effective_confidence` across all assessments (excluding assessments that errored) |

`amber_count` is preserved unchanged for backward compatibility.

### `ReviewReport` — additions

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `confidence_threshold` | `float` | `0.7` | The threshold used for color assignment in this report |

Records what threshold produced the output. Important for reproducibility — a report generated with `--confidence-threshold 0.7` will have different colors than one with `0.3`, and the report should record which was used.

---

## Color Assignment Rules

The color assignment is a pure function `assign_colors(assessments, threshold)`:

```
Given threshold T and assessment A:

# Compute effective confidence
effective_confidence = min(
    A.confidence or 1.0,
    A.qa_confidence or 1.0,     # Note: qa_confidence not yet a field — future spec
    A.grounding_confidence or 1.0
)

# Determine Amber triggers
triggers = []
if A.error is not None:
    triggers.append(AmberReason.error)
if effective_confidence < T:
    triggers.append(AmberReason.low_confidence)
if A.qa_verdict == QAVerdict.disagree:
    triggers.append(AmberReason.qa_disagreement)
if A.qa_verdict == QAVerdict.uncertain:
    triggers.append(AmberReason.qa_uncertain)
if A.grounding_verdict == GroundingVerdict.UNGROUNDED:
    triggers.append(AmberReason.grounding_failure)
if A.grounding_verdict == GroundingVerdict.UNCERTAIN:
    triggers.append(AmberReason.grounding_uncertain)

# Assign color
if triggers:
    color = AssessmentColor.amber
elif A.position == Position.unfavorable and effective_confidence >= T:
    color = AssessmentColor.red
elif A.position in (Position.favorable, Position.neutral) and effective_confidence >= T:
    color = AssessmentColor.green
else:
    color = AssessmentColor.amber  # catch-all (uncertain position without other triggers)
    if A.position == Position.uncertain and AmberReason.qa_uncertain not in triggers:
        triggers.append(AmberReason.qa_uncertain)

# Set fields
A.color = color
A.effective_confidence = effective_confidence
A.amber_reasons = triggers
```

### Summary of rules (from FR-002)

| Condition | Color | Amber Reasons |
|-----------|-------|---------------|
| Error present | Amber | `[error]` |
| Confidence < threshold (and no error) | Amber | `[low_confidence]` |
| QA = disagree (and no error or low conf) | Amber | `[qa_disagreement]` |
| QA = uncertain (and no other trigger) | Amber | `[qa_uncertain]` |
| Grounding = ungrounded | Amber | `[grounding_failure]` |
| Grounding = uncertain | Amber | `[grounding_uncertain]` |
| Position = unfavorable, confidence >= T | Red | `[]` |
| Position = favorable/neutral, confidence >= T | Green | `[]` |
| Position = uncertain (no other triggers) | Amber | `[qa_uncertain]` (if qa caused it) |
| Multiple triggers simultaneously | Amber | All applicable reasons |
| No grounding data (grounding_verdict is None) | N/A | Grounding not a trigger |

---

## State Transitions

**None.** Color is derived at report-build time by a pure function. It is not stored, not mutated, and not persisted. The only "state" is the user-provided `--confidence-threshold` value, which is passed as a parameter to `assign_colors()`.

---

## Schema Version Impact

`ReviewReport.schema_version` is bumped from `"1.0.0"` to `"1.1.0"` (minor — additive fields only, no breaking changes).

---

## Dependency References

| Item | Reference | Status |
|------|-----------|--------|
| `enum.StrEnum` | Python 3.11+ stdlib | ✅ Confirmed (Python 3.12 project) |
| `dataclasses` | Python 3.7+ stdlib | ✅ Confirmed (exists in `review/models.py`) |
| `typer.Option` | `typer` v0.12+ | ✅ Confirmed (exists in `app.py`) |
| `rich.table` | `rich` v13+ | ✅ Confirmed (exists in `report.py`) |
