# Research: Memo Export

**Feature**: specs/021-memo-export
**Date**: 2026-07-05
**Status**: All findings CONFIRMED

---

## 1. python-docx API for DOCX Memo Generation

**Decision**: Use `python-docx` `Document()`, `add_heading()`, `add_paragraph()`, `add_table()` APIs. Cell shading via `run.font.highlight_color` or `shading_elm` for background fill.

**Rationale**: `python-docx` is already a project dependency (`pyproject.toml`, verified in `.specify/memory/verified-sources.md`). No new dependency needed. The API is mature, well-documented, and supports all required memo elements:
- Tables for summary and per-clause sections
- Cell background colors (Green: RGB 198,239,206; Amber: RGB 255,235,156; Red: RGB 255,199,206)
- Paragraphs with mixed formatting (bold headers, italic disclaimers)
- Confidence bars via table cells with proportional width

**Alternatives considered**:
- `python-pptx` — PowerPoint output not requested; heavier dependency
- WeasyPrint — PDF deferred; not in scope
- Manual XML — too error-prone, no advantage over python-docx

**Source**: https://python-docx.readthedocs.io/en/latest/ (confirmed in `.specify/memory/verified-sources.md`)

---

## 2. GitHub-Flavored Markdown for Memo Output

**Decision**: Use GFM table syntax, emoji badges for G/A/R (`✅`/`⚠️`/`❌`), and ASCII confidence bars. All GFM features are zero-dependency.

**Rationale**: GFM renders correctly on GitHub, GitLab, Bitbucket, and most Markdown viewers. Tables, headings, horizontal rules (`---`), bold/italic, and code blocks are universally supported. Emoji `:shortcodes:` or Unicode emoji both work. The existing `_confidence_bar()` in `report.py` provides the ASCII bar pattern (`[████████░░]`).

**Alternatives considered**:
- Raw HTML in Markdown — renders on GitHub but not universally; avoid
- reStructuredText — less widely supported
- AsciiDoc — not zero-dependency

**Source**: https://github.github.com/gfm/ (known standard)

---

## 3. JSON Schema for MemoReport

**Decision**: The existing `ReviewReport` JSON output (`format_json()` in `report.py`) is extended with a wrapper object containing `memo_version`, `mode`, `document`, `playbook`, `review_date`, `overall`, `clauses`, `disclaimer`, and `tier_info`. See `data-model.md` for the full schema.

**Rationale**: The spec defines exactly these fields (FR-02, Scenario 2). The `format_json()` function already handles `ReviewReport` → dict conversion via `dataclasses.asdict()`. The memo JSON wraps this with metadata fields. No schema validation library needed — `json.dumps()` and manual key presence assertions in tests suffice.

**Alternatives considered**:
- Pydantic models — possible but adds coupling; plain dict is sufficient for output serialization
- JSON Schema (jsonschema) — unnecessary; we control both producer and consumer

**Source**: Spec §2 Scenario 2 — concrete JSON structure provided inline.

---

## 4. Confidence Bar Rendering

**Decision**: Reuse the `_confidence_bar()` function from `src/openreview_cli/review/report.py` for Markdown output. DOCX uses table cells with proportional width. JSON uses numeric float.

**Rationale**: The existing function renders `0.82 [████████░░]`. It's already tested and proven in terminal output. For DOCX, proportional-width table cells are the natural equivalent — a cell width of `confidence * 100%` of a fixed column width.

**Alternatives considered**:
- SVG bars — too complex for CLI output
- Unicode block characters — already what we use (U+2588/U+2591)
- Rich renderables — only for terminal, not for file output

**Source**: Existing code in `report.py` at line `_confidence_bar()`.

---

## 5. Output File Naming and Deduplication

**Decision**: Pattern `{mode}-{document-stem}-{timestamp}.{ext}`. If file exists, append `-1`, `-2` etc before extension.

**Rationale**: FR-09 specifies this exact pattern. The document stem is sanitized (spaces → hyphens, special chars removed). Timestamp uses UTC compact format. Deduplication prevents silent overwrites.

**Alternatives considered**:
- UUID filenames — not human-readable
- Always overwrite — violates FR-09 "never silently overwrite"
- Timestamp subdirectories — more complex; filename suffix is simpler

**Source**: Spec FR-09.

---

## 6. Existing Code Patterns to Follow

**Decision**: Match existing patterns in `src/openreview_cli/review/`:
- Dataclasses for models (matching `models.py`)
- Function-based renderers (matching `report.py`)
- Typer CLI flags (matching existing `--format` patterns in `app.py`)
- Test patterns from existing test files

**Rationale**: Consistency reduces cognitive load. The existing report.py already separates terminal from JSON format — the memo exporter extends this pattern to three formats.

**Source**: Codebase walk — `review/report.py`, `review/models.py`, `review/colors.py`, `grounding/models.py`.

---

## 7. No NEEDS CLARIFICATION Items

Every dimension in the Technical Context is resolvable from the spec and existing codebase:
- Language version: Python 3.12 (from constitution)
- Dependencies: python-docx (already installed), stdlib only
- Storage: filesystem (no database)
- Testing: pytest (existing)
- Performance: sub-second generation, no NLP model in export path
- Scale: 3 formats × 3 modes = 9 combinations; exporter is agnostic to mode

All items marked CONFIRMED.
