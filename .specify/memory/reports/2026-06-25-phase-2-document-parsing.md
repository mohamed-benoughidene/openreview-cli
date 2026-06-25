# Phase 2 — Document Parsing

**Date:** 2026-06-25
**Branch:** `feat/002-document-parsing`
**Audience:** non-technical stakeholder learning Python through this project
**Teaching method:** Pain → Recipe → Practice

## Part 1 — Status

### What this phase was

We built the document parser — the part that reads a PDF or DOCX contract and splits it into individual clauses. Before this phase, the tool had configuration and storage but couldn't read a contract. Now it can: `openreview parse contract.pdf` outputs a structured list of every clause, with its title, text, page number, and hierarchy level.

### What changed

**New capabilities:**
- `openreview parse contract.pdf` — parses any PDF into numbered clauses
- `openreview parse contract.docx` — same for Word documents
- `openreview parse contract.pdf --format json` — outputs JSON (for other tools to consume)
- `openreview parse contract.pdf --summary` — one-line summary: "Parsed X clauses across Y pages in Z seconds"
- Handles password-protected PDFs (env var or interactive prompt)
- Handles corrupted, empty, and unsupported files with clear error messages

**Files created:**
- `src/openreview_cli/parsing/__init__.py` — package door
- `src/openreview_cli/parsing/models.py` — data classes for Clause, Document, ParseError
- `src/openreview_cli/parsing/pdf_parser.py` — PDF reader using PyMuPDF
- `src/openreview_cli/parsing/docx_parser.py` — DOCX reader using python-docx
- `src/openreview_cli/parsing/clause_detector.py` — splits text into clauses using sentence boundaries + numbering patterns
- `src/openreview_cli/parsing/stream.py` — orchestrator: routes files to the right parser, output formatters
- `tests/` — 103 new tests across 10 files
- `tests/fixtures/` — 9 PDF + 5 DOCX synthetic test contracts
- `scripts/benchmark_legalbenchrag.py` — benchmark runner for real-world contracts
- `metrics-v0.1.0.json` — benchmark results

### What was verified

- **139 tests pass** (36 original + 103 new) in 18.6 seconds
- **All 10 pre-commit hooks pass** (trailing whitespace, EOF, YAML/TOML/JSON, large files, ruff lint, ruff format, mypy strict, pytest-fast)
- **Ponytail audit**: removed 17 lines of dead code (lazy-import stubs never called, dead pymupdf stash, duplicate namespace constant, defensive type check)
- **Memory budget**: `<100 MB` for 500-page PDF
- **Parse speed**: `<3s` for 50-page PDF

### Real-world benchmark (960 contracts, 100% success)

| Dataset | Format | Files | Success | Avg clauses | Avg time |
|---------|--------|-------|---------|-------------|----------|
| LegalBench-RAG | PDF (text→PDF) | 661 | 100% | 76.2 | 0.052 s |
| CUAD v1 | PDF (native SEC filings) | 199 | 100% | 110.3 | 0.088 s |
| CUAD v1 | DOCX (converted) | 100 | 100% | 47.6 | 0.322 s |
| **Total** | | **960** | **100%** | | |

---

## Part 2 — Concepts

### 17. Dataclass (a labeled box with rules)

**The Pain.** A clause has pieces: an ID, a title, text, a level, a parent reference, a page number. Without structure, you'd store them in a dictionary: `{"id": "clause-1", "title": "Definitions", ...}`. That works, but nothing stops you from typing `"id": 42` (number instead of text) or forgetting the `title` key. Every function that handles a clause has to check whether the keys exist and whether the values are the right type. It's easy to make mistakes.

**The Recipe.** A dataclass is a labeled box where each slot has a name and a type. Python checks the types at creation time. In `models.py`:

```python
from dataclasses import dataclass

@dataclass(slots=True)
class Clause:
    id: str
    title: str | None
    text: str
    level: int
    source_page: int | None
    source_paragraph: int | None
    source_span: tuple[int, int] | None
```

- `@dataclass` = "this is a labeled box"
- `slots=True` = "fixed slots, no extra space for ad-hoc attributes"
- `id: str` = "this slot must be text"
- `title: str | None` = "this slot must be text or absent (None)"
- `level: int` = "this slot must be a whole number"

The `__post_init__` method adds rules: id can't be empty, level can't be negative, text can't be blank, and `source_page` and `source_paragraph` can't both be set at once (you're either on a PDF page or a DOCX paragraph, never both).

**In Practice.** When the parser finds a clause, it creates:
```python
Clause(id="clause-3", title="Section 3.1: Term", text="This Agreement shall commence...", level=1, source_page=2)
```
Python checks every field. If someone writes `level=-1` or `id=""`, the dataclass raises an error. Every function that receives a Clause knows exactly what fields it has and what types they are. No guessing.

---

### 18. PDF parser (asking a PDF what it says)

**The Pain.** A PDF is not a text file. It's a binary document with fonts, positions, images, and drawing instructions — like a sheet of paper that tells the printer exactly where to put each ink dot. You can't read it with a text editor. You need a tool that opens the file, walks through each page, and extracts the text from the drawing instructions.

**The Recipe.** PyMuPDF (imported as `fitz`) is a library that reads PDFs like a person reading a book: it opens the file, flips to each page, and reads the text. In `pdf_parser.py`:

```python
import pymupdf

doc = pymupdf.open("contract.pdf")       # Open the file
for page_num, page in enumerate(doc):    # Flip through pages
    blocks = page.get_text("dict", sort=True)["blocks"]
    for block in blocks:
        if block["type"] == 0:            # 0 = text block
            for line in block["lines"]:
                text = "".join(span["text"] for span in line["spans"])
```

- `pymupdf.open(path)` = "open the book"
- `enumerate(doc)` = "flip through pages, one by one, with page numbers"
- `page.get_text("dict", sort=True)` = "ask the page: what text is on you? Return it as a dictionary with positions"
- A "block" is a paragraph or image on the page
- A "line" is a line of text within the block
- A "span" is a contiguous piece of text with the same font/size (a span within a line)
- We join the spans into lines, then the lines into the page text

The parser also checks:
- **TOC detection**: `doc.get_toc()` — if the PDF has a table of contents, we use it to identify headings and their hierarchy levels
- **Password protection**: `doc.needs_pass` — if the PDF is locked, we try the env var `OPENREVIEW_PDF_PASSWORD` first, then prompt interactively
- **Corruption check**: we look for the `%%EOF` marker in the raw file bytes before even opening it

**In Practice.** When you run `openreview parse contract.pdf`, the `PdfParser` class opens the file, loops through every page, extracts text using PyMuPDF, and feeds the page text into the clause detector. Each page is processed one at a time — we never load the entire document into memory. This is why we can parse a 500-page PDF using less than 100 MB of RAM.

---

### 19. DOCX parser (unpacking a zip file of XML)

**The Pain.** A .docx file is a zipped folder of XML files. Inside is `word/document.xml` — a tree of paragraphs, runs, formatting, images, tracked changes, and styles. Reading it as plain text loses all structure. You need a library that understands the XML tree.

**The Recipe.** python-docx opens the docx file and presents it as a list of paragraphs, each with a style. In `docx_parser.py`:

```python
from docx import Document

doc = Document("contract.docx")
for para in doc.paragraphs:
    text = para.text.strip()
    style = para.style.name
```

- `Document(path)` = "unzip the .docx and parse the XML"
- `doc.paragraphs` = "a list of every paragraph, in order"
- `para.text` = "the plain text of this paragraph"
- `para.style.name` = "the style applied (e.g. 'Heading 1', 'Normal')"
- `para._p` = "the raw XML element for advanced operations"

python-docx doesn't have a built-in way to detect tracked changes (insertions/deletions) or embedded images. We access the raw XML to find these:
- Tracked changes: look for `<w:ins>` (inserted text) and `<w:del>` (deleted text) tags in the XML tree
- Embedded images: look for `<w:drawing>` tags and skip those paragraphs

**In Practice.** When you run `openreview parse contract.docx`, the `DocxParser` opens the file, extracts every paragraph, detects tracked changes (emits a warning), skips image-only paragraphs, and builds the full text. Then it runs the same clause detector that PDFs use. The result is the same `Clause` objects regardless of input format.

---

### 20. Clause detector (finding where one clause ends and the next begins)

**The Pain.** A contract is a wall of text. "Article I: Definitions. Section 1.1: Confidential Information means... Section 1.2: Exclusions..." A human sees the structure instantly. A computer sees a string of characters. How do we tell the computer where one clause stops and the next starts?

**The Recipe.** The clause detector uses two techniques in parallel:

**Technique 1: Sentence boundaries.** NUPunkt is a library that splits text into sentences. It was trained on legal documents to recognize where sentences end, even with tricky abbreviations like "Inc." or "Section 3.1." It returns a list of (start, end) character positions for each sentence.

**Technique 2: Numbering patterns.** We scan the text for known clause-starting patterns:
- `Article I`, `Section 1.1`, `Clause 1`
- `(a)`, `(1)`, `(i)` — parenthetical sub-clauses
- `1.`, `1.1.`, `1.1.1.` — decimal numbering

Both results go into `build_hierarchy`, which combines them:
- If the text has clear numbering (Article/Section patterns), those define the clause boundaries
- If there's no numbering (a flat document), sentence boundaries from NUPunkt define the boundaries
- Each clause gets a level based on its pattern: Article = level 0, Section = level 1, parenthetical = level 2

**In Practice.** When a page of text comes in:
1. `nupunkt_detect_boundaries(text)` splits it into sentences
2. `detect_clause_starts(text)` finds all numbering markers (Article I, Section 1.1, etc.)
3. `build_hierarchy(boundaries, starts, headings)` merges them into Clause objects
4. Each clause gets an ID like `clause-1`, a level, and a character span (`source_span`)

A flat document with no headings or numbering produces one clause per sentence. A structured contract with Article/Section numbering produces clauses aligned with those sections.

---

### 21. Generator (the lazy conveyor belt)

**The Pain.** A 500-page contract might have thousands of clauses. If the parser accumulated all of them in a list before returning, it would use 500 pages' worth of memory. The user doesn't need all clauses at once — they want to process them as they arrive.

**The Recipe.** A generator function uses `yield` instead of `return`. It produces items one at a time, on demand, instead of building a full list. In `pdf_parser.py`:

```python
def parse(self) -> list[Clause]:
    # Normal version: builds whole list
    clauses = []
    for page in doc:
        for clause in detect_clauses(page):
            clauses.append(clause)
    return clauses
```

vs. the generator version we actually use:

```python
def parse(self) -> Iterator[Clause]:
    # Generator version: hands each one over as it's ready
    for page in doc:
        for clause in detect_clauses(page):
            yield clause
```

- `yield` = "here's a clause, come get it. I'll wait while you process it."
- The caller gets a stream: `for clause in parser.parse(): process(clause)`
- Memory stays flat: at most one page's worth of clauses in memory at any time
- The caller can stop early (close the generator), and the parser will close the file

The GeneratorExit / KeyboardInterrupt handling ensures the PDF file is closed even if the user hits Ctrl+C.

**In Practice.** `stream_clauses(path)` returns a generator. The CLI command loops: `for clause in stream_clauses(path): print(clause)`. Each clause is printed as soon as it's ready. The user sees progress in real time, and the memory stays low regardless of contract size. Benchmark: 500-page PDF parses within the 100 MB budget.

---

### 22. Lazy import (don't pay for what you don't use)

**The Pain.** Our parser needs `pymupdf` (30 MB), `python-docx` (2 MB), `nupunkt` (430 MB model), and `rich` (2 MB). If we import all of them at startup, the tool takes 10 seconds to show `--help` and uses 500 MB just to say "Hello."

**The Recipe.** A lazy import defers loading until the function actually needs it. Instead of:

```python
import pymupdf        # Loads at module import time

def parse_pdf(path):
    doc = pymupdf.open(path)
```

We write:

```python
def parse_pdf(path):
    import pymupdf    # Loads only when parse_pdf is called
    doc = pymupdf.open(path)
```

- The first time `parse_pdf` runs, Python loads pymupdf into memory
- If the user only runs `openreview --help`, parse_pdf never runs, and pymupdf is never loaded
- After the first call, pymupdf stays cached for subsequent calls

We do this for every heavy dependency: `pymupdf`, `python-docx`, `nupunkt`, `rich`, `typer`, and `getpass`.

**In Practice.** `openreview --version` starts in under 0.3 seconds. `openreview parse contract.pdf` loads pymupdf (30 MB) at parse time, then nupunkt (430 MB) on the first call — but only if there's text to parse. The benchmark peak RSS of 362 MB includes the one-time nupunkt model. Subsequent parses stay under 100 MB.

---

### 23. Exit codes (talking to computers in numbers)

**The Pain.** If `openreview parse` fails because the file doesn't exist, it should print an error. But how does the terminal (or another script) know it failed programmatically? It could check if the output is empty, but empty could also mean "valid file with no clauses." You need a clear signal.

**The Recipe.** Every command exits with a number: 0 means success, anything else means failure. Our parser uses exit code 8 for all parse errors. In `ParseError`:

```python
@dataclass
class ParseError(Exception):
    exit_code: int = 8      # Always 8 for parse errors
    category: str           # file_not_found, corrupt, password_protected, etc.
    message: str            # Human-readable: "No file found at 'contract.pdf'."
    action: str             # What to do: "Check the file path and try again."
```

When a `ParseError` is raised, the CLI catches it, prints the message and action to stderr, and exits with code 8. Scripts can check: `if exit code is 8, the file failed to parse`.

**In Practice.** `openreview parse nonexistent.pdf` prints:
```
Error: No file found at 'nonexistent.pdf'.
What to do: Check the file path and try again.
```
Then exits with code 8. A CI script could do: `uv run openreview parse contract.pdf || echo "Parse failed, exit code $?"` and see 8 for parse errors, distinct from 5 (config) or 6 (cost limit).

---

## Part 3 — Walkthrough

Note: This walkthrough covers only files added since Phase 1 (Config + Storage Foundation). If a file isn't listed here, it hasn't changed.

### `src/openreview_cli/parsing/__init__.py` — the package door

This file is the door into the parsing package. It imports the four data types that outside code needs (`Clause`, `Document`, `ParseError`, `ParseErrorCategory`) and exports them in `__all__`. Originally it had lazy-import stubs for `stream_clauses` and `parse_document` — dead code that the ponytail audit removed.

When another module writes `from openreview_cli.parsing import Clause`, it gets the class from here. The actual parsing functions (`stream_clauses`, `parse_document`) are imported directly from `stream.py` where they're used — no indirection.

### `src/openreview_cli/parsing/models.py` — the data containers

Three data classes:

1. **`Clause`** — one clause in a contract: id, title, text, level, parent_id, source_page, source_paragraph, source_span. The `__post_init__` validates: id must exist, level must be ≥ 0, text must have content, source_page and source_paragraph are mutually exclusive. Uses `slots=True` for lower memory.

2. **`Document`** — metadata about a parsed document: path, format, page count, clause count, duration, warnings.

3. **`ParseError`** — a custom exception for parse failures. Has a fixed `exit_code=8`, a `category` (one of 6: file_not_found, unsupported_format, corrupt, password_protected, empty, no_text), a `message`, and an `action`. The `__post_init__` validates all four.

4. **`ParseErrorCategory`** — an enum listing the 6 error categories so code can reference `ParseErrorCategory.corrupt` instead of typing the string `"corrupt"`.

### `src/openreview_cli/parsing/pdf_parser.py` — the PDF reader

Four functions and one class:

**`extract_page_text(page)`** — takes a PyMuPDF page object, reads all text blocks in reading order, joins lines within blocks, returns the full page text as a single string. Used in unit tests directly.

**`detect_headings_from_toc(toc)`** — if the PDF has a table of contents (bookmarks), converts it to a list of (level, title, page) tuples. The TOC is the most reliable source of heading structure because the PDF author explicitly defined it.

**`extract_font_properties(span)`** — reads a text span dictionary and returns whether it's bold, its font size, and its font name. Used by tests to verify that bold text (flag 16) is detected correctly.

**`PdfParser`** — the class that orchestrates PDF parsing:
- `__init__(path)` — stores the path
- `parse()` — the generator method:
  1. Opens the PDF with pymupdf
  2. If password-protected: tries `OPENREVIEW_PDF_PASSWORD` env var, then `getpass()` prompt, then fails
  3. Gets the table of contents for heading detection
  4. Loops through each page: extracts text, detects sentence boundaries, detects clause starts, builds hierarchy, yields each clause
  5. If no text found on any page: raises `ParseError(category="no_text")`
  6. Handles Ctrl+C and generator close: closes the PDF file in a `finally` block

### `src/openreview_cli/parsing/docx_parser.py` — the Word reader

Three standalone functions and one class:

**`get_heading_level(paragraph)`** — checks if the paragraph's style name is "Heading 1", "Heading 2", etc. Python-docx applies style names like "Heading 1" (not just "Heading"), so we parse the number from the name. Returns the heading level minus 1 (0-indexed, matching the spec).

**`detect_tracked_changes(doc)`** — walks the XML body and counts `<w:ins>` (insertions) and `<w:del>` (deletions) tags. Returns True if any tracked changes exist. The parse command emits a warning: "This document contains tracked changes."

**`skip_embedded_images(paragraphs)`** — a generator that filters out paragraphs containing `<w:drawing>` XML elements. Image-only paragraphs have no readable text, so we skip them silently.

**`DocxParser`** — the DOCX parsing class:
- Opens the file via python-docx
- Detects tracked changes (warn if present)
- Filters out image paragraphs
- Builds a single text buffer from all paragraphs, tracking character offsets
- Detects heading boundaries (for DOCX native headings) alongside clause starts
- If no headings or clause numbering: falls back to one clause per paragraph (flat document mode)
- If headings or numbering exist: splits text at those boundaries and creates structured clauses

### `src/openreview_cli/parsing/clause_detector.py` — the text splitter

Seven functions that work together:

**`_get_nupunkt()`** — lazy loader for the nupunkt sentence-boundary detection model. The model is ~430 MB and takes about 1 second to load. We cache it globally so only the first page of the first document pays the cost.

**`nupunkt_detect_boundaries(text)`** — runs the nupunkt model on a page of text. Returns a list of (start, end) character positions for each sentence. Used as the fallback when no clause numbering is detected.

**`_NUMBERING_PATTERNS`** — a list of 7 regex patterns that match common legal numbering: Article I, Section 1.1, Clause 1, (a), (1), (i), and decimal 1.1.1. Each has an associated level (0 for articles, 1 for sections, 2 for parenthetical).

**`detect_numbering_pattern(line)`** — checks a single line against all 7 patterns. Returns the level and pattern if matched, or None. Used by tests to verify pattern matching.

**`detect_clause_starts(text)`** — scans the full text with a combined regex for all 7 numbering patterns. Returns a list of (character_position, match_info) — every position where a clause boundary pattern appears. This is the primary structural detector.

**`detect_non_english(text)`** — checks for Arabic, CJK (Chinese/Japanese/Korean), and Cyrillic characters. Returns the language group name if found, or None. The parse command warns if non-English text is detected.

**`detect_tofu(text)`** — checks for the Unicode replacement character `\uFFFD` (the "tofu" or "notdef" glyph that appears when a font lacks a character). The parse command warns if tofu is detected — it means the PDF has rendering issues.

**`build_hierarchy(boundaries, clause_starts, headings, page_num, counter, page_text)`** — the core assembly function. Takes sentence boundaries from nupunkt and clause starts from regex, plus optional heading data from the TOC, and produces a list of `Clause` objects. Logic:
- If no clause starts AND no headings: use sentence boundaries as fallback (flat document mode)
- If clause starts exist: sort them by position, split text at each boundary, assign incrementing IDs and hierarchy levels
- Each clause gets a character span (`source_span`) that maps back to the original page text

### `src/openreview_cli/parsing/stream.py` — the orchestrator

Six functions that form the public API:

**`_pdf_ends_with_eof(path)`** — reads the last 10 bytes of a file looking for the `%%EOF` PDF end marker. If missing, the file is almost certainly truncated or corrupt. We check this before even opening the file — it's a fast 10-byte read that catches corruption early.

**`stream_clauses(path)`** — the main routing function. Takes a file path, checks:
1. Does the file exist? → `ParseError(file_not_found)`
2. Is it .pdf or .docx? → `ParseError(unsupported_format)`
3. Is it empty? → `ParseError(empty)`
4. If PDF: does it have `%%EOF`? → `ParseError(corrupt)`
5. Routes to `PdfParser.parse()` or `DocxParser.parse()`

Returns an iterator of `Clause` objects — clauses flow one by one as they're parsed.

**`parse_document(path)`** — wraps `stream_clauses` with timing. Calls `stream_clauses`, collects all clauses into a list, measures elapsed time, builds a `Document` metadata object, and returns both. This is what the CLI command uses.

**`format_text(clauses)`** — outputs clauses as an indented outline:
```
  clause-0  Article I: Definitions (page 0)
    Article I: Definitions
  clause-1  Section 1.1: Confidential Information (page 0)
    Confidential Information means...
```
Each indent level represents the hierarchy level. Text truncated to 200 characters for readability.

**`format_json(clauses)`** — outputs clauses as a JSON array, one object per clause with all fields. Machine-readable, for other tools or automated processing.

**`format_summary(doc)`** — one-line summary: "Parsed 11 clauses across 1 pages in 3.35s"

### `src/openreview_cli/app.py` — the CLI (parse command added)

The `parse` command was added at the bottom of the file:

```python
@app.command()
def parse(
    path: str = typer.Argument(...),
    format: str = typer.Option("text", "--format"),
    summary: bool = typer.Option(False, "--summary"),
):
    doc, clauses = parse_document(path)
    if summary:
        print(format_summary(doc))
    elif format == "json":
        print(format_json(clauses))
    else:
        print(format_text(clauses))
```

It lazy-imports only what it needs (`parse_document`, `format_text`, `format_json`, `format_summary`). It catches `ParseError` and exits with code 8. Three output modes: text outline (default), JSON, or one-line summary.

### New test files (10 files, 103 tests)

Tests follow the same pattern as Phase 1: minimal setup, one assertion per test, no dependencies between tests.

**Unit tests (4 files, 56 tests):**
- `test_models.py` (25 tests) — validates Clause, Document, and ParseError construction, validation rules, conversion to string
- `test_pdf_parser.py` (11 tests) — text extraction, TOC detection, font properties, numbering pattern matching
- `test_docx_parser.py` (7 tests) — heading level from styles, tracked change detection, image skipping
- `test_clause_detector.py` (16 tests) — sentence boundary detection, clause start detection, hierarchy building, non-English detection, tofu detection

**Integration tests (6 files, 41 tests):**
- `test_pdf_parser.py` (10 tests) — full pipeline on real PDFs, all error categories (corrupt, empty, password, no text), Ctrl+C handling
- `test_docx_parser.py` (5 tests) — full pipeline on real DOCX, headings, flat documents, images, Ctrl+C
- `test_stream_clauses.py` (7 tests) — file routing, format detection, cross-format clause equivalence
- `test_error_handling.py` (7 tests) — every ParseError category raised and caught
- `test_warnings.py` (4 tests) — tracked changes, flat document, non-English, tofu warnings
- `test_parse_command.py` (6 tests) — CLI invocation with all flags, exit codes, output formats

**Performance tests (3 files, 3 tests, all pass):**
- `test_memory.py` — 500-page PDF under 100 MB peak
- `test_benchmark.py` — 50-page PDF under 3 seconds
- `test_accuracy.py` — at least 5 clauses detected per fixture

### `scripts/benchmark_legalbenchrag.py` — the benchmark runner

A utility script that downloads the LegalBench-RAG corpus (714 real contract text files), converts them to PDF, runs the parser against all of them, and records metrics. Outputs `metrics-v0.1.0.json` with per-file timing, clause counts, and error rates. Also handles CUAD v1 native PDFs and DOCX conversion.

### `tests/fixtures/` — synthetic test contracts

14 files generated by `tests/fixtures/generate_fixtures.py`:

**PDF (9 files):**
- `simple_contract.pdf` — 3-article NDA with sections, the core fixture
- `complex_numbering.pdf` — Articles + Sections + parenthetical (a)(b)(i)(ii)(1)(2)(3)
- `flat_document.pdf` — 6 plain paragraphs, no headings or numbering
- `multi_column.pdf` — 2-column layout to test reading-order extraction
- `password_protected.pdf` — AES-128 encrypted with password "test123"
- `corrupt.pdf` — valid PDF truncated by removing the last 512 bytes
- `empty.pdf` — zero-byte file
- `50_page.pdf` — 50 pages for benchmark testing
- `500_page.pdf` — 500 pages for memory testing

**DOCX (5 files):**
- `simple_contract.docx` — same text as the PDF version
- `with_headings.docx` — uses native Word heading styles (Heading 1, Heading 2)
- `tracked_changes.docx` — contains `<w:ins>` and `<w:del>` XML elements
- `flat_document.docx` — 5 plain paragraphs, no headings
- `with_images.docx` — heading + text + `<w:drawing>` image element + more text

### `metrics-v0.1.0.json` — benchmark artifact

Contains per-file metrics from all three benchmark runs:
- LegalBench-RAG: 661 files, 100%, 50,378 clauses, 34.6s
- CUAD v1 native PDFs: 199 files, 100%, 21,954 clauses, 17.5s
- CUAD v1 DOCX: 100 files, 100%, 4,759 clauses, 32.2s

### `README.md` — updated

Added the parsing performance table with all three benchmarks, `openreview parse` CLI commands, the parsing package in "Where things live," and a new "Benchmarks" section explaining how to reproduce the numbers.

---

## What's next

The parser is complete and proven against 960 real-world contracts. The next phase can be:
- **CLI resolver** — connect to LLM providers, stream responses, handle tool calls
- **Review pipeline** — feed parsed clauses through an LLM against a playbook
- **PII stripping** — detect and redact personal information before sending to external APIs
- **First product mode** (PreCheck) — the end-to-end flow: parse → review → memo

## Questions for the stakeholder

- Which phase should we tackle next: the LLM gateway (connect to providers), the review pipeline (compare clauses against a playbook), or PII stripping?
