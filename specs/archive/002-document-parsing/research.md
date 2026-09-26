# Research: Document Parsing Technologies

**Date**: 2026-06-25
**Feature**: 002-document-parsing

## Research Questions & Findings

### RQ1: NUPunkt API and Best Practices

**Source**: Context7 docs, GitHub (alea-institute/nupunkt)

**Decision**: Use NUPunkt for sentence/paragraph boundary detection with custom clause boundary logic on top.

**Key Findings**:
- **Installation**: `pip install nupunkt` (zero runtime dependencies, pure Python 3.11+)
- **License**: MIT (confirmed)
- **Performance**: 10M+ chars/sec (Python), 30M+ chars/sec (Rust version)
- **Precision**: 91.1% on legal text benchmarks
- **Model size**: ~432 MB loaded on first call

**API Reference**:
```python
from nupunkt import sent_tokenize, sent_spans, para_tokenize

# Sentence tokenization
sentences: List[str] = sent_tokenize(text)

# Character-level positions (contiguous, no gaps)
spans: List[Tuple[int, int]] = sent_spans(text)

# Paragraph tokenization
paragraphs: List[str] = para_tokenize(text)

# Adaptive tokenization with confidence
results = sent_tokenize(text, return_confidence=True)
# Returns List[Tuple[str, float]]
```

**Configuration Options**:
- `threshold=0.7` (default) — balanced precision/recall
- `threshold=0.85` — aggressive splitting (high precision)
- `threshold=0.5` — conservative (high recall)
- `dynamic_abbrev=True` — handles legal abbreviations automatically

**Gotchas**:
1. **No async API** — synchronous only. At 10M chars/sec, blocking is negligible.
2. **Full text required** — doesn't do incremental/streaming natively. Buffer text, then call `sent_tokenize`.
3. **Sentence boundaries only** — does NOT detect clause boundaries. Need custom logic for "Article I", "Section 3.1", etc.
4. **Model loaded on first call** — 432MB memory footprint. Plan accordingly.
5. **Spans are contiguous** — `sent_spans()` returns character offsets with no gaps. Safe to advance cursor.

**Alternatives Considered**:
- **CharBoundary** (same authors) — ML-based, 78.2% F1, requires scikit-learn. Rejected: NUPunkt has higher precision with zero deps.
- **NLTK sent_tokenize** — general-purpose, fails on legal abbreviations (Corp., Inc., v.). Rejected: NUPunkt is purpose-built for legal text.
- **Custom regex** — brittle, doesn't handle edge cases. Rejected: NUPunkt's 91.1% precision is proven.

---

### RQ2: PyMuPDF Streaming Patterns

**Source**: Context7 docs (pymupdf.readthedocs.io)

**Decision**: Use `for page in doc:` iteration with `get_text("dict")` for structured data.

**Key Findings**:

**Streaming Pattern**:
```python
import pymupdf

with pymupdf.open("document.pdf") as doc:
    for page in doc:  # lazy iteration
        data = page.get_text("dict", sort=True)
        # Process blocks, lines, spans
```

**Output Formats**:
| Format | Use Case | Speed |
|--------|----------|-------|
| `"text"` | Plain text, no layout | Fastest |
| `"blocks"` | Text blocks with bbox | Fast |
| `"dict"` | Full structure with font info | Best for clause extraction |
| `"words"` | Individual words with positions | Medium |

**Font Properties** (from `get_text("dict")`):
```python
span = {
    "size": 11.0,           # font size in points
    "flags": 16,            # bitfield: bit 4 = bold, bit 1 = italic
    "font": "Helvetica",
    "text": "Section 3.1",
    "bbox": (50, 88, 166, 103)  # (x0, y0, x1, y1)
}

# Detect bold
is_bold = bool(span["flags"] & (1 << 4))  # bit 4
```

**TOC Extraction**:
```python
toc = doc.get_toc()
# Returns: [[level, title, page], ...]
# Example: [[1, "Article I", 1], [2, "Section 1.1", 3]]
```

**Password Detection**:
```python
if doc.needs_pass:
    # PDF requires password
if doc.is_encrypted:
    # PDF is currently encrypted (before auth)
```

**Image-Only PDF Detection**:
```python
def is_image_only(doc):
    for page in doc:
        if page.get_text("text").strip():
            return False
    return True
```

**Performance**:
- Pages loaded on demand during iteration
- Memory stays constant (~10-50MB) regardless of page count
- Typical speed: 50-100 pages/sec for simple text, 10-30 pages/sec for complex layouts
- For 500+ pages: expect 5-30 seconds

**Memory Management**:
- Context manager (`with`) ensures cleanup
- Pages freed after iteration
- No manual cleanup needed

**Alternatives Considered**:
- **pdfplumber** — better table extraction, slower. Rejected: PyMuPDF is faster and sufficient for clause extraction.
- **pdfminer.six** — detailed layout analysis, complex API. Rejected: PyMuPDF is simpler and faster.

---

### RQ3: python-docx Streaming Patterns

**Source**: Context7 docs, python-docx documentation

**Decision**: Accept that python-docx loads full XML upfront. Use generators to process paragraphs immediately.

**Key Findings**:

**Critical Limitation**: python-docx does NOT support true streaming. `Document(path)` loads and parses the entire XML into memory on construction.

**Paragraph Iteration**:
```python
from docx import Document

doc = Document("contract.docx")
for para in doc.paragraphs:  # List[Paragraph], not iterator
    yield para.text  # Process immediately
```

**Heading Detection**:
```python
def get_heading_level(paragraph):
    style_name = paragraph.style.name
    if style_name == "Title":
        return 0
    if style_name.startswith("Heading "):
        return int(style_name.split(" ")[1])  # 1-9
    return None
```

**Font Properties** (for non-styled headings):
```python
for run in paragraph.runs:
    is_bold = run.bold  # True/False/None (inherited)
    font_size = run.font.size  # EMU or None (inherited)
    if font_size:
        size_pt = font_size.pt
```

**Tracked Changes Detection** (requires raw XML):
```python
from lxml import etree

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

def has_tracked_changes(doc):
    body = doc.element.body
    return any(body.iter(f"{{{WORD_NS}}}ins")) or any(body.iter(f"{{{WORD_NS}}}del"))
```

**Image Handling**:
```python
# Skip paragraphs with embedded images
for para in doc.paragraphs:
    if para._p.findall(f".//{{{WORD_NS}}}drawing"):
        continue
    yield para.text
```

**Performance**:
- Load time: O(n) — parses entire XML on `Document()` call
- Memory: Full DOM tree held in memory (lxml ElementTree)
- For 10MB+ files: consider raw `lxml.etree.iterparse` approach

**Mitigation for Large Files**:
```python
import zipfile
from lxml import etree

def stream_large_docx(path):
    with zipfile.ZipFile(path) as z:
        with z.open("word/document.xml") as f:
            for event, elem in etree.iterparse(f, tag="{...}p"):
                text = "".join(t.text or "" for t in elem.findall(".//{...}t"))
                yield text
                elem.clear()  # free memory
```

**Alternatives Considered**:
- **Raw lxml.iterparse** — true streaming, but complex. Rejected: Accept python-docx limitation for Phase 2, revisit if memory issues arise.
- **mammoth** — converts DOCX to HTML, loses structure. Rejected: Need paragraph-level control.

---

### RQ4: Rich Progress Bar Patterns

**Source**: Context7 docs (rich.readthedocs.io)

**Decision**: Use `Progress` with `transient=True` and page-level updates.

**Key Findings**:

**Basic Pattern**:
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
        process(page)
        progress.advance(task)
```

**Unknown Total** (for generators):
```python
task = progress.add_task("Parsing", total=None)  # pulsing spinner
# Update when total becomes known
if i == 0:
    progress.update(task, total=total_pages)
```

**Performance**:
- Overhead: ~1-2MB memory, negligible CPU
- `refresh_per_second=10` (default) is sufficient
- `transient=True` clears progress bar after completion

**Integration with Generators**:
```python
def stream_with_progress(generator, total, description="Processing"):
    with Progress(...) as progress:
        task = progress.add_task(description, total=total)
        for item in generator:
            yield item
            progress.advance(task)
```

**Alternatives Considered**:
- **tqdm** — simpler API, but Rich is already in project. Rejected: Use existing dependency.
- **Custom progress** — more work, inconsistent UI. Rejected: Rich provides polished output.

---

### RQ5: Legal Text Parsing Best Practices

**Source**: Tavily research, academic papers, open-source tools

**Decision**: Use NUPunkt for sentence boundaries, then apply regex patterns for clause detection.

**Key Findings**:

**Common Numbering Patterns**:
```python
# Top-level
r'^\s*(ARTICLE|Article|SECTION|Section)\s+(\d+|[IVXLCDM]+|[A-Z])[:\s.]'

# Decimal numbering
r'^\s*(\d+(?:\.\d+)*)[.)\s]'

# Parenthetical
r'^\s*\(([a-z]|\d+|[ivxlcdm]+)\)[\s.]'
```

**Clause Boundary Detection**:
```python
def split_clauses(text):
    pattern = r'(?m)^\s*(?:(?:ARTICLE|Article|SECTION|Section)\s+(?:\d+|[IVXLCDM]+)|\d+(?:\.\d+)*[.)]|\([a-z]\)|\(\d+\)|\([ivxlcdm]+\))'
    matches = list(re.finditer(pattern, text))

    clauses = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        clauses.append(text[start:end].strip())

    return clauses
```

**Hierarchy Detection**:
```python
def detect_nesting_level(line):
    patterns = [
        (r'^\s*Article\s+[IVXLCDM]+', 0, 'article'),
        (r'^\s*Section\s+\d+', 0, 'section'),
        (r'^\s*\d+\.', 1, 'decimal'),
        (r'^\s*\d+\.\d+\.', 2, 'subdecimal'),
        (r'^\s*\([a-z]\)', 2, 'letter'),
        (r'^\s*\(\d+\)', 3, 'number'),
        (r'^\s*\([ivxlcdm]+\)', 4, 'roman'),
    ]

    for pattern, level, ptype in patterns:
        if re.match(pattern, line.strip()):
            return level, ptype
    return -1, None
```

**Edge Cases**:
- **Hyphenation**: `re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)`
- **Abbreviations**: NUPunkt handles these automatically (Corp., Inc., v., §)
- **Cross-references**: Detect with regex, resolve by navigating hierarchy
- **Numbering resets**: Track context (paragraph numbering may reset under each Section)
- **Mixed conventions**: Same document may use "Article I" and "Section 2.1"
- **Jurisdictional variation**: US uses "Section", UK uses "Clause", civil law uses "Article"

**Open-Source Tools**:
- **NUPunkt** — legal sentence boundary detection (chosen)
- **Blackstone** — spaCy model for legal NER (not needed for Phase 2)
- **Legal-BERT** — pre-trained BERT (overkill for Phase 2)
- **CUAD** — contract dataset for testing (useful for test fixtures)

**Best Practices**:
1. Layer approach: Regex for structure → NLP for semantics → ML for edge cases
2. Preserve hierarchy: Build tree structures, not flat lists
3. Handle abbreviations: Legal text is dense with Corp., Inc., v., §
4. Test on diverse samples: Numbering conventions vary wildly
5. Fallback gracefully: Not all contracts are well-structured

---

## Summary of Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Clause boundary detection | NUPunkt + custom regex | 91.1% precision, handles abbreviations |
| PDF parsing | PyMuPDF `get_text("dict")` | Fast, provides font info, streaming |
| DOCX parsing | python-docx with generators | Accept limitation, revisit if needed |
| Heading detection | TOC → font → numbering | Layered, most reliable first |
| Reading order | `sort=True` (top-left→bottom-right) | Simple, handles multi-column |
| Flat documents | Split by paragraphs | Natural semantic unit |
| Progress display | Rich `Progress` with `transient=True` | Already in project, polished UI |

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| NUPunkt model size (432MB) | Memory budget | Load lazily, unload after parsing |
| python-docx loads full XML | Large DOCX files | Accept for Phase 2, use raw lxml if needed |
| Clause accuracy <95% | Spec violation | Tune NUPunkt threshold, improve regex patterns |
| Complex numbering patterns | Missed clauses | Test on diverse fixtures, iterate patterns |

## Next Steps

1. Create test fixtures (synthetic PDFs and DOCX files)
2. Implement `stream_clauses()` interface
3. Implement PDF parser with NUPunkt integration
4. Implement DOCX parser
5. Validate accuracy on test fixtures
6. Implement CLI command `openreview parse`
