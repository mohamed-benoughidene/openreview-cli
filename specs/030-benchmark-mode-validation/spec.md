# Benchmark Mode Validation — Mode Whitelist, Accuracy Baseline, Orphan E2E Tests

**Feature ID**: 030-benchmark-mode-validation
**Status**: Draft Specification
**Created**: 2026-07-09
**Short name**: benchmark-mode-validation

## 1. Executive Summary

This feature resolves three deferred items (D-75, D-76, D-77) from the Batch 2 product modes delivery.
It adds mode validation to the benchmark CLI, runs accuracy baselines against three research datasets
for all 17 product modes, and adds end-to-end tests for 9 orphan modes that currently have only CLI routing.

**What it does:**

1. **D-75 (mode whitelist):** A `VALID_MODES` frozenset in `benchmark/cli.py` enumerating all 17 product modes.
   The `--modes` option validates input against this set at parse time, emitting a clear error for unknown modes.
   The dead `mode` parameter in `runner.py:71` is removed.
2. **D-76 (accuracy baseline):** The benchmark harness runs each of the 17 modes through CUAD, MAUD, and
   ContractNLI datasets. Baselines are recorded with a mock provider in CI (for regression detection) and
   with a real AI gateway provider (manual one-shot, results published to `docs/benchmarks/`).
3. **D-77 (orphan E2E tests):** Nine orphan modes receive full end-to-end pipeline tests: parse fixture
   document → strip PII → run review → assert three-color output (Green/Amber/Red per clause).
   Tests mock the AI gateway to avoid network calls.

Blueprint references: [the 22 product modes capability], [the Batch 2 product modes delivery],
[the multi-mode accuracy constraint], [the regression detection constraint].

### Deferred items resolved

| Item | Description | Status |
|------|-------------|--------|
| D-75 | Benchmark mode whitelist (`VALID_MODES` frozenset) + dead param removal | Resolved by FR-1, FR-2, FR-3 |
| D-76 | Accuracy baseline run (CUAD, MAUD, ContractNLI × 17 modes) | Resolved by FR-4, FR-5 |
| D-77 | End-to-end pipeline tests for 9 orphan modes | Resolved by FR-6 |

## 2. Clarifications

No clarifications needed at specification time. Key design decisions are documented in each
functional requirement. Assumptions are listed in §7.

### Session 2026-07-09

- **Q: Should `VALID_MODES` be a hard-coded frozenset or a registry pattern?**
  **A:** Hard-coded frozenset (per YAGNI / ponytail). A registry adds abstraction for zero benefit
  when the mode set changes only via constitutional amendment. Documented with a `ponytail:` comment.
- **Q: Should the `mode` param in `runner.py:71` be removed or kept?**
  **A:** Removed (Option A). The `--modes` list in `BenchmarkConfig.modes` handles multi-mode runs.
  Verified that no external caller passes `mode=` as keyword (see §8 Assumptions).
- **Q: Should real AI gateway baselines run in CI?**
  **A:** No. CI runs mock-only (cost, time, flakiness). Real baselines are manual one-shot runs
  committed to `docs/benchmarks/`.

## 3. User Scenarios

### US-1: Developer Validates Modes in Benchmark

A developer runs `openreview benchmark run --modes=precheck,hirecheck,invalidmode`.
The CLI validates each mode against `VALID_MODES`, rejects `invalidmode`, and prints:

```
Error: Unknown mode 'invalidmode'. Valid: assetcheck, buycheck, consultcheck, dealcheck,
engagecheck, guaranteecheck, hirecheck, indemnitycheck, leasecheck, licensecheck, loancheck,
loicheck, precheck, privacycheck, settlementcheck, subcheck, workcheck
```

The command exits with code 78 (configuration error).

### US-2: Accuracy Baseline Run (CI Mode)

CI runs `openreview benchmark run --all --ci` on every push. The benchmark runner executes
all 17 modes across CUAD, MAUD, and ContractNLI using the mock pipeline (`_mock_pipeline`).
Results are compared against the stored baseline from the previous commit. A metric drop
exceeding 2 percentage points F1 fails the CI check and blocks merge.

### US-3: Manual Accuracy Baseline (Real Provider)

A developer runs:

```bash
openreview benchmark run --all --save-baseline --format json --output baseline.json
```

against a real AI gateway provider (e.g., Ollama or a cloud slot). The run completes,
producing a structured JSON report with per-mode × per-dataset metrics. The developer
copies `baseline.json` to `docs/benchmarks/baseline-2026-07-09.json` and commits it
as the reference baseline for subsequent CI regression checks.

### US-4: Orphan Mode E2E Test

A developer runs `pytest tests/integration/test_orphan_modes_e2e.py -v`.
For each of 9 orphan modes (licensecheck, leasecheck, privacycheck, indemnitycheck,
consultcheck, workcheck, loicheck, subcheck, settlementcheck), the test:

1. Parses a fixture document from `tests/fixtures/benchmark/{mode_name}/`
2. Strips PII using the existing PII engine
3. Runs `run_review()` with a mocked AI gateway
4. Asserts the result is a valid `ReviewReport` with non-empty clauses
5. Asserts each clause has a three-color verdict (Green/Amber/Red)

All 9 tests pass.

## 4. Functional Requirements

### FR-1: Mode Whitelist (D-75)

The benchmark CLI SHALL define a `VALID_MODES` frozenset in
`src/openreview_cli/benchmark/cli.py` containing all 17 product modes:

| Category | Modes |
|----------|-------|
| 3 established modes | `precheck`, `hirecheck`, `dealcheck` |
| 5 Batch 2 modes | `assetcheck`, `buycheck`, `engagecheck`, `guaranteecheck`, `loancheck` |
| 9 orphan modes | `licensecheck`, `leasecheck`, `privacycheck`, `indemnitycheck`, `consultcheck`, `workcheck`, `loicheck`, `subcheck`, `settlementcheck` |

```python
VALID_MODES: frozenset[str] = frozenset({
    "precheck", "hirecheck", "dealcheck",
    "assetcheck", "buycheck", "engagecheck", "guaranteecheck", "loancheck",
    "licensecheck", "leasecheck", "privacycheck", "indemnitycheck",
    "consultcheck", "workcheck", "loicheck", "subcheck", "settlementcheck",
})
```

The frozenset SHALL be the single source of truth for benchmark mode validation.
A `ponytail:` comment SHALL document the design choice:
`# ponytail: hard-coded mode list — source of truth for benchmark mode validation.`

**Source**: [D-75], [the 22 product modes capability], [the Batch 2 product modes delivery]

### FR-2: Mode Validation at Parse Time (D-75)

The `benchmark_run` command SHALL validate every entry in `--modes` against `VALID_MODES`
before executing any benchmark logic. Unknown modes SHALL produce:

- Error message: `Error: Unknown mode '{name}'. Valid: {sorted, comma-separated list of valid modes}`
- Exit code: 78 (configuration error, matching existing dataset validation at `cli.py:143-147`)
- The error SHALL be emitted to stderr via `typer.echo(..., err=True)`

Validation SHALL follow the same pattern as dataset validation (lines 154-160 of `cli.py`):

```python
for m in mode_list:
    if m not in VALID_MODES:
        typer.echo(
            f"Error: Unknown mode '{m}'. Valid: {', '.join(sorted(VALID_MODES))}",
            err=True,
        )
        raise typer.Exit(code=78)
```

**Source**: [D-75]

### FR-3: Dead Parameter Removal (D-75)

The `mode: str = "precheck"` parameter on `BenchmarkRunner.run_dataset()` (line 71 of
`runner.py`) is dead code — never referenced in the function body. The spec mandates:

**Decision**: Remove the `mode` parameter entirely.

Justification:
- The `BenchmarkConfig.modes` list (populated from `--modes`) already handles multi-mode runs.
- No internal caller passes `mode=` as a keyword argument (verified: `cli.py:218`,
  `runner.py:193`, `runner.py:run_all()` line 192 — all omit `mode`).
- If external callers exist outside the benchmark package, the parameter SHALL be kept as a
  positional-only compat shim with a deprecation warning for one minor version.

Change:
```python
# Before:
def run_dataset(self, dataset_name: str, pipeline_fn: PipelineFn,
                slot_name: str = "default", mode: str = "precheck") -> DatasetResult:
# After:
def run_dataset(self, dataset_name: str, pipeline_fn: PipelineFn,
                slot_name: str = "default") -> DatasetResult:
```

**Source**: [D-75], [the product modes constraint]

### FR-4: Mock Provider Baseline (D-76)

The benchmark runner SHALL support executing all 17 modes against CUAD, MAUD, and ContractNLI
datasets using the existing mock pipeline (`_mock_pipeline` in `cli.py:302-309`).

Requirements:
- The mock pipeline returns constant/empty predictions (`{"start": 0, "end": 0, "category": category, "label": "entailment", "match": True}`).
- The mock pipeline SHALL accept `text` and `category` parameters as before — mode-awareness
  is not required for mock mode since the mock returns constant values regardless.
- The runner SHALL call `run_dataset()` for each mode in `BenchmarkConfig.modes`, producing
  one `DatasetResult` per mode per dataset. With 17 modes × 3 datasets = 51 `DatasetResult` entries
  (PII dataset adds one more when included).
- The runner SHALL NOT crash on mode-specific discrepancies (all modes produce the same mock output).
- CI regression detection (FR-5 of spec 010) SHALL work with mock-provider results — mock baselines
  are stable by construction, so any code change that affects metric computation will be detected.

**Source**: [D-76], [the multi-mode accuracy constraint], [the regression detection constraint]

### FR-5: Real Provider Baseline — Manual Run (D-76)

Establishing a real accuracy baseline is a manual, documented workflow:

1. Developer ensures a real AI gateway provider is configured (Ollama or cloud, through the
   existing gateway setup).
2. Developer runs:
   ```bash
   openreview benchmark run --all --save-baseline --format json \
     --output docs/benchmarks/baseline-$(date +%F).json
   ```
3. The JSON report SHALL contain per-mode × per-dataset metrics: extraction F1, comparison F1,
   classification F1, hallucination rate, PII recall (where applicable), latency, and peak memory.
4. The developer commits the baseline JSON to the repository under `docs/benchmarks/`.
5. The baseline SHALL include a metadata block recording: provider, model name, git commit SHA,
   and timestamp.
6. The baseline SHALL NOT be automated in CI (cost, time, flakiness, and model-version sensitivity
   make mock baselines the appropriate CI tool).

The existing `_mock_pipeline` in `cli.py` SHALL be replaced with a real gateway call for this
manual workflow. The replacement SHALL route through the existing AI Gateway using the configured
model slot for each mode. If no slot is configured for a mode, the "default" slot SHALL be used.

**Source**: [D-76], [the product modes constraint], [the regression detection constraint]

### FR-6: Orphan Mode E2E Tests (D-77)

A new integration test file `tests/integration/test_orphan_modes_e2e.py` SHALL contain
end-to-end tests for each of the 9 orphan modes.

Each test SHALL:

1. **Locate fixture**: Use `tests/fixtures/benchmark/{mode_name}/` as the fixture root.
   If no fixture document exists, create a minimal `.txt` file containing standard contract
   language (e.g., a single clause defining confidentiality terms).

2. **Parse document**: Call the existing `stream_clauses()` parser on the fixture file.

3. **Strip PII**: Route through the existing PII engine (`PiiEngine.strip_clauses()` or
   equivalent public API).

4. **Run review**: Call `run_review()` with a mocked AI gateway. The mock SHALL follow the
   pattern from `tests/integration/test_benchmark_cuad.py` — monkeypatch the gateway to
   return pre-determined assessment responses.

5. **Assert ReviewReport**: Verify the result is a `ReviewReport` with:
   - `clauses` list is non-empty
   - Each clause has a `color_verdict` field in `{"Green", "Amber", "Red"}`
   - No exceptions raised during the pipeline

6. **Assert three-color output**: For each clause, assert `color_verdict in ("Green", "Amber", "Red")`.

Test structure:
```python
@pytest.mark.parametrize("mode", [
    "licensecheck", "leasecheck", "privacycheck", "indemnitycheck",
    "consultcheck", "workcheck", "loicheck", "subcheck", "settlementcheck",
])
def test_orphan_mode_e2e(mode, monkeypatch, fixtures_dir):
    fixture_path = fixtures_dir / "benchmark" / mode / "contract.txt"
    if not fixture_path.exists():
        pytest.skip(f"No fixture for mode {mode}")
    # mock AI gateway
    monkeypatch.setattr("openreview_cli.gateway.router.Gateway.chat", mock_gateway_chat)
    # run pipeline
    report = run_review(document_path=str(fixture_path), mode=mode)
    # assertions
    assert len(report.clauses) > 0
    for clause in report.clauses:
        assert clause.color_verdict in ("Green", "Amber", "Red")
```

**Fixture creation rule**: If `tests/fixtures/benchmark/{mode_name}/` exists with a valid
document, use it. If not, create a minimal `.txt` fixture containing one clause of standard
contract language appropriate to that mode's domain (e.g., a confidentiality clause for
privacycheck). The fixture SHALL be committed as part of this spec's implementation.

**Source**: [D-77], [the 22 product modes capability], [the Batch 2 product modes delivery]

### FR-7: Mode Coverage in Report

The benchmark output report (terminal and JSON) SHALL include a per-mode breakdown of metrics.

For each dataset evaluated, the report SHALL show:
- Which modes were run
- Per-mode metric values (F1, precision, recall, etc.)
- Aggregate (macro average) across all modes

This ensures a reader of a baseline report knows exactly which modes contributed to the
aggregate numbers.

**Source**: [D-76], [the multi-mode accuracy constraint]

## 5. Success Criteria

| # | Criterion | Measure | Target | Verification |
|---|-----------|---------|--------|-------------|
| SC-1 | Mode validation rejects unknown modes | Exit code | 78 with error listing valid modes | Run `openreview benchmark run --modes=invalidmode` and assert exit 78 |
| SC-2 | All 17 modes accepted without error | No crash, exit 0 | All modes pass validation | Run `openreview benchmark run --modes=<all 17 comma-separated>` and assert exit 0 |
| SC-3 | Dead `mode` param removed from `run_dataset()` | No `mode` in signature | Parameter removed without breaking callers | `git grep "run_dataset"` confirms no `mode=` callers; type checker passes |
| SC-4 | Mock baseline produces 51 DatasetResult entries | 3 datasets × 17 modes | All entries non-empty | Run `--all`, inspect `run.results` length and structure |
| SC-5 | Baseline JSON validates against BenchmarkRun schema | Schema compliance | No pydantic validation errors | Load JSON and validate against `BenchmarkRun` model |
| SC-6 | All 9 orphan mode E2E tests pass | 9 tests | All green | `pytest tests/integration/test_orphan_modes_e2e.py -v` |
| SC-7 | Each orphan test asserts three-color verdict | `color_verdict` in Green/Amber/Red | Every clause has valid color | Assertion per clause in E2E test |
| SC-8 | Mode coverage visible in report | Per-mode breakdown | Terminal/JSON includes mode-specific sections | Inspect report output |
| SC-9 | CI regression detection works with mock baseline | CI passes with mock, fails on seeded regression | Verified | Deliberately regress metric and confirm CI blocks (manual verification) |

### Metrics measured

| Metric | Unit | Applicable Datasets | Source |
|--------|------|-------------------|--------|
| Extraction F1 | f1 | CUAD | Standard span-based F1 |
| Comparison F1 | f1 | MAUD | Binary classification F1 |
| Classification F1 | f1 | ContractNLI | 3-class macro F1 |
| Hallucination rate | rate | All | ROUGE-L lexical overlap (EXPERIMENTAL) |
| PII recall | recall | PII | Seeded corpus recall |
| Latency | ms | All | Wall-clock time |
| Peak memory | MB | All | tracemalloc (NLP model exempt) |

## 6. Key Entities

### VALID_MODES (frozenset)
The authoritative list of 17 product modes. Defined as a module-level constant in
`benchmark/cli.py`. Reused by validation logic and report generation.

### Orphan Mode
One of 9 product modes that exist as CLI subcommands (routing works) but lack full E2E
pipeline tests: licensecheck, leasecheck, privacycheck, indemnitycheck, consultcheck,
workcheck, loicheck, subcheck, settlementcheck.

### Benchmark Baseline (JSON)
A structured accuracy report stored at `docs/benchmarks/baseline-YYYY-MM-DD.json`.
Contains per-dataset × per-mode metrics, run metadata, and provider/model information.
Committed to the repository for reference.

### Orphan Mode Test Suite
A set of 9 parametrized integration tests in `tests/integration/test_orphan_modes_e2e.py`.
Each test covers one orphan mode end-to-end with mocked AI gateway calls.

## 7. Dependencies

| Dependency | Type | Reference | Notes |
|-----------|------|-----------|-------|
| Benchmark CLI (`benchmark/cli.py`) | Internal | — | Target for FR-1, FR-2 (VALID_MODES, validation) |
| Benchmark Runner (`benchmark/runner.py`) | Internal | — | Target for FR-3 (dead param removal), FR-4 (multi-mode runs) |
| Benchmark Models (`benchmark/models.py`) | Internal | — | `BenchmarkConfig.modes`, `BenchmarkRun` used by all FRs |
| Review Pipeline (`review/__init__.py`) | Internal | — | Required by FR-6 (orphan mode tests call `run_review()`) |
| AI Gateway (`gateway/`) | Internal | — | Mocked in FR-6 tests; used in real baseline FR-5 |
| Document Parsing (`parsing/`) | Internal | — | Required by FR-6 (parse fixture documents) |
| PII Engine (`pii/`) | Internal | — | Required by FR-6 (strip PII before review) |
| CUAD Dataset | External research | [P-7] | Required for FR-4, FR-5 baseline |
| MAUD Dataset | External research | [P-7] | Required for FR-4, FR-5 baseline |
| ContractNLI Dataset | External research | [P-7] | Required for FR-4, FR-5 baseline |

No new external dependencies. All internal dependencies are stable
and tested in prior specs. The three research datasets are already consumed by the benchmark
harness (spec 010).

## 8. Assumptions

1. **Hard-coded frozenset is sufficient.** `VALID_MODES` is hard-coded rather than registry-based.
   This is a deliberate simplification (ponytail). If runtime mode extensibility becomes necessary,
   a `ModeRegistry` with `@register_mode` decorator can replace the frozenset without changing
   the validation API.

2. **Dead `mode` parameter has no external callers.** The `run_dataset(mode=...)` keyword argument
   is unused by all known callers (verified in `cli.py:218`, `runner.py:193`, `runner.py:run_all()`).
   If an external caller exists outside the benchmark package, a positional-only compat shim with
   deprecation warning SHALL be added before the final removal.

3. **Mock pipeline is acceptable for CI regression.** The mock returns constant/empty predictions.
   This is acceptable because (a) the mock baseline is deterministic — any code change affecting
   metric computation will be detected, and (b) real-accuracy baselines are a separate,
   non-automated workflow.

4. **Fixture documents exist or can be trivially created.** Each orphan mode's fixture directory
   either already contains a document or a minimal `.txt` fixture with one domain-appropriate
   clause is created. The fixture text does not need to match the mode's domain exactly —
   the test validates the pipeline structure, not semantic accuracy.

5. **Three-color verdict is present on `Clause` model.** The `color_verdict` field is populated
   by the review pipeline's grounding discriminator. If it is absent, the E2E test SHALL check
   for its presence and fail with a clear message indicating the mismatch.

6. **Real provider baseline is reproducible.** The manual baseline workflow assumes the AI gateway
   provider configured at run time produces consistent-enough results for a snapshot. Model version
   drift between baselines is expected and documented alongside each baseline file.

## 9. Risks

| ID | Risk | Impact | Mitigation | FR Reference |
|----|------|--------|------------|-------------|
| R-1 | Removing `mode` param breaks unknown external caller | Runtime TypeError | Audit callers with `git grep` before removal; add deprecation shim if external caller found | FR-3 |
| R-2 | Mock baseline too permissive (mock returns perfect scores) | False confidence in CI regression detection | Mock returns zero-length spans (conservative: F1=0 for sparsely populated ground truth) | FR-4 |
| R-3 | Real baseline run exceeds budget (time/cost) | Cannot establish real baseline | Manual one-shot workflow; developer chooses budget-appropriate provider (Ollama is free) | FR-5 |
| R-4 | Orphan mode fixture directory missing or empty | E2E tests cannot load input | Create minimal `.txt` fixture during implementation; test skips with `pytest.skip` if absent | FR-6 |
| R-5 | `color_verdict` field not yet on Clause model | E2E assertion fails | Check field existence in test and fail with descriptive error; if field absent, amend review pipeline | FR-6 |
| R-6 | Mode count changes (new mode added, mode renamed) | VALID_MODES out of sync | Constitutional amendment process updates VALID_MODES in same PR; no automated sync needed | FR-1 |

## 10. Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Privacy First | Pass | Mock baseline uses no real data. Real baseline routes through existing PII stripping (spec 010 already compliant). No new data leaves the machine beyond existing gateway calls. |
| II. Local-First, CLI-Only | Pass | All work is CLI-invoked (`openreview benchmark run`). No web server, daemon, or telemetry. Real baseline is a direct CLI command. |
| III. Hardware-Bounded | Pass | Mock baseline adds ~0 memory (constant predictions). Real baseline uses existing gateway infrastructure. No new processing loops or in-memory collections. |
| IV. Dependency Minimalism | Pass | No new dependencies. Validation uses stdlib `frozenset`. Tests use existing `pytest` + `monkeypatch`. |
| V. Spec-Driven, YAGNI | Pass | This spec specifies exactly three deferred items (D-75, D-76, D-77). No speculative work beyond the minimum required to resolve each. Hard-coded frozenset over registry (YAGNI). |

## 11. Next Steps

1. **Proceed to `/speckit.plan`** for technical design
2. **Verify assumption R-1**: run `git grep "run_dataset"` to confirm no external `mode=` callers
3. **Verify assumption R-5**: check `Clause` model for `color_verdict` field
4. **Design technical implementation** covering:
   - `VALID_MODES` frozenset placement and validation logic
   - `mode` parameter removal from `run_dataset()`
   - Multi-mode iteration in `run_dataset()` and `run_all()`
   - Orphan mode fixture creation plan
   - Mock gateway response design for 9 orphan modes
5. **Implement** in order: FR-1/FR-2 (validation) → FR-3 (dead param) → FR-6 (E2E tests) → FR-4/FR-5 (baselines)
6. **Run baseline** (manual, after implementation): `openreview benchmark run --all --save-baseline`
7. **Commit baseline** to `docs/benchmarks/baseline-YYYY-MM-DD.json`
