# Interface Contract: Mock Provider Baseline (FR-4)

**Spec ref**: spec 030 FR-4
**Source file**: `src/openreview_cli/benchmark/cli.py` (`_mock_pipeline`)
**Called by**: `benchmark_run()` multi-mode loop

## Interface

```python
def _mock_pipeline(text: str, category: str) -> dict[str, object]:
    """Mock model pipeline — constant/empty predictions.

    Returns:
        dict with keys: start, end, category, label, match
    """
    return {"start": 0, "end": 0, "category": category, "label": "entailment", "match": True}
```

## Usage (multi-mode loop)

```python
for mode in mode_list:
    # mock pipeline is mode-agnostic (returns same values regardless)
    result = runner.run_dataset(dataset, _mock_pipeline)
    result.dataset_name = f"{dataset}::{mode}"
    run.results.append(result)
```

## Behaviour

| Aspect | Value |
|--------|-------|
| Mode-awareness | Not required — mock returns constant predictions |
| Determinism | Yes — always same output for same input |
| Network calls | Zero |
| Expected result count | 17 modes × N datasets |
| CI compatibility | Yes — fast, flake-free, cost-free |

## Rationale (ponytail:)

Mock is mode-agnostic by design. Real provider pipeline (FR-5) is a separate
function that routes through the AI Gateway with mode-aware prompts. The mock's
purpose is CI regression detection, not accuracy measurement.
