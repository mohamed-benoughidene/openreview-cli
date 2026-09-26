# Quickstart: Three-Color Output with Confidence Scores

**Spec**: 013 — Three-Color Output with Confidence Scores
**Date**: 2026-07-03

---

## Validation Scenarios

### Scenario 1 — Default Threshold (0.7)

**Setup**: Run a single-party review on an NDA without the `--confidence-threshold` flag.

```bash
openreview precheck review tests/fixtures/simple-nda.pdf --playbook precheck-nda-v1
```

**Expected**:
- Terminal output shows Green/Amber/Red badges in the Status column
- Clauses with favorable position and confidence >= 0.7 are Green
- Clauses with unfavorable position and confidence >= 0.7 are Red
- Clauses with confidence < 0.7 or QA disagreement are Amber with `⚠ AMBER` badge
- Summary shows `Green: N`, `Amber: N`, `Red: N`

**Pass condition**: Three distinct colors visible in terminal output. No binary OK/AMBER remaining.

---

### Scenario 2 — Custom Threshold

**Setup**: Same review, run twice with different thresholds.

```bash
openreview precheck review tests/fixtures/simple-nda.pdf \
  --playbook precheck-nda-v1 \
  --confidence-threshold 0.9

openreview precheck review tests/fixtures/simple-nda.pdf \
  --playbook precheck-nda-v1 \
  --confidence-threshold 0.3
```

**Expected**:
- `0.9` threshold produces **more** Amber flags than default (0.7)
- `0.3` threshold produces **fewer** Amber flags than default (0.7)
- Both run in under 1 second (no pipeline re-run)

**Pass condition**: Different threshold values produce observably different color distributions. No pipeline re-run (assessments unchanged, only colors change).

---

### Scenario 3 — JSON Output

**Setup**: Run with `--output json`.

```bash
openreview precheck review tests/fixtures/simple-nda.pdf \
  --playbook precheck-nda-v1 \
  --output json
```

**Expected**:
- Each assessment has `"color"` field: `"green"`, `"amber"`, or `"red"`
- Each assessment has `"amber_reasons"` field (list of strings, empty for Green/Red)
- Each assessment has `"effective_confidence"` field (float)
- Each assessment has `"is_amber"` field (boolean, derived from color) — backward compat
- Report root has `"confidence_threshold": 0.7`
- Summary has `"green_count"`, `"red_count"`, `"avg_effective_confidence"`

**Pass condition**: All new fields present in JSON output. `is_amber` is consistent with `color`.

---

### Scenario 4 — All Green (Edge)

**Setup**: All clauses are favorable/neutral with confidence >= 0.7, no errors, QA agrees, grounding passes (or no grounding data).

```bash
openreview precheck review tests/fixtures/all-safe-nda.pdf \
  --playbook precheck-nda-v1
```

**Expected**:
- Every clause shows Green badge
- Summary shows `Green: N, Amber: 0, Red: 0`
- No `⚠ AMBER` badges visible

**Pass condition**: Zero Amber, zero Red. User sees all safe.

---

### Scenario 5 — Low Confidence Amber (Edge)

**Setup**: A clause has confidence 0.4 with favorable position, QA agrees, no errors.

```bash
openreview precheck review tests/fixtures/low-conf-nda.pdf \
  --playbook precheck-nda-v1
```

**Expected**:
- The low-confidence clause shows Amber badge
- Amber reason includes `low_confidence`
- Reason text shows "Below confidence threshold (0.40 < 0.70)"

**Pass condition**: Low confidence alone triggers Amber. User can see why.

---

### Scenario 6 — Backward Compatibility

**Setup**: Code that reads `ca.is_amber` directly.

```python
for assessment in report.assessments:
    if assessment.is_amber:
        print(f"Clause {assessment.clause_id} needs review")
```

**Expected**:
- `is_amber` returns `True` for Amber assessments (whether accessed before or after `assign_colors()`)
- `is_amber` returns `False` for Green and Red assessments
- `amber_count` in summary still works

**Pass condition**: Existing code that checks `is_amber` or `amber_count` continues to function unchanged.

---

### Scenario 7 — Help Text Disclosure

**Setup**: Run `--help` on a review subcommand.

```bash
openreview precheck review --help
```

**Expected**:
- `--confidence-threshold` appears in the help output
- Help text includes the accuracy ceiling disclosure:
  ```
  Note: The comparison accuracy of automated review is bounded by
  approximately 64% F1. Three-color output (Green/Amber/Red) is
  designed to mitigate this — set the threshold generously to push
  uncertain comparisons to Amber rather than risking false Green or Red.
  ```

**Pass condition**: Help text contains the disclosure. Verified by grepping the help output or the source string.

---

## Quick Verification Commands

```bash
# 1. Verify the flag is accepted and help text includes disclosure
openreview precheck review --help | grep -i "confidence-threshold"

# 2. Verify invalid values are rejected
openreview precheck review test.pdf --playbook precheck-nda-v1 --confidence-threshold 1.5 \
  && echo "SHOULD HAVE FAILED" || echo "Correctly rejected"

# 3. Verify JSON output has new fields
openreview precheck review test.pdf --playbook precheck-nda-v1 --output json \
  | python -c "import sys,json; d=json.load(sys.stdin); print('color' in d['assessments'][0])"
```
