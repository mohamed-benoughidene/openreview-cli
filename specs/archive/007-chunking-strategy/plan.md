# Implementation Plan: Chunking Strategy

**Branch**: `feat/007-chunking-strategy` | **Date**: 2026-07-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-chunking-strategy/spec.md`

## Summary

Implement clause-boundary-aware chunking using Recursive Character Text Splitting (RCTS). The chunking module operates on parsed clauses (Phase 2) and PII-stripped text (Phase 3), producing retrieval-ready chunks with hierarchical structure and metadata. No new external dependencies — pure Python on existing Clause dataclass.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: None new — chunking is pure Python operating on existing `openreview_cli.parsing.models.Clause`

**Storage**: SQLite (future: chunks stored for retrieval via sqlite-vss; not in scope for this phase)

**Testing**: pytest (existing infrastructure in `tests/unit/`)

**Target Platform**: Linux (reference: 8 GB RAM, 2-core CPU, no GPU)

**Project Type**: CLI tool (Python package, src layout)

**Performance Goals**: Chunk a 50-page parsed contract in <2 seconds (SC-001)

**Constraints**: Peak memory for chunking logic <10 MB (SC-005), streaming iterator (FR-009)

**Scale/Scope**: Single document at a time, no limit on document size

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | PASS | Chunking operates on PII-stripped text (FR-008). No PII leakage. |
| II. Local-First, CLI-Only | PASS | Local CLI command, no server, no daemon. |
| III. Hardware-Bounded | PASS | <10 MB peak memory (SC-005), streaming chunk iterator (FR-009), `@dataclass(slots=True)` (FR-020). |
| IV. Dependency Minimalism | PASS | No new dependencies. RCTS implemented from scratch. |
| V. Spec-Driven, YAGNI | PASS | Spec written first (007-chunking-strategy/spec.md). Minimal scope: chunking only, no retrieval. |

## Project Structure

### Documentation (this feature)

```text
specs/007-chunking-strategy/
├── plan.md              # This file
├── spec.md              # Feature specification (input)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── chunking-api.md
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── chunking/            # NEW module
│   ├── __init__.py      # Exports stream_chunks, Chunk, ChunkConfig
│   ├── models.py        # Chunk, ChunkConfig dataclasses
│   ├── tokenizer.py     # Whitespace + punctuation tokenizer
│   ├── splitter.py      # RCTS with clause-boundary awareness
│   └── stream.py        # stream_chunks(clauses) -> Iterator[Chunk]

tests/
├── unit/
│   ├── test_chunking_models.py
│   ├── test_chunking_tokenizer.py
│   ├── test_chunking_splitter.py
│   └── test_chunking_stream.py
└── integration/
    └── test_chunking_cli.py
```

**Structure Decision**: Single-project src layout (existing convention). New `chunking/` module follows same pattern as `parsing/` and `pii/`.

## Complexity Tracking

No constitution violations — all principles pass.
