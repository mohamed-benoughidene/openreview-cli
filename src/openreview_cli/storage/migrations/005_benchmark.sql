-- Migration 005: Benchmark harness tables
-- Schema per data-model.md §Persistence

CREATE TABLE IF NOT EXISTS benchmark_runs (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    git_commit TEXT NOT NULL,
    git_branch TEXT,
    config_json TEXT NOT NULL,
    metadata_json TEXT,
    status TEXT NOT NULL DEFAULT 'COMPLETE',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS benchmark_results (
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

CREATE TABLE IF NOT EXISTS benchmark_baselines (
    baseline_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES benchmark_runs(id),
    metrics_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_benchmark_results_run_id ON benchmark_results(run_id);
CREATE INDEX IF NOT EXISTS idx_benchmark_baselines_created_at ON benchmark_baselines(created_at);

PRAGMA user_version = 5;
