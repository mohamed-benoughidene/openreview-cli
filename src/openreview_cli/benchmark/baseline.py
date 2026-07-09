"""Baseline accuracy runner — mock (CI) and real (one-shot) modes."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from openreview_cli.benchmark._utils import _FIXTURES_DIR, _detect_git_branch, _detect_git_commit
from openreview_cli.benchmark.models import BenchmarkConfig
from openreview_cli.benchmark.runner import BenchmarkRunner


@dataclass
class BaselineResult:
    mode: str
    dataset: str
    extraction_f1: float | None = None
    comparison_f1: float | None = None
    classification_f1: float | None = None
    hallucination_rate: float | None = None
    pii_recall: float | None = None
    latency_ms: float | None = None
    peak_memory_mb: float | None = None


@dataclass
class BaselineReport:
    mode_results: list[BaselineResult]
    git_commit: str
    git_branch: str | None
    provider: str
    model: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _mock_pipeline(text: str, category: str) -> dict[str, object]:
    return {"start": 0, "end": 0, "category": category, "label": "entailment", "match": True}


def _build_baseline_result(
    mode: str,
    dataset: str,
    dataset_result: Any | None,
) -> BaselineResult:
    if dataset_result is None:
        return BaselineResult(mode=mode, dataset=f"{dataset}::{mode}")
    metrics = dataset_result.metrics if hasattr(dataset_result, "metrics") else {}
    return BaselineResult(
        mode=mode,
        dataset=f"{dataset}::{mode}",
        extraction_f1=getattr(metrics.get("extraction_f1"), "value", None),
        comparison_f1=getattr(metrics.get("comparison_f1"), "value", None),
        classification_f1=getattr(metrics.get("classification_f1"), "value", None),
        latency_ms=getattr(metrics.get("avg_latency_ms"), "value", None),
        peak_memory_mb=getattr(metrics.get("peak_memory_mb"), "value", None),
    )


def run_mock_baseline(modes: list[str], datasets: list[str] | None = None) -> list[BaselineResult]:
    if datasets is None:
        datasets = ["cuad", "maud", "contract_nli"]
    results: list[BaselineResult] = []
    config = BenchmarkConfig(datasets=datasets, modes=modes)
    runner = BenchmarkRunner(config=config, fixtures_root=_FIXTURES_DIR)
    for dataset in datasets:
        if dataset == "pii":
            continue
        for mode in modes:
            try:
                dr = runner.run_dataset(dataset, _mock_pipeline)
                dr.dataset_name = f"{dataset}::{mode}"
                results.append(_build_baseline_result(mode, dataset, dr))
            except Exception:
                results.append(BaselineResult(mode=mode, dataset=f"{dataset}::{mode}"))
    return results


def build_gateway_pipeline(mode: str) -> Any:
    def pipeline(text: str, category: str) -> dict[str, object]:
        from openreview_cli.gateway.router import Gateway

        gateway = Gateway()
        prompt = (
            f"Analyze this contract clause for {mode} review. Category: {category}. Text: {text}"
        )
        response = gateway.chat("default", [{"role": "user", "content": prompt}])
        try:
            result = json.loads(response)
        except (json.JSONDecodeError, TypeError) as err:
            raise ValueError(
                "Real baseline requires structured JSON output from provider. "
                "Got non-JSON response."
            ) from err
        return {
            "start": result.get("start", 0),
            "end": result.get("end", 0),
            "category": category,
            "label": result.get("label", "entailment"),
            "match": result.get("match", True),
        }

    return pipeline


def run_real_baseline(
    modes: list[str],
    datasets: list[str] | None = None,
) -> BaselineReport:
    if datasets is None:
        datasets = ["cuad", "maud", "contract_nli"]
    config = BenchmarkConfig(datasets=datasets, modes=modes)
    runner = BenchmarkRunner(config=config, fixtures_root=_FIXTURES_DIR)
    mode_results: list[BaselineResult] = []
    for dataset in datasets:
        if dataset == "pii":
            continue
        for mode in modes:
            pipeline = build_gateway_pipeline(mode)
            try:
                dr = runner.run_dataset(dataset, pipeline)
                dr.dataset_name = f"{dataset}::{mode}"
                mode_results.append(_build_baseline_result(mode, dataset, dr))
            except Exception:
                mode_results.append(BaselineResult(mode=mode, dataset=f"{dataset}::{mode}"))
    return BaselineReport(
        mode_results=mode_results,
        git_commit=_detect_git_commit(),
        git_branch=_detect_git_branch(),
        provider="live",
        model="default",
        timestamp=datetime.now(UTC).isoformat(),
    )
