"""Data models for the benchmark harness.

See data-model.md §Entities for full entity definitions.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class MetricValue:
    """A single measured value with statistical context."""

    value: float
    n: int
    unit: str
    ci_lower: float | None = None
    ci_upper: float | None = None

    VALID_UNITS = frozenset({"f1", "precision", "recall", "rate", "ms", "MB", "score"})

    def __post_init__(self) -> None:
        if self.unit not in self.VALID_UNITS:
            raise ValueError(f"Invalid unit '{self.unit}'. Valid: {sorted(self.VALID_UNITS)}")
        if self.n <= 0:
            raise ValueError(f"n must be > 0, got {self.n}")
        if self.unit in ("f1", "precision", "recall", "rate", "score") and not (
            0.0 <= self.value <= 1.0
        ):
            raise ValueError(f"{self.unit} value must be in [0.0, 1.0], got {self.value}")
        if self.unit in ("ms", "MB") and self.value < 0:
            raise ValueError(f"{self.unit} value must be >= 0, got {self.value}")

    def __repr__(self) -> str:
        return f"MetricValue({self.value:.4f}, n={self.n}, unit={self.unit})"


@dataclass
class MetricDatum:
    """A single data point contributing to a MetricValue aggregation."""

    example_id: str
    predicted: Any
    ground_truth: Any
    is_correct: bool
    latency_ms: int | None = None
    memory_mb: float | None = None


@dataclass
class BenchmarkConfig:
    """Configuration for a single benchmark run."""

    datasets: list[str] = field(default_factory=lambda: ["cuad"])
    slots: list[str] = field(default_factory=lambda: ["default"])
    modes: list[str] = field(default_factory=lambda: ["precheck"])
    prompts: dict[str, str] = field(default_factory=dict)
    multi_party: bool = False
    ci_mode: bool = False
    baseline_ref: str | None = None


@dataclass
class DatasetResult:
    """Aggregated metrics for one dataset in one run."""

    dataset_name: str
    dataset_version: str
    n_examples: int
    metrics: dict[str, MetricValue] = field(default_factory=dict)


@dataclass
class ModelSlotResult:
    """Metrics for a single model slot in one run."""

    slot_name: str
    provider: str
    model: str
    metrics: dict[str, MetricValue] = field(default_factory=dict)
    total_latency_ms: int = 0
    peak_memory_mb: float = 0.0


@dataclass
class BenchmarkRun:
    """A single execution of one or more benchmark suites."""

    config: BenchmarkConfig
    timestamp: str | None = None
    git_commit: str = ""
    git_branch: str | None = None
    results: list[DatasetResult] = field(default_factory=list)
    model_slots: list[ModelSlotResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.now(UTC).isoformat()


@dataclass
class RegressionBaseline:
    """Stored reference for regression comparison."""

    baseline_id: str
    metrics: dict[tuple[str, str, str, str], MetricValue]
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(UTC).isoformat()
