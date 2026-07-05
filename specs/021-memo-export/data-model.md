# Data Model: Memo Export

**Feature**: specs/021-memo-export
**Date**: 2026-07-05
**Status**: Final

---

## Overview

The memo export feature introduces five data structures and one service class. All structures follow the project's existing `@dataclass` pattern (`review/models.py`, `grounding/models.py`). No new dependencies.

The data flow is:

```
ReviewReport (from pipeline)
    │
    ▼
MemoExporter.export(report, formats, output_dir)
    │
    ├─▶ render_markdown(report) → str → write .md file
    ├─▶ render_json(report)     → str → write .json file
    └─▶ render_docx(report)     → Document → save .docx file
```

---

## 1. MemoFormat (enum)

Defined in `src/openreview_cli/review/memo/models.py`.

```python
class MemoFormat(StrEnum):
    MARKDOWN = "md"
    JSON = "json"
    DOCX = "docx"
```

| Value | Extension | Renderer |
|-------|-----------|----------|
| `md` | `.md` | Markdown text |
| `json` | `.json` | JSON string |
| `docx` | `.docx` | python-docx Document |

**Validation**: Only three values accepted. Unknown values produce error: "Unsupported export format: {format}. Supported formats: md, json, docx."

---

## 2. MemoReport (dataclass) — JSON Schema

Defined in `src/openreview_cli/review/memo/models.py`. Wraps the existing `ReviewReport` with memo-specific metadata fields. Used as the intermediate representation for JSON output and as the internal data source for all format renderers.

```python
@dataclass
class MemoReport:
    """Top-level memo report wrapping ReviewReport with memo-specific fields."""
    memo_version: str            # "1.0"
    mode: str                    # "precheck" | "dealcheck" | "hirecheck"
    document_name: str           # original filename (no path)
    playbook_name: str           # e.g., "nda-v1"
    playbook_version: str        # semantic version, e.g., "1.2.0"
    review_date: str             # ISO 8601 UTC timestamp
    overall: MemoSummary         # aggregate statistics
    clauses: list[MemoClause]    # per-clause assessments
    disclaimer: str              # AI-generated disclaimer (fixed text)
    tier_info: MemoTierInfo | None = None  # privacy tier info (optional)
```

### MemoSummary

```python
@dataclass
class MemoSummary:
    recommendation: str          # "approve" | "revise" | "reject"
    clauses_checked: int
    matches: int                 # clauses where position is preferred/acceptable and color is green
    differences: int             # clauses where position is walkaway or color is amber/red
    confidence_avg: float        # average confidence across all clauses (0.0–1.0)
```

**Recommendation logic**:
- **approve**: all clauses Green (≥ 95% match rate, no Red clauses)
- **revise**: any Amber clauses present, no Red clauses, or minor issues
- **reject**: any Red clauses present, or match rate < 50%

### MemoClause

```python
@dataclass
class MemoClause:
    id: str                      # clause identifier (e.g., "clause-003")
    title: str                   # clause title or category name
    playbook_requirement: str    # the playbook position text
    contract_text: str           # the contract clause text (truncated at 10k chars)
    assessment: str              # "match" | "difference"
    color: str                   # "green" | "amber" | "red"
    confidence: float            # 0.0–1.0
    citation: MemoCitation | None  # provenance data or None
    severity: str | None         # "minor" | "major" | None (for differences)
    source_filename: str | None  # for multi-document sets (exhibits)
```

### MemoCitation

```python
@dataclass
class MemoCitation:
    clause_id: str               # e.g., "§12.3"
    paragraph_index: int         # 0-based paragraph index
    line_range: tuple[int, int]  # (start_line, end_line)
```

### MemoTierInfo

```python
@dataclass
class MemoTierInfo:
    privacy_tier: str            # "maximum" | "balanced" | "performance"
    pii_stripped: bool
    entities_redacted: int       # count of PII entities redacted
```

---

## 3. MemoExporter (service class)

Defined in `src/openreview_cli/review/memo/exporter.py`.

```python
@dataclass
class MemoExporter:
    report: ReviewReport
    mode: str                    # "precheck" | "dealcheck" | "hirecheck"
    output_dir: Path = Path("review_results")
    formats: set[MemoFormat] = field(default_factory=lambda: {MemoFormat.MARKDOWN})

    def export(self) -> dict[MemoFormat, Path]:
        """Export memo in all requested formats.

        Returns dict mapping each format to the output file path.
        Raises ExportError if the review has no assessments.
        """
        ...
```

**Construction**: Receives the completed `ReviewReport` at construction time. Does not call any review pipeline components.

**Methods**:
| Method | Purpose |
|--------|---------|
| `export()` | Orchestrates export for all requested formats. Calls `_build_memo_report()` then renderers. |
| `_build_memo_report()` | Converts `ReviewReport` → `MemoReport` (intermediate representation). Handles field mapping, defaults, and truncation. |
| `_render_markdown(memo)` | Returns Markdown string |
| `_render_json(memo)` | Returns JSON string |
| `_render_docx(memo)` | Returns python-docx Document |
| `_write_file(content, format)` | Writes output file with correct name and extension. Handles deduplication. |
| `_generate_filename(format)` | Generates filename per FR-09 pattern. |
| `_sanitize_stem(name)` | Sanitizes document stem (spaces → hyphens, remove special chars). |

**Error handling**:
- **No assessments**: raises `ExportError("No review results to export. The review did not complete.")`
- **Unsupported format**: raises `ExportError("Unsupported export format: {fmt}")`
- **DOCX write failure**: logged as error; other formats still written
- **Directory creation failure**: raises `ExportError(f"Cannot create output directory: {path}")`

---

## 4. Section Assembly Logic

The memo is assembled from these sections (all required — FR-03):

| Section | Data Source | Required Fields |
|---------|-------------|-----------------|
| **Header** | `MemoReport` | document name, mode, review date, playbook name/version |
| **Summary Table** | `MemoSummary` | clauses checked, matches, differences, avg confidence, recommendation |
| **Per-Clause** | `list[MemoClause]` | id, title, G/A/R badge, confidence bar, playbook req, contract text, assessment, citation |
| **Recommendation** | `MemoSummary.recommendation` | overall verdict (approve/revise/reject) |
| **Disclaimer** | constant | Fixed AI-generated disclaimer text |
| **Differences Only** | derived from clauses | If differences == 0, show "No differences found" |

**Per-clause rendering details**:
- Color badge: `MemoClause.color` → format-specific visual
- Confidence bar: `MemoClause.confidence` → ASCII/proportional/float
- Contract text truncation: if `len(text) > 10000`, truncate + append "... Truncated to 10,000 characters."
- Missing citation: show "Citation: not available"

### Color-to-RGB Mapping (DOCX Cell Fills)

Per FR-04, the three assessment colors map to specific RGB values for DOCX cell background fills:

| AssessmentColor | RGB Value | Visual |
|-----------------|-----------|--------|
| `green` | `(198, 239, 206)` | Light green fill |
| `amber` | `(255, 235, 156)` | Light yellow/amber fill |
| `red` | `(255, 199, 206)` | Light red/pink fill |

The exporter applies these RGB values when rendering DOCX tables cells:
```python
from docx.oxml.ns import qn

COLOR_RGB_MAP: dict[str, tuple[int, int, int]] = {
    "green": (198, 239, 206),
    "amber": (255, 235, 156),
    "red": (255, 199, 206),
}

def _apply_cell_fill(cell, color: str) -> None:
    rgb = COLOR_RGB_MAP.get(color)
    if rgb is None:
        return  # unknown color — leave default white fill
    shading = cell._tc.get_or_add_tcPr()
    fill_hex = f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
    shading_elm = shading.makeelement(qn("w:shd"), {
        qn("w:fill"): fill_hex,
        qn("w:val"): "clear",
    })
    shading.append(shading_elm)
```

This mapping is used exclusively by the DOCX renderer. Markdown and JSON formats use text badges and string values respectively.

---

## 5. State Transitions

Memo export is a terminal (leaf) operation. It does not change pipeline state.

```
ReviewPipeline.run() → ReviewReport → MemoExporter.export() → .md / .json / .docx file(s)
                                           │
                                           └─▶ No state change. Returns file paths.
```

The exporter is stateless — calling `export()` twice on the same `MemoReport` produces identical output.

---

## 6. Existing Models Reused (unchanged)

| Model | Source | Usage in Memo Export |
|-------|--------|---------------------|
| `ReviewReport` | `review/models.py` | Input to MemoExporter. Read-only access. |
| `ClauseAssessment` | `review/models.py` | Per-clause data source. Fields: `clause_id`, `clause_text`, `playbook_category`, `position`, `confidence`, `color`, `effective_confidence`, `grounding_provenances`. |
| `AssessmentColor` | `review/colors.py` | Color enum values read directly from ClauseAssessment. |
| `CitationProvenance` | `grounding/models.py` | Citation data per clause. Fields: `clause_id`, `paragraph_index`, `confidence`. |
| `DocMeta` | `review/models.py` | Document metadata for header (filename, page_count, pii_stripped). |
| `ReviewSummary` | `review/models.py` | Aggregate stats (mapped to `MemoSummary`). |
