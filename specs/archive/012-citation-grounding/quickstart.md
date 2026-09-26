# Quickstart: Citation Grounding Discriminator (N-5)

**Date**: 2026-07-03 | **Spec**: `specs/012-citation-grounding/spec.md`

---

## Validation Scenarios

### Scenario 1: Strict mode grounding (default)

**Prerequisites**: A parsed NDA document, a playbook, AI Gateway configured.

```bash
openreview precheck contract.pdf --playbook playbooks/precheck-nda-v1.yaml --grounding-mode=strict
```

**Expected output**:
- Terminal table shows a grounding verdict column with values `G` (grounded), `U` (ungrounded), `?` (uncertain)
- Only grounded claims appear in the output table
- A summary line: "Grounding: 8/10 claims grounded, 1 ungrounded, 1 uncertain (strict mode)"
- Ungrounded claims printed as warnings to stderr: "⚠ Claim #3 '...' excluded: not grounded in clause 4.3"
- Audit log written to `output/grounding-audit.jsonl`

**Success criteria**:
- Every surviving claim has a valid `clause_id` and `paragraph_index` in the source document
- Zero false provenances in a manual spot-check of 5 claims

---

### Scenario 2: Lenient mode grounding

```bash
openreview precheck contract.pdf --playbook playbooks/precheck-nda-v1.yaml --grounding-mode=lenient
```

**Expected output**:
- Terminal table shows grounding verdict column with all claims present
- Ungrounded claims marked with `[UNGROUNDED]` prefix in the confidence/verdict cell
- Summary line: "Grounding: 8/10 claims grounded, 1 ungrounded, 1 uncertain (lenient mode)"
- No claims excluded from output

**Success criteria**:
- All 10 input claims appear in the output (100% retention regardless of grounding status)
- Ungrounded/uncertain claims are clearly distinguishable from grounded claims

---

### Scenario 3: Skip grounding

```bash
openreview precheck contract.pdf --playbook playbooks/precheck-nda-v1.yaml --no-grounding
```

**Expected output**:
- No grounding verdict column in terminal table
- No grounding fields in JSON output (all `null`)
- No audit log written
- Behavior identical to pre-spec-012

**Success criteria**:
- Identical output to running the same command without grounding flags on spec-011 code

---

### Scenario 4: Audit log inspection

```bash
cat output/grounding-audit.jsonl | python -m json.tool --no-ensure-ascii
```

**Expected output** (one entry per line, formatted for reading):

```json
{
  "claim_hash": "a1b2c3d4e5f6...",
  "verdict": "grounded",
  "confidence": 0.95,
  "provenances": [
    {"clause_id": "4.3", "paragraph_index": 2, "confidence": 0.95}
  ],
  "reason": null,
  "timestamp": "2026-07-03T12:00:00.000000"
}
```

**Success criteria**:
- One entry per claim in the review report
- All fields populated (reason null only for grounded claims)
- Timestamps are valid ISO-8601
- Claim hashes are valid SHA-256 hex strings (64 chars)

---

### Scenario 5: Unit test validation

```bash
uv run pytest tests/unit/test_grounding_*.py -v
```

**Expected output**: All tests pass (4 test files):

```
tests/unit/test_grounding_models.py .....                          [ 25%]
tests/unit/test_grounding_discriminator.py ..........               [ 75%]
tests/unit/test_grounding_metrics.py ....                          [ 95%]
tests/unit/test_grounding_audit.py .                               [100%]
```

**Success criteria**:
- Models test: verifies `GroundingVerdict` enum values, `CitationProvenance` construction, `CGReport` field defaults, `DiscriminationAuditEntry` hash behavior
- Discriminator test: verifies strict/lenient modes, skip logic for `citation_valid=false`, empty claims list, multi-clause provenance, edge cases (duplicate IDs, no clause structure)
- Metrics test: verifies CP/CR/CL computation with known inputs, edge cases (zero claims, all grounded/no grounded mix)
- Audit log test: verifies append/flush, file creation, JSONL format, hash integrity

---

### Scenario 6: Integration test

```bash
uv run pytest tests/integration/test_grounding_pipeline.py -v
```

**Expected output**:

```
tests/integration/test_grounding_pipeline.py .....                 [100%]
```

**Success criteria**:
- End-to-end: seeded `ReviewReport` → `CitationGroundingDiscriminator` → merged `ReviewReport` with grounding fields
- Verifies that `CGReport.merge_into()` correctly populates `ClauseAssessment` fields
- Verifies strict mode claim filtering

---

### Scenario 7: Accuracy benchmark

```bash
uv run pytest tests/unit/test_grounding_discriminator.py -k accuracy -v
```

**Expected output**:

```
tests/unit/test_grounding_discriminator.py::test_accuracy_above_985 PASSED [ 50%]
tests/unit/test_grounding_discriminator.py::test_accuracy_per_corruption PASSED [100%]
```

**Success criteria**:
- `test_accuracy_above_985`: ≥98.5% overall accuracy against seeded corpus of ≥1,000 claims
- `test_accuracy_per_corruption`: No corruption type (clause_swap, category_swap, hallucination, anachronism) below 95% accuracy
