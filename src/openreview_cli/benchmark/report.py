"""Report generator for benchmark results.

Produces JSON output matching cli-contract.md §JSON Report Schema
and Rich terminal tables with color-coded PASS/WARNING/FAIL per metric.
"""

import json
from typing import Any

from openreview_cli.benchmark.models import BenchmarkRun

REGRESSION_THRESHOLD_PP = 2.0  # percentage points F1 drop


def generate_json_report(run: BenchmarkRun, regression: dict[str, Any] | None = None) -> str:
    """Generate JSON report string from a BenchmarkRun."""
    from dataclasses import asdict

    report: dict[str, Any] = {
        "$schema": "openreview-cli/benchmark-report-v1",
        "run_id": run.id,
        "timestamp": run.timestamp,
        "git_commit": run.git_commit,
        "git_branch": run.git_branch,
        "config": asdict(run.config),
        "results": [asdict(r) for r in run.results],
        "model_slots": [asdict(s) for s in run.model_slots],
    }
    if regression:
        report["regression"] = regression
    return json.dumps(report, indent=2, default=str)


def print_terminal_report(
    run: BenchmarkRun,
    regression: dict[str, Any] | None = None,
    verbose: bool = False,
) -> None:
    """Print a human-readable Rich table report."""
    from rich.console import Console
    from rich.table import Table

    console = Console()

    # Summary header
    console.print(f"\n[bold]Benchmark Run:[/bold] {run.id[:8]}")
    console.print(f"  Git commit: {run.git_commit or 'unknown'}")
    console.print(f"  Timestamp:  {run.timestamp}")
    console.print()

    for result in run.results:
        table = Table(title=f"Dataset: {result.dataset_name}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        table.add_column("N", style="dim")
        table.add_column("Unit", style="yellow")

        for metric_name, mv in sorted(result.metrics.items()):
            color = _metric_color(metric_name, mv.value)
            value_str = f"{mv.value:.4f}" if isinstance(mv.value, float) else str(mv.value)
            table.add_row(metric_name, f"[{color}]{value_str}[/{color}]", str(mv.n), mv.unit)

        console.print(table)
        console.print()

    if regression:
        _print_regression_table(console, regression)

    if verbose:
        _print_config_summary(console, run)


def _metric_color(metric_name: str, value: float) -> str:
    """Return Rich color based on metric threshold."""
    if "recall" in metric_name:
        if value >= 0.95:
            return "green"
        elif value >= 0.85:
            return "yellow"
        return "red"
    if "f1" in metric_name or "precision" in metric_name:
        if value >= 0.80:
            return "green"
        elif value >= 0.70:
            return "yellow"
        return "red"
    if "rate" in metric_name:
        if value <= 0.05:
            return "green"
        elif value <= 0.10:
            return "yellow"
        return "red"
    return "white"


def _print_regression_table(console: Any, regression: dict[str, Any]) -> None:
    """Print regression comparison table."""
    from rich.table import Table

    table = Table(title="Regression Comparison")
    table.add_column("Metric Key", style="cyan")
    table.add_column("Delta", style="white")
    table.add_column("Status", style="yellow")

    deltas = regression.get("deltas", {})
    for key, delta in sorted(deltas.items()):
        if isinstance(delta, (int, float)):
            color = "red" if delta < -REGRESSION_THRESHOLD_PP / 100 else "green"
            status = "REGRESSION" if delta < -REGRESSION_THRESHOLD_PP / 100 else "OK"
            delta_str = f"{delta:+.4f}"
        else:
            color = "white"
            status = str(delta)
            delta_str = str(delta)
        table.add_row(key, f"[{color}]{delta_str}[/{color}]", status)

    console.print(table)
    console.print()


def _print_config_summary(console: Any, run: BenchmarkRun) -> None:
    """Print configuration details."""
    console.print("[bold]Configuration:[/bold]")
    console.print(f"  Datasets: {', '.join(run.config.datasets)}")
    console.print(f"  Slots:    {', '.join(run.config.slots)}")
    console.print(f"  Modes:    {', '.join(run.config.modes)}")
    console.print(f"  CI mode:  {run.config.ci_mode}")
    console.print()
