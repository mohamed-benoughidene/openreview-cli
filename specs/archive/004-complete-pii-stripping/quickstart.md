# Quickstart Validation Guide: Complete PII Stripping Integration

**Date**: 2026-06-30 | **Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Overview

This guide provides runnable validation scenarios to verify the PII stripping integration works end-to-end. Each scenario tests a specific aspect of the feature and includes prerequisites, setup commands, test commands, and expected outcomes.

**Prerequisites**:
- Python 3.12+ installed
- `uv` package manager installed
- Repository cloned and dependencies synced: `uv sync`
- Test fixtures available in `tests/fixtures/pii/`

---

## Scenario 1: Basic PII Stripping (Happy Path)

**Goal**: Verify that PII is automatically stripped when running `openreview precheck` on a document containing sensitive information.

**Prerequisites**:
- Test PDF with known PII: `tests/fixtures/pii/sample_contract.pdf` (contains 5 party names, 3 dates, 2 monetary amounts)

**Setup**:

```bash
# Ensure dependencies are installed
uv sync

# Verify test fixture exists
ls tests/fixtures/pii/sample_contract.pdf
```

**Test Command**:

```bash
uv run openreview precheck tests/fixtures/pii/sample_contract.pdf
```

**Expected Outcome**:

1. **Exit Code**: 0 (success)
2. **Standard Output**:
   ```
   ✓ PII stripping complete: 10 entities detected (5 party names, 3 dates, 2 amounts)
   ✓ Review memo generated: ./review_results/abc123/memo.txt
   ✓ Encrypted PII mapping: ./review_results/abc123/pii_mapping.enc
   ✓ Audit trail logged

   Review Summary:
   - Document: sample_contract.pdf (10 pages)
   - Processing time: 1.2 seconds
   - PII entities: 10 (all replaced with placeholders)
   - Review mode: PreCheck (NDA)
   - Status: Complete
   ```
3. **Files Created**:
   - `./review_results/abc123/memo.txt` — PII-stripped review memo (contains `[PARTY_A]`, `[DATE]`, `[AMOUNT]` placeholders)
   - `./review_results/abc123/pii_mapping.enc` — Fernet-encrypted PII mapping
4. **Database**:
   - `pii_cache` table: 1 row (document_hash, config_hash, paths)
   - `pii_audit_trail` table: 1 row (entity_count=10, status="success")

**Validation**:

```bash
# Verify memo contains placeholders, not raw PII
grep -c "PARTY_A\|DATE\|AMOUNT" ./review_results/abc123/memo.txt
# Expected: >0 (placeholders present)

# Verify memo does NOT contain raw PII (example: "John Smith")
grep -c "John Smith" ./review_results/abc123/memo.txt
# Expected: 0 (raw PII not present)

# Verify encrypted mapping exists and is non-empty
ls -lh ./review_results/abc123/pii_mapping.enc
# Expected: file exists, size > 0

# Verify audit trail in SQLite
uv run python -c "
import sqlite3
conn = sqlite3.connect('.openreview/openreview.db')
cursor = conn.execute('SELECT entity_count, status FROM pii_audit_trail ORDER BY timestamp DESC LIMIT 1')
row = cursor.fetchone()
print(f'Entity count: {row[0]}, Status: {row[1]}')
# Expected: Entity count: 10, Status: success
"
```

---

## Scenario 2: --no-pii Flag (Opt-Out)

**Goal**: Verify that `--no-pii` flag disables PII stripping and processes raw text.

**Prerequisites**:
- Same test PDF as Scenario 1

**Test Command**:

```bash
uv run openreview precheck --no-pii tests/fixtures/pii/sample_contract.pdf
```

**Expected Outcome**:

1. **Exit Code**: 0 (success)
2. **Standard Output**:
   ```
   ⚠ PII stripping disabled. Raw text processed.
   ✓ Review memo generated: ./review_results/def456/memo.txt
   ✓ Audit trail logged

   Review Summary:
   - Document: sample_contract.pdf (10 pages)
   - Processing time: 0.9 seconds
   - PII entities: N/A (stripping disabled)
   - Review mode: PreCheck (NDA)
   - Status: Complete (raw PII in output)
   ```
3. **Files Created**:
   - `./review_results/def456/memo.txt` — Review memo with raw PII intact (contains "John Smith", actual dates, actual amounts)
   - **No** `pii_mapping.enc` file created
4. **Database**:
   - `pii_cache` table: no new row (or row with `config_hash` indicating `--no-pii`)
   - `pii_audit_trail` table: 1 row (entity_count=0, status="success")

**Validation**:

```bash
# Verify memo contains raw PII
grep -c "John Smith" ./review_results/def456/memo.txt
# Expected: >0 (raw PII present)

# Verify no encrypted mapping created
ls ./review_results/def456/pii_mapping.enc 2>&1
# Expected: "No such file or directory"

# Verify audit trail shows no PII detected
uv run python -c "
import sqlite3
conn = sqlite3.connect('.openreview/openreview.db')
cursor = conn.execute('SELECT entity_count, status FROM pii_audit_trail ORDER BY timestamp DESC LIMIT 1')
row = cursor.fetchone()
print(f'Entity count: {row[0]}, Status: {row[1]}')
# Expected: Entity count: 0, Status: success
"
```

---

## Scenario 3: Config Change Detection

**Goal**: Verify that changing the PII threshold in `config.yml` triggers re-processing.

**Prerequisites**:
- Same test PDF as Scenario 1
- Initial run with default threshold (0.5) completed (Scenario 1)

**Setup**:

```bash
# Run with default threshold (0.5)
uv run openreview precheck tests/fixtures/pii/sample_contract.pdf
# Note the entity count from output (e.g., 10 entities)
```

**Test Command**:

```bash
# Change threshold to 0.7 (more conservative)
cat > config.yml <<EOF
pii:
  threshold: 0.7
EOF

# Re-run on same document
uv run openreview precheck tests/fixtures/pii/sample_contract.pdf
```

**Expected Outcome**:

1. **Exit Code**: 0 (success)
2. **Standard Output**:
   ```
   ✓ PII stripping complete: 8 entities detected (4 party names, 2 dates, 2 amounts)
   ✓ Review memo generated: ./review_results/abc123/memo.txt
   ✓ Encrypted PII mapping: ./review_results/abc123/pii_mapping.enc
   ✓ Audit trail logged

   Review Summary:
   - Document: sample_contract.pdf (10 pages)
   - Processing time: 1.1 seconds
   - PII entities: 8 (all replaced with placeholders)
   - Review mode: PreCheck (NDA)
   - Status: Complete
   ```
   **Note**: Entity count decreased from 10 to 8 (higher threshold → fewer detections)
3. **Database**:
   - `pii_cache` table: row updated with new `config_hash`
   - `pii_audit_trail` table: 2 rows (one for each run, different `config_hash`)

**Validation**:

```bash
# Verify config hash changed
uv run python -c "
import sqlite3
conn = sqlite3.connect('.openreview/openreview.db')
cursor = conn.execute('SELECT config_hash, entity_count FROM pii_audit_trail ORDER BY timestamp')
rows = cursor.fetchall()
for row in rows:
    print(f'Config hash: {row[0][:16]}..., Entity count: {row[1]}')
# Expected: 2 rows with different config_hash values, different entity_counts
"

# Verify cache was updated (not duplicated)
uv run python -c "
import sqlite3
conn = sqlite3.connect('.openreview/openreview.db')
cursor = conn.execute('SELECT COUNT(*) FROM pii_cache')
count = cursor.fetchone()[0]
print(f'Cache entries: {count}')
# Expected: 1 (updated, not duplicated)
"
```

---

## Scenario 4: Accuracy Validation

**Goal**: Verify PII detection accuracy (recall ≥90%, precision ≥95%) on the validation corpus.

**Prerequisites**:
- Validation corpus: `tests/fixtures/pii/ground_truth.json` (50+ contracts with annotated PII)

**Setup**:

```bash
# Verify ground truth exists
ls tests/fixtures/pii/ground_truth.json

# Count ground truth entities
uv run python -c "
import json
with open('tests/fixtures/pii/ground_truth.json') as f:
    data = json.load(f)
print(f'Ground truth entities: {len(data)}')
# Expected: >500 (50 contracts × ~10 entities each)
"
```

**Test Command**:

```bash
uv run pytest tests/integration/test_pii_accuracy.py -v
```

**Expected Outcome**:

1. **Test Output**:
   ```
   tests/integration/test_pii_accuracy.py::test_pii_recall PASSED
   tests/integration/test_pii_accuracy.py::test_pii_precision PASSED
   tests/integration/test_pii_accuracy.py::test_pii_clean_text PASSED

   === 3 passed in 45.2s ===
   ```
2. **Accuracy Metrics** (printed by test):
   ```
   PII Accuracy Report:
   - Total ground truth entities: 523
   - Detected entities: 487
   - True positives: 475
   - False positives: 12
   - False negatives: 48
   - Recall: 90.8% (≥90% ✓)
   - Precision: 97.5% (≥95% ✓)
   ```

**Validation**:

```bash
# Verify recall ≥90%
uv run pytest tests/integration/test_pii_accuracy.py::test_pii_recall -v
# Expected: PASSED

# Verify precision ≥95%
uv run pytest tests/integration/test_pii_accuracy.py::test_pii_precision -v
# Expected: PASSED

# Verify zero false positives on clean text
uv run pytest tests/integration/test_pii_accuracy.py::test_pii_clean_text -v
# Expected: PASSED
```

---

## Scenario 5: Memory Budget Validation

**Goal**: Verify peak memory <100 MB (excluding NLP model) during PII stripping of a 500-page document.

**Prerequisites**:
- Synthetic 500-page PDF: `tests/fixtures/pii/synthetic_500page.pdf` (generated by test fixture)

**Setup**:

```bash
# Generate synthetic 500-page document (if not exists)
uv run python tests/fixtures/pii/generate_synthetic.py
```

**Test Command**:

```bash
uv run pytest tests/integration/test_pii_memory.py -v -m memory
```

**Expected Outcome**:

1. **Test Output**:
   ```
   tests/integration/test_pii_memory.py::test_pii_memory_budget PASSED
   tests/integration/test_pii_memory.py::test_pii_processing_time PASSED

   === 2 passed in 28.3s ===
   ```
2. **Memory Metrics** (printed by test):
   ```
   PII Memory Report:
   - Document: synthetic_500page.pdf (500 pages)
   - PII entities: 2000
   - Peak memory: 87.3 MB (<100 MB ✓)
   - Processing time: 24.1 seconds (<30 seconds ✓)
   ```

**Validation**:

```bash
# Verify peak memory <100 MB
uv run pytest tests/integration/test_pii_memory.py::test_pii_memory_budget -v
# Expected: PASSED

# Verify processing time <30 seconds
uv run pytest tests/integration/test_pii_memory.py::test_pii_processing_time -v
# Expected: PASSED
```

---

## Scenario 6: GDPR Retention (30-Day Expiry)

**Goal**: Verify that encrypted PII mappings expire after 30 days and can be deleted on demand.

**Prerequisites**:
- Completed Scenario 1 (PII mapping created)

**Test Command (On-Demand Deletion)**:

```bash
# List documents with PII data
uv run openreview pii list

# Expected output:
# Documents with PII data:
# 1. sample_contract.pdf
#    - Document hash: abc123def456...
#    - PII entities: 10
#    - Created: 2026-06-30 14:23:15
#    - Expires: 2026-07-30 14:23:15

# Delete PII data for specific document
uv run openreview pii delete abc123

# Expected output:
# ✓ Deleted PII data for document hash: abc123def456
#   - Encrypted mapping: removed
#   - Audit trail: removed (1 records)
#   - Cache entry: removed

# Verify deletion
uv run openreview pii list
# Expected: "No documents with PII data"
```

**Validation**:

```bash
# Verify encrypted mapping deleted
ls ./review_results/abc123/pii_mapping.enc 2>&1
# Expected: "No such file or directory"

# Verify cache entry deleted
uv run python -c "
import sqlite3
conn = sqlite3.connect('.openreview/openreview.db')
cursor = conn.execute('SELECT COUNT(*) FROM pii_cache WHERE document_hash LIKE ?', ('abc123%',))
count = cursor.fetchone()[0]
print(f'Cache entries: {count}')
# Expected: 0
"

# Verify audit trail deleted
uv run python -c "
import sqlite3
conn = sqlite3.connect('.openreview/openreview.db')
cursor = conn.execute('SELECT COUNT(*) FROM pii_audit_trail WHERE document_hash LIKE ?', ('abc123%',))
count = cursor.fetchone()[0]
print(f'Audit trail entries: {count}')
# Expected: 0
"
```

---

## Scenario 7: Error Recovery (Partial Failure)

**Goal**: Verify that PII stripping preserves partial results when some pages fail.

**Prerequisites**:
- PDF with corrupted page: `tests/fixtures/pii/corrupted_page.pdf` (page 5 has invalid OCR data)

**Test Command**:

```bash
uv run openreview precheck tests/fixtures/pii/corrupted_page.pdf
```

**Expected Outcome**:

1. **Exit Code**: 2 (partial failure)
2. **Standard Output**:
   ```
   ⚠ PII stripping partial: 15 entities detected, 1 page failed
   ✓ Review memo generated: ./review_results/ghi789/memo.txt (pages 1-4, 6-10)
   ⚠ Failed pages: 5 (OCR error: low confidence)
   ✓ Encrypted PII mapping: ./review_results/ghi789/pii_mapping.enc (partial)
   ✓ Audit trail logged

   Review Summary:
   - Document: corrupted_page.pdf (10 pages)
   - Processing time: 1.5 seconds
   - PII entities: 15 (replaced with placeholders)
   - Failed pages: 1 (page 5)
   - Review mode: PreCheck (NDA)
   - Status: Partial
   ```
3. **Files Created**:
   - `./review_results/ghi789/memo.txt` — Review memo for pages 1-4, 6-10 (page 5 excluded)
   - `./review_results/ghi789/pii_mapping.enc` — Partial encrypted mapping (pages 1-4, 6-10)
4. **Database**:
   - `pii_audit_trail` table: 1 row (status="partial", failed_pages=[5])

**Validation**:

```bash
# Verify memo excludes failed page
grep -c "Page 5" ./review_results/ghi789/memo.txt
# Expected: 0 (page 5 not in memo)

# Verify audit trail shows partial status
uv run python -c "
import sqlite3, json
conn = sqlite3.connect('.openreview/openreview.db')
cursor = conn.execute('SELECT status, failed_pages FROM pii_audit_trail ORDER BY timestamp DESC LIMIT 1')
row = cursor.fetchone()
print(f'Status: {row[0]}, Failed pages: {json.loads(row[1])}')
# Expected: Status: partial, Failed pages: [5]
"
```

---

## Cleanup

After running all scenarios, clean up test artifacts:

```bash
# Remove review results
rm -rf ./review_results/

# Reset database (optional, for fresh start)
rm .openreview/openreview.db

# Remove generated test fixtures (if created)
rm tests/fixtures/pii/synthetic_500page.pdf
```

---

## Success Criteria Summary

| Scenario | Test | Expected Result |
|----------|------|-----------------|
| 1. Basic PII Stripping | Manual run | 10 entities detected, placeholders in memo, encrypted mapping created |
| 2. --no-pii Flag | Manual run | Raw PII in memo, no encrypted mapping, warning logged |
| 3. Config Change Detection | Manual run | Re-processing triggered, entity count changed, config hash updated |
| 4. Accuracy Validation | `pytest test_pii_accuracy.py` | Recall ≥90%, precision ≥95%, zero false positives on clean text |
| 5. Memory Budget | `pytest test_pii_memory.py` | Peak memory <100 MB, processing time <30s for 500 pages |
| 6. GDPR Retention | `openreview pii delete` | Mapping, audit trail, cache entry deleted |
| 7. Error Recovery | Manual run (corrupted PDF) | Partial results preserved, failed pages reported, exit code 2 |

All scenarios must pass before declaring Phase 3 complete.
