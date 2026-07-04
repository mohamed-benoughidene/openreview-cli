# Data Model — 5-Stage Async Pipeline Framework

**Date**: 2026-07-04 | **Spec Reference**: spec.md §3 (Key Entities)

## Entities

### PipelineContext

The shared mutable dict that flows through all stages. The pipeline runner does **not** inspect or validate its contents — stages read prior outputs and write their own.

**Type**: `dict[str, Any]`

**Conventional keys** (informal — stages may add any key):

| Key | Set by | Type | Description |
|-----|--------|------|-------------|
| `document_path` | Caller (CLI) | `str` | Path to the input document |
| `document` | ParseStage | `Document` | Parsed document metadata (pages, toc, etc.) |
| `clauses` | ParseStage | `list[Clause]` | Streamed clause list from document parser |
| `stripped_clauses` | StripStage | `list[Clause]` | PII-stripped clauses |
| `chunks` | ChunkStage | `list[Chunk]` | Recursively chunked clauses |
| `retrieved` | RetrieveStage | `list[SearchResult]` | Retrieved relevant passages |
| `generated` | GenerateStage | `str` | Generated output text |
| `playbook` | Caller | `Playbook` | The playbook used for assessment |
| `playbook_version` | Caller | `int \| None` | Playbook version if loaded from database |
| `errors` | Pipeline runner (implicit) | `list[StageResult]` | Accumulated non-critical stage errors |
| `cancelled` | Pipeline runner | `bool` | Whether execution was cancelled |

**Validation**: None (per spec FR-009 — minimal coupling, no schema enforcement).

### Stage (Protocol/ABC)

Abstract base class for all pipeline stages.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | (required) | Human-readable stage name (e.g. "parse", "strip") |
| `critical` | `bool` | `False` | If `True`, stage failure halts the pipeline immediately |
| `cleanup` | `Callable[[], None] \| None` | `None` | Optional callback invoked after stage result is merged, before next stage starts |

| Method | Signature | Description |
|--------|-----------|-------------|
| `run()` | `async (ctx: PipelineContext) → dict[str, Any]` | Execute the stage. Receives shared context, returns stage-specific results to merge. |

**State transitions**:
- `stage.run()` is called exactly once per pipeline execution (unless skipped)
- `stage.cleanup()` is called after `run()` completes (success or error) if the callback is defined
- A stage that implements `should_skip() → bool` may be skipped entirely

### StageResult

Record of a single stage execution, stored in `PipelineReport.stage_results`.

| Field | Type | Description |
|-------|------|-------------|
| `stage_name` | `str` | Name of the stage |
| `duration_s` | `float` | Wall-clock duration in seconds |
| `error` | `str \| None` | Error message if the stage failed (None on success) |
| `output_keys` | `list[str]` | Keys written to the shared context by this stage |
| `skipped` | `bool` | Whether the stage was skipped (e.g. `should_skip()` returned True) |
| `memory_mb` | `float \| None` | Peak memory delta attributed to this stage (None if not measured) |

**Validation**:
- `stage_name` must be non-empty
- `duration_s` must be >= 0
- `output_keys` must not contain `"errors"` or `"cancelled"` (reserved context keys)

### PipelineReport

Final output of a pipeline run.

| Field | Type | Description |
|-------|------|-------------|
| `stage_results` | `list[StageResult]` | Results for each stage in execution order |
| `total_duration_s` | `float` | Total wall-clock duration of the pipeline |
| `cancelled` | `bool` | `True` if execution was interrupted via cancellation token |
| `peak_memory_mb` | `float \| None` | Peak RSS memory measured during the run (None if not tracked) |

**Validation**:
- `total_duration_s` must be >= sum of all `stage_results[].duration_s` (allows runner overhead)

### ProgressEvent

Event emitted during pipeline execution for user-facing progress.

| Field | Type | Description |
|-------|------|-------------|
| `stage_index` | `int` | 0-based index of current stage |
| `total_stages` | `int` | Total number of stages in pipeline |
| `stage_name` | `str` | Name of the current stage |
| `status` | `Literal["running", "completed", "failed", "skipped", "cancelled"]` | Stage status |
| `message` | `str \| None` | Optional human-readable detail |
| `duration_s` | `float \| None` | Stage duration (set on completed/failed/skipped events) |

## Relationships

```
Pipeline
  ├── stages: list[Stage]
  ├── cancellation_token: asyncio.Event (optional)
  ├── max_memory_mb: int (optional)
  ├── progress_callback: Callable[[ProgressEvent], None] (optional)
  └── run(ctx: PipelineContext) → PipelineReport

Stage (abstract)
  ├── name: str
  ├── critical: bool
  └── cleanup: Callable | None

StageAdapter (concrete Stage)
  └── wraps: existing module (parsing, pii, chunking, retrieval, gateway)

Pipeline.run()
  ├── for each Stage:
  │   ├── emit ProgressEvent("running")
  │   ├── result = await stage.run(ctx)
  │   ├── merge result into ctx
  │   ├── stage.cleanup() if defined
  │   ├── emit ProgressEvent("completed" | "failed")
  │   └── append StageResult to report
  └── return PipelineReport
```

## State Machine

```
Pipeline lifecycle:
  INITIALIZED → RUNNING → [STAGE_RUNNING → STAGE_CLEANUP → ...] → COMPLETED
                                                                    → CANCELLED
                                                                    → FAILED (critical stage error)

Stage lifecycle:
  PENDING → RUNNING → CLEANUP → COMPLETED
                        ↓
                      FAILED (non-critical: pipeline continues;
                              critical: pipeline terminates)
```

## Reserved Context Keys

The pipeline runner reserves these keys in the shared context:
- `errors`: `list[StageResult]` — accumulated non-critical stage errors
- `cancelled`: `bool` — set to `True` when cancellation is requested

Stage adapters MUST NOT write to these keys. The runner merges stage results with `ctx.update(result)` and any attempt to overwrite `errors` or `cancelled` is silently ignored (runner overwrites on each merge).
