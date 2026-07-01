# Implementation Plan: PII-to-Chunk Pipeline Bridge

**Branch**: `feat/008-pii-chunk-bridge` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/008-pii-chunk-bridge/spec.md`

## Summary

Add a `strip_pii_clauses()` function that strips PII from each clause's text individually while preserving clause metadata, so the chunking pipeline (`stream_chunks`) can operate on PII-safe text. The existing `strip_pii()` and `strip_and_persist()` remain unchanged.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: presidio-analyzer, presidio-anonymizer (existing in `src/openreview_cli/pii/engine.py`)

**Storage**: No new storage — existing `PiiResult` mapping file format reused

**Testing**: pytest (existing test patterns in `tests/unit/test_pii_engine.py` and `tests/integration/`)

**Target Platform**: Linux x86_64 (reference: 8 GB RAM, 2-core CPU)

**Project Type**: CLI tool (openreview-cli)

**Performance Goals**: `strip_pii_clauses()` within 10% of equivalent `strip_pii()` call (SC-004)

**Constraints**: Peak memory <100 MB (NLP model exempt — ~500 MB); no new external dependencies

**Scale/Scope**: Single document per call; typical 20–200 clauses per document

## Constitution Check

*GATE: Pass before Phase 0. Re-check after Phase 1.*

| Principle | Status | Rationale |
|-----------|--------|-----------|
| I. Privacy First | **Pass** | Bridge strips PII before chunking; no new data exposure paths |
| II. Local-First, CLI-Only | **Pass** | No network calls; no server; all processing local |
| III. Hardware-Bounded | **Pass** | Reuses existing PII engine; per-clause replacement adds no significant memory overhead |
| IV. Dependency Minimalism | **Pass** | No new dependencies — all reuse existing Presidio + Pydantic + stdlib |
| V. Spec-Driven, YAGNI | **Pass** | Minimal bridge function; no speculative abstractions; spec exists and is clarified |

## Project Structure

### Documentation (this feature)

```text
specs/008-pii-chunk-bridge/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (empty — no external interfaces)
├── spec.md              # Feature specification
├── checklists/
└── features.json
```

### Source Code (repository root)

```text
src/openreview_cli/
└── pii/
    └── engine.py              # Add strip_pii_clauses() function

tests/
├── unit/
│   └── test_pii_engine.py     # Add unit tests for strip_pii_clauses()
└── integration/
    └── test_chunking_cli.py   # Add T014 integration test
```

**Structure Decision**: Single project with one new function in the existing PII engine module. No new files, no new modules.

## Complexity Tracking

No violations — all principles pass.

## Clarifications Incorporated

Clarifications from `/speckit.clarify` session (2026-07-01):
- **Partial failure**: Return partial results with warnings (match existing `strip_pii()`)
- **PiiResult.stripped_text**: Joined text of all stripped clauses (consistent with existing)
- **Audit logging**: No per-clause audit added; reuse existing document-level audit
