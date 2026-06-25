# Quickstart: Document Parsing Validation

**Date**: 2026-06-25
**Feature**: 002-document-parsing

## Overview

This guide shows how to validate that the document parsing system works correctly. It covers prerequisites, setup, test commands, and expected outcomes.

## Prerequisites

### System Requirements

- Python 3.12 or later
- uv package manager
- 8 GB RAM (constitutional requirement)
- 2 GB free disk space

### Dependencies

```bash
# Install all dependencies
uv sync

# Verify parsing dependencies are installed
uv run python -c "import pymupdf; import docx; import nupunkt; print('OK')"
```

### Test Fixtures

Test fixtures are synthetic PDF and DOCX files with known clause structures. They are created as part of Phase 2 implementation.

```bash
# Check if fixtures exist
ls tests/fixtures/pdf/
ls tests/fixtures/docx/
```

Expected fixtures:
- `simple_contract.pdf` — Basic NDA with clear structure
- `complex_numbering.pdf` — Contract with Article I, Section 3.1, (a)(i) numbering
- `flat_document.pdf` — Document with no headings or structure
- `multi_column.pdf` — Two-column layout
- `password_protected.pdf` — Password-protected PDF (for error testing)
- `corrupt.pdf` — Corrupt file (for error testing)
- `empty.pdf` — Empty file (for error testing)
- Similar fixtures for DOCX

## Validation Scenarios

### Scenario 1: Parse a Simple PDF

**Goal**: Verify basic PDF parsing works.

**Command**:
```bash
uv run openreview parse tests/fixtures/pdf/simple_contract.pdf
```

**Expected Output**:
```
Article I: Definitions
  Section 1.1: Confidential Information
    (a) What counts as confidential
    (b) What's excluded
  Section 1.2: Receiving Party
Article II: Obligations
  Section 2.1: Non-disclosure
  Section 2.2: Standard of care
...

Parsed 47 clauses across 12 pages in 1.23s
```

**Validation**:
- ✅ Command exits with code 0
- ✅ Output shows hierarchical structure with indentation
- ✅ Clause count is reasonable (40-60 for a simple NDA)
- ✅ Parse time is <3 seconds

---

### Scenario 2: Parse a DOCX File

**Goal**: Verify DOCX parsing produces the same structure as PDF.

**Command**:
```bash
uv run openreview parse tests/fixtures/docx/simple_contract.docx
```

**Expected Output**:
```
Article I: Definitions
  Section 1.1: Confidential Information
    (a) What counts as confidential
    (b) What's excluded
  ...

Parsed 47 clauses across 12 pages in 0.98s
```

**Validation**:
- ✅ Command exits with code 0
- ✅ Output matches PDF structure (same clause count, same hierarchy)
- ✅ Parse time is similar to PDF

---

### Scenario 3: JSON Output

**Goal**: Verify JSON output format is correct.

**Command**:
```bash
uv run openreview parse tests/fixtures/pdf/simple_contract.pdf --format json | head -50
```

**Expected Output**:
```json
[
  {
    "id": "clause-0",
    "title": "Article I: Definitions",
    "text": "This Agreement is entered into as of June 25, 2026...",
    "level": 0,
    "parent_id": null,
    "source_page": 0,
    "source_paragraph": null
  },
  {
    "id": "clause-1",
    "title": "Section 1.1: Confidential Information",
    "text": "\"Confidential Information\" means any information...",
    "level": 1,
    "parent_id": "clause-0",
    "source_page": 1,
    "source_paragraph": null
  },
  ...
]
```

**Validation**:
- ✅ Output is valid JSON (can be parsed by `jq` or `python -m json.tool`)
- ✅ Each clause has all required fields
- ✅ `parent_id` references are correct
- ✅ Clauses are in document order

---

### Scenario 4: Summary Output

**Goal**: Verify summary flag works.

**Command**:
```bash
uv run openreview parse tests/fixtures/pdf/simple_contract.pdf --summary
```

**Expected Output**:
```
Parsed 47 clauses across 12 pages in 1.23s
```

**Validation**:
- ✅ Output is a single line
- ✅ Clause count, page count, and duration are shown

---

### Scenario 5: Error Handling — File Not Found

**Goal**: Verify error handling for missing files.

**Command**:
```bash
uv run openreview parse nonexistent.pdf
```

**Expected Output**:
```
Error: No file found at 'nonexistent.pdf'.

What to do: Check the file path and try again.
```

**Validation**:
- ✅ Command exits with code 8
- ✅ Error message is clear and actionable

---

### Scenario 6: Error Handling — Password-Protected PDF

**Goal**: Verify error handling for password-protected files.

**Command**:
```bash
uv run openreview parse tests/fixtures/pdf/password_protected.pdf
```

**Expected Output**:
```
Error: This contract is password-protected.

What to do: Enter the password or provide an unlocked copy.
```

**Validation**:
- ✅ Command exits with code 8
- ✅ Error message mentions password protection

---

### Scenario 7: Error Handling — Unsupported Format

**Goal**: Verify error handling for unsupported file types.

**Command**:
```bash
uv run openreview parse document.xlsx
```

**Expected Output**:
```
Error: Format '.xlsx' is not supported. Supported: .pdf, .docx

What to do: Provide a PDF or DOCX file.
```

**Validation**:
- ✅ Command exits with code 8
- ✅ Error message lists supported formats

---

### Scenario 8: Flat Document Handling

**Goal**: Verify flat documents are split into paragraphs.

**Command**:
```bash
uv run openreview parse tests/fixtures/pdf/flat_document.pdf
```

**Expected Output**:
```
Warning: No document structure detected. Treating each paragraph as a separate clause.

clause-0: The parties agree to the following terms...
clause-1: This Agreement shall be governed by the laws of...
clause-2: Any disputes arising under this Agreement...
...

Parsed 23 clauses across 5 pages in 0.87s
```

**Validation**:
- ✅ Warning message is displayed
- ✅ Each paragraph becomes a separate clause at level 0
- ✅ Parse completes successfully

---

### Scenario 9: Multi-Column Layout

**Goal**: Verify reading order is correct for multi-column PDFs.

**Command**:
```bash
uv run openreview parse tests/fixtures/pdf/multi_column.pdf
```

**Expected Output**:
```
Left column paragraph 1...
Left column paragraph 2...
Right column paragraph 1...
Right column paragraph 2...
...
```

**Validation**:
- ✅ Text is in top-left to bottom-right reading order
- ✅ Columns are not interleaved

---

### Scenario 10: Performance — Large PDF

**Goal**: Verify memory stays under 100MB for large documents.

**Command**:
```bash
uv run python -c "
import tracemalloc
tracemalloc.start()
from openreview_cli.parsing import stream_clauses
clauses = list(stream_clauses('tests/fixtures/pdf/500_page_contract.pdf'))
current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
print(f'Peak memory: {peak / 1024 / 1024:.2f} MB')
print(f'Clauses: {len(clauses)}')
assert peak < 100 * 1024 * 1024, 'Memory exceeded 100MB!'
print('✅ Memory test passed')
"
```

**Expected Output**:
```
Peak memory: 47.23 MB
Clauses: 1247
✅ Memory test passed
```

**Validation**:
- ✅ Peak memory <100 MB
- ✅ All clauses are parsed
- ✅ No memory errors

---

### Scenario 11: Accuracy Test

**Goal**: Verify clause boundary detection accuracy ≥95%.

**Command**:
```bash
uv run pytest tests/integration/test_stream_clauses.py::test_clause_boundary_accuracy -v
```

**Expected Output**:
```
tests/integration/test_stream_clauses.py::test_clause_boundary_accuracy PASSED
```

**Validation**:
- ✅ Test passes
- ✅ Accuracy ≥95% on test fixtures

---

## Running All Tests

### Unit Tests

```bash
uv run pytest tests/unit/test_pdf_parser.py -v
uv run pytest tests/unit/test_docx_parser.py -v
uv run pytest tests/unit/test_clause_detector.py -v
```

### Integration Tests

```bash
uv run pytest tests/integration/test_parse_command.py -v
uv run pytest tests/integration/test_stream_clauses.py -v
```

### Full Test Suite

```bash
uv run pytest tests/ -v
```

### Memory Tests

```bash
uv run pytest -m memory -v
```

### Performance Tests

```bash
uv run pytest tests/benchmarks/ -v
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'pymupdf'"

**Solution**: Install dependencies with `uv sync`.

### Issue: "Memory exceeded 100MB"

**Solution**: Check that you're using streaming iteration (`for clause in stream_clauses(...)`), not collecting all clauses into a list.

### Issue: "Clause accuracy <95%"

**Solution**:
1. Check test fixtures have correct expected boundaries
2. Tune NUPunkt threshold (try `threshold=0.8` for higher precision)
3. Improve regex patterns for clause detection

### Issue: "PDF has no extractable text"

**Solution**: The PDF is image-only (scanned). Phase 2 does not support OCR. Use a text-based PDF or wait for Phase 3 (OCR support).

## Next Steps

After validating all scenarios:
1. Review test coverage: `uv run pytest --cov=openreview_cli.parsing`
2. Check type hints: `uv run mypy src/openreview_cli/parsing/`
3. Run linter: `uv run ruff check src/openreview_cli/parsing/`
4. Format code: `uv run ruff format src/openreview_cli/parsing/`
5. Run pre-commit: `uv run pre-commit run --all-files`

## References

- [spec.md](spec.md) — Feature specification
- [plan.md](plan.md) — Implementation plan
- [data-model.md](data-model.md) — Data model details
- [contracts/stream_clauses.md](contracts/stream_clauses.md) — API contract
