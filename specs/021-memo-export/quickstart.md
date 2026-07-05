# Quickstart: Memo Export Validation

**Feature**: specs/021-memo-export
**Date**: 2026-07-05
**Purpose**: Runnable scenarios that prove the memo export feature works end-to-end.

---

## Prerequisites

- Python 3.12, `uv` installed
- `uv sync` run from repo root (all deps installed)
- Test fixtures exist in `tests/fixtures/` (playbook YAML, sample PDF/DOCX)
- Review pipeline working (`openreview precheck --help` shows command)

**No new dependencies required** — `python-docx` already in `pyproject.toml`.

---

## Scenario 1 — Markdown Export (P1, FR-01/FR-02/FR-03)

**Command**:
```bash
uv run openreview precheck tests/fixtures/sample-nda.pdf \
    --playbook precheck-nda-v1 \
    --format md
```

**Expected outcome**:
- File created at `review_results/precheck-sample-nda-{timestamp}.md`
- File contains: `#` header with document name, mode, date, playbook version
- Contains a summary table with `clauses_checked`, `matches`, `differences`
- Contains per-clause sections with G/A/R badges (`✅`/`⚠️`/`❌`)
- Contains confidence bars (`[████████░░] 0.82`)
- Contains disclaimer text
- Contains recommendation (approve/revise/reject)

**Validation command**:
```bash
ls -la review_results/*.md
head -20 review_results/precheck-sample-nda-*.md
grep -c "Disclaimer" review_results/precheck-sample-nda-*.md
grep -c "✅\|⚠️\|❌" review_results/precheck-sample-nda-*.md
```

---

## Scenario 2 — JSON Export (P1, FR-01/FR-02)

**Command**:
```bash
uv run openreview dealcheck tests/fixtures/sample-merger.pdf \
    --playbook merger-v2 \
    --format json
```

**Expected outcome**:
- File created at `review_results/dealcheck-sample-merger-{timestamp}.json`
- Valid JSON parseable by `json.loads()`
- Contains keys: `memo_version`, `mode`, `document`, `playbook`, `review_date`, `overall`, `clauses`, `disclaimer`
- Each clause contains: `id`, `assessment`, `color`, `confidence`, `citation`

**Validation command**:
```bash
python3 -c "
import json
with open('review_results/dealcheck-sample-merger-*.json') as f:
    data = json.load(f)
assert data['memo_version'] == '1.0'
assert 'clauses' in data
assert len(data['clauses']) > 0
for c in data['clauses']:
    assert all(k in c for k in ['id','assessment','color','confidence','citation'])
print('JSON schema valid')
"
```

---

## Scenario 3 — DOCX Export (P2, FR-01/FR-02)

**Command**:
```bash
uv run openreview hirecheck tests/fixtures/sample-contract.docx \
    --playbook employment-v1 \
    --format docx
```

**Expected outcome**:
- File created at `review_results/hirecheck-sample-contract-{timestamp}.docx`
- Opens without error via `python-docx`
- Contains at least one table
- Contains a paragraph with disclaimer text
- Green/Amber/Red cell fill colors applied

**Validation command**:
```bash
python3 -c "
from docx import Document
import glob
doc = Document(glob.glob('review_results/hirecheck-*.docx')[0])
assert len(doc.tables) > 0, 'No tables found'
disclaimer_found = any('Disclaimer' in p.text for p in doc.paragraphs)
assert disclaimer_found, 'Disclaimer not found'
print('DOCX valid: tables=', len(doc.tables), 'paragraphs=', len(doc.paragraphs))
"
```

---

## Scenario 4 — Multiple Formats (P3, FR-11)

**Command**:
```bash
uv run openreview precheck tests/fixtures/sample-nda.pdf \
    --playbook precheck-nda-v1 \
    --format md --format json --format docx
```

**Expected outcome**:
- Three files in `review_results/` with same base name but `.md`, `.json`, `.docx` extensions
- All three files share the same timestamp in filename

**Validation command**:
```bash
ls -la review_results/precheck-sample-nda-*.md
ls -la review_results/precheck-sample-nda-*.json
ls -la review_results/precheck-sample-nda-*.docx
echo "All three formats produced"
```

---

## Scenario 5 — Custom Output Directory (P3, FR-10)

**Command**:
```bash
mkdir -p /tmp/test-memos
uv run openreview precheck tests/fixtures/sample-nda.pdf \
    --playbook precheck-nda-v1 \
    --format md \
    --output-dir /tmp/test-memos
```

**Expected outcome**:
- File written to `/tmp/test-memos/precheck-sample-nda-{timestamp}.md`
- No file written to `review_results/`

**Validation command**:
```bash
ls -la /tmp/test-memos/precheck-*.md
```

---

## Scenario 6 — Edge Cases

### 6a. Empty review results
Run review that produces no assessments. Export fails with:
```
Error: No review results to export. The review did not complete.
```

### 6b. Unsupported format
```bash
uv run openreview precheck sample.pdf --playbook nda-v1 --format pdf
```
Expected output:
```
Error: Unsupported export format: pdf. Supported formats: md, json, docx.
```

### 6c. File already exists (deduplication)
Run same export command twice. Second run produces `*-1.md` instead of overwriting.

**Validation**:
```bash
ls -la review_results/precheck-sample-nda-*.md
# Should show two files: one without suffix, one with -1
```

### 6d. Duplicate format flags
```bash
uv run openreview precheck sample.pdf --playbook nda-v1 --format md --format md
```
Expected: only one `.md` file produced (deduplication).

---

## Scenario 7 — Perfect Match (FR-12, SC-07)

Run review on a contract that perfectly matches the playbook:
```bash
uv run openreview precheck tests/fixtures/matching-nda.pdf \
    --playbook precheck-nda-v1 \
    --format md
```

**Expected**: differences section states "No differences found" rather than being omitted. Disclaimer present. Playbook version present.

---

## Test Commands (pytest)

Run the full memo export test suite:
```bash
uv run pytest tests/unit/review/test_memo_exporter.py -v
uv run pytest tests/unit/review/test_memo_formats.py -v
uv run pytest tests/unit/review/test_memo_filename.py -v
uv run pytest tests/integration/test_memo_export.py -v
uv run pytest tests/integration/test_memo_edge_cases.py -v
```

Run all memo-related tests:
```bash
uv run pytest -k "memo" -v
```

## Data Model Reference

See `specs/021-memo-export/data-model.md` for:
- `MemoFormat` enum definition
- `MemoReport`, `MemoClause`, `MemoSummary`, `MemoCitation`, `MemoTierInfo` dataclass fields
- `MemoExporter` class API
- Section assembly logic

## Contracts

No external API contracts. The memo export is a local file generation feature. Internal interfaces are documented in `data-model.md` and the source code.
