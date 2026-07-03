# CLI Interface Contract: Three-Color Output with Confidence Scores

**Spec**: 013 — Three-Color Output with Confidence Scores
**Date**: 2026-07-03

---

## `--confidence-threshold` Flag

### Specification

| Property | Value |
|----------|-------|
| **Name** | `--confidence-threshold` |
| **Type** | `float` |
| **Range** | `[0.0, 1.0]` |
| **Default** | `0.7` |
| **Scope** | Per-command (each review-producing subcommand) |
| **Required** | No |
| **Repeatable** | No |
| **Environment variable** | None (CLI-only) |

### Validation

- Values `< 0.0` or `> 1.0` are rejected with:
  ```
  Error: Invalid value for '--confidence-threshold': <value> is not in the range [0.0, 1.0].
  ```
- Non-float values are rejected by Typer's built-in type coercion.

### Help Text

```
--confidence-threshold FLOAT  [default: 0.7]
  Confidence threshold for Green/Amber/Red assignment (0.0-1.0).
  Clauses with effective confidence below this threshold are marked Amber.
  Note: The comparison accuracy of automated review is bounded by
  approximately 64% F1. Three-color output (Green/Amber/Red) is
  designed to mitigate this — set the threshold generously to push
  uncertain comparisons to Amber rather than risking false Green or Red.
```

---

## CLI Invocation Examples

### Default threshold
```bash
openreview precheck review document.pdf --playbook precheck-nda-v1
```
→ Uses threshold 0.7. Clauses with effective confidence >= 0.7 and favorable/neutral → Green. Unfavorable with confidence >= 0.7 → Red. Everything else → Amber.

### Custom threshold (risk-averse)
```bash
openreview precheck review document.pdf --playbook precheck-nda-v1 --confidence-threshold 0.9
```
→ Only clauses with confidence >= 0.9 can be Green/Red. Most assessments will be Amber.

### Custom threshold (relaxed)
```bash
openreview precheck review document.pdf --playbook precheck-nda-v1 --confidence-threshold 0.3
```
→ Only clauses with confidence < 0.3 trigger Amber from low confidence. QA disagreement, error, and grounding failure still trigger Amber.

### Edge threshold (all pass)
```bash
openreview precheck review document.pdf --playbook precheck-nda-v1 --confidence-threshold 0.0
```
→ No clause is Amber due to confidence threshold. Only error/QA-disagree/grounding Amber triggers apply.

### Edge threshold (all Amber)
```bash
openreview precheck review document.pdf --playbook precheck-nda-v1 --confidence-threshold 1.0
```
→ Every clause with confidence < 1.0 is Amber. Only perfect assessments (confidence=1.0, no triggers) pass.

---

## Terminal Output Format

### Status Column (three-color badges)

| Color | Badge | Meaning |
|-------|-------|---------|
| Green | `● OK` (green text) | Safe — no action needed |
| Amber | `⚠ AMBER` (bold yellow) | Needs human review — reasons shown |
| Red | `● RED` (bold red) | Problematic — needs attention |

The Status column replaces the current binary `⚠ AMBER` / `OK` with the three-state display.

### Amber Reason Breakdown

When a clause is Amber, the reasons are visible in the detail. The terminal shows:
- The `⚠ AMBER` badge in the Status column
- Below the table, or in an expandable row, the specific reasons (e.g., "Low confidence (0.45), QA disagreement")

### Summary Section

```text
Summary
  Green:       5  (new)
  Amber:       3  (existing, renamed from "Amber flags")
  Red:         2  (new)
  Favorable:   3
  Neutral:     2
  Unfavorable: 2
  Uncertain:   1
  No-match:    1

  Amber flags: 3         (preserved for backward compat)
  Avg confidence: 0.62
  Avg effective confidence: 0.58   (new)
  Confidence threshold: 0.7        (new)
```

---

## JSON Output Schema

### Assessment object additions

```json
{
  "clause_id": "1",
  "color": "amber",
  "amber_reasons": ["low_confidence", "qa_disagreement"],
  "effective_confidence": 0.45,
  "is_amber": true,
  "...existing fields...": {}
}
```

| Field | Type | Description |
|-------|------|-------------|
| `color` | `string` | One of `"green"`, `"amber"`, `"red"` |
| `amber_reasons` | `array[string]` | List of reason strings (empty for Green/Red) |
| `effective_confidence` | `number` | Aggregated confidence (null if not computed) |
| `is_amber` | `boolean` | **DEPRECATED** — derived from `color` for backward compat |
| `confidence_threshold` | `number` | At report root — the threshold used |

### Summary additions

```json
{
  "green_count": 5,
  "red_count": 2,
  "amber_count": 3,
  "avg_confidence": 0.62,
  "avg_effective_confidence": 0.58
}
```

### Report root additions

```json
{
  "confidence_threshold": 0.7,
  "schema_version": "1.1.0"
}
```

---

## Backward Compatibility Guarantees

1. **`is_amber` field**: Still present in JSON output, derived from `color`. Existing consumers reading `is_amber` continue to work.
2. **`amber_count`**: Still present in summary.
3. **`--confidence-threshold` is optional**: Omitting it uses the default — no behavioral change for existing scripts.
4. **CLI exit codes**: Unchanged — all new error cases (invalid threshold) exit with the standard error code.
5. **Existing review output format**: The terminal table structure is preserved; only the Status column content changes from binary to three-color.
