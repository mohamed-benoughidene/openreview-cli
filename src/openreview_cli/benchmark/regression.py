"""Baseline storage and regression comparison.

Saves/loads baselines from SQLite, computes deltas per
(dataset, mode, slot, metric), flags drops exceeding threshold.
"""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openreview_cli.benchmark.models import BenchmarkRun
from openreview_cli.storage.database import get_connection


def _metrics_key(dataset: str, mode: str, slot: str, metric: str) -> str:
    """Create a canonical string key for a metric tuple."""
    return f"{dataset}|{mode}|{slot}|{metric}"


def save_baseline(db_path: Path, run: BenchmarkRun) -> str:
    """Save a benchmark run as the regression baseline.

    Returns the baseline_id (git commit SHA).
    """
    baseline_id = run.git_commit or run.id

    # Build metrics snapshot
    metrics_snapshot: dict[str, dict[str, Any]] = {}
    for result in run.results:
        mode = run.config.modes[0] if run.config.modes else "precheck"
        slot = run.config.slots[0] if run.config.slots else "default"
        for metric_name, mv in result.metrics.items():
            key = _metrics_key(result.dataset_name, mode, slot, metric_name)
            metrics_snapshot[key] = asdict(mv)

    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO benchmark_baselines (baseline_id, created_at, run_id, metrics_json) "
            "VALUES (?, ?, ?, ?)",
            (
                baseline_id,
                datetime.now(UTC).isoformat(),
                run.id,
                json.dumps(metrics_snapshot),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return baseline_id


def load_baseline(db_path: Path, baseline_id: str | None = None) -> dict[str, Any] | None:
    """Load a baseline from the database.

    If baseline_id is None, loads the most recent baseline.
    Returns None if no baseline found.
    """
    conn = get_connection(db_path)
    try:
        if baseline_id:
            row = conn.execute(
                "SELECT metrics_json, baseline_id FROM benchmark_baselines WHERE baseline_id = ?",
                (baseline_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT metrics_json, baseline_id FROM benchmark_baselines ORDER BY created_at DESC LIMIT 1"
            ).fetchone()

        if row is None:
            return None

        return {
            "baseline_id": row["baseline_id"],
            "metrics": json.loads(row["metrics_json"]),
        }
    finally:
        conn.close()


def compute_deltas(
    current: BenchmarkRun,
    baseline_metrics: dict[str, Any],
    threshold_pp: float = 2.0,
) -> dict[str, Any]:
    """Compute deltas between current run and baseline.

    Returns dict with:
      - baseline_id: str
      - deltas: dict of key -> delta float
      - regressions_detected: bool
      - regression_details: list of regression descriptions
    """
    deltas: dict[str, float] = {}
    regressions_detected = False
    regression_details: list[str] = []

    for result in current.results:
        mode = current.config.modes[0] if current.config.modes else "precheck"
        slot = current.config.slots[0] if current.config.slots else "default"
        for metric_name, mv in result.metrics.items():
            key = _metrics_key(result.dataset_name, mode, slot, metric_name)
            baseline_entry = baseline_metrics.get(key)
            if baseline_entry and isinstance(baseline_entry, dict):
                baseline_value = baseline_entry.get("value", 0.0)
                delta = mv.value - baseline_value
                deltas[key] = round(delta, 4)
                if delta < -(threshold_pp / 100):
                    regressions_detected = True
                    regression_details.append(
                        f"{key}: {mv.value:.4f} vs baseline {baseline_value:.4f} "
                        f"(delta {delta:.4f}) exceeds threshold {threshold_pp}pp"
                    )

    return {
        "baseline_id": baseline_metrics.get("baseline_id", "unknown"),
        "deltas": deltas,
        "regressions_detected": regressions_detected,
        "regression_details": regression_details,
    }
