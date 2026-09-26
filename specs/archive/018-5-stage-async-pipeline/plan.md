# Implementation Plan: 5-Stage Async Pipeline Framework

**Branch**: `feat/018-5-stage-async-pipeline` | **Date**: 2026-07-04 | **Spec**: `specs/018-5-stage-async-pipeline/spec.md`

**Input**: Feature specification from `specs/018-5-stage-async-pipeline/spec.md`

## Summary

Build a reusable async pipeline runner (`src/openreview_cli/pipeline/`) that decouples stage logic from orchestration. Five stage types — Parse → Strip → Chunk → Retrieve → Generate — each wrap an existing capability module. The pipeline runner provides sequential execution, async IO concurrency within stages, per-stage cleanup for memory budget, error isolation (critical vs non-critical), and progress reporting. The first consumer is `run_review()` in `review/__init__.py`, rewritten to use the framework without changing user-facing behaviour.

## Technical Context

**Language/Version**: Python 3.12 (as specified, via `.python-version` and `pyproject.toml`)

**Primary Dependencies**: None new. Pipeline uses stdlib only: `asyncio`, `dataclasses`, `abc`, `time`, `tracemalloc`, `logging`. Stage adapters depend on existing modules:
- `openreview_cli.parsing` (C-08) — document parsing
- `openreview_cli.pii` (N-4a / C-10) — PII stripping
- `openreview_cli.chunking` (C-32) — clause chunking
- `openreview_cli.retrieval` (C-19) — hybrid retrieval
- `openreview_cli.gateway` (C-12) — AI Gateway routing

**Storage**: None. Pipeline context is an in-memory dict. Any stage that persists data (e.g., retrieval writes to SQLite) does so through its own module's storage layer.

**Testing**: `pytest` (existing infra). TDD — write pipeline runner tests first, then stage adapter tests. Test categories:
- Unit: `tests/unit/test_pipeline_runner.py`, `tests/unit/test_pipeline_stages.py`
- Integration: `tests/integration/test_pipeline_e2e.py` (5-stage mock pipeline)
- Memory: `tests/integration/test_pipeline_memory.py` (tracemalloc assertions)

**Target Platform**: Linux (CI), macOS (dev), Windows (compatibility — no platform-specific code). Local CLI only.

**Project Type**: CLI application (Python package `openreview-cli`)

**Performance Goals**:
- 5-stage pipeline on 50-page PDF: <30 seconds (fast local implementations, no network IO)
- Pipeline runner overhead: <15 MB peak above the heaviest single stage (measured via tracemalloc)
- Cleanup callback releases stage-owned references before next stage allocates, keeping pipeline overhead under `max_memory_mb`

**Constraints**:
- Peak memory <100 MB processing (110 MB test ceiling); PII NLP model (~500 MB spaCy) is exempt per constitution Principle III
- No new third-party dependencies (stdlib only for orchestration)
- No multiprocessing or subprocess forking (async IO concurrency only)
- No change to user-facing CLI behaviour
- Forbidden dependencies: langchain, llama-index, FAISS, spaCy (for PII), sentence-transformers, Click, loguru/structlog, FastAPI/Flask

**Scale/Scope**: Single CLI invocation. One document at a time, 5 stages per document. Stage count is fixed but composable (subset pipeline supported).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Privacy First** | Pass | PII stripping happens in StripStage before any network call (GenerateStage). Pipeline context does not log raw text. Stage adapters reuse existing PII module which enforces privacy. |
| **II. Local-First, CLI-Only** | Pass | Pipeline runs synchronously from CLI perspective. No daemon, no web server, no background process. Async is internal-only for IO concurrency. All-local stage configuration is supported. |
| **III. Hardware-Bounded** | Pass | Per-stage `cleanup()` callbacks release memory before next stage allocates. Pipeline runner overhead is <15 MB peak. Streaming parsing (page-by-page) is already in ParseStage's adapter. No multiprocessing. spaCy exemption continues to apply. |
| **IV. Dependency Minimalism** | Pass | Zero new runtime dependencies. Stdlib `asyncio`, `dataclasses`, `abc`, `time`, `tracemalloc` for the pipeline runner. Stage adapters reference existing modules only. No forbidden deps. |
| **V. Spec-Driven, YAGNI** | Pass | This plan implements exactly the spec. No speculative abstractions: no interface with one implementation, no factory for one product. Pipeline runner is a concrete `Pipeline` class with a `Stage` protocol. |

**Gate Result**: PASS — no violations. All principles satisfied by the proposed design. No Complexity Tracking required.

## Project Structure

### Documentation (this feature)

```text
specs/018-5-stage-async-pipeline/
├── plan.md              # This file (/speckit.plan command output)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── __init__.py              # __version__ = "0.1.0" (unchanged)
├── __main__.py              # python -m entry point (unchanged)
├── app.py                   # Typer app (unchanged, no new CLI command)
├── errors.py                # Exit codes (unchanged)
├── pipeline/                # NEW — pipeline framework
│   ├── __init__.py          # Public API: Pipeline, Stage, PipelineReport, run_pipeline
│   ├── base.py              # Stage protocol (ABC), StageResult, PipelineContext
│   ├── runner.py            # Pipeline orchestrator — run(), cancellation, progress
│   ├── errors.py            # PipelineError, StageError, CriticalStageError
│   ├── progress.py          # ProgressEvent, ProgressCallback types
│   └── adapters/            # Stage adapters wrapping existing modules
│       ├── __init__.py      # Exports all stage adapters
│       ├── parse.py         # ParseStage — wraps openreview_cli.parsing.parse_document
│       ├── strip.py         # StripStage — wraps openreview_cli.pii.strip_pii_clauses
│       ├── chunk.py         # ChunkStage — wraps openreview_cli.chunking.stream_chunks
│       ├── retrieve.py      # RetrieveStage — wraps openreview_cli.retrieval.RetrievalEngine
│       └── generate.py      # GenerateStage — wraps openreview_cli.gateway.Gateway
├── review/
│   ├── __init__.py          # REFACTORED: run_review() uses pipeline framework
│   └── ... (unchanged)
├── parsing/                 # Unchanged (C-08)
├── pii/                     # Unchanged (C-10/C-11)
├── chunking/                # Unchanged (C-32)
├── retrieval/               # Unchanged (C-19)
└── gateway/                 # Unchanged (C-12)

tests/
├── unit/
│   ├── test_pipeline_runner.py     # NEW — Pipeline orchestrator tests
│   ├── test_pipeline_stages.py     # NEW — Stage adapter unit tests
│   └── ... (unchanged)
├── integration/
│   ├── test_pipeline_e2e.py        # NEW — 5-stage mock pipeline integration test
│   ├── test_pipeline_memory.py     # NEW — tracemalloc memory budget test
│   └── ... (unchanged)
└── fixtures/                # Unchanged
```

**Structure Decision**: Single project (Python package) — no change to existing layout. New `pipeline/` package under `src/openreview_cli/`. Stage adapters live within `pipeline/` as `adapters/` sub-package, keeping adapter coupling local to the pipeline module.

## Implementation Phases

### Phase 0: Research & Unknowns (resolved in research.md)

All NEEDS CLARIFICATION from spec analysis:
1. ~~How does the existing `run_review()` loop work?~~ → Resolved: reads from review/__init__.py, it's a synchronous per-document loop calling parse → pii → extract → QA → report inline
2. ~~How do existing modules export their interfaces?~~ → Resolved: `parse_document()` in parsing (returns `(Document, list[Clause])`), `strip_pii_clauses()` in pii, `stream_chunks()` in chunking, `RetrievalEngine.search()` in retrieval (class method, not bare function), `Gateway.chat()` in gateway
3. ~~What cancellation pattern fits the CLI?~~ → Resolved: asyncio.Event-based cancellation_token, caught at run() level via KeyboardInterrupt → set event → await current stage to finish → return partial PipelineReport
4. ~~How to measure memory per stage?~~ → Resolved: tracemalloc snapshots before/after each stage run, plus psutil.Process().memory_info().rss for peak tracking
5. ~~Adoption sequence for run_review()?~~ → Resolved: land pipeline/ standalone with tests (this PR), then refactor run_review() in same branch, preserve all existing acceptance tests

### Phase 1: Implementation

1. Create `src/openreview_cli/pipeline/` package
2. Implement core: `base.py` (Stage ABC, StageResult, PipelineContext), `runner.py` (Pipeline orchestrator), `progress.py` (progress event types), `errors.py` (pipeline error hierarchy)
3. Implement stage adapters in `adapters/` (five wrappers)
4. Write unit tests for runner (ordering, error isolation, skip, cancellation, empty pipeline)
5. Write unit tests for each stage adapter (input/output contract)
6. Write integration test for 5-stage mock pipeline
7. Write memory integration test (tracemalloc peak <15 MB overhead)
8. Refactor `run_review()` to use pipeline framework
9. Verify all existing review acceptance tests pass with zero changes

### Phase 2: Tasks (deferred to /speckit.tasks)

Task breakdown file at `specs/018-5-stage-async-pipeline/tasks.md`.

## Key Design Decisions

### Pipeline Runner Abstraction

```python
class Stage(ABC):
    name: str
    critical: bool = False
    cleanup: Callable[[], None] | None = None

    @abstractmethod
    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        ...
```

The `Pipeline` class orchestrates stages:
- Accepts `list[Stage]`, optional `max_memory_mb`, optional `cancellation_token` (asyncio.Event)
- `run()` is an async method that iterates stages, calls `stage.run(ctx)`, merges results into ctx, calls `stage.cleanup()`, reports progress
- Returns `PipelineReport` with per-stage results, total duration, cancellation flag, peak memory

### Async Model

- Pipeline runner itself is async (top-level `run()` is a coroutine)
- CLI entry point wraps with `asyncio.run()` — synchronous from user's perspective
- Each stage's `run()` is a coroutine (may use asyncio.gather for IO-bound parallel work within a stage)
- No threading, no multiprocessing — asyncio event loop handles concurrency

### Memory Budget

- `tracemalloc.start()` before pipeline run
- Snapshot before each stage, snapshot after cleanup
- If peak delta exceeds `max_memory_mb`, emit warning to logger
- Cleanup callback is the mechanism: stage releases large references (full text, full clause list) when `cleanup()` is called
- The runner holds only the shared context dict (which contains only stage outputs, not intermediate allocations)

### Stage Adapter Pattern

Each adapter wraps an existing capability module:

```python
class ParseStage(Stage):
    name = "parse"
    def __init__(self):
        self._result: dict | None = None

    async def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        doc, clauses = parse_document(ctx["document_path"])
        return {"document": doc, "clauses": clauses}

    def cleanup(self) -> None:
        self._result = None
```

Adapters are thin — typically 10-30 lines each. They translate between the pipeline context dict and the existing module's function signature.

### CLI Integration

No new CLI command. The pipeline framework is adopted by refactoring `run_review()`:

```python
def run_review(...):
    stages = [
        ParseStage(),
        StripStage(no_pii=no_pii),
        ChunkStage(),
        RetrieveStage(),
        GenerateStage(extraction_model=extraction_model, qa_model=qa_model),
    ]
    pipeline = Pipeline(stages=stages, progress_callback=_report_progress)
    report = asyncio.run(pipeline.run({"document_path": str(doc_path)}))
    # Convert PipelineReport to existing ReviewReport format
    ...
```

### Error Isolation

- Non-critical stage failure: error captured in StageResult, stored in ctx["errors"], subsequent stages execute
- Critical stage failure (e.g., ParseStage marked critical): pipeline halts immediately, error propagated to caller
- `KeyboardInterrupt` during async run: cancellation token set, in-flight stage receives cancellation, partial PipelineReport returned with `cancelled=True`
- Zero-byte input: stage returns empty result set (not an error)

## Adoption Plan

1. [x] Land pipeline framework as private module with tests — THIS PLAN
2. [ ] Refactor `run_review()` to use pipeline framework — within same feature branch
3. [ ] Verify all existing review acceptance tests pass with zero changes
4. [ ] Bilateral and benchmark pipelines can adopt in follow-up PRs (out of scope for this feature)

This plan aligns with spec §5 (Adoption Strategy — Incremental).
