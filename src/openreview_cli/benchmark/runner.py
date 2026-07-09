"""BenchmarkRunner — orchestrates dataset loading → pipeline → metric computation."""

import asyncio
import contextlib
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from openreview_cli.benchmark.hallu_detect import HallucinationDetector
from openreview_cli.benchmark.memory import MemoryProfiler
from openreview_cli.benchmark.metrics import (
    avg_latency,
    classification_f1,
    comparison_f1,
    extraction_f1,
)
from openreview_cli.benchmark.models import (
    BenchmarkConfig,
    BenchmarkRun,
    DatasetResult,
    MetricDatum,
    MetricValue,
)

# Type alias for a "model pipeline" function that processes text and returns predictions
PipelineFn = Callable[[str, str], dict[str, Any]]


class BenchmarkRunner:
    """Orchestrates benchmark execution across datasets and model slots."""

    def __init__(
        self,
        config: BenchmarkConfig,
        fixtures_root: str | Path | None = None,
        cache_dir: str | Path | None = None,
        detector: HallucinationDetector
        | None = None,  # ponytail: wired for D-7, not yet consumed by runner methods
        pipeline: Any | None = None,  # ponytail: D-23 pipeline delegation
    ) -> None:
        self.config = config
        self.fixtures_root = Path(fixtures_root) if fixtures_root else Path.cwd()
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.detector = detector
        self._pipeline = pipeline
        self.memory_profiler = MemoryProfiler()

    def run_pii(self, detect_fn: Callable[[str], list[dict[str, str]]]) -> DatasetResult:
        """Run PII accuracy evaluation."""
        from openreview_cli.benchmark.datasets.pii_contracts import load_pii_dataset
        from openreview_cli.benchmark.metrics_pii import evaluate_pii_accuracy

        # Collect documents
        documents: list[tuple[str, str, list[dict[str, str]]]] = []
        for datum in load_pii_dataset(self.fixtures_root):
            gt = datum.ground_truth
            if not isinstance(gt, list):
                continue
            # Need text - load from file
            txt_path = self.fixtures_root / "pii" / "seeded_contracts" / datum.example_id
            text = txt_path.read_text(encoding="utf-8") if txt_path.exists() else ""
            documents.append((datum.example_id, text, gt))

        metrics = evaluate_pii_accuracy(documents, detect_fn)

        return DatasetResult(
            dataset_name="pii",
            dataset_version="v1",
            n_examples=len(documents),
            metrics=metrics,
        )

    def run_dataset(  # noqa: PLR0912
        self,
        dataset_name: str,
        pipeline_fn: PipelineFn,
        slot_name: str = "default",
    ) -> DatasetResult:
        """Run a single dataset through a model pipeline."""
        if dataset_name == "pii":
            raise ValueError("Use run_pii() for PII evaluation")

        data_items = list(self._load_dataset(dataset_name))
        metric_data: list[MetricDatum] = []
        latencies: list[int] = []

        for item in data_items:
            text = item.get("document_text", "")
            category = item.get("category", "unknown")

            start = time.monotonic()
            if self._pipeline is not None:
                prediction = self._run_pipeline_for_item(text, category)
            else:
                prediction = pipeline_fn(text, category)
            elapsed = int((time.monotonic() - start) * 1000)
            latencies.append(elapsed)

            metric_data.append(
                MetricDatum(
                    example_id=item.get("example_id", ""),
                    predicted=prediction,
                    ground_truth=item.get("ground_truth_spans", []),
                    is_correct=False,
                    latency_ms=elapsed,
                )
            )

        # Compute metrics
        metrics: dict[str, MetricValue] = {}

        if dataset_name == "cuad":
            predicted_spans = [
                (d.predicted.get("start", 0), d.predicted.get("end", 0))
                if isinstance(d.predicted, dict)
                else (0, 0)
                for d in metric_data
            ]
            gt_spans = [
                list(d.ground_truth) if isinstance(d.ground_truth, list) else []
                for d in metric_data
            ]
            # Sample F1 on first example for simplicity
            # In full implementation, this would aggregate across all
            f1_vals: list[float] = []
            for ps, gs in zip(predicted_spans, gt_spans, strict=False):
                if gs:
                    text = data_items[0].get("document_text", "")
                    ef1 = extraction_f1([ps], gs, text)
                    f1_vals.append(ef1.value)
            if f1_vals:
                metrics["extraction_f1"] = MetricValue(
                    value=sum(f1_vals) / len(f1_vals),
                    n=len(f1_vals),
                    unit="f1",
                )

        elif dataset_name in ("maud",):
            predicted_bools = [
                d.predicted.get("match", False) if isinstance(d.predicted, dict) else False
                for d in metric_data
            ]
            gt_bools = [
                d.ground_truth.get("match", False) if isinstance(d.ground_truth, dict) else False
                for d in metric_data
            ]
            if predicted_bools:
                metrics["comparison_f1"] = comparison_f1(predicted_bools, gt_bools)

        elif dataset_name == "contract_nli":
            predicted_classes = [
                str(d.predicted.get("label", "")) if isinstance(d.predicted, dict) else ""
                for d in metric_data
            ]
            gt_classes = [
                str(d.ground_truth.get("label", "")) if isinstance(d.ground_truth, dict) else ""
                for d in metric_data
            ]
            if predicted_classes:
                metrics["classification_f1"] = classification_f1(predicted_classes, gt_classes)

        if latencies:
            metrics["avg_latency_ms"] = avg_latency(latencies)

        return DatasetResult(
            dataset_name=dataset_name,
            dataset_version="v1",
            n_examples=len(data_items),
            metrics=metrics,
        )

    def _run_pipeline_for_item(self, text: str, category: str) -> dict[str, Any]:
        """Delegate per-item processing to the configured pipeline."""
        from openreview_cli.pipeline.runner import (
            Pipeline,  # noqa: TC001 — local import avoids circular dep
        )

        pipeline: Pipeline = self._pipeline  # type: ignore[assignment]
        ctx: dict[str, Any] = {"text": text, "category": category}
        with contextlib.suppress(Exception):
            asyncio.run(pipeline.run(ctx))
        return cast("dict[str, Any]", ctx.get("prediction", {}))

    def _load_dataset(self, name: str) -> list[dict[str, Any]]:
        """Load dataset items by name."""
        from openreview_cli.benchmark.datasets.contract_nli import load_contract_nli_dataset
        from openreview_cli.benchmark.datasets.cuad import load_cuad_dataset
        from openreview_cli.benchmark.datasets.maud import load_maud_dataset

        loaders: dict[str, Callable[..., list[dict[str, Any]]]] = {
            "cuad": lambda: list(load_cuad_dataset(cache_dir=self.cache_dir)),
            "maud": lambda: list(load_maud_dataset(cache_dir=self.cache_dir)),
            "contract_nli": lambda: list(load_contract_nli_dataset(cache_dir=self.cache_dir)),
        }
        loader = loaders.get(name)
        if loader is None:
            raise ValueError(f"Unknown dataset: {name}")
        return loader()

    def run_all(
        self,
        pipeline_fn: PipelineFn,
        pii_detect_fn: Callable[[str], list[dict[str, str]]] | None = None,
    ) -> BenchmarkRun:
        """Run all configured datasets and slots."""
        results: list[DatasetResult] = []

        for dataset in self.config.datasets:
            if dataset == "pii":
                if pii_detect_fn:
                    results.append(self.run_pii(pii_detect_fn))
            else:
                for slot in self.config.slots:
                    result = self.run_dataset(dataset, pipeline_fn, slot_name=slot)
                    results.append(result)

        return BenchmarkRun(
            config=self.config,
            results=results,
        )
