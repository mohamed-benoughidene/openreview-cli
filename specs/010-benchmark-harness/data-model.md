# Data Model — Benchmark Harness (Phase 1)

## Entities

### BenchmarkRun

A single execution of one or more benchmark suites against one or more model slots.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` (UUID) | Yes | Unique run identifier |
| `timestamp` | `str` (ISO-8601) | Yes | When the run started |
| `git_commit` | `str` (SHA) | Yes | Code version under test |
| `git_branch` | `str` | No | Branch name (for CI runs) |
| `config` | `BenchmarkConfig` | Yes | Full configuration snapshot |
| `results` | `list[DatasetResult]` | Yes | Per-dataset results |
| `model_slots` | `list[ModelSlotResult]` | Yes | Per-slot breakdown |
| `metadata` | `dict[str, Any]` | No | Custom metadata (CI run URL, etc.) |

### BenchmarkConfig

Configuration for a single benchmark run.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `datasets` | `list[str]` | Yes | Dataset names to evaluate (e.g., `["cuad", "maud", "contract_nli"]`) |
| `slots` | `list[str]` | Yes | Model slot names (from gateway registry) |
| `modes` | `list[str]` | Yes | Product modes to evaluate (e.g., `["precheck", "dealcheck"]`) |
| `prompts` | `dict[str, str]` | No | Prompt variant name → template body (for A/B testing) |
| `multi_party` | `bool` | No | Enable experimental multi-party mode (default: false) |
| `ci_mode` | `bool` | No | CI mode — regression comparison required (default: false) |
| `baseline_ref` | `str` | No | Baseline commit SHA or tag for comparison (default: last run) |

### DatasetResult

Aggregated metrics for one dataset in one run.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `dataset_name` | `str` | Yes | One of `cuad`, `maud`, `contract_nli` |
| `dataset_version` | `str` | Yes | Version string from corpus metadata |
| `n_examples` | `int` | Yes | Total items evaluated |
| `metrics` | `dict[str, MetricValue]` | Yes | Key: metric name (e.g., `"extraction_f1"`, `"hallucination_rate"`) |
| `per_task_breakdown` | `dict[str, dict]` | No | Per-question or per-category breakdown |
| `mode_breakdown` | `dict[str, dict[str, MetricValue]]` | No | Per-mode metrics if run across modes |

### MetricValue

A single measured value with statistical context.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `value` | `float` | Yes | The measured value |
| `ci_lower` | `float` | No | 95% confidence interval lower bound |
| `ci_upper` | `float` | No | 95% confidence interval upper bound |
| `n` | `int` | Yes | Sample size |
| `unit` | `str` | Yes | One of: `"f1"`, `"precision"`, `"recall"`, `"rate"`, `"ms"`, `"MB"`, `"score"` |

**Valid units**: `f1`, `precision`, `recall`, `rate`, `ms`, `MB`, `score`

### ModelSlotResult

Metrics for a single model slot in one run.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `slot_name` | `str` | Yes | Slot name from gateway config |
| `provider` | `str` | Yes | Provider name (e.g., `"ollama"`, `"openai"`) |
| `model` | `str` | Yes | Model name (e.g., `"llama3.2:3b"`, `"gpt-4o-mini"`) |
| `metrics` | `dict[str, MetricValue]` | Yes | Per-dataset aggregated metrics for this slot |
| `total_latency_ms` | `int` | Yes | Cumulative wall-clock time |
| `peak_memory_mb` | `float` | Yes | Peak memory from tracemalloc (NLP-exempt areas only) |

### RegressionBaseline

Stored reference for regression comparison.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `baseline_id` | `str` | Yes | Git commit SHA or tag |
| `metrics` | `dict[tuple[str, str, str, str], MetricValue]` | Yes | Key: (dataset, mode, slot, metric_name) → MetricValue |
| `created_at` | `str` (ISO-8601) | Yes | When this baseline was recorded |

### PromptVariant

A named prompt template variant for A/B testing.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Human-readable variant name (e.g., `"v2-shorter"`) |
| `template` | `str` | Yes | The prompt template string |
| `dataset_results` | `dict[str, DatasetResult]` | Yes | Results per dataset for this variant |

### MetricDatum (internal representation)

Represents a single data point contributing to a MetricValue aggregation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `example_id` | `str` | Yes | Identifier for the source example |
| `predicted` | `Any` | Yes | Model output |
| `ground_truth` | `Any` | Yes | Expected output |
| `is_correct` | `bool` | Yes | Whether prediction matches ground truth (for accuracy metrics) |
| `latency_ms` | `int` | No | Per-example latency |
| `memory_mb` | `float` | No | Per-example peak memory |

## Relationships

```
BenchmarkRun
 ├── config: BenchmarkConfig
 ├── results: list<DatasetResult>
 │    └── metrics: dict<str, MetricValue>
 ├── model_slots: list<ModelSlotResult>
 │    └── metrics: dict<str, MetricValue>
 └── metadata: dict

BenchmarkConfig
 ├── datasets: list<str>          → Dataset names
 ├── slots: list<str>             → Gateway slot names
 ├── modes: list<str>             → Product mode names
 ├── prompts: dict<str, str>      → Prompt variant name → template
 └── baseline_ref: str            → Regression baseline SHA

RegressionBaseline
 └── metrics: dict<(dataset,mode,slot,metric), MetricValue>
```

## Validation Rules

1. `MetricValue.value` MUST be in valid range for the unit:
   - `f1`, `precision`, `recall`: 0.0–1.0
   - `rate`: 0.0–1.0 (hallucination rate)
   - `ms`: ≥0
   - `MB`: ≥0
2. `MetricValue.n` MUST be > 0
3. `BenchmarkRun.config.datasets` MUST be non-empty
4. `BenchmarkRun.config.slots` MUST be non-empty
5. `DatasetResult.dataset_name` MUST be one of known values (`cuad`, `maud`, `contract_nli`)
6. `RegressionBaseline.baseline_id` MUST be a valid git commit SHA

## State Transitions

No complex state machine — benchmark runs are **write-once, immutable**:

1. `CONFIGURING` → harness resolves datasets, slots, prompts
2. `RUNNING` → evaluation in progress (streaming per-item results)
3. `COMPLETE` → all items evaluated, metrics aggregated
4. `FAILED` → any unrecoverable error during evaluation

Run results are persisted to SQLite on completion.

## Persistence

Tables in existing `storage/` module:

```sql
CREATE TABLE benchmark_runs (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    git_commit TEXT NOT NULL,
    git_branch TEXT,
    config_json TEXT NOT NULL,       -- JSON-serialized BenchmarkConfig
    metadata_json TEXT,              -- Optional metadata
    status TEXT NOT NULL DEFAULT 'COMPLETE',
    created_at TEXT NOT NULL
);

CREATE TABLE benchmark_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES benchmark_runs(id),
    dataset_name TEXT NOT NULL,
    slot_name TEXT NOT NULL,
    mode TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    ci_lower REAL,
    ci_upper REAL,
    n INTEGER NOT NULL,
    unit TEXT NOT NULL
);

CREATE TABLE benchmark_baselines (
    baseline_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES benchmark_runs(id),
    metrics_json TEXT NOT NULL       -- Full metrics snapshot
);
```
