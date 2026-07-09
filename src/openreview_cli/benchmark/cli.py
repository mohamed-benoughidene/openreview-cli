"""CLI subcommand for `openreview benchmark`.

Wires dataset selection, model slots, output format, regression
comparison, and experimental flags to the BenchmarkRunner.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from openreview_cli.benchmark._utils import _FIXTURES_DIR, _detect_git_branch, _detect_git_commit
from openreview_cli.benchmark.baseline import _mock_pipeline
from openreview_cli.benchmark.hallu_detect import (
    CGDPODetector,
    HallucinationDetector,
    LexicalOverlapDetector,
)
from openreview_cli.benchmark.models import BenchmarkConfig, DatasetResult
from openreview_cli.benchmark.report import print_terminal_report
from openreview_cli.benchmark.runner import BenchmarkRunner
from openreview_cli.config.paths import get_data_dir

benchmark_app = typer.Typer(
    name="benchmark",
    help="Run benchmarks against research baselines (CUAD, MAUD, ContractNLI, PII).",
    no_args_is_help=True,
)

VALID_DATASETS = frozenset({"cuad", "maud", "contract_nli", "pii"})
VALID_FORMATS = frozenset({"terminal", "json"})
VALID_HALLUCINATION_METHODS = frozenset({"lexical", "cg-dpo"})
# ponytail: hard-coded mode list — source of truth for benchmark mode validation.
VALID_MODES: frozenset[str] = frozenset(
    {
        "precheck",
        "hirecheck",
        "dealcheck",
        "assetcheck",
        "buycheck",
        "engagecheck",
        "guaranteecheck",
        "loancheck",
        "licensecheck",
        "leasecheck",
        "privacycheck",
        "indemnitycheck",
        "consultcheck",
        "workcheck",
        "loicheck",
        "subcheck",
        "settlementcheck",
        "franchisecheck",
        "opcheck",
        "partnercheck",
        "sponsorcheck",
        "distrocheck",
    }
)

console = Console()


def _validate_modes(mode_list: list[str]) -> None:
    for m in mode_list:
        if m not in VALID_MODES:
            typer.echo(
                f"Error: Unknown mode '{m}'. Valid: {', '.join(sorted(VALID_MODES))}",
                err=True,
            )
            raise typer.Exit(code=78)


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
    hallucination_method: str = typer.Option(
        "lexical",
        "--hallucination-method",
        help=f"Hallucination detector: {', '.join(sorted(VALID_HALLUCINATION_METHODS))}",
    ),
    use_pipeline: bool = typer.Option(
        False,
        "--use-pipeline",
        help="Delegate per-item processing to the Pipeline framework",
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

    if hallucination_method not in VALID_HALLUCINATION_METHODS:
        typer.echo(
            f"Error: Invalid hallucination method '{hallucination_method}'. "
            f"Valid: {', '.join(sorted(VALID_HALLUCINATION_METHODS))}",
            err=True,
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
    _validate_modes(mode_list)

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

    detector: HallucinationDetector = (
        LexicalOverlapDetector() if hallucination_method == "lexical" else CGDPODetector()
    )

    if use_pipeline:
        from openreview_cli.pipeline.adapters.benchmark import BenchmarkStage
        from openreview_cli.pipeline.runner import Pipeline

        pipeline = Pipeline([BenchmarkStage()])
    else:
        pipeline = None

    runner = BenchmarkRunner(
        config=config,
        fixtures_root=fixtures_root,
        cache_dir=cache_dir if download_datasets else None,
        detector=detector,
        pipeline=pipeline,
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
        for mode in mode_list:
            tagged_name = f"{dataset}::{mode}"
            if verbose:
                typer.echo(f"Running dataset: {tagged_name}")
            try:
                result = runner.run_dataset(dataset, _mock_pipeline)
                result.dataset_name = tagged_name
                run.results.append(result)
            except Exception as e:
                typer.echo(f"Error running dataset {tagged_name}: {e}", err=True)
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


@benchmark_app.command("baseline")
def benchmark_baseline(
    modes: str = typer.Option(
        ",".join(sorted(VALID_MODES)),
        "--modes",
        help="Comma-separated product modes",
    ),
    datasets: str = typer.Option(
        "cuad,maud,contract_nli",
        "--datasets",
        help="Comma-separated datasets",
    ),
    provider: str = typer.Option(
        "mock",
        "--provider",
        help="Provider: mock (CI) or live (real model)",
    ),
    format: str = typer.Option(
        "terminal",
        "--format",
        help=f"Output format: {', '.join(sorted(VALID_FORMATS))}",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        help="Write output to file path",
    ),
    save_baseline: bool = typer.Option(
        False,
        "--save-baseline",
        help="Save as official baseline (requires --format json and --output)",
    ),
) -> None:
    """Run accuracy baseline — mock (CI) or real provider.

    Produces precision/recall/F1 numbers across modes and datasets.
    Mock mode returns constant predictions for deterministic CI results.
    Real mode calls the configured AI provider.
    """
    from openreview_cli.benchmark.baseline import (
        BaselineReport,
        run_mock_baseline,
        run_real_baseline,
    )

    mode_list = [m.strip() for m in modes.split(",") if m.strip()]
    dataset_list = [d.strip() for d in datasets.split(",") if d.strip()]

    for d in dataset_list:
        if d not in VALID_DATASETS:
            typer.echo(
                f"Error: Unknown dataset '{d}'. Valid: {', '.join(sorted(VALID_DATASETS))}",
                err=True,
            )
            raise typer.Exit(code=78)

    _validate_modes(mode_list)

    if save_baseline and format != "json":
        typer.echo(
            "Error: --save-baseline requires --format json. "
            "Use --format json to enable JSON output.",
            err=True,
        )
        raise typer.Exit(code=78)

    if output and format != "json":
        typer.echo(
            "Error: --output requires --format json. Use --format json to enable file output.",
            err=True,
        )
        raise typer.Exit(code=78)

    git_commit = _detect_git_commit()
    git_branch = _detect_git_branch()

    if provider == "mock":
        raw_results = run_mock_baseline(mode_list, dataset_list)
        report = BaselineReport(
            mode_results=raw_results,
            git_commit=git_commit,
            git_branch=git_branch,
            provider="mock",
            model="mock",
            timestamp=datetime.now(UTC).isoformat(),
        )
    elif provider == "live":
        report = run_real_baseline(mode_list, dataset_list)
    else:
        typer.echo(
            f"Error: Unknown provider '{provider}'. Use 'mock' or 'live'.",
            err=True,
        )
        raise typer.Exit(code=78)

    if format == "json":
        from dataclasses import asdict

        report_dict = asdict(report)
        json_str = json.dumps(report_dict, indent=2, default=str)
        if output:
            Path(output).write_text(json_str)
            typer.echo(f"Baseline written to {output}")
        else:
            typer.echo(json_str)
    else:
        typer.echo(
            f"Baseline report: {len(report.mode_results)} results across {len(mode_list)} modes"
        )
        for mr in report.mode_results:
            typer.echo(
                f"  {mr.dataset}: "
                f"extract_f1={mr.extraction_f1 or 'N/A'}, "
                f"compare_f1={mr.comparison_f1 or 'N/A'}, "
                f"class_f1={mr.classification_f1 or 'N/A'}, "
                f"latency={mr.latency_ms or 'N/A'}ms"
            )
