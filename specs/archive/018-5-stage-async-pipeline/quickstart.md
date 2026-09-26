# Quickstart — 5-Stage Async Pipeline Framework

**Date**: 2026-07-04 | **Spec Reference**: spec.md §2 (User Scenarios)

## Prerequisites

- Python 3.12, uv installed
- Repository clone with submodules: `git submodule update --init`
- Dev environment: `uv sync`

## Validation Scenarios

### Scenario 1: Pipeline runs 5 stages in order (P1)

**Test file**: `tests/unit/test_pipeline_runner.py` (NEW)

```python
# Write this test as the FIRST task (TDD)
async def test_five_stage_pipeline_ordering():
    """Each stage's run() is called exactly once, in order."""
    stages = [MockStage("parse"), MockStage("strip"), MockStage("chunk"),
              MockStage("retrieve"), MockStage("generate")]
    pipeline = Pipeline(stages=stages)
    report = await pipeline.run({"document_path": "test.pdf"})
    assert [s.call_count for s in stages] == [1, 1, 1, 1, 1]
    assert stages[0].call_order < stages[1].call_order < stages[2].call_order \
        < stages[3].call_order < stages[4].call_order
    assert len(report.stage_results) == 5
```

**Run**: `uv run pytest tests/unit/test_pipeline_runner.py::test_five_stage_pipeline_ordering -v`

**Expected**: PASS — runner invokes each stage once in order, returns report with 5 entries.

### Scenario 2: Non-critical error continues pipeline (P1)

**Test file**: `tests/unit/test_pipeline_runner.py`

```python
async def test_non_critical_error_continues():
    """Non-critical stage failure is captured but pipeline continues."""
    stages = [
        MockStage("parse", fail=False),
        MockStage("strip", fail=True),    # non-critical
        MockStage("chunk", fail=False),
    ]
    pipeline = Pipeline(stages=stages)
    report = await pipeline.run({"document_path": "test.pdf"})
    assert report.stage_results[0].error is None
    assert report.stage_results[1].error is not None  # strip failed
    assert report.stage_results[2].error is None       # chunk still executed
    assert "errors" in report.stage_results[1].output_keys  # errors accumulated
```

**Run**: `uv run pytest tests/unit/test_pipeline_runner.py::test_non_critical_error_continues -v`

**Expected**: PASS — chunk runs despite strip failure, error captured in StageResult.

### Scenario 3: Critical error halts pipeline (P1)

**Test file**: `tests/unit/test_pipeline_runner.py`

```python
async def test_critical_error_halts():
    """Critical stage failure stops pipeline immediately."""
    stages = [
        MockStage("parse", critical=True, fail=True),
        MockStage("strip", fail=False),
    ]
    pipeline = Pipeline(stages=stages)
    with pytest.raises(CriticalStageError):
        await pipeline.run({"document_path": "test.pdf"})
```

**Run**: `uv run pytest tests/unit/test_pipeline_runner.py::test_critical_error_halts -v`

**Expected**: PASS — CriticalStageError propagated, strip never called.

### Scenario 4: Stage cleanup releases memory (P2)

**Test file**: `tests/unit/test_pipeline_runner.py`

```python
async def test_cleanup_releases_memory():
    """cleanup() is invoked after stage result is merged."""
    cleanup_called = False

    class CleanupStage(Stage):
        name = "cleanup-test"
        async def run(self, ctx):
            ctx["big_data"] = "x" * 1024 * 1024  # 1 MB string
            return {"big_data": "set"}
        def cleanup(self):
            nonlocal cleanup_called
            cleanup_called = True

    pipeline = Pipeline(stages=[CleanupStage()])
    await pipeline.run({})
    assert cleanup_called
```

**Run**: `uv run pytest tests/unit/test_pipeline_runner.py::test_cleanup_releases_memory -v`

**Expected**: PASS — cleanup is called after run() completes.

### Scenario 5: Custom 2-stage pipeline (P2)

**Test file**: `tests/unit/test_pipeline_stages.py`

```python
async def test_custom_two_stage_pipeline():
    """Only Parse + Chunk stages run when composed."""
    stages = [ParseStage(), ChunkStage()]
    pipeline = Pipeline(stages=stages)
    report = await pipeline.run({"document_path": "fixtures/sample.pdf"})
    assert "document" in report.stage_results[0].output_keys
    assert "chunks" in report.stage_results[1].output_keys
```

**Run**: `uv run pytest tests/unit/test_pipeline_stages.py::test_custom_two_stage_pipeline -v`

**Expected**: PASS — only two stages run, context has only parse + chunk keys.

### Scenario 6: Empty pipeline (Edge case)

**Test file**: `tests/unit/test_pipeline_runner.py`

```python
async def test_empty_pipeline():
    """Empty stage list returns empty report immediately."""
    pipeline = Pipeline(stages=[])
    report = await pipeline.run({"key": "value"})
    assert len(report.stage_results) == 0
    assert report.total_duration_s == 0.0
    assert report.cancelled is False
```

**Run**: `uv run pytest tests/unit/test_pipeline_runner.py::test_empty_pipeline -v`

**Expected**: PASS — no error, empty report returned.

### Scenario 7: Stage with no output (Edge case)

**Test file**: `tests/unit/test_pipeline_runner.py`

```python
async def test_stage_returns_none():
    """Stage returning None is treated as successful no-op."""
    stages = [NoOpStage(), MockStage("after", fail=False)]
    pipeline = Pipeline(stages=stages)
    report = await pipeline.run({})
    assert report.stage_results[0].error is None
    assert report.stage_results[1].error is None
```

**Run**: `uv run pytest tests/unit/test_pipeline_runner.py::test_stage_returns_none -v`

**Expected**: PASS — None return is treated as successful no-op.

### Scenario 8: Cancellation during pipeline (Edge case)

**Test file**: `tests/unit/test_pipeline_runner.py`

```python
async def test_cancellation_returns_partial_report():
    """Setting cancellation token completes current stage and returns."""
    token = asyncio.Event()
    stages = [
        MockStage("first"),
        SlowStage("second", delay=10.0),  # will be cancelled
    ]
    async def cancel_later():
        await asyncio.sleep(0.01)
        token.set()

    async def run_and_cancel():
        pipeline = Pipeline(stages=stages, cancellation_token=token)
        return await pipeline.run({})

    report = await asyncio.gather(run_and_cancel(), cancel_later())[0]
    assert report.cancelled is True
    assert len(report.stage_results) == 1  # only first completed
```

**Run**: `uv run pytest tests/unit/test_pipeline_runner.py::test_cancellation_returns_partial_report -v`

**Expected**: PASS — cancellation returns partial report with first stage only.

### Scenario 9: Memory budget warning (P2)

**Test file**: `tests/integration/test_pipeline_memory.py`

```python
async def test_memory_warning_on_large_stage():
    """Warning emitted when stage allocates more than max_memory_mb."""
    stages = [BigStage("large", size_mb=50)]
    pipeline = Pipeline(stages=stages, max_memory_mb=10)
    with caplog.at_level(logging.WARNING):
        report = await pipeline.run({})
    assert any("exceeded" in msg for msg in caplog.text)
```

**Run**: `uv run pytest tests/integration/test_pipeline_memory.py::test_memory_warning_on_large_stage -v`

**Expected**: PASS — warning logged for stage exceeding memory threshold.

## Running All Pipeline Tests

```bash
# Unit tests (no I/O, no network)
uv run pytest tests/unit/test_pipeline_runner.py tests/unit/test_pipeline_stages.py -v

# Integration tests (mock stages, document fixtures)
uv run pytest tests/integration/test_pipeline_e2e.py tests/integration/test_pipeline_memory.py -v

# Full pipeline test suite
uv run pytest tests/ -k "pipeline" -v

# Memory budget test
uv run pytest tests/integration/test_pipeline_memory.py -v --memcheck
```

## Refactoring run_review() — Verification

After the pipeline framework is tested, refactor `run_review()` and verify:

```bash
# Existing review tests must pass with zero changes
uv run pytest tests/unit/test_review_pipeline.py tests/unit/test_review_models.py tests/unit/test_review_report.py -v

# PreCheck integration tests
uv run pytest tests/integration/test_precheck_review.py -v

# Full test suite for regression
uv run pytest tests/ -k "review" -v
```

All existing tests must pass without modification.
