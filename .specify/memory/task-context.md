# Task Context — Memo Export

**Feature**: `021-memo-export` | **Branch**: `feat/021-memo-export`
**Generated**: 2026-07-05 | **Sources**: `verified-sources.md`, `plan.md`, filesystem scan

---

## Verified Dependencies

Extracted from `.specify/memory/verified-sources.md` (last generated for feature 018, verified current as of 2026-07-04):

| VERIFIED DEP | VERSION | SOURCE |
|---|---|---|
| python-docx | >=1.2.0 | pyproject.toml, resolved in uv.lock |
| json | stdlib (Python 3.12) | stdlib |
| pathlib | stdlib (Python 3.12) | stdlib |
| dataclasses | stdlib (Python 3.12) | stdlib |
| datetime | stdlib (Python 3.12) | stdlib |
| typing | stdlib (Python 3.12) | stdlib |
| ReviewReport | openreview_cli.review.models | exists on filesystem |
| ClauseAssessment | openreview_cli.review.models | exists on filesystem |
| AssessmentColor | openreview_cli.review.colors | exists on filesystem |
| CitationProvenance | openreview_cli.grounding.models | exists on filesystem |

Additionally: all 15 runtime deps confirmed in pyproject.toml and uv.lock (see verified-sources.md). No forbidden deps present.

---

## Project Structure (actual)

### Source: `src/openreview_cli/` (2 levels deep, relevant paths)

```
src/openreview_cli/
├── __init__.py
├── __main__.py
├── app.py
├── errors.py
├── py.typed
├── benchmark/
├── bilateral/
├── chunking/
├── cli/
├── config/
├── gateway/
├── grounding/
│   └── models.py              # CitationProvenance
├── parsing/
├── pii/
├── pipeline/                   # EXISTING (created by 018)
├── prompts/
├── retrieval/
├── review/                     # Target module
│   ├── __init__.py
│   ├── _gateway.py
│   ├── base.py
│   ├── colors.py               # AssessmentColor
│   ├── extraction.py
│   ├── models.py               # ReviewReport, ClauseAssessment
│   ├── pipeline.py
│   ├── playbook.py
│   ├── playbooks/
│   ├── prompts.py
│   ├── qa.py
│   └── report.py
│   └── memo/                   # NEW — does not exist yet
├── storage/
└── ui/
```

### Tests: `tests/` (2 levels deep, relevant paths)

```
tests/
├── __init__.py
├── conftest.py
├── fixtures/
├── helpers/
├── unit/
│   ├── __init__.py
│   ├── bilateral/
│   ├── recovery/
│   └── ... (50+ test files, directly in tests/unit/)
│   └── review/                 # NOT EXISTS — plan says create tests/unit/review/
├── integration/
│   └── ... (40+ test files)
```

---

## Existing Files

### `src/openreview_cli/review/` — all existing files

| Path | Exports / Content | Status |
|---|---|---|
| `review/__init__.py` | Public API exports | EXISTS |
| `review/models.py` | ReviewReport, ClauseAssessment, Playbook dataclasses | EXISTS |
| `review/colors.py` | AssessmentColor enum, assign_colors() | EXISTS |
| `review/report.py` | Terminal + JSON formatting, _confidence_bar() | EXISTS |
| `review/pipeline.py` | Review pipeline orchestration | EXISTS |
| `review/extraction.py` | Extraction agent — prompt building, model routing | EXISTS |
| `review/qa.py` | QA agent — verification prompt, disagreement logic | EXISTS |
| `review/base.py` | ReviewCommand base class with PII orchestration | EXISTS |
| `review/playbook.py` | Playbook loader | EXISTS |
| `review/prompts.py` | Extraction and QA prompt templates | EXISTS |
| `review/_gateway.py` | Shared AI Gateway call helper | EXISTS |
| `review/playbooks/` | Bundled YAML playbooks | EXISTS |

### `src/openreview_cli/grounding/models.py` — CitationProvenance

| Path | Exports | Status |
|---|---|---|
| `grounding/models.py` | CitationProvenance (referenced by plan for memo display) | EXISTS |

---

## Plan vs Filesystem

### Source paths from plan.md

| plan.md Path | Exists? | Notes |
|---|---|---|
| `src/openreview_cli/review/__init__.py` | ✅ EXISTS | Unchanged |
| `src/openreview_cli/review/models.py` | ✅ EXISTS | Unchanged, minor additions for memo_version if needed |
| `src/openreview_cli/review/colors.py` | ✅ EXISTS | Unchanged |
| `src/openreview_cli/review/report.py` | ✅ EXISTS | Unchanged |
| `src/openreview_cli/review/pipeline.py` | ✅ EXISTS | Unchanged |
| `src/openreview_cli/review/extraction.py` | ✅ EXISTS | Unchanged |
| `src/openreview_cli/review/qa.py` | ✅ EXISTS | Unchanged |
| `src/openreview_cli/review/base.py` | ✅ EXISTS | Unchanged |
| `src/openreview_cli/review/playbook.py` | ✅ EXISTS | Unchanged |
| `src/openreview_cli/review/prompts.py` | ✅ EXISTS | Unchanged |
| `src/openreview_cli/review/_gateway.py` | ✅ EXISTS | Unchanged |
| `src/openreview_cli/review/memo/__init__.py` | **❌ NEW** | Will create |
| `src/openreview_cli/review/memo/exporter.py` | **❌ NEW** | Will create |
| `src/openreview_cli/review/memo/formats.py` | **❌ NEW** | Will create |
| `src/openreview_cli/review/memo/filename.py` | **❌ NEW** | Will create |
| `src/openreview_cli/review/memo/models.py` | **❌ NEW** | Will create |

### Test paths from plan.md

| plan.md Path | Exists? | Notes |
|---|---|---|
| `tests/unit/review/test_memo_exporter.py` | **❌ NEW** | tests/unit/review/ dir does not exist |
| `tests/unit/review/test_memo_formats.py` | **❌ NEW** | tests/unit/review/ dir does not exist |
| `tests/unit/review/test_memo_filename.py` | **❌ NEW** | tests/unit/review/ dir does not exist |
| `tests/integration/test_memo_export.py` | **❌ NEW** | Does not exist |
| `tests/integration/test_memo_edge_cases.py` | **❌ NEW** | Does not exist |

### Mismatches

| MISMATCH | Details |
|---|---|
| `tests/unit/review/` | plan.md defines tests under `tests/unit/review/` subdirectory, but filesystem has no `tests/unit/review/` — all unit tests live directly in `tests/unit/`. The plan assumes a subdirectory pattern used by `bilateral/` and `recovery/` but not currently by review tests. Task generator should decide: create `tests/unit/review/` (matching bilateral/recovery pattern) or place at `tests/unit/` (matching existing review test pattern). |

### Summary

- ✅ All 11 existing review module paths confirmed — unchanged per plan
- ✅ All 5 new memo source paths confirmed NEW (no stale paths)
- ✅ All 5 new test paths confirmed NEW
- ⚠️ 1 MISMATCH: `tests/unit/review/` directory structure (plan specifies subdirectory, filesystem has no such dir — decision needed)
- ✅ Zero new runtime dependencies needed (python-docx already in pyproject.toml)
