# Research Document — Benchmark Mode Validation

**Date**: 2026-07-09
**Feature**: Mode whitelist (D-75), accuracy baseline (D-76), orphan E2E tests (D-77)
**Spec**: [spec.md](./spec.md)

---

## 1. Current Benchmark State (D-75 Gap)

**Finding**: `--modes` option at `cli.py:77-79` accepts free-form string, zero validation.
Input splits to `mode_list` at line 163 but never checked against known modes.
No `VALID_MODES` constant exists anywhere in the codebase.

**Impact**: Invalid mode names silently pass validation, produce empty results or
confusing errors downstream in the benchmark runner.

**Gap**: FR-1 mandates `VALID_MODES` frozenset; FR-2 mandates parse-time validation.
Neither exists today. The validation pattern already exists for datasets at
`cli.py:143-160` — mode validation SHALL mirror this exactly.

---

## 2. Dead `mode` Parameter (FR-3) — Caller Audit

**Finding**: `BenchmarkRunner.run_dataset()` at `runner.py:66-71` has
`mode: str = "precheck"` parameter. The parameter is **never referenced**
in the function body (lines 72-161).

**All callers (git grep)**:

| File | Line | Call | `mode=` present? |
|------|------|------|-------------------|
| `cli.py` | 218 | `runner.run_dataset(dataset, _mock_pipeline)` | No |
| `runner.py` | 193 | `self.run_dataset(dataset, pipeline_fn, slot_name=slot)` | No |
| `tests/integration/test_benchmark_cuad.py` | 62 | `runner.run_dataset("cuad", _mock_pipeline)` | No |

**Verdict**: Zero callers pass `mode=`. Parameter is dead code. Safe to remove.

**Design**: Simple removal per spec FR-3. No deprecation shim needed.
The `BenchmarkConfig.modes` list handles multi-mode iteration.

---

## 3. Mock vs Real Provider Split (D-76)

**Rationale**: Two separate workflows for two audiences:

### Mock Provider (CI)
- Used in automated regression detection (FR-4, spec 010 FR-5)
- Returns constant/empty predictions — deterministic by construction
- Any code change affecting metric computation detected as regression
- Fast, cost-free, network-free, flake-free
- Runs in CI on every push

### Real Provider (Manual One-Shot)
- Used for accuracy baselines (FR-5)
- Routes through existing AI Gateway
- Expensive, slow, model-version sensitive
- Results committed to `docs/benchmarks/` as JSON baseline
- Not automated in CI

**Existing mock pipeline**: `_mock_pipeline()` at `cli.py:302-309`. Returns
`{"start": 0, "end": 0, "category": category, "label": "entailment", "match": True}`.

**Real pipeline**: No `_real_pipeline` exists yet. Must be created for FR-5.
Routes through `Gateway.chat()` with configured model slot.

---

## 4. `color` Field Location (R-5 Reconciliation Path)

**Finding**: The spec FR-6 references `clauses` and `color_verdict` on the
ReviewReport model. The actual codebase model differs:

| Spec Reference | Actual Model |
|----------------|--------------|
| `report.clauses` | `report.assessments : list[ClauseAssessment]` |
| `clause.color_verdict` | `assessment.color : AssessmentColor \| None` |
| `"Green"/"Amber"/"Red"` | `"green"/"amber"/"red"` (lowercase enum) |

**Source model**: `ReviewReport` at `review/models.py:173-182`.
- `assessments: list[ClauseAssessment]`
- `ClauseAssessment.color: AssessmentColor | None` at line 109
- `AssessmentColor` at `review/colors.py:10-13`: `StrEnum` with
  `green = "green"`, `amber = "amber"`, `red = "red"`

**Reconciliation**: E2E tests in FR-6 SHALL use the actual model:
- `report.assessments` (not `report.clauses`)
- `assessment.color` equality check against `AssessmentColor.green`, `.amber`, `.red`
- Or `str(assessment.color) in ("green", "amber", "red")`

**R-5 mitigation**: Check `assessment.color is not None` before enum comparison.
If `color` is `None`, the three-color assignment hasn't run — surface a clear error.

---

## 5. 17 Modes + Their Playbook Sources

| # | Mode | CLI Wired (app.py) | BUNDLED_PLAYBOOKS | Playbook File | Fixture Dir (benchmark/) |
|---|------|-------------------|-------------------|---------------|--------------------------|
| 1 | precheck | Line 1105 (`typer.Typer` sub-app) | Line 21 | `precheck-nda-v1.yaml` | — |
| 2 | hirecheck | Line 2325 (`_register_product_mode`) | Line 26 | `hirecheck-v1.yaml` | — |
| 3 | dealcheck | Line 2319 (`_register_product_mode`) | Line 25 | `dealcheck-v1.yaml` | — |
| 4 | assetcheck | Line 2385 (`_register_product_mode`) | Line 33 | `asset-transfer-v1.yaml` | — |
| 5 | buycheck | Line 2391 (`_register_product_mode`) | Line 34 | `asset-purchase-v1.yaml` | — |
| 6 | engagecheck | Line 2397 (`_register_product_mode`) | Line 35 | `engagement-letter-v1.yaml` | — |
| 7 | guaranteecheck | Line 2373 (`_register_product_mode`) | Line 36 | `personal-guarantee-v1.yaml` | — |
| 8 | loancheck | Line 2379 (`_register_product_mode`) | Line 37 | `loan-agreement-v1.yaml` | — |
| 9 | licensecheck | Line 2307 (`_register_product_mode`) | Line 22 | `saas-license-v1.yaml` | ✔ 5 PDFs + GT |
| 10 | leasecheck | Line 2313 (`_register_product_mode`) | Line 23 | `commercial-lease-v1.yaml` | ✔ 5 PDFs + GT |
| 11 | privacycheck | Line 2343 (`_register_product_mode`) | Line 24 | `dpa-v1.yaml` | ✔ 5 PDFs + GT |
| 12 | indemnitycheck | Line 2331 (`_register_product_mode`) | Line 27 | `indemnification-v1.yaml` | ✔ 5 PDFs + GT |
| 13 | consultcheck | Line 2337 (`_register_product_mode`) | Line 28 | `consulting-agreement-v1.yaml` | ✔ 5 PDFs + GT |
| 14 | workcheck | Line 2349 (`_register_product_mode`) | Line 29 | `work-for-hire-v1.yaml` | ✔ 5 PDFs + GT |
| 15 | loicheck | Line 2355 (`_register_product_mode`) | Line 30 | `letter-of-intent-v1.yaml` | ✔ 5 PDFs + GT |
| 16 | subcheck | Line 2361 (`_register_product_mode`) | Line 31 | `subcontractor-agreement-v1.yaml` | ✔ 5 PDFs + GT |
| 17 | settlementcheck | Line 2367 (`_register_product_mode`) | Line 32 | `settlement-agreement-v1.yaml` | ✔ 5 PDFs + GT |

**All 17 modes confirmed wired** in `app.py`. All 17 have `BUNDLED_PLAYBOOKS` entries
in `playbook.py`. All 9 orphan modes have fixture directories at
`tests/fixtures/benchmark/{mode}/` with 5 PDFs + `ground_truth.json` each.

---

## 6. D-72 Skeleton Scripts Status

**Finding**: `scripts/benchmarks/` directory does not exist. The D-72 skeletons
were never created (deferred from spec 028, remained unbuilt through spec 029).
No scripts exist for per-mode accuracy benchmarks.

**Impact on spec 030**: D-72 is not being resolved by this spec. The mock baseline
(FR-4) uses the benchmark harness directly, not per-mode scripts. D-72 remains
deferred until a future spec.

---

## 7. Existing Benchmark Test Files

| File | Tests | Pattern |
|------|-------|---------|
| `test_benchmark_cuad.py` | CUAD loader, mock pipeline, multi-dataset | `BenchmarkRunner` + mock pipeline |
| `test_benchmark_hallucination.py` | ROUGE-L hallucination detection | LexicalOverlapDetector |
| `test_benchmark_pii_accuracy.py` | PII benchmark integration | PiiEngine + mock |
| `test_benchmark_prompt_ab.py` | Prompt variant comparison | SVM classifier |
| `test_benchmark_timing.py` | Timing measurement | Wall-clock + schedule |

**Pattern**: All use `BenchmarkConfig` + `BenchmarkRunner` from `benchmark/models.py`
and `benchmark/runner.py`. Mock pipeline defined as module-level function.

---

## 8. Runner Call Chain

```
cli.py:benchmark_run()
  └─ cli.py:296 → _run_pii_evaluation(runner, verbose)
       └─ runner.run_pii(detect_pii)
  └─ cli.py:218 → runner.run_dataset(dataset, _mock_pipeline)
  └─ runner.run_all()  ← unused currently (cli.py doesn't call it)
       └─ runner.run_dataset(dataset, pipeline_fn, slot_name=slot)
```

`run_all()` loops over `config.datasets` and `config.slots` but does NOT iterate
over `config.modes`. The FR-4 multi-mode baseline must add mode iteration.
