# Feature Specification: Document Parsing

**Feature Branch**: `002-document-parsing`

**Created**: 2026-06-25

**Status**: Draft

**Input**: User description: "Phase 2 from build order roadmap: PDF parser (PyMuPDF, page-by-page streaming), DOCX parser (python-docx), hierarchical document model. TDD approach — tests first to verify parsing works per TestingStrategy.md"

## Clarifications

### Session 2026-06-25

- Q: Should scanned PDF OCR (Docling) be included in Phase 2? → A: No — defer to a later phase. Phase 2 covers native PDF and DOCX only. PDFs with no extractable text get a clear error message.
- Q: What is the clause segmentation accuracy target? → A: ≥95% — measured against the 75 synthetic contracts with hand-verified ground truth.
- Q: What scope should clause IDs use? → A: Within-document unique (e.g., "clause-1", "clause-2" per document).
- Q: Should there be hard size limits for large documents? → A: No — streaming handles any size at constant memory. Always show page-level progress bar during parsing.
- Q: How should flat documents with no detectable structure be handled? → A: Each paragraph (blank-line-separated block) becomes a sibling clause at level 0, with a warning.
- Q: What shape should `--format json` output take? → A: Flat array of clause objects with `parent_id` field encoding nesting (flat, not nested tree).
- Q: What defines "equivalent hierarchical output" for PDF vs DOCX (SC-005)? → A: Structure + threshold — same clause count within ±10%, same hierarchy. Text compared positionally, not byte-identically.
- Q: When are test fixtures created? → A: Part of Phase 2, written alongside tests and committed together.
- Q: Should Phase 2 build only the CLI command or also the internal API? → A: Internal `stream_clauses(path) → Iterator[Clause]` generator is the core deliverable. `openreview parse` CLI command wraps it for diagnostics.
- Q: Where should parsing code live in the package? → A: `src/openreview_cli/parsing/` module.
- Q: What clause boundary detection strategy should be used? → A: NUPunkt as the primary engine (zero deps, MIT, 91.1% precision on legal text). PDF TOC extraction (`get_toc()`) validates headings when available. Font analysis (size/bold) and numbering patterns serve as supplementary tiebreakers. CharBoundary dropped entirely — NUPunkt alone covers the need.
- Q: How do DOCX heading styles map to hierarchy levels? → A: Direct 1:1 — Heading 1 → level 0, Heading 2 → level 1, etc.
- Q: What is the reading order guarantee within a page? → A: `sort=True` (top-left to bottom-right coordinates) via PyMuPDF's built-in sorting.
- Q: How should non-English text be detected? → A: Character-set heuristic — detect non-Latin scripts (Arabic, CJK, Cyrillic) via Unicode ranges. Zero deps.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Parse a PDF Contract (Priority: P1)

A lawyer has a contract in PDF format and wants to extract its structure — sections, clauses, sub-clauses — so that downstream stages (PII stripping, chunking, comparison) can work with it. They run a single command and see the document's hierarchical structure printed to the terminal. The parser reads the PDF page-by-page, never loading the full document into memory, and yields one clause at a time.

**Why this priority**: PDF is the most common contract format. Without PDF parsing, no review can run. This is the foundation for all downstream pipeline stages.

**Independent Test**: Can be fully tested by running `openreview parse contract.pdf` on a known test PDF and verifying the output contains the expected sections, clauses, and hierarchy.

**Acceptance Scenarios**:

1. **Given** a valid native PDF contract exists at a known path, **When** the user runs `openreview parse contract.pdf`, **Then** the system outputs the document's hierarchical structure (sections, clauses, sub-clauses with their text and nesting level)
2. **Given** a 50-page PDF contract, **When** the user runs `openreview parse contract.pdf`, **Then** the system completes parsing in under 3 seconds on the reference hardware (8 GB RAM, 2-core CPU)
3. **Given** a PDF contract is being parsed, **When** parsing is in progress, **Then** peak memory usage stays under 100 MB (the parser streams page-by-page, never loading the full document)
4. **Given** a PDF contract with numbered sections (e.g., "Section 3.1", "3.1(a)", "Article III"), **When** parsed, **Then** the hierarchy correctly reflects the nesting: Article → Section → Sub-section → Clause

---

### User Story 2 - Parse a DOCX Contract (Priority: P1)

A lawyer receives a contract as a Word document (.docx) and wants to extract its structure the same way as a PDF. The parser iterates paragraphs lazily, identifying headings, numbered clauses, and body text to build the same hierarchical document model.

**Why this priority**: DOCX is the second most common contract format, especially for drafts and negotiations. Lawyers frequently receive contracts in Word format.

**Independent Test**: Can be fully tested by running `openreview parse contract.docx` on a known test DOCX and verifying the output matches the expected hierarchy.

**Acceptance Scenarios**:

1. **Given** a valid DOCX contract exists at a known path, **When** the user runs `openreview parse contract.docx`, **Then** the system outputs the document's hierarchical structure matching the PDF output format
2. **Given** a DOCX contract with Word heading styles (Heading 1, Heading 2, etc.), **When** parsed, **Then** the hierarchy correctly maps heading levels to the document tree
3. **Given** a DOCX contract with numbered paragraphs (1., 1.1, 1.1(a)), **When** parsed, **Then** the hierarchy correctly reflects the numbering-based nesting
4. **Given** a DOCX contract, **When** parsed, **Then** only the current paragraph object lives in memory at any time (lazy iteration)

---

### User Story 3 - Common Document Model (Priority: P1)

A downstream stage (PII stripping, chunking, or comparison) receives parsed clauses from either a PDF or DOCX source and processes them identically. The consumer never needs to know which parser produced the data. Every clause carries its position in the hierarchy, its text, and its location in the source document.

**Why this priority**: The entire pipeline depends on a uniform document model. If PDF and DOCX produce different output structures, every downstream stage needs format-specific code — doubling the work and the bug surface.

**Independent Test**: Can be tested by parsing the same contract in both PDF and DOCX format and verifying both produce identical hierarchical structures (same clause count, same nesting, same text content).

**Acceptance Scenarios**:

1. **Given** the same contract exists in both PDF and DOCX format, **When** both are parsed, **Then** both produce the same hierarchical structure (same number of clauses, same nesting levels, equivalent text content)
2. **Given** a parsed clause from any parser, **When** a downstream stage processes it, **Then** the clause provides: unique identifier, title/heading, full text, hierarchy level, parent reference, and source location (page number or paragraph index)
3. **Given** a parsed document, **When** clauses are streamed one at a time, **Then** each clause is yielded exactly once and in document order (top to bottom, left to right)

---

### User Story 4 - Handle Malformed Documents Gracefully (Priority: P2)

A lawyer uploads a document that is corrupt, password-protected, empty, or in an unsupported format. The system detects the problem, displays a clear error message with guidance on what to do, and exits with the appropriate error code — it never crashes or hangs.

**Why this priority**: Lawyers encounter malformed documents regularly. The tool must fail gracefully with actionable messages rather than cryptic errors or frozen screens.

**Independent Test**: Can be tested by running `openreview parse` on each type of malformed document in the "Garbage In" collection and verifying the correct error message and exit code.

**Acceptance Scenarios**:

1. **Given** a corrupt PDF file, **When** the user runs `openreview parse corrupt.pdf`, **Then** the system exits with code 8 and displays: "The file appears to be corrupt or truncated. What to do: Get a clean copy of the contract"
2. **Given** a password-protected PDF, **When** the user runs `openreview parse protected.pdf`, **Then** the system prompts for the password (interactive mode) or exits with code 8 and a clear message (non-interactive mode)
3. **Given** an empty file (0 bytes), **When** the user runs `openreview parse empty.pdf`, **Then** the system exits with code 8 and displays: "The file appears to be empty or unreadable"
4. **Given** a file with an unsupported extension (e.g., .xlsx, .rtf), **When** the user runs `openreview parse file.xlsx`, **Then** the system exits with code 8 and displays: "Format '.xlsx' is not supported. Supported: .pdf, .docx"
5. **Given** a DOCX with tracked changes and comments, **When** parsed, **Then** the system displays a warning: "This document contains tracked changes. The review may be inaccurate" and continues parsing
6. **Given** a document in a non-English language, **When** parsed, **Then** the system displays a warning: "The contract appears to be in {language}. Results may be less accurate" and continues parsing

---

### User Story 5 - Parse Command with Output Options (Priority: P3)

A lawyer wants to parse a document and see the output in different formats — a human-readable summary for quick inspection, or a structured format (JSON) for piping into other tools or scripts.

**Why this priority**: Output flexibility is useful for debugging and integration but not blocking for Phase 2. The default human-readable output is sufficient for initial testing.

**Independent Test**: Can be tested by running `openreview parse contract.pdf --format json` and verifying valid JSON output with the expected structure.

**Acceptance Scenarios**:

1. **Given** a valid contract, **When** the user runs `openreview parse contract.pdf` (default format), **Then** the system displays a human-readable hierarchical outline of the document (indented sections and clauses)
2. **Given** a valid contract, **When** the user runs `openreview parse contract.pdf --format json`, **Then** the system outputs valid JSON as a flat array of clause objects with `parent_id` references for nesting
3. **Given** a valid contract, **When** the user runs `openreview parse contract.pdf --summary`, **Then** the system displays a one-line summary: "Parsed {n} clauses across {m} pages in {t}s"

---

### Edge Cases

- What happens when a PDF has embedded fonts that render as boxes (tofu characters)? The system warns: "Some text could not be read correctly. Results may contain errors" and continues with best-effort extraction.
- What happens when a 1MB file contains a single clause repeated 10,000 times? The system parses it without exceeding the memory budget — streaming handles repetition without accumulation.
- What happens when a PDF has no extractable text (image-only, not scanned OCR)? The system exits with code 8: "This PDF contains no extractable text. If it is a scanned document, install the OCR extension: openreview install ocr"
- What happens when a DOCX has embedded images or OLE objects? The system skips non-text content silently — only text paragraphs contribute to the clause stream.
- What happens when parsing is interrupted mid-document (Ctrl+C)? The system exits cleanly, no partial output is written, no temporary files are left behind.
- What happens when a contract has no recognizable section structure (flat text, no headings)? The system splits by blank-line-separated paragraphs into sibling clauses at level 0 and warns: "No document structure detected. Treating each paragraph as a separate clause."
- What happens when a PDF has a multi-column layout? The system uses top-left to bottom-right reading order — column content is ordered correctly by coordinate sorting.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST parse native PDF documents (text-based, not scanned) using page-by-page streaming — the full document is never loaded into memory (see also FR-017 for the hard streaming constraint)
- **FR-002**: System MUST parse DOCX documents using lazy paragraph iteration — only the current paragraph object lives in memory at any time. **Known limitation**: python-docx loads the full document XML on `Document()` construction; however, clause text is yielded immediately per paragraph without accumulation, keeping working memory low for typical contracts
- **FR-003**: System MUST produce a common hierarchical document model from both PDF and DOCX sources, such that downstream stages are format-agnostic. The core API is the `stream_clauses(path) → Iterator[Clause]` generator (see FR-021)
- **FR-004**: Each parsed clause MUST carry: a unique identifier (unique within the document, e.g., "clause-0", "clause-1"), title/heading (if present), full text content, hierarchy level (integer), parent clause reference (None for root), and source location (page number for PDF, paragraph index for DOCX)
- **FR-005**: System MUST detect document hierarchy using NUPunkt as the primary clause boundary detection engine. TOC extraction (`get_toc()` for PDFs), font analysis (size, bold), numbering patterns (e.g., "Article III", "Section 3.1", "3.1(a)"), and DOCX heading styles serve as supplementary signals that may **validate or supplement** NUPunkt's output but must **never override** NUPunkt's detected clause boundaries. DOCX heading styles map directly: Heading 1 → level 0, Heading 2 → level 1, etc.
- **FR-006**: System MUST stream clauses in reading order using top-left to bottom-right coordinate sorting. For PDFs, this is achieved via PyMuPDF's `sort=True` parameter or equivalent (y, x) coordinate sorting, which correctly handles multi-column layouts
- **FR-007**: System MUST provide a CLI command `openreview parse <path>` that outputs the parsed document structure
- **FR-008**: System MUST support `--format` flag on the parse command with values: `text` (default, human-readable), `json` (structured output as a flat array of clause objects with `parent_id` for nesting)
- **FR-009**: System MUST support `--summary` flag on the parse command to display a one-line parse result (clause count, page count, duration)
- **FR-010**: System MUST detect and handle the following error conditions with exit code 8: file not found, unsupported format, corrupt file, password-protected PDF, empty file, no extractable text
- **FR-011**: System MUST detect and warn (non-fatal) about: tracked changes in DOCX, non-English text (detected via Unicode-range heuristic for non-Latin scripts: Arabic `\u0600-\u06FF`, CJK `\u4E00-\u9FFF`, Cyrillic `\u0400-\u04FF`), embedded fonts rendering as boxes (tofu character `\uFFFD`), flat documents with no structure
- **FR-012**: System MUST use lazy imports for all document parsing libraries — heavy dependencies are imported only when the relevant parser code path is reached, not at module load time
- **FR-013**: System MUST keep peak memory usage under 100 MB during parsing of any document, regardless of document size
- **FR-014**: System MUST complete parsing of a 50-page native PDF in under 3 seconds on the reference hardware (8 GB RAM, 2-core CPU, no GPU) as defined in the constitution
- **FR-015**: System MUST handle Ctrl+C (SIGINT) during parsing by exiting cleanly — no partial output, no temporary files left behind
- **FR-016**: System MUST auto-detect document format from file extension (.pdf, .docx) and route to the correct parser
- **FR-017**: System MUST NOT load the entire document into memory at any point — parsing is strictly streaming (this is the hard constraint; see FR-001 for the PDF-specific streaming approach)
- **FR-018**: Parsed clauses MUST use `@dataclass(slots=True)` (or equivalent memory-efficient representation) to minimize per-clause memory overhead
- **FR-019**: System MUST handle the "Garbage In" collection gracefully — every malformed document produces a clear error or warning, never a crash or hang
- **FR-020**: System MUST display a page-level progress bar during parsing (e.g., "Page 12 of 47") so the user never sees a frozen screen. When the total page count is unknown (e.g., during streaming), the progress bar MUST use a pulsing/indeterminate animation until the count is available
- **FR-021**: System MUST expose an internal `stream_clauses(path) → Iterator[Clause]` generator as the core parsing API. The `openreview parse` CLI command MUST wrap this generator — downstream pipeline stages call the generator directly, not the CLI
- **FR-022**: System MUST use NUPunkt as the primary clause boundary detection engine. Supplementary signals (TOC, font, numbering) may **validate or supplement** NUPunkt's output but must **never override** NUPunkt's detected clause boundaries. This policy aligns with FR-005
- **FR-023**: When a document has no detectable hierarchy (flat text), the parser MUST split by blank-line-separated paragraphs into sibling clauses at level 0, and warn: "No document structure detected. Treating each paragraph as a separate clause."

### Key Entities

- **Clause**: The fundamental unit of parsed document content. Key attributes: id (unique within document, format "clause-{n}" auto-incremented), title (heading text or None), text (full clause text), level (hierarchy depth: 0 = top-level article, 1 = section, 2 = sub-section, etc.), parent_id (reference to parent clause ID or None for root), source_page (page number for PDF), source_paragraph (paragraph index for DOCX). Relationships: has zero or one parent clause, has zero or more child clauses.
- **Document**: The top-level container for a parsed document. Key attributes: source_path (original file path), format (pdf or docx), page_count, clause_count, parse_duration_seconds, warnings (list of non-fatal warnings). Relationships: has many clauses.
- **ParseError**: Represents a fatal parsing failure. Key attributes: exit_code (always 8), category (file_not_found, unsupported_format, corrupt, password_protected, empty, no_text), message (human-readable), action (what the user should do). Relationships: none.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can parse a 50-page native PDF contract and see its full hierarchical structure in under 3 seconds
- **SC-002**: Users can parse a DOCX contract and get the same hierarchical output format as PDF — downstream stages process both identically
- **SC-003**: Parsing any document, regardless of size, keeps peak memory usage under 100 MB on the reference hardware
- **SC-004**: 100% of malformed documents in the "Garbage In" collection produce a clear error message or warning — zero crashes, zero hangs
- **SC-005**: The same contract in PDF and DOCX format produces equivalent hierarchical output (same clause count within 10%, same nesting structure, equivalent text content)
- **SC-006**: Clause segmentation correctly identifies section boundaries in at least 95% of clauses across the synthetic contract test set (75 contracts). Measurement: for each contract, compare detected clause boundaries against hand-verified ground truth; accuracy = correct boundaries / total boundaries; aggregate accuracy across all 75 contracts must be ≥ 0.95
- **SC-007**: ~~The parse command completes with a visible result~~ — **Removed**: covered by SC-001 (PDF parse <3s) and SC-002 (DOCX parse produces output)
- **SC-008**: All parsing tests (unit + integration) pass in CI, with integration tests exercising real PDF and DOCX fixtures from `tests/fixtures/`

## Assumptions

- Phase 2 covers native PDF and DOCX parsing only. Scanned PDF OCR (Docling) is deferred to a later phase — if a PDF has no extractable text, the system reports it clearly and suggests installing the OCR extension
- The `PyMuPDF`, `python-docx`, and `nupunkt` libraries are available as runtime dependencies (will be added via `uv add` when the feature lands). NUPunkt is the primary clause boundary detection engine (zero deps, MIT-licensed, 91.1% precision on legal text). CharBoundary is not used — NUPunkt alone is sufficient
- Test fixtures (synthetic PDFs and DOCX files) will be created in `tests/fixtures/` alongside the tests — known-good contracts with verified clause structure for TDD validation
- NUPunkt is the primary clause boundary detection engine. PDF TOC extraction (`get_toc()`), font analysis (size, bold), numbering patterns (regex for "Section X.Y", "Article X", "(a)", "(i)"), and DOCX heading styles serve as supplementary signals. NUPunkt boundaries may be refined by supplementary signals but never overridden
- DOCX heading styles map directly: Heading 1 → level 0, Heading 2 → level 1, etc. PDF headings are detected via NUPunkt + font analysis + numbering patterns
- Reading order uses top-left to bottom-right coordinate sorting within each page (`sort=True` equivalent)
- Clause text is extracted as-is — no normalization, no summarization, no AI processing. Raw text extraction is the parser's only job
- The `stream_clauses(path) → Iterator[Clause]` internal generator is the core deliverable. The `openreview parse` CLI command wraps this generator for diagnostics. Downstream pipeline stages call the generator directly
- Parsers live in `src/openreview_cli/parsing/` with the Clause dataclass and the `stream_clauses` unified interface. CLI glue lives in `src/openreview_cli/app.py`
- Document format detection uses file extension only (.pdf, .docx). Content-based detection (magic bytes) is not needed in Phase 2
- A page-level progress bar ("Page 12 of 47") is shown during every parse operation via Rich. No hard size limit — streaming handles any document size at constant memory
- JSON output (`--format json`) is a flat array of clause objects with `parent_id` references encoding nesting, not a nested tree
- Clause IDs are auto-incremented integers wrapped as strings with the format "clause-{n}" (e.g., "clause-0", "clause-1") and are unique within a single document
- Cross-platform path handling reuses the `platformdirs`-based path resolution from Phase 1
- The "Garbage In" test collection (from TestingStrategy.md) will be built incrementally — Phase 2 requires at minimum: one corrupt PDF, one password-protected PDF, one empty file, one unsupported format, one DOCX with tracked changes, one flat document with no structure
- TDD workflow: integration tests are written first (they FAIL because no parser exists), then the parser implementation makes them PASS. Unit tests cover individual functions (NUPunkt integration, hierarchy detection, clause construction). All tests run in CI
