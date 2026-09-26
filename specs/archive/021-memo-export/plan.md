# Implementation Plan: Memo Export

**Branch**: `feat/021-memo-export` | **Date**: 2026-07-05 | **Spec**: `specs/021-memo-export/spec.md`

**Input**: Feature specification from `/specs/021-memo-export/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Convert the existing structured `ReviewReport` (from the single-party review pipeline) into formatted memo documents in three formats: Markdown (.md), JSON (.json), and DOCX (.docx). Covers first three review modes: PreCheck, DealCheck, HireCheck. Absorbs nine deferred presentation enhancements (D-4, D-5, D-6, D-7, D-8, D-16, D-20, D-30, D-34). No changes to the review pipeline — pure presentation layer.

The exporter reads the `ReviewReport` object, constructs memo sections (header, summary, per-clause assessments with G/A/R color coding and confidence bars, recommendation, disclaimer, playbook version), and renders each section in the target format. Output files are written to `review_results/` (default) or a user-specified `--output-dir`. The `--format` CLI flag accepts multiple values (`md`, `json`, `docx`); default is Markdown.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**:
- `python-docx>=1.2.0` — DOCX document generation (already installed, verified in `.specify/memory/verified-sources.md`)
- Standard library only: `json`, `pathlib`, `dataclasses`, `datetime`, `typing`
- Existing project modules: `openreview_cli.review.models` (ReviewReport, ClauseAssessment), `openreview_cli.review.colors` (AssessmentColor) — `src/openreview_cli/review/colors.py` exists on filesystem, exports `AssessmentColor(StrEnum)`, `openreview_cli.grounding.models` (CitationProvenance) — `src/openreview_cli/grounding/models.py` exists on filesystem, exports `CitationProvenance`

**Storage**: Filesystem — output directory `review_results/` (default) or user-specified path. Auto-creates if missing. No database needed.

**Testing**: pytest with existing test infrastructure (`tests/unit/`, `tests/integration/`). Three independent tests per format (FR-01–FR-12). Edge case tests for truncation, missing citations, and duplicate format flags.

**Target Platform**: Linux, macOS, Windows (local CLI)

**Project Type**: Local CLI tool (Python package `openreview-cli`)

**Performance Goals**:
- Memo generation for a 50-clause report: < 1s total (all three formats)
- DOCX generation for 50 clauses: < 500ms
- Peak memory: < 100 MB base + DOCX library overhead (python-docx is lightweight, ~5 MB loaded)
- No full-document text loaded in memory — streaming from ReviewReport dataclass

**Constraints**:
- Python 3.12 minimum
- `uv` package manager only
- No new dependencies (python-docx already in `pyproject.toml`)
- No web server / no long-running process
- PII data already stripped before memo generation — memo operates on sanitized data
- AGPL-3.0 + Commercial dual license compatibility
- No automated Pass/Fail — memo uses Green/Amber/Red + confidence scores
- Citation grounding runs post-generation — memo displays provenance from ReviewReport
- Color codes read from ReviewReport, not computed in exporter
- Prompts are versioned artifacts — memo reads playbook version from report metadata
- Gateway routing untouched — memo is post-pipeline

**Scale/Scope**:
- ~100–200 lines of exporter code per format (3 exporters: Markdown, JSON, DOCX)
- ~150 lines of CLI flag wiring (`--format`, `--output-dir`)
- ~200 lines of shared utilities (filename generation, directory creation, deduplication)
- Tests: ~300 lines (6 test files)
- 3 review modes (PreCheck, DealCheck, HireCheck) — mode only affects filename prefix and header text

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Justification |
|-----------|---------|---------------|
| **I. Privacy First** | PASS | Memo reads PII-stripped ReviewReport. Raw contract text never written to output without prior PII removal. No new network calls. |
| **II. Local-First, CLI-Only** | PASS | Memo written to local filesystem only. No server, daemon, telemetry, or network path. |
| **III. Hardware-Bounded** | PASS | Streaming generation — no full-document load. ReviewReport already in memory from pipeline. DOCX generation < 500ms for 50 clauses. No NLP model involved. |
| **IV. Dependency Minimalism** | PASS | Zero new runtime deps. `python-docx` already in `pyproject.toml`. Stdlib `json`, `pathlib`, `dataclasses` for everything else. |
| **V. Spec-Driven, YAGNI** | PASS | Pure presentation layer based on existing ReviewReport. No pipeline changes. No speculative abstractions (one exporter interface, one implementation per format). |

**Result**: **PASS** — no violations. Complexity tracking section not required.

## Project Structure

### Documentation (this feature)

```text
specs/021-memo-export/
├── spec.md              # Feature specification (input)
├── plan.md              # This file — implementation plan
├── research.md          # Phase 0 — research findings
├── data-model.md        # Phase 1 — data model and relationships
├── quickstart.md        # Phase 1 — validation guide
└── tasks.md             # Phase 2 — task breakdown (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/openreview_cli/review/
├── __init__.py           # Exports (unchanged)
├── models.py             # ReviewReport, ClauseAssessment (unchanged, minor additions for memo_version if needed)
├── colors.py             # AssessmentColor, assign_colors (unchanged)
├── report.py             # Terminal + JSON formatting (unchanged, existing)
├── pipeline.py           # Review pipeline (unchanged)
├── extraction.py         # Extraction agent (unchanged)
├── qa.py                 # QA agent (unchanged)
├── base.py               # Base command (unchanged)
├── playbook.py           # Playbook loader (unchanged)
├── prompts.py            # Prompt templates (unchanged)
├── _gateway.py           # Gateway helper (unchanged)
├── memo/                 # NEW — memo export module
│   ├── __init__.py       # Public API: export_memo(), MemoFormat
│   ├── exporter.py       # MemoExporter — orchestrator class
│   ├── formats.py        # Format renderers: render_markdown(), render_json(), render_docx()
│   ├── filename.py       # Filename generation, dedup, output directory logic
│   └── models.py         # MemoFormat enum, MemoReport dataclass (JSON schema)

tests/
├── unit/review/
│   ├── test_memo_exporter.py  # Unit: MemoExporter construction, section assembly
│   ├── test_memo_formats.py   # Unit: each format renderer output correctness
│   └── test_memo_filename.py  # Unit: filename generation, dedup, output dir
└── integration/
    ├── test_memo_export.py    # Integration: CLI --format flags, end-to-end export
    └── test_memo_edge_cases.py # Edge cases: empty report, truncation, missing citations
```

**Structure Decision**: Single-project layout follows existing pattern. New `memo/` subpackage under `review/` keeps export logic co-located with the review pipeline it serves. `formats.py` separates renderers from orchestration and filename logic.

## Research Needs (resolved in research.md)

No NEEDS CLARIFICATION items. The spec is comprehensive. Research covers:
1. python-docx API for creating tables, cell shading, paragraphs, and runs — confirmed from verified-sources
2. GitHub-Flavored Markdown conventions for tables and badges — well-documented standard
3. JSON schema for MemoReport extending ReviewReport — design derived from spec §2 Scenario 2
4. Confidence bar rendering patterns (ASCII bars) — used in existing `_confidence_bar()` in report.py
5. Output file naming conventions — specified in FR-09, confirmed
