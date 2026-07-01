# Quickstart: SLM Model Params Extension

**Date**: 2026-07-01 | **Feature**: 006-slm-model-params

## Prerequisites

- Python 3.12, `uv sync` completed
- Existing gateway tests passing: `uv run pytest tests/unit/test_gateway_models.py tests/unit/test_gateway_router.py -q`

## Validation Scenarios

### Scenario 1: ModelEntry accepts extra_params

**Run**:
```bash
uv run pytest tests/unit/test_gateway_models.py -q -k "extra_params"
```

**Expected**: All `extra_params`-related ModelEntry tests pass — construction with and without the field, serialization of nested dicts.

### Scenario 2: Protected keys are stripped

**Run**:
```bash
uv run pytest tests/unit/test_gateway_router.py -q -k "protected"
```

**Expected**: Tests confirm that `model`, `messages`, `input`, and `timeout` are stripped from `extra_params` before merging. Warning is logged.

### Scenario 3: Health check shows extra_params count

**Run**:
```bash
uv run pytest tests/unit/test_gateway_router.py -q -k "health"
```

**Expected**: Health check output includes `extra_params: N` for slots with extra params configured.

### Scenario 4: Full regression

**Run**:
```bash
uv run pytest tests/unit/test_gateway_models.py tests/unit/test_gateway_router.py -q
```

**Expected**: All existing and new tests pass. Zero regressions.

### Scenario 5: Type safety

**Run**:
```bash
uv run mypy src/openreview_cli/gateway/models.py src/openreview_cli/gateway/router.py --strict
```

**Expected**: No type errors. `extra_params: dict[str, Any] | None = None` is mypy-strict compatible.

## Links

- Data model: [data-model.md](data-model.md)
- CLI contract: [contracts/cli-contract.md](contracts/cli-contract.md)
- Research: [research.md](research.md)
