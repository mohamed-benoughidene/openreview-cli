"""CLI subcommand for `openreview benchmark`.

Wires dataset selection, model slots, output format, regression
comparison, and experimental flags to the BenchmarkRunner.
"""

import importlib.resources
import subprocess
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from openreview_cli.benchmark.models import BenchmarkConfig, DatasetResult
from openreview_cli.benchmark.report import print_terminal_report
from openreview_cli.benchmark.runner import BenchmarkRunner
from openreview_cli.config.paths import get_data_dir

# Resolve tests/fixtures relative to the package root
_FIXTURES_DIR = (
    Path(str(importlib.resources.files("openreview_cli"))).resolve().parent.parent
    / "tests"
    / "fixtures"
)

benchmark_app = typer.Typer(
    name="benchmark",
    help="Run benchmarks against research baselines (CUAD, MAUD, ContractNLI, PII).",
    no_args_is_help=True,
)

VALID_DATASETS = frozenset({"cuad", "maud", "contract_nli", "pii"})
VALID_FORMATS = frozenset({"terminal", "json"})

console = Console()


def _detect_git_commit() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.STDOUT
            )
            .decode()
            .strip()
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def _detect_git_branch() -> str | None:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.STDOUT
            )
            .decode()
            .strip()
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


@benchmark_app.command("run")
def benchmark_run(
    datasets: str = typer.Option(
        "cuad",
        "--datasets",
        help="Comma-separated list of datasets: cuad,maud,contract_nli,pii",
    ),
    slots: str = typer.Option(
        "default",
        "--slots",
        help="Comma-separated model slot names",
    ),
    modes: str = typer.Option(
        "precheck",
        "--modes",
        help="Comma-separated product modes",
    ),
    prompt_variant: list[str] | None = typer.Option(
        None,
        "--prompt-variant",
        help="Prompt variant names for A/B testing (repeatable)",
    ),
    all_datasets: bool = typer.Option(
        False,
        "--all",
        help="Run all datasets, slots, and modes",
    ),
    ci: bool = typer.Option(
        False,
        "--ci",
        help="CI mode — strict exit codes, compare to baseline",
    ),
    compare: str | None = typer.Option(
        None,
        "--compare",
        help="Baseline ref to compare against (commit SHA, tag, or 'last')",
    ),
    save_baseline: bool = typer.Option(
        False,
        "--save-baseline",
        help="Save this run as the regression baseline",
    ),
    download_datasets: bool = typer.Option(
        False,
        "--download-datasets",
        help="Download/refresh dataset corpora",
    ),
    memory_watch: bool = typer.Option(
        False,
        "--memory-watch",
        help="Enable per-item memory profiling",
    ),
    multi_party: bool = typer.Option(
        False,
        "--multi-party",
        help="Enable experimental multi-party evaluation",
    ),
    format: str = typer.Option(
        "terminal",
        "--format",
        help=f"Output format: {', '.join(sorted(VALID_FORMATS))}",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        help="Write JSON report to file path",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Detailed per-item progress",
    ),
) -> None:
    """Run benchmarks against research baselines.

    Evaluates extraction, comparison, classification, and PII accuracy
    metrics across configured datasets and model slots.
    """
    if format not in VALID_FORMATS:
        typer.echo(
            f"Error: Invalid format '{format}'. Valid: {', '.join(sorted(VALID_FORMATS))}", err=True
        )
        raise typer.Exit(code=78)

    # Resolve datasets
    if all_datasets:
        dataset_list = sorted(VALID_DATASETS)
    else:
        dataset_list = [d.strip() for d in datasets.split(",") if d.strip()]
        for d in dataset_list:
            if d not in VALID_DATASETS:
                typer.echo(
                    f"Error: Unknown dataset '{d}'. Valid: {', '.join(sorted(VALID_DATASETS))}",
                    err=True,
                )
                raise typer.Exit(code=78)

    slot_list = [s.strip() for s in slots.split(",") if s.strip()]
    mode_list = [m.strip() for m in modes.split(",") if m.strip()]

    # Check experimental multi-party flag
    if multi_party:
        typer.echo(
            "Warning: --multi-party is EXPERIMENTAL. Results are informational only.",
            err=True,
        )

    config = BenchmarkConfig(
        datasets=dataset_list,
        slots=slot_list,
        modes=mode_list,
        prompts={},
        ci_mode=ci,
        multi_party=multi_party,
    )

    fixtures_root = _FIXTURES_DIR
    data_dir = get_data_dir()
    cache_dir = data_dir / "datasets"

    if download_datasets:
        cache_dir.mkdir(parents=True, exist_ok=True)

    runner = BenchmarkRunner(
        config=config,
        fixtures_root=fixtures_root,
        cache_dir=cache_dir if download_datasets else None,
    )

    git_commit = _detect_git_commit()
    git_branch = _detect_git_branch()

    # Build the run
    from openreview_cli.benchmark.models import BenchmarkRun

    run = BenchmarkRun(
        config=config,
        git_commit=git_commit,
        git_branch=git_branch,
    )

    # If PII is in the dataset list, run PII evaluation
    if "pii" in dataset_list:
        pii_result = _run_pii_evaluation(runner, verbose)
        run.results.append(pii_result)

    # For other datasets, use a mock pipeline (real LLM integration deferred)
    for dataset in dataset_list:
        if dataset == "pii":
            continue
        if verbose:
            typer.echo(f"Running dataset: {dataset}")
        try:
            result = runner.run_dataset(dataset, _mock_pipeline)
            run.results.append(result)
        except Exception as e:
            typer.echo(f"Error running dataset {dataset}: {e}", err=True)
            if ci:
                raise typer.Exit(code=78) from None

    # ponytail: prompt A/B test removed — no real templates exist yet. Returns when real A/B lands.

    # Regression comparison
    regression_data: dict[str, Any] | None = None
    if ci or compare:
        from openreview_cli.benchmark.regression import (
            compute_deltas,
        )
        from openreview_cli.benchmark.regression import (
            load_baseline as _load_baseline,
        )
        from openreview_cli.benchmark.regression import (
            save_baseline as _save_baseline,
        )

        db_path = data_dir / "openreview.db"
        baseline_ref = compare if compare else None
        baseline = _load_baseline(db_path, baseline_ref)
        if baseline:
            regression_data = compute_deltas(run, baseline["metrics"])
            if regression_data.get("regressions_detected", False):
                details_val: list[str] = list(regression_data.get("regression_details", []) or [])
                for detail in details_val:
                    typer.echo(f"Regression: {detail}", err=True)
                if ci:
                    typer.echo(
                        f"CI mode: {len(details_val)} "
                        f"regression(s) detected. Exiting with code 75.",
                        err=True,
                    )
                    raise typer.Exit(code=75)
        elif compare:
            typer.echo(f"Warning: Baseline '{compare}' not found. Skipping comparison.", err=True)

        if save_baseline:
            saved_id_2 = _save_baseline(db_path, run)
            typer.echo(f"Baseline saved: {saved_id_2}")

    # Generate output
    if format == "json":
        from openreview_cli.benchmark.report import generate_json_report

        json_str = generate_json_report(run, regression=regression_data)
        if output:
            Path(output).write_text(json_str)
            typer.echo(f"Report written to {output}")
        else:
            typer.echo(json_str)
    else:
        print_terminal_report(run, regression=regression_data, verbose=verbose)


def _run_pii_evaluation(runner: BenchmarkRunner, verbose: bool = False) -> "DatasetResult":
    """Run PII evaluation using the PII engine."""
    from openreview_cli.pii.engine import PiiEngine

    engine = PiiEngine(threshold=0.7)

    def detect_pii(text: str) -> list[dict[str, str]]:
        results = []
        entities = engine.detect_on_page(text)
        for ent in entities:
            results.append(
                {
                    "value": ent.text if hasattr(ent, "text") else str(ent),
                    "type": ent.label if hasattr(ent, "label") else "UNKNOWN",
                }
            )
        return results

    if verbose:
        typer.echo("Running PII benchmark...")

    result = runner.run_pii(detect_pii)
    return result


def _mock_pipeline(text: str, category: str) -> dict[str, object]:
    """Mock model pipeline for testing.

    Returns a placeholder prediction. In production, this would
    route through the gateway to the configured model slot.
    """
    # ponytail: mock — returns empty spans. Replace with real gateway call.
    return {"start": 0, "end": 0, "category": category, "label": "entailment", "match": True}
