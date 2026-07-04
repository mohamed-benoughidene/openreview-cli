# Task Context — 5-Stage Async Pipeline Framework

**Feature**: `018-5-stage-async-pipeline` | **Branch**: `feat/018-5-stage-async-pipeline`
**Generated**: 2026-07-04 | **Sources**: `verified-sources.md`, `pyproject.toml`, `plan.md`, filesystem scan

---

## Section 1: Verified Dependencies

See `.specify/memory/verified-sources.md` for full verification. Key takeaways:

- **Runtime deps**: 15 packages in pyproject.toml, all resolved in `uv.lock`, all installed in `.venv`
- **Dev deps**: 4 packages (mypy, pytest, ruff, types-pyyaml), all resolved
- **New deps for pipeline**: **Zero** — pipeline runner uses stdlib only (`asyncio`, `dataclasses`, `abc`, `time`, `tracemalloc`, `logging`)
- **Forbidden deps**: None present (langchain, llama-index, FAISS, spaCy as direct dep, sentence-transformers, Click as framework, loguru/structlog, FastAPI/Flask all absent)
- **Existing modules**: All five referenced capability modules (`parsing/`, `pii/`, `chunking/`, `retrieval/`, `gateway/`) confirmed on filesystem

---

## Section 2: Project Structure (Actual)

### Source: `src/openreview_cli/`

```
src/openreview_cli/
├── __init__.py              # EXISTS — version = 0.1.0, exports
├── __main__.py              # EXISTS — python -m entry point
├── app.py                   # EXISTS — Typer app, CLI commands
├── errors.py                # EXISTS — exit codes, error formatting
├── py.typed                 # EXISTS — PEP 561 marker
├── benchmark/               # EXISTS — benchmark harness
├── bilateral/               # EXISTS — bilateral review mode
├── chunking/                # EXISTS — clause chunking (C-32)
├── cli/                     # EXISTS — CLI utilities
├── config/                  # EXISTS — configuration loader
├── gateway/                 # EXISTS — AI Gateway (C-12)
├── grounding/               # EXISTS — grounding/hallucination detection
├── parsing/                 # EXISTS — document parsing (C-08)
├── pii/                     # EXISTS — PII stripping (C-10)
├── prompts/                 # EXISTS — prompt management
├── retrieval/               # EXISTS — hybrid retrieval (C-19)
├── review/                  # EXISTS — single-party review (C-13)
├── storage/                 # EXISTS — SQLite storage layer
└── ui/                      # EXISTS — UI components
```

### Tests: `tests/`

```
tests/
├── __init__.py              # EXISTS
├── conftest.py              # EXISTS — fixtures (memory_tracker, fixtures_dir)
├── fixtures/                # EXISTS — test data (PDFs, DOCXs, etc.)
├── unit/                    # EXISTS — unit tests (50+ files)
│   ├── test_pipeline_runner.py    # NEW — will create
│   ├── test_pipeline_stages.py    # NEW — will create
│   └── ... (existing test files)
└── integration/             # EXISTS — integration tests (40+ files)
    ├── test_pipeline_e2e.py       # NEW — will create
    ├── test_pipeline_memory.py    # NEW — will create
    └── ... (existing test files)
```

---

## Section 3: File Path Audit — tasks.md Mapping

Every file path referenced in `specs/018-5-stage-async-pipeline/tasks.md`:

### Source Files (Implementation)

| tasks.md Ref | Absolute Path | Status | Notes |
|---|---|---|---|
| `src/openreview_cli/pipeline/__init__.py` | `/home/mohamed/lab/openreview/src/openreview_cli/pipeline/__init__.py` | **NEW** | Package does not exist yet |
| `src/openreview_cli/pipeline/base.py` | `/home/mohamed/lab/openreview/src/openreview_cli/pipeline/base.py` | **NEW** | Stage ABC, StageResult, PipelineContext |
| `src/openreview_cli/pipeline/errors.py` | `/home/mohamed/lab/openreview/src/openreview_cli/pipeline/errors.py` | **NEW** | Pipeline error hierarchy |
| `src/openreview_cli/pipeline/progress.py` | `/home/mohamed/lab/openreview/src/openreview_cli/pipeline/progress.py` | **NEW** | ProgressEvent, ProgressCallback |
| `src/openreview_cli/pipeline/runner.py` | `/home/mohamed/lab/openreview/src/openreview_cli/pipeline/runner.py` | **NEW** | Pipeline orchestrator, PipelineReport |
| `src/openreview_cli/pipeline/adapters/__init__.py` | `/home/mohamed/lab/openreview/src/openreview_cli/pipeline/adapters/__init__.py` | **NEW** | Adapter base utilities |
| `src/openreview_cli/pipeline/adapters/parse.py` | `/home/mohamed/lab/openreview/src/openreview_cli/pipeline/adapters/parse.py` | **NEW** | ParseStage |
| `src/openreview_cli/pipeline/adapters/strip.py` | `/home/mohamed/lab/openreview/src/openreview_cli/pipeline/adapters/strip.py` | **NEW** | StripStage |
| `src/openreview_cli/pipeline/adapters/chunk.py` | `/home/mohamed/lab/openreview/src/openreview_cli/pipeline/adapters/chunk.py` | **NEW** | ChunkStage |
| `src/openreview_cli/pipeline/adapters/retrieve.py` | `/home/mohamed/lab/openreview/src/openreview_cli/pipeline/adapters/retrieve.py` | **NEW** | RetrieveStage |
| `src/openreview_cli/pipeline/adapters/generate.py` | `/home/mohamed/lab/openreview/src/openreview_cli/pipeline/adapters/generate.py` | **NEW** | GenerateStage |
| `src/openreview_cli/review/__init__.py` | `/home/mohamed/lab/openreview/src/openreview_cli/review/__init__.py` | **EXISTS** | To be refactored (Phase 5) |

### Test Files

| tasks.md Ref | Absolute Path | Status | Notes |
|---|---|---|---|
| `tests/unit/test_pipeline_runner.py` | `/home/mohamed/lab/openreview/tests/unit/test_pipeline_runner.py` | **NEW** | All P1-T-* and P3-T-* tests |
| `tests/unit/test_pipeline_stages.py` | `/home/mohamed/lab/openreview/tests/unit/test_pipeline_stages.py` | **NEW** | All P2-T-* tests |
| `tests/integration/test_pipeline_e2e.py` | `/home/mohamed/lab/openreview/tests/integration/test_pipeline_e2e.py` | **NEW** | All IT-T-* tests |
| `tests/integration/test_pipeline_memory.py` | `/home/mohamed/lab/openreview/tests/integration/test_pipeline_memory.py` | **NEW** | P3-T-005 memory integration test |

### Existing Modules Referenced (not created by this feature)

| Module Path | Status | Plan Ref |
|---|---|---|
| `src/openreview_cli/parsing/` | EXISTS (7 files) | C-08 — ParseStage adapter wraps `stream.parse_document()` |
| `src/openreview_cli/pii/` | EXISTS (11 files) | C-10 — StripStage adapter wraps `strip_pii_clauses()` |
| `src/openreview_cli/chunking/` | EXISTS (5 files) | C-32 — ChunkStage adapter wraps `chunk_clauses()` |
| `src/openreview_cli/retrieval/` | EXISTS (10 files) | C-19 — RetrieveStage adapter wraps `search()` |
| `src/openreview_cli/gateway/` | EXISTS (9 files) | C-12 — GenerateStage adapter wraps `Gateway.chat()` |

---

## Section 4: Plan vs Filesystem — Module Existence Summary

### Modules Referenced in plan.md §Project Structure

| plan.md Path | Exists on Filesystem? | Notes |
|---|---|---|
| `src/openreview_cli/` package | ✅ EXISTS | Top-level package skeleton intact |
| `src/openreview_cli/parsing/` | ✅ EXISTS | C-08 — document parsing engine |
| `src/openreview_cli/pii/` | ✅ EXISTS | C-10 — PII stripping engine |
| `src/openreview_cli/chunking/` | ✅ EXISTS | C-32 — clause chunking |
| `src/openreview_cli/retrieval/` | ✅ EXISTS | C-19 — hybrid retrieval (BM25 + dense) |
| `src/openreview_cli/gateway/` | ✅ EXISTS | C-12 — AI Gateway (routing, cost, registry) |
| `src/openreview_cli/review/` | ✅ EXISTS | C-13 — single-party review (target for Phase 5 refactor) |
| `src/openreview_cli/pipeline/` | **❌ NEW** | Does not exist yet — will be created by this feature |
| `src/openreview_cli/pipeline/adapters/` | **❌ NEW** | Sub-package — will be created by this feature |
| `tests/unit/test_pipeline_runner.py` | **❌ NEW** | Will be created by this feature |
| `tests/unit/test_pipeline_stages.py` | **❌ NEW** | Will be created by this feature |
| `tests/integration/test_pipeline_e2e.py` | **❌ NEW** | Will be created by this feature |
| `tests/integration/test_pipeline_memory.py` | **❌ NEW** | Will be created by this feature |

### Plan-Compliance Verdict

- ✅ All five existing modules referenced by stage adapters are confirmed on disk
- ✅ All 11 pipeline source files are confirmed NEW (no stale paths copy-pasted from plan)
- ✅ All 4 test files are confirmed NEW (no stale paths)
- ✅ `review/__init__.py` is confirmed EXISTS (correct target for Phase 5 refactor)
- ✅ No file path in tasks.md references a non-existent location incorrectly
