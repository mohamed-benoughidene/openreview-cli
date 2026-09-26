# Implementation Plan: Benchmark Mode Validation — Mode Whitelist, Accuracy Baseline, Orphan E2E Tests

**Branch**: `feat/030-benchmark-mode-validation` | **Date**: 2026-07-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/030-benchmark-mode-validation/spec.md`
**Resolves**: D-75 (mode whitelist), D-76 (accuracy baseline), D-77 (orphan E2E tests)

## Summary

Add mode validation to the benchmark CLI (`VALID_MODES` frozenset + parse-time check),
remove dead `mode` parameter from `BenchmarkRunner.run_dataset()`, wire multi-mode
iteration for mock-provider CI baselines across all 17 modes × 3 datasets, and
add end-to-end pipeline tests for 9 orphan modes.

No new runtime dependencies. All 17 modes already wired as CLI subcommands.
All 9 orphan modes already have benchmark fixture directories with PDFs.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: No new runtime deps. Existing stack: httpx, pydantic, rich, typer,
PyMuPDF, python-docx, presidio-analyzer, presidio-anonymizer, cryptography, litellm,
questionary, platformdirs, pyyaml.

**Storage**: No new tables. Baseline JSON files stored in `docs/benchmarks/`.

**Testing**: pytest. New integration test file for orphan mode E2E tests.

**Target Platform**: Linux, macOS, Windows (CLI)

**Performance Goals**: <100 MB peak (110 MB floor). Mock baseline adds ~0 memory.
Orphan E2E tests reuse existing parser/PII/gateway — no new memory pressure.

**Constraints**: Python 3.12 + uv only. Forbidden deps list respected. Local CLI only.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | **Pass** | Mock baseline uses no real data. Real baseline routes through existing PII stripping (spec 010 compliant). No new data leaves the machine beyond existing gateway calls. E2E tests mock the AI gateway — no network calls. |
| II. Local-First, CLI-Only | **Pass** | All work is CLI-invoked (`openreview benchmark run`). No server, daemon, or telemetry. Real baseline is manual CLI command. |
| III. Hardware-Bounded | **Pass** | Mock baseline adds ~0 memory. VALID_MODES is a frozenset (~1 KB). Multi-mode iteration reuses existing runner. Orphan E2E tests use existing parsers — peak within 110 MB floor. |
| IV. Dependency Minimalism | **Pass** | Zero new dependencies. Validation uses stdlib `frozenset`. Tests use existing `pytest` + `monkeypatch`. Baseline uses existing `json`. |
| V. Spec-Driven, YAGNI | **Pass** | Spec written before implementation. Hard-coded frozenset over registry (YAGNI). No speculative abstractions. Dead param simply removed (no deprecation shim for zero callers). |

**Constitution Gate Verdict**: PASS — all five principles satisfied.

---

## Phase 0: Research & Outline

### Research Findings

Complete research in [research.md](./research.md). Key findings:

1. **D-75 gap**: `--modes` option has zero validation. `VALID_MODES` frozenset must be added.
   Pattern exists for datasets (`cli.py:154-160`) — mode validation mirrors it exactly.

2. **Dead param callers**: Zero callers pass `mode=` keyword to `run_dataset()`.
   Safe to remove parameter.

3. **Mock/real split**: Mock pipeline exists (`_mock_pipeline` at `cli.py:302-309`).
   Real gateway pipeline does not exist — must be created for FR-5.

4. **color field reconciliation**: Spec refers to `report.clauses` and `color_verdict`.
   Actual model uses `report.assessments` and `assessment.color: AssessmentColor | None`.
   Test code must use actual model.

5. **17 modes confirmed**: All registered in `app.py` via `_register_product_mode()`.
   All have `BUNDLED_PLAYBOOKS` entries. All 9 orphan modes have benchmark fixture dirs
   with 5 PDFs + `ground_truth.json` each.

6. **D-72 skeletons**: `scripts/benchmarks/` does not exist. D-72 remains deferred.

---

## Phase 1: Design & Contracts

### Project Structure

```
specs/030-benchmark-mode-validation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 data entities
├── quickstart.md        # Phase 1 validation scenarios
├── contracts/           # Interface contracts
│   ├── MODE_VALIDATION.md
│   ├── MOCK_PROVIDER.md
│   ├── REAL_BASELINE.md
│   ├── ORPHAN_E2E_TESTS.md
│   └── DEAD_PARAM_REMOVAL.md
├── tasks.md             # Phase 2 (speckit.tasks)
└── spec.md              # Feature specification
```

### Source Code Changes

```
src/openreview_cli/benchmark/
├── cli.py               # ADD VALID_MODES frozenset, mode validation, multi-mode loop
├── runner.py             # REMOVE dead `mode` param from run_dataset()
└── models.py             # Unchanged (or optional `mode` field on DatasetResult)

tests/integration/
└── test_orphan_modes_e2e.py   # NEW — 9 parametrized E2E tests
```

### Implementation Order

1. **FR-1/FR-2 (validation)**: `VALID_MODES` frozenset + parse-time validation in `cli.py`
2. **FR-3 (dead param)**: Remove `mode: str = "precheck"` from `runner.py:71`
3. **FR-6 (E2E tests)**: New `test_orphan_modes_e2e.py` with 9 parametrized tests
4. **FR-4 (mock baseline)**: Multi-mode iteration loop in `benchmark_run()` for `--all`
5. **FR-5 (real baseline)**: `_build_gateway_pipeline()` function + manual workflow docs
6. **FR-7 (mode coverage in report)**: Per-mode breakdown in terminal/JSON output

---

## Phase 1.5: Agent Context Update

```bash
.specify/extensions/agent-context/scripts/bash/update-agent-context.sh \
  specs/030-benchmark-mode-validation/plan.md
```

Run after plan.md is finalized.

---

## Phase 1.6: Constitution Check (Re-evaluated Post-Design)

| Principle | Status | Justification (Post-Design) |
|-----------|--------|-----------------------------|
| I. Privacy First | **Pass** | Design uses mock pipeline for CI. Real baseline routes through existing PII-stripping pipeline. No new data exposure. |
| II. Local-First, CLI-Only | **Pass** | All commands are CLI-invoked. No server, daemon, or background process added. |
| III. Hardware-Bounded | **Pass** | VALID_MODES = 1 KB frozenset. Multi-mode iteration reuses existing runner. E2E tests parse single PDFs sequentially. |
| IV. Dependency Minimalism | **Pass** | Zero new dependencies. Exclusively uses frozenset, json, pytest, monkeypatch. |
| V. Spec-Driven, YAGNI | **Pass** | Spec preceded design. Hard-coded frozenset (no registry). Simple param removal (no deprecation shim). No speculative baseline infrastructure. |

**Constitution Gate Verdict**: PASS.

---

## Dependencies

| What | Spec Ref | Status |
|------|----------|--------|
| Benchmark CLI (`benchmark/cli.py`) | FR-1, FR-2 | Target for validation + multi-mode loop |
| Benchmark Runner (`benchmark/runner.py`) | FR-3 | Target for dead param removal |
| Benchmark Models (`benchmark/models.py`) | FR-4, FR-7 | Optional mode field on DatasetResult |
| Review Pipeline (`review/__init__.py`) | FR-6 | E2E tests call `run_review()` |
| AI Gateway (`gateway/`) | FR-5, FR-6 | Mocked in E2E tests, real in FR-5 |
| Document Parsing (`parsing/`) | FR-6 | Parse fixture PDFs |
| PII Engine (`pii/`) | FR-6 | Strip PII before review |
| CUAD/MAUD/ContractNLI datasets | FR-4, FR-5 | Already consumed by benchmark harness |

## Architecture Implications

| Implication | Source | Impact |
|------------|--------|--------|
| Mode validation prevents silent errors | FR-1, FR-2 | Unknown modes caught at parse time, exit 78 |
| Multi-mode iteration produces 51 results | FR-4 | 17 modes × 3 datasets = 51 DatasetResult entries |
| Mock baseline is deterministic | FR-4 | CI regression detection works by construction |
| Real baseline is manual only | FR-5 | No CI automation — cost/time/flake sensitivity |
| Orphan E2E tests use actual models | FR-6 | Test code uses `assessments` + `AssessmentColor` enum, not spec pseudocode |
| Report shows per-mode breakdown | FR-7 | Terminal/JSON includes mode-specific sections |

## Risks

| ID | Risk | Impact | Mitigation | FR Reference |
|----|------|--------|------------|-------------|
| R-1 | Unknown external caller of `mode=` param | TypeError | Git grep shows zero callers; verified before removal | FR-3 |
| R-2 | Mock baseline too permissive (mock returns perfect scores) | False confidence | Mock returns zero-length spans (F1~0) | FR-4 |
| R-3 | Real baseline exceeds budget/time | Cannot establish | Manual one-shot; Ollama is free | FR-5 |
| R-4 | Fixture directory not found for orphan mode | Test fails with skip | All 9 directories exist with 5 PDFs each | FR-6 |
| R-5 | `color` field `None` on ClauseAssessment | Assertion failure | Check `is not None` before enum comparison | FR-6 |
| R-6 | Mode count changes | VALID_MODES stale | Constitutional amendment updates in same PR | FR-1 |

## Implementation Details

### FR-1/FR-2: VALID_MODES + Validation

```python
# In cli.py, after VALID_DATASETS (line 33)
VALID_MODES: frozenset[str] = frozenset({
    "precheck", "hirecheck", "dealcheck",
    "assetcheck", "buycheck", "engagecheck", "guaranteecheck", "loancheck",
    "licensecheck", "leasecheck", "privacycheck", "indemnitycheck",
    "consultcheck", "workcheck", "loicheck", "subcheck", "settlementcheck",
})
# ponytail: hard-coded mode list — source of truth for benchmark mode validation.
```

Validation inserted after format check and before dataset resolution:

```python
# After line 147 (format validation)
if not all_datasets:
    mode_list = [m.strip() for m in modes.split(",") if m.strip()]
    for m in mode_list:
        if m not in VALID_MODES:
            typer.echo(
                f"Error: Unknown mode '{m}'. Valid: {', '.join(sorted(VALID_MODES))}",
                err=True,
            )
            raise typer.Exit(code=78)
```

### FR-3: Dead Param Removal

In `runner.py:66-72`, change:

```python
# Before:
def run_dataset(
    self,
    dataset_name: str,
    pipeline_fn: PipelineFn,
    slot_name: str = "default",
    mode: str = "precheck",
) -> DatasetResult:

# After:
def run_dataset(
    self,
    dataset_name: str,
    pipeline_fn: PipelineFn,
    slot_name: str = "default",
) -> DatasetResult:
```

### FR-4: Multi-Mode Iteration

In `cli.py`, replace the single-mode loop (lines 212-223) with multi-mode:

```python
# For each dataset, iterate over each mode
for dataset in dataset_list:
    if dataset == "pii":
        continue
    for mode in mode_list:
        if verbose:
            typer.echo(f"Running dataset: {dataset}, mode: {mode}")
        try:
            result = runner.run_dataset(dataset, _mock_pipeline)
            # Tag result with mode for per-mode breakdown (FR-7)
            result.dataset_name = f"{dataset}::{mode}"
            run.results.append(result)
        except Exception as e:
            typer.echo(f"Error running dataset {dataset} mode {mode}: {e}", err=True)
            if ci:
                raise typer.Exit(code=78) from None
```

### FR-5: Real Gateway Pipeline

**IMPORTANT: The real-provider baseline MUST produce REAL accuracy data, not dummy.**
The `_build_gateway_pipeline()` below MUST call `Gateway.chat()` with the actual
prompt and document text, parse the structured response, and extract real assessments.
If the structured response is unavailable or unparseable, the function MUST fail with
a clear `ValueError` — NOT silently return dummy data.

The mock-return skeleton below exists only as a starting scaffold. The implementation
MUST replace the static return dict with actual structured output parsing.

New function in `cli.py`:

```python
def _build_gateway_pipeline(mode: str) -> PipelineFn:
    """Build a real AI gateway pipeline for the given mode."""
    from openreview_cli.gateway.router import Gateway

    gateway = Gateway()

    def _pipeline(text: str, category: str) -> dict[str, object]:
        response = gateway.chat(
            messages=[{"role": "user", "content": f"Analyze this {mode} clause: {text}"}],
            model_slot="default",  # Use mode-specific slot if available
        )
        # Parse response into prediction dict — MUST extract real data
        return _parse_gateway_response(response, category)

    return _pipeline


def _parse_gateway_response(
    response: dict[str, Any], category: str
) -> dict[str, object]:
    """Parse gateway response into prediction dict matching PipelineFn contract.

    REAL baseline implementation: MUST parse structured output from Gateway.chat()
    response and extract real assessment data. If the response lacks expected
    structured fields, raise ValueError with clear message — do NOT fall back
    to dummy values.
    """
    # ponytail: naive parsing — replace with structured output parsing when available
    # WARNING: This skeleton returns dummy data. The real-provider baseline
    # implementation MUST call Gateway.chat() with actual document text and
    # parse the structured response. If structured output is unavailable,
    # raise ValueError, NOT silent fallback to dummy.
    return {
        "start": 0,
        "end": 0,
        "category": category,
        "label": "entailment",
        "mode": category,
    }
```

### FR-6: Orphan E2E Tests

See [contracts/ORPHAN_E2E_TESTS.md](./contracts/ORPHAN_E2E_TESTS.md) for full test contract.

### FR-7: Per-Mode Report Breakdown

The `DatasetResult.dataset_name` convention (`{dataset}::{mode}`) provides mode-level
distinction. The report layer (`report.py`) SHALL parse this convention to group
results by mode in the terminal output and include mode name in JSON output.

## Test Plan

### Unit Tests

| Test | What it validates |
|------|-------------------|
| VALID_MODES contains 17 entries | Size and content check |
| Mode validation rejects unknown mode | Exit 78, error message |
| Mode validation passes known mode | No exit, continues |
| `run_dataset()` accepts new signature | No `mode` parameter |
| `_mock_pipeline` returns expected dict | Contract compliance |

### Integration Tests

| Test | File | What it validates |
|------|------|-------------------|
| Orphan mode E2E (×9 parametrized) | `test_orphan_modes_e2e.py` | Full pipeline: parse → PII → review → three-color for each orphan mode |
| Multi-mode mock baseline | Existing benchmark tests | All 17 modes × 3 datasets produce valid results |
| Baseline JSON schema | Existing benchmark tests | Baseline validates against BenchmarkRun schema |

### Verification Checklist

- [ ] `openreview benchmark run --modes=invalidmode` → exit 78, error on stderr
- [ ] `openreview benchmark run --modes=precheck,hirecheck,dealcheck` → exit 0
- [ ] `openreview benchmark run --modes=<all 17>` → exit 0
- [ ] `git grep "def run_dataset" src/` shows no `mode` parameter
- [ ] All existing benchmark tests pass
- [ ] `pytest tests/integration/test_orphan_modes_e2e.py -v` → 9 passed
- [ ] Each orphan test clause assessment has `color` in {green, amber, red}
- [ ] Mock baseline produces 51 DatasetResult entries (17 modes × 3 datasets)
- [ ] Real baseline workflow documented in quickstart.md
- [ ] Pre-commit suite passes
- [ ] `uv run mypy src/ tests/` — strict clean
