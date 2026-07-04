# Phase 0 Research — 5-Stage Async Pipeline Framework

**Date**: 2026-07-04 | **Spec**: `specs/018-5-stage-async-pipeline/spec.md`

## Research Tasks and Resolutions

### Task 1: How does the existing `run_review()` loop work?

**Method**: Read `src/openreview_cli/review/__init__.py` (266 lines) and `src/openreview_cli/review/base.py` (131 lines).

**Decision**: The existing `run_review()` is a synchronous per-document loop:
1. Parse document via `stream.parse_document()` → list of `Clause` objects
2. Strip PII via `pii.engine.strip_and_persist()` if not `no_pii`
3. For each clause: extract assessment via `extraction.extract_clause()`, verify via `qa.verify_assessment()`, assign colors
4. Assemble `ReviewReport` per document

The stages are inlined — no abstraction between parse, strip, extract, QA, report. The pipeline framework will replace this inline flow with a composable stage list.

### Task 2: What interfaces do existing modules export?

**Method**: Read `__init__.py` files for each capability module.

**Decision**:
- `parsing/__init__.py`: exports `stream_clauses(path) → Iterator[Clause]`, `parse_document()`, format helpers
- `pii/__init__.py` (54 lines): exports `strip_pii_clauses(clauses, ...) → list[Clause]`, `PiiConfig`, `PiiResult`
- `chunking/__init__.py` (4 lines): exports `chunk_clauses(clauses, strategy, ...) → list[Chunk]`
- `retrieval/__init__.py` (39 lines): exports `search(query, index_path, ...) → list[SearchResult]`, `ingest(chunks, ...)`
- `gateway/__init__.py` (27 lines): exports `Gateway`, `GatewayConfig`, `chat()` method

Each adapter wraps the corresponding export. Adapters are thin (10-30 lines).

### Task 3: What cancellation pattern fits the CLI?

**Decision**: Use `asyncio.Event` as a cancellation token. The pipeline runner checks it between stages and inside each stage's IO loop. On `KeyboardInterrupt`, the CLI wrapper:
1. Sets the cancellation event
2. Waits for the current stage to finish (graceful cancellation)
3. Returns partial `PipelineReport` with `cancelled=True`

Rationale: stdlib `asyncio.Event` is zero-dependency, supports cooperative cancellation patterns, and composes with `asyncio.wait_for()` for timeouts.

### Task 4: How to measure memory per stage?

**Decision**: Use `tracemalloc` (stdlib) for snapshot-based memory tracking:
- `tracemalloc.start()` before pipeline run
- Snapshot before each stage, snapshot after `cleanup()`
- Compare size of differential: stage memory = snapshot_diff.total_size
- Also track `psutil.Process().memory_info().rss` for peak RSS

`psutil` is already an optional dev dependency in `pyproject.toml` (used by existing memory tests). The pipeline uses `tracemalloc` as primary measurement and falls back to `psutil` if available for RSS peaks.

### Task 5: What is the adoption sequence for `run_review()`?

**Decision**: Follow spec §5 (Adoption Strategy):
1. Land `pipeline/` as standalone module with full test suite — NO changes to consumers
2. In the same branch, refactor `run_review()` to use pipeline framework
3. Verify zero regressions in existing review test suite
4. Bilateral/benchmark consumers are follow-up PRs (out of scope for this feature)

### Task 6: asyncio best practices for Python 3.12 CLI tool

**Decision**: Use `asyncio.run(pipeline.run(...))` as the entry point. Inside each stage, use `asyncio.gather()` for concurrent IO-bound work (e.g., parallel API calls for multiple playbook questions). No threading, no multiprocessing — GIL-bound CPU work stays within each stage's sync function, wrapped in `asyncio.to_thread()` only if proven necessary by profiling.

### Task 7: Stage interface best practices — protocol vs ABC

**Decision**: Use `abc.ABC` with `@abstractmethod` for the Stage base class. The spec requires `run(context) → dict` and optional `cleanup()`. ABC provides:
- Clear type enforcement (cannot instantiate without implementing `run()`)
- `cleanup()` as optional method (concrete class decides whether to override)
- Compatibility with mypy strict mode (project constraint)

## External Dependency References

All libraries referenced by the pipeline framework are stdlib:
- `asyncio` — Python 3.12 stdlib, CONFIRMED
- `dataclasses` — Python 3.12 stdlib, CONFIRMED
- `abc` — Python 3.12 stdlib, CONFIRMED
- `time` — Python 3.12 stdlib, CONFIRMED
- `tracemalloc` — Python 3.12 stdlib, CONFIRMED
- `logging` — Python 3.12 stdlib, CONFIRMED
- `psutil` — Optional dev dependency, already in pyproject.toml for memory tests, CONFIRMED

No new dependencies required. Zero additional install footprint.

## Unresolved Items

None. All NEEDS CLARIFICATION resolved above.
