# Data Model: Document Parsing

**Date**: 2026-06-25
**Feature**: 002-document-parsing

## Overview

The document parsing system produces a hierarchical structure of clauses from PDF and DOCX contracts. The core entity is `Clause`, which represents a single unit of document content with its position in the hierarchy.

## Entities

### Clause

The fundamental unit of parsed document content.

**Attributes**:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | `str` | Unique within document, format "clause-{n}" | `"clause-0"`, `"clause-42"` |
| `title` | `str \| None` | Heading text if present | `"Section 3.1: Confidentiality"` |
| `text` | `str` | Full clause text content | `"The parties agree to..."` |
| `level` | `int` | Hierarchy depth (0 = top-level) | `0` (Article), `1` (Section), `2` (Sub-section) |
| `parent_id` | `str \| None` | Reference to parent clause ID | `"clause-0"` or `None` for root |
| `source_page` | `int \| None` | Page number (PDF only, 0-indexed) | `5` |
| `source_paragraph` | `int \| None` | Paragraph index (DOCX only, 0-indexed) | `42` |
| `source_span` | `tuple[int, int] \| None` | Character offset range in source text | `(1234, 1567)` |

**Relationships**:
- Has zero or one parent clause (via `parent_id`)
- Has zero or more child clauses (inverse relationship)
- Belongs to one `Document`

**Validation Rules**:
- `id` must be unique within the document
- `level` must be ≥ 0
- `text` must be non-empty (after stripping whitespace)
- If `parent_id` is set, the parent clause must exist in the same document
- `source_page` and `source_paragraph` are mutually exclusive (PDF vs DOCX)

**Example**:
```python
Clause(
    id="clause-5",
    title="Section 3.1: Confidentiality",
    text="The Receiving Party shall not disclose Confidential Information to any third party without prior written consent.",
    level=1,
    parent_id="clause-0",
    source_page=3,
    source_paragraph=None,
    source_span=(4521, 4890)
)
```

---

### Document

The top-level container for a parsed document.

**Attributes**:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `source_path` | `Path` | Original file path | `Path("/path/to/contract.pdf")` |
| `format` | `str` | Document format ("pdf" or "docx") | `"pdf"` |
| `page_count` | `int` | Number of pages (PDF) or estimated pages (DOCX) | `47` |
| `clause_count` | `int` | Total number of clauses | `156` |
| `parse_duration_seconds` | `float` | Time taken to parse | `2.34` |
| `warnings` | `list[str]` | Non-fatal warnings during parsing | `["No document structure detected"]` |

**Relationships**:
- Has many `Clause` objects

**Validation Rules**:
- `source_path` must exist
- `format` must be "pdf" or "docx"
- `page_count` must be ≥ 1
- `clause_count` must be ≥ 0
- `parse_duration_seconds` must be ≥ 0

**Example**:
```python
Document(
    source_path=Path("/path/to/contract.pdf"),
    format="pdf",
    page_count=47,
    clause_count=156,
    parse_duration_seconds=2.34,
    warnings=[]
)
```

---

### ParseError

Represents a fatal parsing failure.

**Attributes**:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `exit_code` | `int` | Always 8 for parse errors | `8` |
| `category` | `str` | Error category | `"password_protected"` |
| `message` | `str` | Human-readable error message | `"This contract is password-protected."` |
| `action` | `str` | What the user should do | `"Enter the password or provide an unlocked copy."` |

**Categories**:
- `file_not_found` — File does not exist at the given path
- `unsupported_format` — File extension is not .pdf or .docx
- `corrupt` — File is corrupt or truncated
- `password_protected` — PDF requires a password
- `empty` — File is empty (0 bytes)
- `no_text` — PDF has no extractable text (image-only)

**Validation Rules**:
- `exit_code` must be 8
- `category` must be one of the predefined categories
- `message` must be non-empty
- `action` must be non-empty

**Example**:
```python
ParseError(
    exit_code=8,
    category="password_protected",
    message="This contract is password-protected.",
    action="Enter the password or provide an unlocked copy."
)
```

---

## Hierarchy Structure

The clauses form a tree structure where each clause can have a parent and children.

**Example Hierarchy**:
```
clause-0: Article I: Definitions (level 0, parent_id=None)
├── clause-1: Section 1.1: Confidential Information (level 1, parent_id="clause-0")
│   ├── clause-2: (a) What counts as confidential (level 2, parent_id="clause-1")
│   └── clause-3: (b) What's excluded (level 2, parent_id="clause-1")
├── clause-4: Section 1.2: Receiving Party (level 1, parent_id="clause-0")
└── clause-5: Section 1.3: Disclosing Party (level 1, parent_id="clause-0")

clause-6: Article II: Obligations (level 0, parent_id=None)
├── clause-7: Section 2.1: Non-disclosure (level 1, parent_id="clause-6")
└── clause-8: Section 2.2: Standard of care (level 1, parent_id="clause-6")
```

**Level Mapping**:
- Level 0: Article, Chapter, or top-level section
- Level 1: Section (e.g., "Section 3.1")
- Level 2: Sub-section (e.g., "3.1(a)")
- Level 3: Sub-sub-section (e.g., "(i)")
- Level 4+: Deeply nested items

---

## State Transitions

There are no state transitions in Phase 2. Parsing is a one-way transformation:

```
Document File → Parser → Iterator[Clause] → Output
```

The parser is stateless — it reads the document and produces clauses without maintaining state between invocations.

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      Document File                           │
│                  (PDF or DOCX on disk)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Format Detection                          │
│              (check file extension .pdf/.docx)               │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
┌──────────────────┐      ┌──────────────────┐
│   PDF Parser     │      │  DOCX Parser     │
│  (PyMuPDF)       │      │  (python-docx)   │
└────────┬─────────┘      └────────┬─────────┘
         │                         │
         └────────────┬────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 Clause Detector                              │
│  (NUPunkt sentence boundaries + regex clause detection)     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Hierarchy Builder                               │
│  (detect nesting from numbering patterns + headings)        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Iterator[Clause]                                │
│         (stream_clauses() generator yields clauses)          │
└─────────────────────────────────────────────────────────────┘
```

---

## Validation Strategy

### Unit Tests

**Clause Validation**:
- Test that `id` is unique within a document
- Test that `level` is ≥ 0
- Test that `text` is non-empty
- Test that `parent_id` references an existing clause

**Document Validation**:
- Test that `source_path` exists
- Test that `format` is "pdf" or "docx"
- Test that `page_count` ≥ 1

**ParseError Validation**:
- Test that `exit_code` is 8
- Test that `category` is valid
- Test that `message` and `action` are non-empty

### Integration Tests

**Hierarchy Validation**:
- Parse a contract with known structure
- Verify that parent-child relationships are correct
- Verify that levels are assigned correctly
- Verify that clause count matches expected count

**Accuracy Validation**:
- Parse test fixtures with hand-verified clause boundaries
- Calculate accuracy: (correct boundaries / total boundaries) ≥ 95%
- Test on diverse contract types (NDA, MSA, employment agreement)

---

## Memory Considerations

**Clause Size**:
- Each `Clause` object uses `@dataclass(slots=True)` to minimize memory
- Estimated size: ~200 bytes per clause (text varies)
- For a 50-page contract with 150 clauses: ~30 KB

**Streaming Pattern**:
- Clauses are yielded one at a time via generator
- Downstream stages process and discard immediately
- No need to hold all clauses in memory

**Peak Memory**:
- PDF parsing: ~10-50 MB (PyMuPDF page cache)
- DOCX parsing: ~5-20 MB (python-docx XML tree)
- NUPunkt model: ~432 MB (loaded on first call)
- Total peak: <100 MB (constitutional requirement)

---

## Future Extensions (Not in Phase 2)

**Cross-References**:
- Add `references: list[str]` field to track "See Section 5.2" references
- Resolve references to actual clause IDs

**Metadata**:
- Add `metadata: dict` field to Document for title, author, creation date

**Annotations**:
- Add `annotations: list[Annotation]` for tracked changes, comments

**Graph Structure**:
- Add `GraphNode` and `GraphEdge` entities for contract graph (Phase 7+)
