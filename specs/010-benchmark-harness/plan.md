# Implementation Plan: Benchmark Harness

**Branch**: `feat/010-benchmark-harness` | **Date**: 2026-07-02 | **Spec**: `specs/010-benchmark-harness/spec.md`

**Input**: Feature specification from `/specs/010-benchmark-harness/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command.

## Summary

Build a CLI benchmark harness (`openreview benchmark`) that evaluates extraction, comparison, classification, hallucination, PII recall, latency, and memory across three research baselines (CUAD first, MAUD and ContractNLI follow). Integrates with CI as a regression gate. Meets hardware budget via per-item tracemalloc profiling with NLP model exemption.

Decisions carried forward from spec [§Clarifications]:
- CUAD first (extractive QA, 41 classes, 500+ contracts)
- PASS/FAIL gate for hardware budget with NLP model exemption
- `openreview benchmark` subcommand wraps all benchmark functionality

## Technical Context

**Language/Version**: Python 3.12 (pinned by constitution, .python-version)

**Primary Dependencies**:
- *Existing*: PyMuPDF (C-05), python-docx (C-06), clause detector (C-07/08), gateway router (C-12/13), PII engine (Phase 3), Rich (output), pytest (tests)
- *New candidates*: huggingface `datasets` lib for corpus download OR raw JSON/parquet fetch
- *No new runtime deps beyond dataset loading* — benchmark logic is pure Python using existing infra

**Storage**: SQLite (existing `storage/` module) for:
- Benchmark run results (BenchmarkRun, DatasetResult tables)
- Regression baselines (pinned by git commit SHA)
- Per-metric history for trend tracking

**Testing**:
- Unit tests: metric calculation, data model validation, result comparison
- Integration tests: CUAD subset evaluation, CI gate simulation
- Benchmark tests: full-suite smoke test (pytest marker: `benchmark`)
- Memory tests: tracemalloc per-item profiling (pytest marker: `memory`)

**Target Platform**: Linux CI (GitHub Actions), macOS/Windows dev machines

**Project Type**: CLI tool (Python package — extend `openreview benchmark` subcommand)

**Performance Goals**:
- Full suite (all-local SLM) completes in <30 minutes [§7 Success Criteria]
- Per-item peak memory <100 MB (non-NLP) per constitution Principle III
- Regression gate: <2 percentage points F1 drop triggers CI failure

**Constraints**:
- <100 MB peak processing memory (<110 MB floor, NLP model exempt)
- Reference machine: 8 GB RAM, 2-core CPU, no GPU
- CUAD dataset ~500 contracts in PDF — must stream, not bulk-load
- Cloud model latency excluded from hardware budget; measured separately for comparison

**Scale/Scope**:
- CUAD: ~500 contracts, 41 clause types, ~13k annotations
- MAUD: ~100 agreements, 39 tasks (spec says 39, research says 92 questions — reconcile)
- ContractNLI: ~600 examples, 3 classes
- All datasets CC BY 4.0 — compatible with AGPL-3.0

**Resolved (from research.md)**:
1. Dataset download mechanism → **Raw HTTP+JSON/parquet** via `httpx` (existing dep). Rejected `datasets` lib due to Principle IV violation (transitive bloat). [R1]
2. CUAD/MAUD ground-truth span alignment → **Character-offset spans, token-level F1** using stdlib `re` tokenization. Matches NeurIPS 2021 CUAD protocol. [R2]
3. Hallucination measurement method → **Staged implementation**: ROUGE-L lexical overlap placeholder (EXPERIMENTAL) until parallel spec lands. Flagged in reports. [R3]
4. MAUD task count → **92 questions** grouped into **39 deal-point categories** from ABA 2021 study. Both granularities reported. [R4]
5. PII benchmark seeded corpus → **Partially sufficient** for initial release (1,730 entities across 54 docs, 0 false positives). Full recall/precision deferred to T049. [R5]
6. CI integration point → **New parallel CI job** on push to main only (not per-PR). Uses `--ci --compare HEAD~1`. [R6]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | **Pass** | PII recall uses seeded documents only (never real PII). Cloud model slots route through existing PII stripping engine. |
| II. Local-First, CLI-Only | **Pass** | `openreview benchmark` is a CLI subcommand. No web server, no daemon. CI integration calls the CLI directly. |
| III. Hardware-Bounded | **Pass** | per-item tracemalloc profiling. NLP model memory exempt per constitutional amendment 1.2.0. Budget violation → CI failure. |
| IV. Dependency Minimalism | **Pass** | Dataset download uses raw HTTP+JSON via `httpx` (already a project dependency) — no new dependency required. Decision documented in research.md R1. No other new deps anticipated. |
| V. Spec-Driven, YAGNI | **Pass** | Spec exists before implementation (this file). Per-mode features gated by success criteria. |

**GATE RESULT**: PASS (Principle IV resolved in research.md R1 — raw HTTP+JSON via httpx, no new deps)

## Project Structure

### Documentation (this feature)

```text
specs/010-benchmark-harness/
├── spec.md                # Feature specification (§1-11)
├── plan.md                # This file (/speckit.plan command output)
├── research.md            # Phase 0 output — resolved unknowns
├── data-model.md          # Phase 1 output — entities, fields, relationships
├── quickstart.md          # Phase 1 output — runnable validation guide
├── contracts/             # Phase 1 output — interface contracts
│   └── cli-contract.md    # CLI subcommand contract
└── tasks.md               # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── benchmark/                      # NEW: Benchmark harness package
│   ├── __init__.py                 # Public exports
│   ├── runner.py                   # BenchmarkRunner — orchestrates dataset → pipeline → metrics
│   ├── datasets/                   # Dataset loaders
│   │   ├── __init__.py
│   │   ├── cuad.py                 # CUAD loader (HuggingFace or raw JSON)
│   │   ├── maud.py                 # MAUD loader
│   │   └── contract_nli.py         # ContractNLI loader
│   ├── metrics.py                  # MetricValue, F1/precision/recall/rate calculators
│   ├── models.py                   # BenchmarkRun, DatasetResult, MetricValue, ModelSlotResult
│   ├── report.py                   # JSON + Rich terminal report generation
│   ├── regression.py               # Baseline comparison, regression detection
│   ├── prompt_ab.py                # Prompt A/B testing (McNemar's test)
│   ├── hallu_detect.py             # Hallucination rate measurement (§6.3, needs parallel spec)
│   └── memory.py                   # tracemalloc-based per-item memory profiling
├── app.py                          # Add `benchmark` subcommand
├── ...                             # Existing files unchanged

tests/
├── unit/
│   ├── test_benchmark_runner.py    # Runner orchestration tests
│   ├── test_benchmark_metrics.py   # Metric calculation correctness
│   ├── test_benchmark_models.py    # Data model validation
│   ├── test_benchmark_regression.py# Baseline comparison logic
│   └── test_benchmark_memory.py    # tracemalloc profiling tests
├── integration/
│   ├── test_benchmark_cuad.py      # CUAD subset integration test
│   ├── test_benchmark_ci_gate.py   # CI regression gate simulation
│   └── test_benchmark_prompt_ab.py # Prompt A/B testing integration
└── fixtures/
    └── benchmark/                  # Benchmark fixtures (small CUAD subset, seeded docs)
```

**Structure Decision**: New `benchmark/` package under `src/openreview_cli/`. Each dataset gets its own loader module in `benchmark/datasets/`. Metrics, models, report generation, and regression are separated modules. This mirrors the existing project pattern (see `parsing/`, `pii/`, `gateway/` packages).

## Complexity Tracking

No constitution violations to justify. The benchmark package is a single new directory under the existing source tree, no new runtime deps beyond dataset loading.

## Dependencies — new candidates

| Candidate | Type | Why needed | Alternative |
|-----------|------|------------|-------------|
| `datasets` (HuggingFace) | Runtime | `load_dataset("theatticusproject/cuad")` — handles download, caching, format conversion | Raw HTTP+JSON/parquet — minimal but manual |
| scipy | Runtime | `scipy.stats.mcnemar` for prompt A/B significance testing | Manual implementation of McNemar's test (approx 20 lines) |

Resolution: both are decided in research.md.
