# Data Model — Benchmark Mode Validation

**Date**: 2026-07-09
**Feature**: Mode whitelist (D-75), accuracy baseline (D-76), orphan E2E tests (D-77)

---

## Entity: VALID_MODES (frozenset[str])

A module-level constant in `benchmark/cli.py` enumerating all 17 product modes.
Single source of truth for benchmark mode validation.

```python
VALID_MODES: frozenset[str] = frozenset({
    "precheck", "hirecheck", "dealcheck",
    "assetcheck", "buycheck", "engagecheck", "guaranteecheck", "loancheck",
    "licensecheck", "leasecheck", "privacycheck", "indemnitycheck",
    "consultcheck", "workcheck", "loicheck", "subcheck", "settlementcheck",
})
```

**Source**: FR-1, spec §4.1, BUNDLED_PLAYBOOKS keys in `playbook.py:20-37`.

### Validation Rules

- All 17 entries match the keys in `BUNDLED_PLAYBOOKS` dict (source of truth for
  playbook-mode mapping)
- `len(VALID_MODES)` = 17. A constitutional amendment that adds/removes a mode
  must update this constant in the same PR
- A `ponytail:` comment documents the design choice:
  `# ponytail: hard-coded — single source of truth for benchmark mode validation.`
- If runtime mode extensibility is ever needed, a `ModeRegistry` with
  `@register_mode` decorator can replace the frozenset without changing the
  validation API

### State Transitions

| Event | Action |
|-------|--------|
| New mode added (constitutional amendment) | Add key to `VALID_MODES` in same PR |
| Mode renamed | Update key + all references in same PR |
| Mode removed | Remove key from `VALID_MODES` in same PR |
| Runtime extensibility needed | Replace frozenset with `ModeRegistry` class |

---

## Entity: BenchmarkConfig (extended)

Existing dataclass at `benchmark/models.py:53-63`. No new fields needed.
The `modes: list[str]` field already exists (line 58) and is populated from
`--modes` at `cli.py:163`. Validation (FR-2) is a gate before config creation.

```python
@dataclass
class BenchmarkConfig:
    datasets: list[str] = field(default_factory=lambda: ["cuad"])
    slots: list[str] = field(default_factory=lambda: ["default"])
    modes: list[str] = field(default_factory=lambda: ["precheck"])
    prompts: dict[str, str] = field(default_factory=dict)
    multi_party: bool = False
    ci_mode: bool = False
    baseline_ref: str | None = None
```

**FR-4 implication**: `modes` will contain all 17 modes when `--all` is used.
Runner must iterate over all modes in `config.modes` per-dataset.

---

## Entity: DatasetResult (existing)

Current model at `benchmark/models.py:66-73`. No changes needed for FR-4/FR-7,
but the per-mode breakdown in reports (FR-7) requires the runner to produce one
`DatasetResult` per (dataset × mode) combination.

For FR-7, `DatasetResult.metadata` or a convention of embedding mode name in
the `dataset_name` field will distinguish per-mode results:
```
"dataset_name": "cuad::precheck"
"dataset_name": "cuad::hirecheck"
```

Alternative: add an optional `mode: str | None = None` field to DatasetResult.
Decision deferred to implementation — the simpler key-convention approach
is preferred (YAGNI — avoids changing the model unless the report layer
requires structured mode data).

---

## Entity: BaselineResult (NEW — FR-5)

New dataclass for capturing per-mode-per-dataset baseline metrics.
Represents one cell in the baseline matrix: 17 modes × 3 datasets = 51 cells.

```python
@dataclass
class BaselineResult:
    """One (mode, dataset) cell in a baseline report."""
    mode: str
    dataset: str
    extraction_f1: float | None = None
    comparison_f1: float | None = None
    classification_f1: float | None = None
    hallucination_rate: float | None = None
    pii_recall: float | None = None
    latency_ms: float | None = None
    peak_memory_mb: float | None = None


@dataclass
class BaselineReport:
    """Full baseline report for one manual run."""
    mode_results: list[BaselineResult]
    git_commit: str
    git_branch: str | None
    provider: str
    model: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)
```

**Note on BaselineReport**: This entity models the JSON output structure
described in FR-5. It is produced during manual baseline runs, not used
at runtime in the benchmark CLI. Stored as `docs/benchmarks/baseline-*.json`.
Validated against `BenchmarkRun` schema for CI regression comparison.

**Rationale**: Separate from existing `BenchmarkRun`/`RegressionBaseline`
because (a) it captures per-mode, per-dataset metrics in a flat structure,
and (b) it includes provider/model metadata not required by the CI regression
comparison flow. The CI regression system (`regression.py`) loads the baseline
and compares metrics; BaselineReport serialization SHALL produce a JSON
structure that `load_baseline()` can consume.

---

## Entity: Orphan Mode E2E Test

Described in spec FR-6. Not a code entity — a parametrized pytest test with:

```python
@pytest.mark.parametrize("mode", [
    "licensecheck", "leasecheck", "privacycheck", "indemnitycheck",
    "consultcheck", "workcheck", "loicheck", "subcheck", "settlementcheck",
])
def test_orphan_mode_e2e(mode, monkeypatch, fixtures_dir):
```

**Test input**: `tests/fixtures/benchmark/{mode_name}/doc_1.pdf` (exists for all 9 orphan modes)

**Test output**: `ReviewReport` with:
- `report.assessments` non-empty
- Each `assessment.color` is one of `AssessmentColor.green | .amber | .red`

**Mock**: Monkeypatch `Gateway.chat` to return pre-determined assessment responses
(following pattern from `tests/integration/test_benchmark_cuad.py`).

---

## Entity: Runner Call Chain Change (FR-4)

### Before (line 218)
```python
result = runner.run_dataset(dataset, _mock_pipeline)
```

### After (multi-mode iteration)
```python
for mode in mode_list:
    result = runner.run_dataset(dataset, _mock_pipeline)
    result.dataset_name = f"{dataset}::{mode}"  # or metadata
    run.results.append(result)
```

This produces `17 modes × N datasets` DatasetResult entries. For `--all`:
- 17 modes × 3 datasets (CUAD, MAUD, ContractNLI) = 51 results
- Plus PII dataset when included (1 result, mode-agnostic)

---

## Field Reconciliation: Spec vs. Code

| Spec Term (FR-6) | Actual Code Location | Actual Type | Access Path |
|------------------|---------------------|-------------|-------------|
| `report.clauses` | `ReviewReport.assessments` | `list[ClauseAssessment]` | `report.assessments` |
| `color_verdict` | `ClauseAssessment.color` | `AssessmentColor \| None` | `assessment.color` |
| `"Green"/"Amber"/"Red"` | `AssessmentColor.{green, amber, red}` | `StrEnum` (lowercase) | `assessment.color == AssessmentColor.green` |
| `clause_id` | `ClauseAssessment.clause_id` | `str` | `assessment.clause_id` |
| `clause_text` | `ClauseAssessment.clause_text` | `str` | `assessment.clause_text` |

**Test code must use the actual model, not spec pseudocode.**
