# Interface Contract: Dead `mode` Parameter Removal (FR-3)

**Spec ref**: spec 030 FR-3
**Target**: `src/openreview_cli/benchmark/runner.py`, method `run_dataset()`

## Current Signature (line 66-72)

```python
def run_dataset(
    self,
    dataset_name: str,
    pipeline_fn: PipelineFn,
    slot_name: str = "default",
    mode: str = "precheck",    # ← DEAD PARAMETER
) -> DatasetResult:
```

## New Signature

```python
def run_dataset(
    self,
    dataset_name: str,
    pipeline_fn: PipelineFn,
    slot_name: str = "default",
) -> DatasetResult:
```

## Caller Audit (all known callers, no `mode=` usage)

| Caller | File | Current Call | After Removal |
|--------|------|-------------|---------------|
| `benchmark_run()` | `cli.py:218` | `runner.run_dataset(dataset, _mock_pipeline)` | No change |
| `run_all()` | `runner.py:193` | `self.run_dataset(dataset, pipeline_fn, slot_name=slot)` | No change |
| Test CUAD | `test_benchmark_cuad.py:62` | `runner.run_dataset("cuad", _mock_pipeline)` | No change |

## Safety

Zero callers use `mode=` keyword. No positional callers pass a 4th argument.
Removal is source-compatible and binary-compatible for all known callers.

## Rollback

If an unknown external caller exists outside the benchmark package, add:

```python
def run_dataset(
    self,
    dataset_name: str,
    pipeline_fn: PipelineFn,
    slot_name: str = "default",
    mode: str | None = None,  # DEPRECATED — positional-only compat shim
) -> DatasetResult:
    if mode is not None:
        warnings.warn(
            "mode parameter is deprecated and has no effect",
            DeprecationWarning,
            stacklevel=2,
        )
```

But per spec assumption A2 and git grep verification, no external caller exists.
Simple removal is sufficient.
