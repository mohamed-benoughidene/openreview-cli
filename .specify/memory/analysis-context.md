# Analysis Context — 5-Stage Async Pipeline Framework (018)

**Generated**: 2026-07-04 | **Feature**: `018-5-stage-async-pipeline` | **Branch**: `feat/018-5-stage-async-pipeline`

---

## 1. Grounding Chain Status

| Source | Status | Lines | Notes |
|--------|--------|-------|-------|
| `verified-sources.md` | ✅ Loaded | 87 lines | Deps confirmed (15 runtime, 4 dev), zero new needed, all 5 capability modules on disk, no forbidden deps |
| `task-context.md` | ✅ Loaded | 134 lines | All 11 pipeline source paths = NEW, all 4 test paths = NEW, `review/__init__.py` = EXISTS, all existing modules confirmed |
| `analysis-context.md` | ✅ Creating now | — | Grounding chain complete |

**Grounding chain**: `verified-sources.md` → `task-context.md` (references verified-sources.md) → `analysis-context.md` (this file). Chain is intact and consistent.

---

## 2. Plan Claims vs Reality

### Dependencies

| Claim | Source | Reality | Verdict |
|-------|--------|---------|---------|
| Zero new runtime deps | plan.md §Primary Dependencies | ✅ Stdlib only: `asyncio`, `dataclasses`, `abc`, `time`, `tracemalloc`, `logging` — all confirmed in Python 3.12 | ✅ MATCH |
| No forbidden deps | plan.md §Constraints | ✅ None present (langchain, llama-index, FAISS, spaCy-direct, sentence-transformers, Click, loguru, FastAPI/Flask all absent) | ✅ MATCH |
| `psutil` not a dep | spec.md FR-010 (mentions psutil as option) | ✅ `psutil` is not in pyproject.toml. Plan correctly chose `tracemalloc` instead. | ✅ MATCH (spec allows either) |

### File Paths

| Claim | Source | Reality | Verdict |
|-------|--------|---------|---------|
| `src/openreview_cli/pipeline/` | plan.md §Project Structure | ❌ Does not exist — marked NEW in task-context.md | ✅ MATCH (will be created) |
| 11 source files, 4 test files | plan.md, tasks.md | All 15 paths confirmed NEW in task-context.md | ✅ MATCH |
| `review/__init__.py` exists | plan.md (refactor target) | ✅ EXISTS on disk | ✅ MATCH |
| `parsing/`, `pii/`, `chunking/`, `retrieval/`, `gateway/` | plan.md §Stage Adapter Pattern | ✅ All 5 confirmed on disk in task-context.md | ✅ MATCH |

### Module Interfaces (UNVERIFIED — flagged for analysis)

The plan and tasks reference specific function names from existing modules. These have NOT been verified against actual module `__init__.py` exports:

| Claim | Source | Reality |
|-------|--------|---------|
| `openreview_cli.parsing.stream.parse_document()` | plan.md §Stage Adapter Pattern | ⚠️ UNVERIFIED — function signature not confirmed against `parsing/__init__.py` |
| `openreview_cli.parsing.stream_clauses()` | plan.md §Research Resolution 2 | ⚠️ UNVERIFIED — name mismatch with above (two different names used for same module) |
| `openreview_cli.pii.strip_pii_clauses()` | plan.md, tasks.md | ⚠️ UNVERIFIED — function name not confirmed |
| `openreview_cli.chunking.chunk_clauses()` | plan.md, tasks.md | ⚠️ UNVERIFIED — function name not confirmed |
| `openreview_cli.retrieval.search()` | plan.md, tasks.md | ⚠️ UNVERIFIED — function name not confirmed |
| `openreview_cli.gateway.Gateway.chat()` | plan.md, tasks.md | ⚠️ UNVERIFIED — method signature not confirmed |

**Risk**: If actual function signatures differ, stage adapter implementations (P2-I-002 through P2-I-006) will need adjustment. Tasks.md P2-I-005 acknowledges this for retrieval ("if signature differs, stub with NotImplementedError") but other adapters assume exact match.

### Contracts Directory

`contracts/pipeline-api.md` is referenced in tasks.md §Interface Contract Map but was NOT read during this analysis (cap limit). The analysis assumes the contracts align with the plan and data-model.md.

---

## 3. Mismatches

| ID | Location | Issue | Severity |
|----|----------|-------|----------|
| M1 | plan.md vs tasks.md | Stage ABC in P1-I-001 lacks `should_skip()` method, but P2-T-008 tests it | HIGH |
| M2 | plan.md §Research Resolution 2 vs plan.md §Stage Adapter Pattern | Function name inconsistency: `stream_clauses()` vs `parse_document()` for same parsing module | MEDIUM |
| M3 | tasks.md P2-I-005 | Retrieval stub with `NotImplementedError` conflicts with SC-005 (zero-regression adoption) if run_review() is refactored before retrieval adapter is complete | HIGH |
| M4 | spec.md FR-010 | Mentions `psutil` as optional measurement tool, but `psutil` is not in deps and not in stdlib. Plan correctly uses `tracemalloc` only. | LOW |
| M5 | plan.md §Performance Goals | "Cleanup callback reduces stage-local memory to zero" — zero is unrealistic (GC non-determinism, reference cycles) | MEDIUM |

---

## 4. Assumptions for Analysis

The following assumptions are carried into the cross-artifact analysis. If any is invalid, findings may change.

1. **Function signatures match**: The 6 UNVERIFIED module function names listed above are assumed to match actual exports. If wrong, stage adapter tasks (P2-I-002 through P2-I-006) may require signature adjustments or wrappers.
2. **Contracts align with plan**: The `contracts/pipeline-api.md` is assumed to match the interfaces described in plan.md and data-model.md. Not verified in this analysis.
3. **`conftest.py` has `memory_tracker` fixture**: Memory tests (P3-T-005) rely on `memory_tracker` fixture declared in `tests/conftest.py`. Not verified.
4. **`@pytest.mark.integration` and `@pytest.mark.memory` are registered**: Tasks.md assumes these markers exist in pytest config. Not verified.
5. **Stage adapter base needed**: P2-I-001 creates shared adapter utilities. Whether this is needed or each adapter can be independent is assumed per plan.
6. **`asyncio.Event` cancellation**: The plan assumes `asyncio.Event` for cancellation. The spec allows "asyncio.Event or callback". Assumption is reasonable.
7. **No existing `pipeline/` module**: Confirmed NEW by task-context.md. No naming collision risk.

---

## 5. Reality Check (Constitution §Analysis Grounding Rule)

| Check | Result |
|-------|--------|
| VERSION DRIFT — Any version number in plan.md that doesn't match CONFIRMED anchor | ✅ None. Python 3.12 confirmed. No other version numbers in plan.md that differ from reality. |
| PATH CONFLICT — Any file path in tasks.md that is neither EXISTS nor NEW | ✅ None. All 15 paths confirmed. |
| UNVERIFIED API — Any API/function name in plan.md with NO ANCHOR in verified-sources.md | ⚠️ 6 function names unverified (see §2 Module Interfaces above) |
| `analysis-context.md` exists | ✅ Created by this analysis |

**Verdict**: Grounding is intact but 6 API function names require verification before implementation. These are flagged as findings in the analysis report.
