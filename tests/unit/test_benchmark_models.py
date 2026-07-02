"""Unit tests for benchmark data models (T004)."""

from dataclasses import asdict

import pytest

from openreview_cli.benchmark.models import (
    BenchmarkConfig,
    BenchmarkRun,
    DatasetResult,
    MetricDatum,
    MetricValue,
    ModelSlotResult,
    RegressionBaseline,
)


class TestMetricValue:
    def test_valid_f1(self) -> None:
        mv = MetricValue(value=0.85, n=100, unit="f1")
        assert mv.value == 0.85
        assert mv.n == 100
        assert mv.unit == "f1"

    def test_valid_precision(self) -> None:
        mv = MetricValue(value=0.9, n=50, unit="precision")
        assert mv.value == 0.9

    def test_valid_recall(self) -> None:
        mv = MetricValue(value=0.95, n=50, unit="recall")
        assert mv.value == 0.95

    def test_valid_rate(self) -> None:
        mv = MetricValue(value=0.03, n=200, unit="rate")
        assert mv.value == 0.03

    def test_valid_ms(self) -> None:
        mv = MetricValue(value=1250.0, n=100, unit="ms")
        assert mv.value == 1250.0

    def test_valid_mb(self) -> None:
        mv = MetricValue(value=12.5, n=100, unit="MB")
        assert mv.value == 12.5

    def test_invalid_unit(self) -> None:
        with pytest.raises(ValueError, match="Invalid unit"):
            MetricValue(value=0.5, n=10, unit="invalid")

    def test_n_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="n must be > 0"):
            MetricValue(value=0.5, n=0, unit="f1")

    def test_f1_range(self) -> None:
        with pytest.raises(ValueError, match="f1 value must be in"):
            MetricValue(value=1.5, n=10, unit="f1")

    def test_ms_non_negative(self) -> None:
        with pytest.raises(ValueError, match="ms value must be >= 0"):
            MetricValue(value=-1.0, n=10, unit="ms")

    def test_asdict(self) -> None:
        mv = MetricValue(value=0.85, n=100, unit="f1", ci_lower=0.80, ci_upper=0.90)
        d = asdict(mv)
        assert d["value"] == 0.85
        assert d["n"] == 100
        assert d["unit"] == "f1"
        assert d["ci_lower"] == 0.80
        assert d["ci_upper"] == 0.90

    def test_asdict_no_ci(self) -> None:
        mv = MetricValue(value=0.85, n=100, unit="f1")
        d = asdict(mv)
        assert d["ci_lower"] is None
        assert d["ci_upper"] is None


class TestMetricDatum:
    def test_creates_with_required(self) -> None:
        md = MetricDatum(
            example_id="ex1",
            predicted="A",
            ground_truth="A",
            is_correct=True,
        )
        assert md.example_id == "ex1"
        assert md.is_correct is True

    def test_creates_with_all_fields(self) -> None:
        md = MetricDatum(
            example_id="ex1",
            predicted="A",
            ground_truth="B",
            is_correct=False,
            latency_ms=150,
            memory_mb=25.0,
        )
        assert md.latency_ms == 150
        assert md.memory_mb == 25.0


class TestBenchmarkConfig:
    def test_defaults(self) -> None:
        cfg = BenchmarkConfig()
        assert cfg.datasets == ["cuad"]
        assert cfg.slots == ["default"]
        assert cfg.modes == ["precheck"]
        assert cfg.prompts == {}
        assert cfg.multi_party is False

    def test_custom(self) -> None:
        cfg = BenchmarkConfig(
            datasets=["cuad", "maud"],
            slots=["default", "fast"],
            modes=["precheck", "dealcheck"],
            ci_mode=True,
        )
        assert "cuad" in cfg.datasets
        assert "fast" in cfg.slots
        assert cfg.ci_mode is True

    def test_asdict(self) -> None:
        cfg = BenchmarkConfig(datasets=["cuad"])
        d = asdict(cfg)
        assert d["datasets"] == ["cuad"]
        assert d["ci_mode"] is False


class TestDatasetResult:
    def test_creates(self) -> None:
        mv = MetricValue(value=0.85, n=100, unit="f1")
        dr = DatasetResult(
            dataset_name="cuad",
            dataset_version="v1",
            n_examples=100,
            metrics={"extraction_f1": mv},
        )
        assert dr.dataset_name == "cuad"
        assert dr.metrics["extraction_f1"].value == 0.85

    def test_asdict(self) -> None:
        mv = MetricValue(value=0.85, n=100, unit="f1")
        dr = DatasetResult(
            dataset_name="cuad",
            dataset_version="v1",
            n_examples=100,
            metrics={"extraction_f1": mv},
        )
        d = asdict(dr)
        assert d["dataset_name"] == "cuad"
        assert d["metrics"]["extraction_f1"]["value"] == 0.85


class TestModelSlotResult:
    def test_creates(self) -> None:
        msr = ModelSlotResult(
            slot_name="default",
            provider="ollama",
            model="llama3.2:3b",
            total_latency_ms=5000,
            peak_memory_mb=50.0,
        )
        assert msr.slot_name == "default"
        assert msr.total_latency_ms == 5000

    def test_asdict(self) -> None:
        msr = ModelSlotResult(
            slot_name="default",
            provider="ollama",
            model="llama3.2:3b",
        )
        d = asdict(msr)
        assert d["slot_name"] == "default"
        assert d["total_latency_ms"] == 0


class TestBenchmarkRun:
    def test_creates(self) -> None:
        cfg = BenchmarkConfig()
        run = BenchmarkRun(config=cfg, git_commit="abc123")
        assert run.id is not None
        assert run.git_commit == "abc123"
        assert run.config.datasets == ["cuad"]

    def test_asdict_includes_schema(self) -> None:
        cfg = BenchmarkConfig()
        run = BenchmarkRun(config=cfg, git_commit="abc123")
        d = asdict(run)
        assert d["id"] == run.id
        assert d["git_commit"] == "abc123"
        assert "results" in d
        assert "model_slots" in d


class TestRegressionBaseline:
    def test_creates(self) -> None:
        mv = MetricValue(value=0.85, n=100, unit="f1")
        baseline = RegressionBaseline(
            baseline_id="abc123",
            metrics={("cuad", "precheck", "default", "extraction_f1"): mv},
        )
        assert baseline.baseline_id == "abc123"
        assert baseline.metrics[("cuad", "precheck", "default", "extraction_f1")].value == 0.85
