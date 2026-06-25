# Contract: stream_clauses() Interface

**Date**: 2026-06-25
**Feature**: 002-document-parsing

## Overview

The `stream_clauses()` function is the core API for document parsing. It provides a unified interface that downstream pipeline stages consume without knowing the source document format (PDF or DOCX).

## Function Signature

```python
def stream_clauses(path: str | Path) -> Iterator[Clause]:
    """
    Parse a document and yield clauses one at a time.

    Args:
        path: Path to the document file (.pdf or .docx)

    Yields:
        Clause: Parsed clause objects in document order

    Raises:
        ParseError: If the document cannot be parsed (exit code 8)

    Example:
        >>> for clause in stream_clauses("contract.pdf"):
        ...     print(f"{clause.id}: {clause.title}")
        clause-0: Article I: Definitions
        clause-1: Section 1.1: Confidential Information
        ...
    """
```

## Input Contract

### File Path

- **Type**: `str` or `pathlib.Path`
- **Format**: Must be an absolute or relative path to an existing file
- **Extension**: Must be `.pdf` or `.docx` (case-insensitive)
- **Size**: No hard limit, but must be readable

### Validation

```python
def validate_input(path: str | Path) -> None:
    """Validate input before parsing."""
    path = Path(path)

    # Check file exists
    if not path.exists():
        raise ParseError(
            exit_code=8,
            category="file_not_found",
            message=f"No file found at '{path}'.",
            action="Check the file path and try again."
        )

    # Check file is not empty
    if path.stat().st_size == 0:
        raise ParseError(
            exit_code=8,
            category="empty",
            message="The file appears to be empty or unreadable.",
            action="Provide a non-empty document file."
        )

    # Check file extension
    ext = path.suffix.lower()
    if ext not in (".pdf", ".docx"):
        raise ParseError(
            exit_code=8,
            category="unsupported_format",
            message=f"Format '{ext}' is not supported. Supported: .pdf, .docx",
            action="Provide a PDF or DOCX file."
        )
```

## Output Contract

### Clause Stream

The function yields `Clause` objects in **document order** (top to bottom, left to right within each page).

**Guarantees**:
1. **Order**: Clauses are yielded in the order they appear in the document
2. **Uniqueness**: Each clause has a unique `id` within the document
3. **Completeness**: All text content is included in exactly one clause
4. **Hierarchy**: Parent-child relationships are correctly established via `parent_id`
5. **Streaming**: Clauses are yielded one at a time — the full document is never loaded into memory

### Clause Structure

Each `Clause` object contains:

```python
@dataclass(slots=True)
class Clause:
    id: str                          # "clause-{n}" format
    title: str | None                # Heading text or None
    text: str                        # Full clause text
    level: int                       # Hierarchy depth (0 = top-level)
    parent_id: str | None            # Parent clause ID or None
    source_page: int | None          # Page number (PDF) or None
    source_paragraph: int | None     # Paragraph index (DOCX) or None
    source_span: tuple[int, int] | None  # Character offset range
```

### Example Output

```python
for clause in stream_clauses("nda.pdf"):
    print(f"ID: {clause.id}")
    print(f"Title: {clause.title}")
    print(f"Level: {clause.level}")
    print(f"Parent: {clause.parent_id}")
    print(f"Text: {clause.text[:100]}...")
    print(f"Source: page {clause.source_page}")
    print("---")
```

**Output**:
```
ID: clause-0
Title: Article I: Definitions
Level: 0
Parent: None
Text: This Agreement is entered into as of June 25, 2026, by and between...
Source: page 0
---
ID: clause-1
Title: Section 1.1: Confidential Information
Level: 1
Parent: clause-0
Text: "Confidential Information" means any information disclosed by...
Source: page 1
---
```

## Error Contract

### ParseError

If parsing fails, the function raises a `ParseError` with:
- `exit_code`: Always 8
- `category`: One of the predefined error categories
- `message`: Human-readable error description
- `action`: What the user should do to fix the problem

### Error Categories

| Category | When Raised | Example Message |
|----------|-------------|-----------------|
| `file_not_found` | File does not exist | "No file found at '/path/to/file.pdf'." |
| `unsupported_format` | Extension is not .pdf or .docx | "Format '.xlsx' is not supported. Supported: .pdf, .docx" |
| `corrupt` | File is corrupt or truncated | "The file appears to be corrupt or truncated." |
| `password_protected` | PDF requires a password | "This contract is password-protected." |
| `empty` | File is 0 bytes | "The file appears to be empty or unreadable." |
| `no_text` | PDF has no extractable text | "This PDF contains no extractable text. If it is a scanned document, install the OCR extension: openreview install ocr" |

### Error Handling Example

```python
from openreview_cli.parsing import stream_clauses, ParseError

try:
    for clause in stream_clauses("contract.pdf"):
        process(clause)
except ParseError as e:
    print(f"Error: {e.message}")
    print(f"What to do: {e.action}")
    sys.exit(e.exit_code)
```

## Performance Contract

### Memory

- **Peak memory**: <100 MB for any document size
- **Streaming**: Clauses are yielded one at a time, not accumulated
- **Cleanup**: All resources are released when the generator is exhausted or closed

### Speed

- **50-page PDF**: <3 seconds
- **500-page PDF**: <30 seconds (estimated)
- **DOCX**: Similar to PDF (depends on document complexity)

### Progress

- The function does NOT display progress directly
- The CLI wrapper (`openreview parse`) displays a progress bar
- Downstream pipeline stages can wrap the generator with their own progress display

## Usage Patterns

### Pattern 1: Simple Iteration

```python
for clause in stream_clauses("contract.pdf"):
    print(clause.text)
```

### Pattern 2: Collect All Clauses

```python
clauses = list(stream_clauses("contract.pdf"))
print(f"Parsed {len(clauses)} clauses")
```

### Pattern 3: Filter by Level

```python
for clause in stream_clauses("contract.pdf"):
    if clause.level == 0:
        print(f"Top-level: {clause.title}")
```

### Pattern 4: Build Hierarchy

```python
clauses = list(stream_clauses("contract.pdf"))
root_clauses = [c for c in clauses if c.parent_id is None]
for root in root_clauses:
    children = [c for c in clauses if c.parent_id == root.id]
    print(f"{root.title} ({len(children)} children)")
```

### Pattern 5: With Progress Display

```python
from rich.progress import track

for clause in track(stream_clauses("contract.pdf"), description="Processing"):
    process(clause)
```

## Implementation Notes

### Format Detection

```python
def stream_clauses(path: str | Path) -> Iterator[Clause]:
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        yield from _stream_pdf_clauses(path)
    elif ext == ".docx":
        yield from _stream_docx_clauses(path)
    else:
        raise ParseError(...)
```

### PDF Parser

```python
def _stream_pdf_clauses(path: Path) -> Iterator[Clause]:
    import pymupdf  # Lazy import

    with pymupdf.open(path) as doc:
        # Check for password protection
        if doc.needs_pass:
            raise ParseError(category="password_protected", ...)

        # Check for image-only PDF
        if _is_image_only(doc):
            raise ParseError(category="no_text", ...)

        # Extract TOC if available
        toc = doc.get_toc()

        # Stream pages
        for page_num, page in enumerate(doc):
            data = page.get_text("dict", sort=True)
            # Process blocks, detect clauses, yield
            ...
```

### DOCX Parser

```python
def _stream_docx_clauses(path: Path) -> Iterator[Clause]:
    from docx import Document  # Lazy import

    doc = Document(path)

    # Check for tracked changes
    if _has_tracked_changes(doc):
        # Warn but continue
        warnings.append("This document contains tracked changes.")

    # Stream paragraphs
    for para_idx, para in enumerate(doc.paragraphs):
        # Detect headings, detect clauses, yield
        ...
```

## Testing

### Unit Tests

```python
def test_stream_clauses_pdf():
    clauses = list(stream_clauses("tests/fixtures/pdf/simple_contract.pdf"))
    assert len(clauses) > 0
    assert all(c.id.startswith("clause-") for c in clauses)
    assert all(c.level >= 0 for c in clauses)

def test_stream_clauses_docx():
    clauses = list(stream_clauses("tests/fixtures/docx/simple_contract.docx"))
    assert len(clauses) > 0
    assert all(c.id.startswith("clause-") for c in clauses)

def test_stream_clauses_error_handling():
    with pytest.raises(ParseError) as exc_info:
        list(stream_clauses("nonexistent.pdf"))
    assert exc_info.value.category == "file_not_found"
```

### Integration Tests

```python
def test_stream_clauses_accuracy():
    # Test on fixtures with hand-verified clause boundaries
    for fixture in test_fixtures:
        clauses = list(stream_clauses(fixture.path))
        accuracy = calculate_accuracy(clauses, fixture.expected_boundaries)
        assert accuracy >= 0.95
```

## Future Extensions

### Async Support (Not in Phase 2)

```python
async def stream_clauses_async(path: str | Path) -> AsyncIterator[Clause]:
    """Async version for concurrent pipeline stages."""
    # Wrap synchronous generator in async
    for clause in stream_clauses(path):
        yield clause
```

### Filtering Options (Not in Phase 2)

```python
def stream_clauses(
    path: str | Path,
    min_level: int = 0,
    max_level: int | None = None,
    include_text: bool = True,
) -> Iterator[Clause]:
    """Stream clauses with optional filtering."""
    ...
```

### Metadata Extraction (Not in Phase 2)

```python
def parse_document(path: str | Path) -> tuple[Document, Iterator[Clause]]:
    """Parse document and return metadata + clause stream."""
    ...
```
