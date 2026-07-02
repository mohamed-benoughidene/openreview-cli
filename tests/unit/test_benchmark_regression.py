"""Unit tests for baseline storage and regression comparison (T019)."""

import json
from pathlib import Path

from openreview_cli.benchmark.models import (
    BenchmarkConfig,
    BenchmarkRun,
    DatasetResult,
    MetricValue,
)
from openreview_cli.benchmark.regression import compute_deltas, save_baseline


class TestComputeDeltas:
    def test_no_change(self) -> None:
        mv = MetricValue(value=0.85, n=100, unit="f1")
        result = DatasetResult(
            dataset_name="cuad",
            dataset_version="v1",
            n_examples=100,
            metrics={"extraction_f1": mv},
        )
        run = BenchmarkRun(
            config=BenchmarkConfig(),
            git_commit="abc123",
            results=[result],
        )
        baseline_metrics = {
            "cuad|precheck|default|extraction_f1": {"value": 0.85, "n": 100, "unit": "f1"},
        }
        deltas = compute_deltas(run, baseline_metrics)
        assert deltas["regressions_detected"] is False
        assert deltas["deltas"]["cuad|precheck|default|extraction_f1"] == 0.0

    def test_regression_detected(self) -> None:
        mv = MetricValue(value=0.75, n=100, unit="f1")
        result = DatasetResult(
            dataset_name="cuad",
            dataset_version="v1",
            n_examples=100,
            metrics={"extraction_f1": mv},
        )
        run = BenchmarkRun(
            config=BenchmarkConfig(),
            git_commit="abc123",
            results=[result],
        )
        baseline_metrics = {
            "cuad|precheck|default|extraction_f1": {"value": 0.85, "n": 100, "unit": "f1"},
        }
        deltas = compute_deltas(run, baseline_metrics)
        assert deltas["regressions_detected"] is True
        assert deltas["deltas"]["cuad|precheck|default|extraction_f1"] == -0.1

    def test_improvement_not_regression(self) -> None:
        mv = MetricValue(value=0.90, n=100, unit="f1")
        result = DatasetResult(
            dataset_name="cuad",
            dataset_version="v1",
            n_examples=100,
            metrics={"extraction_f1": mv},
        )
        run = BenchmarkRun(
            config=BenchmarkConfig(),
            git_commit="abc123",
            results=[result],
        )
        baseline_metrics = {
            "cuad|precheck|default|extraction_f1": {"value": 0.85, "n": 100, "unit": "f1"},
        }
        deltas = compute_deltas(run, baseline_metrics)
        assert deltas["regressions_detected"] is False
        assert deltas["deltas"]["cuad|precheck|default|extraction_f1"] == 0.05

    def test_custom_threshold(self) -> None:
        mv = MetricValue(value=0.84, n=100, unit="f1")
        result = DatasetResult(
            dataset_name="cuad",
            dataset_version="v1",
            n_examples=100,
            metrics={"extraction_f1": mv},
        )
        run = BenchmarkRun(
            config=BenchmarkConfig(),
            git_commit="abc123",
            results=[result],
        )
        baseline_metrics = {
            "cuad|precheck|default|extraction_f1": {"value": 0.85, "n": 100, "unit": "f1"},
        }
        # 1pp drop, threshold 2pp — should not trigger
        deltas = compute_deltas(run, baseline_metrics, threshold_pp=2.0)
        assert deltas["regressions_detected"] is False


class TestSaveBaseline:
    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        mv = MetricValue(value=0.85, n=100, unit="f1")
        result = DatasetResult(
            dataset_name="cuad",
            dataset_version="v1",
            n_examples=100,
            metrics={"extraction_f1": mv},
        )
        run = BenchmarkRun(
            config=BenchmarkConfig(),
            git_commit="abc123",
            results=[result],
        )
        db_path = tmp_path / "test.db"
        # Initialize database with benchmark tables
        from openreview_cli.storage.database import get_connection

        conn = get_connection(db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS benchmark_baselines (
                baseline_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                run_id TEXT NOT NULL,
                metrics_json TEXT NOT NULL
            );
        """)
        conn.commit()
        conn.close()

        baseline_id = save_baseline(db_path, run)
        assert baseline_id == "abc123"

        # Verify saved data
        conn = get_connection(db_path)
        row = conn.execute(
            "SELECT metrics_json FROM benchmark_baselines WHERE baseline_id = ?",
            (baseline_id,),
        ).fetchone()
        conn.close()
        assert row is not None
        saved = json.loads(row["metrics_json"])
        assert "cuad|precheck|default|extraction_f1" in saved
        assert saved["cuad|precheck|default|extraction_f1"]["value"] == 0.85
