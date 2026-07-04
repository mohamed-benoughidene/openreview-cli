# Implementation Context — 5-Stage Async Pipeline (018)

**Generated**: 2026-07-04 | **Branch**: `feat/018-5-stage-async-pipeline`
**Phase**: 0 (Setup) + 1 (Core) implementation | **Spec**: `018-5-stage-async-pipeline`

---

## Grounding Chain Verification

| Source | Status | Description |
|--------|--------|-------------|
| `.specify/memory/verified-sources.md` | ✅ EXISTS (87 lines) | Deps confirmed, zero new needed, 5 capability modules on disk |
| `.specify/memory/task-context.md` | ✅ EXISTS (134 lines) | All 15 file paths verified (11 source NEW, 4 test NEW) |
| `.specify/memory/analysis-context.md` | ✅ EXISTS (94 lines) | Grounding chain intact, 6 unverified APIs flagged for Phase 2 |
| `.specify/memory/impl-context.md` | ✅ Creating now | Chain complete |

**Chain**: `verified-sources.md` → `task-context.md` → `analysis-context.md` → `impl-context.md` ✓

---

## Environment

| Property | Value |
|----------|-------|
| Python version | 3.12 (`.python-version`, `pyproject.toml`) |
| Package manager | `uv` (lock at `uv.lock`) |
| uv lock status | ✅ Up-to-date (last `uv sync` successful) |
| Branch | `feat/018-5-stage-async-pipeline` |
| Existing modules | `parsing/`, `pii/`, `chunking/`, `retrieval/`, `gateway/` all confirmed |
| Test framework | `pytest` (dev dep) + `pytest-asyncio` (added for Phase 1) |

---

## Implementation Scope (Phases 0 + 1)

### Phase 0 — Setup (4 tasks)

| Task | Path | Done |
|------|------|------|
| ST-001 | `src/openreview_cli/pipeline/__init__.py` | ✅ |
| ST-002 | `src/openreview_cli/pipeline/adapters/__init__.py` | ✅ |
| ST-003 | Verify no new deps needed (stdlib confirmed) | ✅ |
| ST-004 | Verify constitution compliance (Principle IV passed) | ✅ |

### Phase 1 — Pipeline Core (26 tasks: 13 tests + 13 impl)

| Task | Entity | Done |
|------|--------|------|
| P1-T-001..013 | Runner tests (ordering, errors, cancellation, progress, etc.) | ✅ |
| P1-I-001..013 | Stage ABC, StageResult, PipelineContext, errors, progress, Pipeline runner | ✅ |

---

## Key Implementation Paths (from tasks.md)

| Path | Purpose |
|------|---------|
| `src/openreview_cli/pipeline/base.py` | `Stage` ABC, `StageResult`, `PipelineContext` type alias |
| `src/openreview_cli/pipeline/errors.py` | `PipelineError`, `StageError`, `CriticalStageError`, `MemoryBudgetError`, `CancelledError` |
| `src/openreview_cli/pipeline/progress.py` | `ProgressEvent`, `ProgressCallback` |
| `src/openreview_cli/pipeline/runner.py` | `Pipeline` class + `PipelineReport` |
| `src/openreview_cli/pipeline/__init__.py` | Public API exports |
| `tests/unit/test_pipeline_base.py` | Stage ABC + StageResult tests |
| `tests/unit/test_pipeline_errors.py` | Error hierarchy tests |
| `tests/unit/test_pipeline_progress.py` | ProgressEvent tests |
| `tests/unit/test_pipeline_runner.py` | All 13 runner tests |

---

## Chain Issues

| Issue | Status |
|-------|--------|
| M1: Stage ABC lacks `should_skip()` in base but P2-T-008 tests it | ⚠️ Phase 2 — not implementing now |
| M2: Function name inconsistency (`parse_document` vs `stream_clauses`) | ⚠️ Phase 2 |
| M3: retrieval stub with NotImplementedError vs SC-005 | ⚠️ Phase 5 |
| M4: psutil not in deps (plan uses tracemalloc only) | ✅ No issue — tracemalloc is stdlib |
| M5: "Cleanup reduces memory to zero" unrealistic | ✅ Runner uses best-effort cleanup |
| No forbidden deps imported | ✅ Confirmed |
| `pytest-asyncio` needed for async tests | ⚠️ Added as dev dep for Phase 1 |

---

## Implementation Notes

- **Stdlib only**: `asyncio`, `abc`, `dataclasses`, `time`, `tracemalloc`, `logging` — no new runtime deps
- **TDD**: Tests written before (or concurrently with) implementation; all pass
- **Memory**: Runner only tracks tracemalloc deltas if tracemalloc is already tracing
- **Error isolation**: Non-critical `StageError` → captured, pipeline continues. `CriticalStageError` → pipeline halts, exception raised with partial report attached
- **Cancellation**: `asyncio.Event` checked between stages; current stage completes, partial report returned
- **Reserved keys**: `errors` and `cancelled` protected from stage overwrites
