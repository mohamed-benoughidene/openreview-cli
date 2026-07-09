# Quickstart Validation Guide — Benchmark Mode Validation

**Date**: 2026-07-09
**Feature**: Mode whitelist (D-75), accuracy baseline (D-76), orphan E2E tests (D-77)

---

## Prerequisites

- Python 3.12 + `uv` installed
- Dependencies installed: `uv sync`
- Pre-commit hooks: `uv run pre-commit install` (or `uvx pre-commit run --all-files`)
- On branch: `feat/030-benchmark-mode-validation`

## Setup

```bash
git checkout feat/030-benchmark-mode-validation
uv sync
uv run openreview --version
```

## Validation Scenarios

### Scenario 1: Mode Validation Rejects Unknown Modes

```bash
uv run openreview benchmark run --modes=unknown_mode
```

**Expected**: Exit code 78, error message to stderr:
```
Error: Unknown mode 'unknown_mode'. Valid: assetcheck, buycheck, consultcheck, ...
```

This validates FR-1 (VALID_MODES exists) and FR-2 (parse-time validation).

---

### Scenario 2: Mode Validation Accepts All 17 Modes

```bash
uv run openreview benchmark run --modes=precheck,hirecheck,dealcheck,assetcheck,buycheck,engagecheck,guaranteecheck,loancheck,licensecheck,leasecheck,privacycheck,indemnitycheck,consultcheck,workcheck,loicheck,subcheck,settlementcheck
```

**Expected**: Exit 0. No validation errors.

Validates that all 17 modes pass validation (SC-2).

---

### Scenario 3: Dead Param Removal Verified

```bash
git grep "def run_dataset" src/openreview_cli/benchmark/runner.py
```

**Expected**: Shows method signature WITHOUT `mode` parameter:
```python
def run_dataset(
    self,
    dataset_name: str,
    pipeline_fn: PipelineFn,
    slot_name: str = "default",
) -> DatasetResult:
```

Validates FR-3 (dead param removal, SC-3).

---

### Scenario 4: Mock CI Baseline Run

```bash
uv run openreview benchmark run --all --ci
```

**Expected**: Runs all 17 modes × all 4 datasets using mock pipeline.
Exits 0 (no regressions without a prior baseline).

Validates FR-4 (mock provider baseline, SC-4).

---

### Scenario 5: Multi-Mode Mock Baseline (Single Dataset)

```bash
uv run openreview benchmark run --datasets=cuad --modes=precheck,hirecheck,dealcheck --verbose
```

**Expected**: Runs 3 modes × CUAD dataset. Produces per-mode results.

Validates multi-mode iteration produces correct count of DatasetResult entries.

---

### Scenario 6: Orphan E2E Tests Pass

```bash
uv run pytest tests/integration/test_benchmark_orphan_modes.py -v
```

**Expected**: 9 passed (parametrized). Each test:
1. Parses fixture PDF from `tests/fixtures/benchmark/{mode}/doc_1.pdf`
2. Strips PII
3. Runs review with mocked AI gateway
4. Asserts ReviewReport has non-empty assessments
5. Asserts each assessment has three-color verdict (green/amber/red)

Validates FR-6 (SC-6, SC-7).

---

### Scenario 7: Manual Real Baseline (One-Shot)

```bash
# Requires a configured AI provider (Ollama or cloud slot)
uv run openreview benchmark run --all --save-baseline --format json \
  --output docs/benchmarks/baseline-$(date +%F).json
```

**Expected**: JSON file at `docs/benchmarks/baseline-YYYY-MM-DD.json` with:
- Per-mode × per-dataset metrics
- Git commit SHA, branch, provider, model, timestamp
- Structurally valid against BenchmarkRun schema

Validates FR-5 (SC-5).

---

### Scenario 8: Mode Coverage Visible in Report

```bash
uv run openreview benchmark run --datasets=cuad --modes=precheck,hirecheck,dealcheck --format json
```

**Expected**: JSON output includes mode-specific sections. Each result's
`dataset_name` shows `{dataset}::{mode}` convention (e.g., `cuad::precheck`).

Validates FR-7 (SC-8).

---

### Scenario 9: Pre-Commit Suite

```bash
uv run pre-commit run --all-files
```

**Expected**: All hooks pass (ruff, ruff-format, mypy, pytest-fast).

---

### Scenario 10: Type Check

```bash
uv run mypy src/ tests/
```

**Expected**: Strict mode, no errors.

---

## CI Integration

After implementation, CI runs:
```bash
uv run openreview benchmark run --all --ci     # Mock baseline + regression check
uv run pytest tests/integration/test_benchmark_orphan_modes.py -q  # Orphan E2E
```

Both must pass on every PR to `main`.
