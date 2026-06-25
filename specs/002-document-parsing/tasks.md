---

description: "Implementation tasks for Phase 2 — Document Parsing (PDF, DOCX, hierarchical clause model)"
---

# Tasks: 002-document-parsing

**Input**: Design documents from `/specs/002-document-parsing/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [data-model.md](data-model.md), [research.md](research.md), contracts/

**Tests**: All user stories include TDD phases — write AND verify tests FAIL before implementation, then implement to PASS.

**Organization**: Tasks grouped by user story for independent implementation and testing. TDD workflow: tests fail → implementation → tests pass.

---

## Summary

| Phase | Tasks | Story | Priority | Scope |
|-------|-------|-------|----------|-------|
| Phase 1: Setup | T001–T005 | — | P0 | Module skeleton, dependencies, fixtures |
| Phase 2: Foundational | T006–T009 | — | P0 | Data models, error types, base patterns |
| Phase 3: PDF Parsing | T010–T016 | US1 | **P1 — MVP** | PDF streaming, NUPunkt, hierarchy |
| Phase 4: DOCX Parsing | T017–T022 | US2 | **P1 — MVP** | DOCX parsing, heading detection |
| Phase 5: Common Model | T023–T030 | US3 | **P1 — MVP** | `stream_clauses()`, cross-format |
| Phase 6: Error Handling | T031–T036 | US4 | P2 | Graceful errors, garbage-in |
| Phase 7: CLI Command | T037–T042 | US5 | P3 | `parse` subcommand, output formats |
| Phase 8: Polish | T043–T046 | — | P4 | Performance, accuracy, memory |
| **Total** | **46 tasks** | | | |

**MVP scope**: Phases 1–5 (US1 + US2 + US3 = all P1 stories). P2/P3 can follow incrementally.

---

## Format

- `[P]` — Can run in parallel (different files, no dependencies)
- `[US1]` etc. — Maps task to user story
- Exact file paths in descriptions
- **TDD**: Tests are separate tasks written BEFORE implementation

---

## Phase 1: Setup — Module Skeleton, Deps, Fixtures (P0)

**Purpose**: Create the parsing module structure, install dependencies, and produce test fixtures. Everything else depends on this.

**No story label** — shared infrastructure.

- [X] **T001** Create `src/openreview_cli/parsing/` package with `__init__.py` (lazy-imports `stream_clauses`), `models.py` (empty stub), `pdf_parser.py`, `docx_parser.py`, `clause_detector.py`, `stream.py`
- [X] **T002** [P] Install parsing deps: `uv add PyMuPDF python-docx nupunkt`
- [X] **T003** [P] Create `tests/fixtures/pdf/` directory with synthetic test PDFs:
  - `simple_contract.pdf` — 3-page NDA with clear Article/Section numbering
  - `complex_numbering.pdf` — mixed Article I, Section 3.1, (a), (i) numbering
  - `flat_document.pdf` — no headings, blank-line-separated paragraphs
  - `multi_column.pdf` — two-column layout with alternating clauses
  - `password_protected.pdf` — AES-128 protected, password "test123"
  - `corrupt.pdf` — truncated PDF (truncate a valid PDF's last 512 bytes)
  - `empty.pdf` — zero-byte file
  - `50_page.pdf` — synthetic 50-page contract (generated programmatically, ~25 clauses) for speed benchmark (T045)
  - `500_page.pdf` — synthetic 500-page contract (generated programmatically, ~250 clauses) for memory test (T044)
- [X] **T004** [P] Create `tests/fixtures/docx/` directory with synthetic test DOCX files:
  - `simple_contract.docx` — same content as simple_contract.pdf
  - `with_headings.docx` — Heading 1/2/3 styles with nested content
  - `tracked_changes.docx` — DOCX with `w:ins` and `w:del` tracked changes
  - `flat_document.docx` — no headings, same content as flat_document.pdf
  - `with_images.docx` — DOCX with embedded drawing/image elements between text paragraphs
- [X] **T005** Create `tests/fixtures/__init__.py` and `conftest.py` additions — shared fixture paths fixture (`fixtures_dir`) for all parsing test files

**Checkpoint**: `uv run pytest tests/ -q` passes with no parsing tests (existing tests still green). Fixtures are findable.

---

## Phase 2: Foundational — Data Models & Error Infrastructure (P0)

**Purpose**: Core data types that every parser and every story depends on. Must be complete before any US implementation.

**No story label** — blocks all user stories.

- [X] **T006** [P] [US1][US2][US3] Implement `Clause` dataclass in `src/openreview_cli/parsing/models.py`:
  - `@dataclass(slots=True)`
  - Fields: `id: str`, `title: str | None`, `text: str`, `level: int`, `parent_id: str | None`, `source_page: int | None`, `source_paragraph: int | None`, `source_span: tuple[int, int] | None`
  - `__post_init__` validates: `id` non-empty, `level >= 0`, `text` non-empty after strip, `source_page`/`source_paragraph` mutually exclusive
- [X] **T007** [P] [US1][US2][US3] Implement `Document` and `ParseError` dataclasses in `src/openreview_cli/parsing/models.py`:
  - `Document`: `source_path: Path`, `format: str` ("pdf"/"docx"), `page_count: int`, `clause_count: int`, `parse_duration_seconds: float`, `warnings: list[str]`
  - `ParseError`: `exit_code: int` (always 8), `category: str`, `message: str`, `action: str` — with `ParseErrorCategory` enum (`file_not_found`, `unsupported_format`, `corrupt`, `password_protected`, `empty`, `no_text`)
  - `__post_init__` validators for both
- [X] **T008** Write `tests/unit/test_models.py`:
  - Clause construction and validation (valid cases, invalid level, empty text, conflicting source fields)
  - Verify Clause uses `@dataclass(slots=True)` — assert `TypeError` when assigning undeclared attribute
  - Document construction and validation (valid cases, invalid format, page_count < 1)
  - ParseError construction with every category, exit_code enforcement
  - Mutually exclusive source_page / source_paragraph
- [X] **T009** [P] Create `src/openreview_cli/parsing/__init__.py` with lazy-import `stream_clauses` and public API surface (`Clause`, `Document`, `ParseError`, `ParseErrorCategory`)

**Checkpoint**: `uv run pytest tests/unit/test_models.py -q` passes. Models can be imported from `openreview_cli.parsing`.

---

## Phase 3: US1 — Parse a PDF Contract 🎯 MVP (P1)

**Goal**: Stream a native PDF page-by-page, detect clauses via NUPunkt + numbering patterns, yield hierarchical clauses. <100MB memory, <3s for 50 pages.

**Independent Test**: `openreview parse tests/fixtures/pdf/simple_contract.pdf` prints the correct hierarchical outline.

### Tests for US1 ⚠️ Write FIRST — MUST FAIL

- [X] **T010** [P] [US1] Write `tests/unit/test_pdf_parser.py`:
  - Unit tests for `extract_page_text()` — extracts text with `sort=True`, preserves reading order
  - Unit tests for `detect_headings_from_toc()` — `doc.get_toc()` maps to clause hierarchy
  - Unit tests for `extract_font_properties()` — bold/size detection from span flags
  - Unit tests for `detect_numbering_pattern()` — regex patterns for Article/Section/decimal/letter/roman
  - All tests MUST FAIL (import error) before implementation
- [X] **T011** [P] [US1] Write `tests/integration/test_pdf_parser.py`:
  - Parse `simple_contract.pdf` → verify 3+ clauses with correct hierarchy (level 0 = Article, level 1 = Section)
  - Parse `complex_numbering.pdf` → verify 10+ clauses with mixed numbering conventions
  - Parse `flat_document.pdf` → verify paragraph-level clauses at level 0, assert warning "No document structure detected. Treating each paragraph as a separate clause."
  - Parse `multi_column.pdf` → verify correct top-left→bottom-right reading order across columns
  - Parse `password_protected.pdf` → verify `ParseError` with `password_protected` category
  - Parse `corrupt.pdf` → verify `ParseError` with `corrupt` category
  - Parse `empty.pdf` → verify `ParseError` with `empty` category
  - Ctrl+C during parse → verify clean exit, context manager closed, no partial output, no temp files
  - All tests MUST FAIL (import error or NotImplementedError) before implementation

### Implementation for US1

- [X] **T012** [US1] Implement `PdfParser` class in `src/openreview_cli/parsing/pdf_parser.py`:
  - `__init__(path: Path)` — lazy import `pymupdf`, validate path exists, detect password
  - `parse() -> Iterator[Clause]` — context-managed `pymupdf.open()`, `for page in doc:` streaming
  - `page.get_text("dict", sort=True)` for structured text + font info
  - Page-level progress via Rich `Progress` with `transient=True`
  - Track `source_page` (0-indexed) on each clause
  - Handle password-protected PDFs: `doc.needs_pass` → prompt or `ParseError`
  - Handle no-extractable-text PDFs: all pages empty → `ParseError("no_text")`
  - Handle image-only pages: skip non-text blocks silently
  - Handle Ctrl+C: clean context manager exit, no partial output
  - Lazy import: `import pymupdf` only inside `__init__` or `parse`
- [X] **T013** [US1] Implement `clause_detector.py` in `src/openreview_cli/parsing/clause_detector.py`:
  - `nupunkt_detect_boundaries(text: str) -> list[tuple[int, int]]` — primary engine via `nupunkt.sent_spans()`
  - `detect_clause_starts(text: str) -> list[int]` — regex patterns for Article/Section/decimal/letter/roman starts
  - `build_hierarchy(spans: list[tuple[int, int]], headings: list[tuple[int, str, int]]) -> list[Clause]` — numbering pattern → level mapping, parent_id resolution
  - NUPunkt loaded lazily (first call caches model reference)
  - Flat document fallback: split by blank-line-separated paragraphs, all level 0, emit warning
- [X] **T014** [US1] Wire PDF parser → clause detector in `src/openreview_cli/parsing/pdf_parser.py`:
  - `PdfParser.parse()` calls `nupunkt_detect_boundaries()` on page text
  - Calls `detect_clause_starts()` to find clause boundaries
  - Calls `build_hierarchy()` to produce `Clause` instances
  - TOC extraction (`doc.get_toc()`) feeds heading hierarchy (supplementary to NUPunkt)
  - Font analysis (size, bold) as supplementary signal for unnumbered headings
  - Yields each clause immediately via generator
- [X] **T015** [US1] Add page-level progress bar to `PdfParser.parse()`:
  - Rich `Progress` with `SpinnerColumn`, `TextColumn`, `BarColumn`, page counter
  - `transient=True` — progress disappears after completion
  - Unknown total: use pulsing animation until page count known (after first page iteration or doc.page_count)
  - Wrap PDF iteration with progress advancement
- [X] **T016** [US1] Make tests pass:
  - Run `pytest tests/unit/test_pdf_parser.py -q` — all pass
  - Run `pytest tests/integration/test_pdf_parser.py -q` — all pass
  - Fix any failures before moving on

**Checkpoint**: All US1 tests pass. `list(stream_clauses("tests/fixtures/pdf/simple_contract.pdf"))` yields correct clauses.

---

## Phase 4: US2 — Parse a DOCX Contract 🎯 MVP (P1)

**Goal**: Parse a DOCX contract with heading detection, lazy paragraph iteration, flat-document fallback. Output matches the PDF parser's clause model.

**Independent Test**: `openreview parse tests/fixtures/docx/simple_contract.docx` produces the same clause structure as the PDF version.

### Tests for US2 ⚠️ Write FIRST — MUST FAIL

- [X] **T017** [P] [US2] Write `tests/unit/test_docx_parser.py`:
  - Unit tests for `get_heading_level()` — Heading 1→0, Heading 2→1, None→-1
  - Unit tests for `detect_tracked_changes()` — detects `w:ins` and `w:del` in tracked_changes fixture
  - Unit tests for `skip_embedded_images()` — paragraph with drawing element skipped
  - Unit tests for paragraph → clause mapping (source_paragraph indexing)
  - All MUST FAIL before implementation
- [X] **T018** [P] [US2] Write `tests/integration/test_docx_parser.py`:
  - Parse `simple_contract.docx` → verify clauses match the PDF equivalent structure
  - Parse `with_headings.docx` → verify Heading 1→level 0, Heading 2→level 1, heading text becomes clause title
  - Parse `flat_document.docx` → verify paragraph-level clauses at level 0, assert warning "No document structure detected. Treating each paragraph as a separate clause."
  - Parse `with_headings.docx` with embedded image → verify image paragraphs are skipped silently, clause count matches expected
  - Ctrl+C during parse → verify clean exit, no partial output
  - All MUST FAIL before implementation

### Implementation for US2

- [X] **T019** [US2] Implement `DocxParser` class in `src/openreview_cli/parsing/docx_parser.py`:
  - `__init__(path: Path)` — lazy import `docx`, validate path
  - `parse() -> Iterator[Clause]` — `Document(path)`, iterate `doc.paragraphs`
  - Track `source_paragraph` (0-indexed) on each clause
  - Accept python-docx limitation: full XML loaded on `Document()` construction
  - Handle Ctrl+C: yield nothing, exit cleanly
  - Yield text immediately per paragraph (no accumulation)
  - Lazy import: `from docx import Document` only inside `__init__` or `parse`
- [X] **T020** [US2] Implement DOCX heading detection in `docx_parser.py`:
  - `paragraph.style.name.startswith("Heading ")` → level extraction (`int(name.split()[-1])`)
  - Font analysis fallback for non-styled headings: `run.bold`, `run.font.size`
  - Heading text becomes clause `title`, body text is appended to current clause `text`
  - Numbering pattern regex as supplementary signal
- [X] **T021** [US2] Implement DOCX tracked-changes detection in `docx_parser.py`:
  - Raw XML via `lxml` — check `body.iter(f"{{{ns}}}ins")` and `body.iter(f"{{{ns}}}del")`
  - Emit warning: `"This document contains tracked changes. The review may be inaccurate"`
  - Continue parsing normally (tracked changes not rendered in extracted text per python-docx default)
- [X] **T022** [US2] Implement DOCX clause detection via `clause_detector.py`:
  - Reuse `nupunkt_detect_boundaries()`, `detect_clause_starts()`, `build_hierarchy()` from T013
  - DOCX heading styles + numbering patterns feed hierarchy builder
  - Flat document fallback: same blank-line-split logic as PDF parser
  - Make tests pass: `pytest tests/unit/test_docx_parser.py` and `tests/integration/test_docx_parser.py`

**Checkpoint**: PDF and DOCX parsers each produce clause streams independently. Tests pass.

---

## Phase 5: US3 — Common Document Model 🎯 MVP (P1)

**Goal**: Unified `stream_clauses(path) -> Iterator[Clause]` generator routes to the correct parser. PDF and DOCX produce equivalent hierarchical output (same clause count ±10%, same nesting).

**Independent Test**: Parse the same contract in both `.pdf` and `.docx` formats → compare clause counts, levels, parent relationships.

### Tests for US3 ⚠️ Write FIRST — MUST FAIL

- [X] **T023** [P] [US3] Write `tests/integration/test_stream_clauses.py`:
  - `stream_clauses(path)` routes to `PdfParser` for `.pdf`, `DocxParser` for `.docx`
  - `stream_clauses(path)` raises `ParseError` for unsupported format
  - `stream_clauses(path)` raises `ParseError` for non-existent path
  - Cross-format equivalence: `simple_contract.pdf` vs `simple_contract.docx` — same clause count (±10%), same nesting levels
  - Cross-format equivalence: `flat_document.pdf` vs `flat_document.docx` — same clause count, all level 0
  - All MUST FAIL
- [X] **T024** [US3] Write cross-format hierarchy equivalence test:
  - Compare parent-child relationships across PDF and DOCX versions of same contract
  - Verify `parent_id` chain integrity (no dangling parent references)
  - Verify document `warnings` list matches across formats
  - MUST FAIL

### Implementation for US3

- [X] **T025** [US3] Implement `stream_clauses()` in `src/openreview_cli/parsing/stream.py`:
  - `stream_clauses(path: str | Path) -> Iterator[Clause]` — format detection via file extension
  - `.pdf` → lazy-import `PdfParser`, yield from `PdfParser(path).parse()`
  - `.docx` → lazy-import `DocxParser`, yield from `DocxParser(path).parse()`
  - Any other extension → raise `ParseError("unsupported_format")`
  - Non-existent path → raise `ParseError("file_not_found")`
  - Wrap all exceptions from parsers into `ParseError` with appropriate category
  - Include document metadata in a `Document` namedtuple sent as the first yielded value (or via a separate `parse_document(path) -> tuple[Document, list[Clause]]` helper)
- [X] **T026** [US3] Implement `parse_document()` helper in `src/openreview_cli/parsing/stream.py`:
  - `parse_document(path) -> tuple[Document, list[Clause]]` — collect all clauses, measure duration, build Document
  - Lazy import: only import needed parser based on file extension
  - Return `Document` metadata + clause list
- [X] **T027** [US3] Implement non-English text detection in `clause_detector.py`:
  - Unicode-range heuristic: detect Arabic (`\u0600-\u06FF`), CJK (`\u4E00-\u9FFF`), Cyrillic (`\u0400-\u04FF`)
  - Emit warning: `"The contract appears to be in {language}. Results may be less accurate"`
  - Zero dependencies (pure Unicode range checks)
  - Embedded font rendering issue detection: check for replacement character `\uFFFD` (tofu) in extracted text
- [X] **T028** [US3] Implement embedded-font warning in `clause_detector.py`:
  - Scan extracted text for `\uFFFD` (replacement character, aka tofu)
  - Emit warning: `"Some text could not be read correctly. Results may contain errors"`
- [X] **T029** [US3] Add `stream_clauses()` to `__init__.py` public API:
  - `__all__` exports: `stream_clauses`, `parse_document`, `Clause`, `Document`, `ParseError`, `ParseErrorCategory`
- [X] **T030** [US3] Make all tests pass:
  - `pytest tests/integration/test_stream_clauses.py -q` — all pass
  - Cross-format equivalence verified

**Checkpoint**: `stream_clauses()` handles PDF and DOCX transparently. P1 MVP complete. All P1 tests green.

---

## Phase 6: US4 — Handle Malformed Documents Gracefully (P2)

**Goal**: Every garbage-in scenario produces a clear `ParseError` with exit code 8. No crashes, no hangs, no cryptic tracebacks.

**Independent Test**: `openreview parse` on each malformed fixture (corrupt, password-protected, empty, unsupported extension) → correct error message and exit code 8.

### Tests for US4 ⚠️ Write FIRST — MUST FAIL

- [X] **T031** [P] [US4] Write `tests/integration/test_error_handling.py`:
  - Corrupt PDF → `ParseError("corrupt")` with message "The file appears to be corrupt or truncated."
  - Password-protected PDF (non-interactive) → `ParseError("password_protected")` with message and action
  - Empty file (0 bytes) → `ParseError("empty")` with message "The file appears to be empty or unreadable."
  - Unsupported format (.xlsx) → `ParseError("unsupported_format")` with message listing supported formats
  - Non-existent path → `ParseError("file_not_found")` with message "No file found at..."
  - No-extractable-text PDF (image-only) → `ParseError("no_text")` with OCR suggestion
  - All error categories yield `exit_code == 8`
  - All MUST FAIL
- [X] **T032** [US4] Write `tests/integration/test_warnings.py`:
  - DOCX with tracked changes → warning emitted, parsing continues
  - Document with non-Latin script → warning with detected language, parsing continues
  - Flat document (no headings) → warning "No document structure detected...", all clauses at level 0
  - Text with tofu characters → warning "Some text could not be read correctly..."
  - All MUST FAIL

### Implementation for US4

- [X] **T033** [US4] Implement error handling in `stream.py`:
  - Wrap `PdfParser.parse()` and `DocxParser.parse()` calls in try/except
  - Catch `pymupdf.FileDataError` → `ParseError("corrupt")`
  - Catch generic exceptions → `ParseError("corrupt")` with details
  - File-not-found check before parser creation
  - Unsupported-format check before parser creation
  - Empty-file check via `Path.stat().st_size == 0`
- [X] **T034** [US4] Implement password prompt in `pdf_parser.py`:
  - `doc.needs_pass` → check for `OPENREVIEW_PDF_PASSWORD` env var first
  - If env var set, call `doc.authenticate(password)` directly
  - If no env var and interactive (`sys.stdin.isatty()`), prompt via `getpass.getpass()`
  - If no env var and non-interactive, raise `ParseError("password_protected")`
  - Handle wrong password → retry or error
- [X] **T035** [US4] Implement image-only PDF detection in `pdf_parser.py`:
  - After streaming all pages, if no text found → raise `ParseError("no_text")`
  - Message: "This PDF contains no extractable text. If it is a scanned document, install the OCR extension: openreview install ocr"
  - Check is deferred until after page iteration (not upfront) to maintain streaming
- [X] **T036** [US4] Make all error-handling tests pass:
  - `pytest tests/integration/test_error_handling.py tests/integration/test_warnings.py -q` — all pass

**Checkpoint**: Every malformed document produces a sensible error or warning. Exit code always 8 for fatal errors.

---

## Phase 7: US5 — Parse Command with Output Options (P3)

**Goal**: `openreview parse <path>` CLI command with `--format text|json` and `--summary` flags.

**Independent Test**: `openreview parse contract.pdf --format json | python -m json.tool` validates JSON output.

### Tests for US5 ⚠️ Write FIRST — MUST FAIL

- [X] **T037** [P] [US5] Write `tests/integration/test_parse_command.py`:
  - `openreview parse` without path → exits with help message
  - `openreview parse tests/fixtures/pdf/simple_contract.pdf` → prints indented hierarchical outline
  - `openreview parse tests/fixtures/pdf/simple_contract.pdf --format json` → valid JSON with flat array of clause objects, each with `parent_id`
  - `openreview parse tests/fixtures/pdf/simple_contract.pdf --summary` → single line: "Parsed N clauses across M pages in T.TTs"
  - Error cases via CLI: non-existent file, unsupported format → exit code 8, error message to stderr
  - All MUST FAIL

### Implementation for US5

- [X] **T038** [US5] Add `parse` command to `src/openreview_cli/app.py`:
  - `openreview parse <path>` via `typer.Argument`
  - `--format` option: `typer.Option("text", "--format", help="Output format")` with values `text` and `json`
  - `--summary` option: `typer.Option(False, "--summary", help="Show one-line summary")`
  - Wraps `stream_clauses()` (or `parse_document()`) from `parsing/stream.py`
  - Lazy imports: `from openreview_cli.parsing import stream_clauses, parse_document` inside the command
  - Error handling: catch `ParseError`, print message to stderr, `raise typer.Exit(code=8)`
  - Progress bar displayed during parse, cleared on completion
- [X] **T039** [US5] Implement text formatter in `src/openreview_cli/parsing/stream.py` or a new `formatter.py`:
  - `format_text(clauses: list[Clause]) -> str` — indented outline:
    ```
    clause-5  Section 3.1: Confidentiality
      (page 3) The Receiving Party shall not disclose...

    clause-6  (a) Exclusions
      (page 3) Confidential Information does not include...
    ```
  - Indentation: 2 spaces per level
  - Show page number for PDF, paragraph number for DOCX
  - Truncate long clause text to first 200 chars for readability (full text in JSON mode)
- [X] **T040** [US5] Implement JSON formatter:
  - `format_json(clauses: list[Clause]) -> str` — flat array of clause dicts:
    ```json
    [
      {"id": "clause-0", "title": "Article I: Definitions", "text": "...", "level": 0, "parent_id": null, "source_page": 1, "source_paragraph": null},
      {"id": "clause-1", "title": "Section 1.1", "text": "...", "level": 1, "parent_id": "clause-0", "source_page": 1, "source_paragraph": null}
    ]
    ```
  - `json.dumps(indent=2, ensure_ascii=False)`
- [X] **T041** [US5] Implement summary formatter:
  - `format_summary(doc: Document) -> str` — single line:
    `"Parsed {doc.clause_count} clauses across {doc.page_count} pages in {doc.parse_duration_seconds:.2f}s"`
- [X] **T042** [US5] Make CLI tests pass:
  - `pytest tests/integration/test_parse_command.py -q` — all pass
  - Manual smoke test: `uv run openreview parse tests/fixtures/pdf/simple_contract.pdf --format json`

**Checkpoint**: `openreview parse` works end-to-end with all three output modes.

---

## Phase 8: Polish — Performance, Accuracy, Memory (P4)

**Purpose**: Validate that the P1/P2/P3 implementations meet the hard constraints from the spec and constitution.

- [X] **T043** Write `tests/unit/test_clause_detector.py` for remaining unit coverage:
  - NUPunkt boundary detection (mock or small text sample)
  - Numbering pattern detection (all patterns: Article, Section, decimal, letter, roman)
  - Hierarchy construction with parent_id resolution
  - Flat-document fallback (blank-line split)
  - Non-English detection via Unicode ranges
  - Tofu character detection
- [X] **T044** Implement memory budget test (`@pytest.mark.memory`):
  - Parse a synthetic 500-page PDF fixture (generated programmatically)
  - Use `tracemalloc` or `memory_tracker` fixture from `conftest.py`
  - Assert peak < 100 MB (constitutional floor: <110 MB)
  - Mark with `@pytest.mark.memory` so it runs in the `memory` CI job
- [X] **T045** Implement speed benchmark test:
  - Parse a 50-page PDF fixture
  - Assert elapsed < 3.0 seconds
  - Use `time.perf_counter()` for precision
  - Mark with `@pytest.mark.benchmark`
- [X] **T046** Implement clause boundary accuracy test:
  - Load all test fixtures with hand-verified clause boundary ground truth
  - Calculate accuracy: correct_boundaries / total_boundaries
  - Assert ≥ 0.95 (95% minimum)
  - Report per-fixture accuracy for diagnostics
  - Mark with `@pytest.mark.accuracy`

**Checkpoint**: All performance constraints verified. Clause accuracy ≥95%.

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup ─────────────────────────────────────────────────┐
        │                                                        │
        ▼                                                        │
Phase 2: Foundational ── BLOCKS all user stories ───────────────┤
        │                                                        │
        ├─────────────────────────────┬──────────────────┐       │
        ▼                             ▼                  ▼       │
Phase 3: US1 (PDF) ── P1 MVP   Phase 4: US2 (DOCX) ── P1   Phase 5: US3 (Common) ── P1
        │                             │                  │
        └──────────────────┬──────────┘                  │
                           │ (US3 depends on US1 + US2) │
                           ▼                             │
                     Phase 5: US3 (Common Model) ◄──────┘
                           │
                           ▼
              MVP COMPLETE — Phases 1–5 (all P1 stories)
                           │
                           ▼
                     Phase 6: US4 (Error Handling) ── P2
                           │
                           ▼
                     Phase 7: US5 (CLI Command) ── P3
                           │
                           ▼
                     Phase 8: Polish ── P4
```

- **Setup (Phase 1)**: No dependencies. Can start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **US1 + US2 (Phases 3–4)**: Can proceed in parallel after Foundational. No cross-dependency.
- **US3 (Phase 5)**: Depends on both US1 and US2 (needs both parsers working for cross-format equivalence).
- **US4 (Phase 6)**: Depends on US3 (needs `stream_clauses()` wrapper). Can start after Phase 5.
- **US5 (Phase 7)**: Depends on US3 + US4 (needs `stream_clauses()` + error handling).
- **Polish (Phase 8)**: Depends on all user stories being complete.

### Within Each User Story

- Tests written and FAIL before any implementation
- Core logic (parser class) before integration (formatters, CLI)
- Unit tests before integration tests
- Story complete → move to next priority

---

## Parallel Execution Examples

```bash
# Phase 1 — create module + install deps + fixtures in parallel:
T002: uv add PyMuPDF python-docx nupunkt
T003: create tests/fixtures/pdf/*.pdf fixtures
T004: create tests/fixtures/docx/*.docx fixtures

# Phase 2 — models created in parallel:
T006: Clause dataclass
T007: Document + ParseError dataclasses

# Phases 3–4 — US1 and US2 can proceed in parallel:
# Developer A: T010 → T011 → T012 → T013 → T014 → T015 → T016
# Developer B: T017 → T018 → T019 → T020 → T021 → T022

# Phase 5 — test files in parallel:
T023: test_stream_clauses.py
T024: cross-format equivalence

# Phase 6 — test files in parallel:
T031: test_error_handling.py
T032: test_warnings.py

# Phase 7 — test + implementation in parallel files:
T037: test_parse_command.py (test)
T038: app.py (parse command)
T039: formatter.py (text output)
T040: formatter.py (JSON output)

# Phase 8 — all performance tests in parallel (marked differently):
T043: test_clause_detector.py
T044: memory test (--mark memory)
T045: speed benchmark
T046: accuracy test
```

---

## Implementation Strategy

### MVP First (Phases 1–5: US1 + US2 + US3 = All P1)

1. Complete Phase 1: Setup — module skeleton, deps, fixtures
2. Complete Phase 2: Foundational — models (CRITICAL — blocks everything)
3. Complete Phase 3: US1 — PDF parser with clause detection
4. Complete Phase 4: US2 — DOCX parser with clause detection (parallel with US1 if staffed)
5. Complete Phase 5: US3 — `stream_clauses()` unified interface + cross-format equivalence
6. **STOP and VALIDATE**: All P1 tests green, `openreview parse` works for PDF and DOCX
7. Deploy/demo if ready

### Incremental Delivery

1. MVP (Phases 1–5) → PDF + DOCX parsing with unified clause model → Demo
2. Add US4 (Phase 6) → Robust error handling → Demo
3. Add US5 (Phase 7) → CLI output formats → Demo
4. Polish (Phase 8) → Performance validation → Release

---

## Task Count by User Story

| User Story | Priority | Phases | Tasks | Independent? |
|-----------|----------|--------|-------|------------|
| Setup | P0 | 1 | 5 | — |
| Foundational | P0 | 2 | 4 | — |
| US1: PDF Parsing | **P1 MVP** | 3 | 7 | Yes — standalone tests with PDF fixtures |
| US2: DOCX Parsing | **P1 MVP** | 4 | 6 | Yes — standalone tests with DOCX fixtures |
| US3: Common Model | **P1 MVP** | 5 | 8 | No — depends on US1 + US2 |
| US4: Error Handling | P2 | 6 | 6 | Yes — standalone tests with garbage-in fixtures |
| US5: CLI Command | P3 | 7 | 6 | Yes — standalone CLI tests |
| Polish | P4 | 8 | 4 | No — depends on all stories |
| **Total** | | | **46** | |

---

## Notes

- [P] tasks = different files, no dependencies
- [US1] etc. = user story label for traceability
- TDD: tests MUST fail before implementation, then MUST pass after
- Each user story independently completable and testable (except US3)
- Commit after each task or logical group
- Stop at any checkpoint to validate or demo
- Lazy imports for ALL parsing libraries (`pymupdf`, `docx`, `nupunkt`) — loaded only when the relevant parser is invoked
