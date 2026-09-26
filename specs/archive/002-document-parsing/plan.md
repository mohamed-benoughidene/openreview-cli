# Implementation Plan: Document Parsing

**Branch**: `002-document-parsing` | **Date**: 2026-06-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-document-parsing/spec.md`

## Summary

Build a document parsing system that extracts hierarchical clause structures from PDF and DOCX contracts. The system uses NUPunkt (91.1% precision on legal text) as the primary clause boundary detection engine, with PyMuPDF for PDF streaming and python-docx for DOCX extraction. The core deliverable is a `stream_clauses(path) → Iterator[Clause]` generator that downstream pipeline stages consume without knowing the source format. A CLI command `openreview parse` wraps the generator for diagnostics.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**:
- `PyMuPDF` (fitz) ≥1.24 — PDF parsing, page-by-page streaming, font analysis, TOC extraction
- `python-docx` ≥1.1 — DOCX parsing, paragraph iteration, heading style detection
- `nupunkt` — Legal sentence/paragraph boundary detection (91.1% precision, MIT-licensed, zero runtime deps)
- `rich` ≥13 — Progress bars, terminal UI (already in project)
- `typer` ≥0.12 — CLI framework (already in project)

**Storage**: N/A — Phase 2 is in-memory streaming only. No persistent storage. Downstream phases (chunking, embedding) will use SQLite.

**Testing**: pytest ≥8.0 (already in project)

**Target Platform**: Linux, macOS, Windows (cross-platform via platformdirs)

**Project Type**: CLI tool

**Performance Goals**:
- Parse 50-page native PDF in <3 seconds
- Parse 500+ page PDF without exceeding 100MB memory
- Clause boundary detection accuracy ≥95% on synthetic contract test set

**Constraints**:
- Peak memory <100 MB (constitutional hard floor <110 MB)
- Streaming only — never load full document into memory
- Lazy imports for all parsing libraries (PyMuPDF, python-docx, nupunkt)
- No async required for parsing (synchronous generators are sufficient)

**Scale/Scope**:
- Support documents from 1 page to 500+ pages
- Handle contracts with complex numbering (Article I, Section 3.1, (a)(i), etc.)
- Support both structured documents (with headings/TOC) and flat documents (no structure)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Privacy First** | ✅ Pass | Parsing is local-only. No data leaves the machine until Phase 3 (PII stripping). No API calls in Phase 2. |
| **II. Local-First, CLI-Only** | ✅ Pass | Pure CLI tool. No web server, no daemon, no telemetry. All processing happens locally. |
| **III. Hardware-Bounded** | ✅ Pass | Streaming architecture ensures <100MB memory. Lazy imports keep startup <1s. Page-by-page processing handles any document size. |
| **IV. Dependency Minimalism** | ✅ Pass | All dependencies are justified: PyMuPDF (PDF parsing), python-docx (DOCX parsing), nupunkt (legal clause detection). No forbidden dependencies. NUPunkt has zero runtime deps. |
| **V. Spec-Driven, YAGNI** | ✅ Pass | Implementation follows spec exactly. No speculative abstractions. TDD approach ensures correctness. |

**Gate Result**: ✅ PASS — No violations.

## Project Structure

### Documentation (this feature)

```text
specs/002-document-parsing/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── stream_clauses.md
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── __init__.py
├── __main__.py
├── _version.py
├── app.py                    # Typer app, parse command
└── parsing/                  # NEW: Document parsing module
    ├── __init__.py
    ├── models.py             # Clause, Document, ParseError dataclasses
    ├── pdf_parser.py         # PyMuPDF-based PDF parser
    ├── docx_parser.py        # python-docx-based DOCX parser
    ├── clause_detector.py    # NUPunkt integration + hierarchy detection
    └── stream.py             # Unified stream_clauses() interface

tests/
├── unit/
│   ├── test_models.py
│   ├── test_pdf_parser.py
│   ├── test_docx_parser.py
│   └── test_clause_detector.py
├── integration/
│   ├── test_parse_command.py
│   └── test_stream_clauses.py
└── fixtures/
    ├── pdf/
    │   ├── simple_contract.pdf
    │   ├── complex_numbering.pdf
    │   ├── flat_document.pdf
    │   ├── multi_column.pdf
    │   ├── password_protected.pdf
    │   ├── corrupt.pdf
    │   └── empty.pdf
    └── docx/
        ├── simple_contract.docx
        ├── with_headings.docx
        ├── tracked_changes.docx
        └── flat_document.docx
```

**Structure Decision**: Single `parsing/` module under `src/openreview_cli/`. This keeps parsing logic isolated from CLI glue (`app.py`) and allows downstream phases to import the `stream_clauses` generator directly.

## Complexity Tracking

> **No violations to justify.** All dependencies are justified by the feature they enable.

## Key Technical Decisions

### 1. NUPunkt as Primary Clause Boundary Engine

**Decision**: Use NUPunkt for sentence/paragraph boundary detection, then apply custom logic to identify clause boundaries from the resulting segments.

**Rationale**: NUPunkt achieves 91.1% precision on legal text and correctly handles abbreviations (Corp., Inc., v., §). It provides `sent_spans()` for character-level positions, which we can use to map back to original document locations.

**Implementation**:
- Extract text from PDF/DOCX
- Pass to `nupunkt.sent_tokenize()` to get sentence boundaries
- Apply regex patterns to detect clause starts (Article I, Section 3.1, etc.)
- Build hierarchy from numbering patterns

**Gotcha**: NUPunkt does NOT detect clause boundaries directly — only sentence/paragraph boundaries. We need custom logic to identify where clauses start based on numbering patterns and heading detection.

### 2. PyMuPDF Streaming Pattern

**Decision**: Use `for page in doc:` iteration with `page.get_text("dict")` for structured data.

**Rationale**: PyMuPDF loads pages on demand during iteration. `get_text("dict")` provides font properties (size, bold) for heading detection and bounding boxes for spatial analysis.

**Implementation**:
```python
with pymupdf.open(pdf_path) as doc:
    for page in doc:
        data = page.get_text("dict")
        # Process blocks, lines, spans with font info
```

**Memory Management**: Context manager ensures cleanup. Pages are freed after iteration. Memory stays constant regardless of document size.

### 3. python-docx Limitation

**Decision**: Accept that python-docx loads the full document XML on `Document()` construction. Use generators to process paragraphs immediately without storing them.

**Rationale**: python-docx does NOT support true streaming. The entire XML is parsed upfront. However, `paragraphs` returns a list of lightweight wrappers, and we can yield text immediately without accumulating.

**Implementation**:
```python
def stream_docx_clauses(path):
    doc = Document(path)
    for para in doc.paragraphs:
        yield para.text  # Process immediately, don't store
```

**Mitigation**: For very large DOCX files (>10MB), we could use raw `lxml.etree.iterparse` to stream `word/document.xml`, but this adds complexity. We'll accept the python-docx limitation for Phase 2 and revisit if memory issues arise.

### 4. Heading Detection Strategy

**Decision**: Layered approach — TOC extraction (PDF) → font analysis → numbering patterns.

**Rationale**:
- PDF TOC (`get_toc()`) gives exact heading hierarchy when available (100% accurate)
- Font analysis (size, bold) catches unnumbered headings
- Numbering patterns (Article I, Section 3.1) are reliable for structured documents

**Implementation**:
- PDF: Extract TOC first, then use font analysis for headings not in TOC
- DOCX: Use `paragraph.style.name` for Heading 1/2/3, then font properties for non-styled headings
- Both: Apply regex patterns to detect numbering-based hierarchy

### 5. Reading Order

**Decision**: Use PyMuPDF's `sort=True` parameter for top-left to bottom-right ordering.

**Rationale**: Handles multi-column layouts by sorting text blocks by (y, x) coordinates. Simple and effective for most contracts.

**Implementation**: `page.get_text("dict", sort=True)` or manual sorting of blocks by bbox.

### 6. Flat Document Handling

**Decision**: Split by blank-line-separated paragraphs into sibling clauses at level 0.

**Rationale**: When no structure is detected, paragraphs are the natural semantic unit. This gives downstream stages something to work with rather than a single massive clause.

**Implementation**: Regex split on `\n\s*\n`, each paragraph becomes a clause at level 0.

## Error Handling

| Error | Detection | Exit Code | Message |
|-------|-----------|-----------|---------|
| File not found | `Path.exists()` | 8 | "No file found at '{path}'." |
| Unsupported format | Extension check | 8 | "Format '.{ext}' is not supported. Supported: .pdf, .docx" |
| Corrupt file | PyMuPDF/python-docx exception | 8 | "The file appears to be corrupt or truncated." |
| Password-protected | `doc.needs_pass` (PDF) | 8 | "This contract is password-protected." |
| Empty file | `Path.stat().st_size == 0` | 8 | "The file appears to be empty or unreadable." |
| No extractable text | All pages return empty text | 8 | "This PDF contains no extractable text. If it is a scanned document, install the OCR extension: openreview install ocr" |

## Progress Display

**Decision**: Use Rich `Progress` with `transient=True` and page-level updates.

**Implementation**:
```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

with Progress(
    SpinnerColumn(),
    TextColumn("[bold]{task.description}"),
    BarColumn(),
    TextColumn("{task.completed}/{task.total} pages"),
    transient=True,
) as progress:
    task = progress.add_task("Parsing", total=page_count)
    for page in doc:
        # Process page
        progress.advance(task)
```

**Gotcha**: For generators with unknown length, use `total=None` initially, then update when total is known (after first page or after scanning document).

## Testing Strategy

### Unit Tests
- `test_models.py`: Clause, Document, ParseError dataclass creation and validation
- `test_pdf_parser.py`: PDF parsing with various fixtures (simple, complex, flat, multi-column)
- `test_docx_parser.py`: DOCX parsing with various fixtures (simple, headings, tracked changes, flat)
- `test_clause_detector.py`: NUPunkt integration, hierarchy detection, numbering patterns

### Integration Tests
- `test_parse_command.py`: CLI command `openreview parse` with various inputs
- `test_stream_clauses.py`: Unified `stream_clauses()` interface with PDF and DOCX

### Test Fixtures
- Create synthetic PDFs and DOCX files with known clause structures
- Include edge cases: corrupt, password-protected, empty, flat, multi-column
- Hand-verify clause boundaries for ≥95% accuracy target

### TDD Workflow
1. Write integration tests first (they FAIL because no parser exists)
2. Implement parsers to make tests PASS
3. Add unit tests for individual functions
4. Refactor and optimize

## Performance Validation

### Memory Test
```python
def test_peak_memory_500_page_pdf():
    import tracemalloc
    tracemalloc.start()
    clauses = list(stream_clauses("tests/fixtures/pdf/500_page_contract.pdf"))
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 100 * 1024 * 1024  # <100MB
```

### Speed Test
```python
def test_parse_speed_50_page_pdf():
    import time
    start = time.perf_counter()
    clauses = list(stream_clauses("tests/fixtures/pdf/50_page_contract.pdf"))
    elapsed = time.perf_counter() - start
    assert elapsed < 3.0  # <3 seconds
```

### Accuracy Test
```python
def test_clause_boundary_accuracy():
    # Load test fixtures with hand-verified clause boundaries
    for fixture in test_fixtures:
        clauses = list(stream_clauses(fixture.path))
        accuracy = calculate_accuracy(clauses, fixture.expected_boundaries)
        assert accuracy >= 0.95  # ≥95%
```

## Dependencies to Add

```bash
uv add PyMuPDF python-docx nupunkt
```

**Note**: `rich` and `typer` are already in the project.

## Next Steps

After this plan is approved:
1. Run `/speckit.tasks` to break implementation into tasks
2. Run `/speckit.implement` to execute tasks with TDD workflow
3. Add test fixtures (synthetic PDFs and DOCX files)
4. Implement parsers (PDF first, then DOCX)
5. Implement `stream_clauses()` unified interface
6. Implement CLI command `openreview parse`
7. Validate performance and accuracy targets
