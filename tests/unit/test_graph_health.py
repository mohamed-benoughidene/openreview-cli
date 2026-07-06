from __future__ import annotations

import pytest

from openreview_cli.graph.health import (
    DEFAULT_WEIGHTS,
    compute_health,
    normalise_weights,
)
from openreview_cli.graph.metrics import GraphMetrics


def _perfect_metrics() -> GraphMetrics:
    return GraphMetrics(
        density=0.0,
        max_depth=1,
        orphan_ratio=0.0,
        broken_ref_count=0,
        definition_coverage=1.0,
    )


def _pathological_metrics() -> GraphMetrics:
    return GraphMetrics(
        density=1.0,
        max_depth=10,
        orphan_ratio=1.0,
        broken_ref_count=10,
        definition_coverage=0.0,
    )


class TestNormaliseWeights:
    def test_default_weights_already_sum_one(self) -> None:
        w = normalise_weights(DEFAULT_WEIGHTS)
        assert abs(sum(w) - 1.0) < 1e-9

    def test_normalises_non_sum_one(self) -> None:
        w = normalise_weights([0.2, 0.2, 0.2, 0.3, 0.3])
        assert abs(sum(w) - 1.0) < 1e-9

    def test_all_zero_falls_back(self) -> None:
        w = normalise_weights([0.0, 0.0, 0.0, 0.0, 0.0])
        assert w == DEFAULT_WEIGHTS


class TestComputeHealth:
    def test_perfect_graph_scores_98(self) -> None:
        """Perfect metrics score 98 because depth=1 gives c2=0.9 (penalty)."""
        result = compute_health(_perfect_metrics())
        assert result.score == 98

    def test_pathological_graph_scores_0(self) -> None:
        result = compute_health(_pathological_metrics())
        assert result.score == 0

    def test_custom_weights_change_score(self) -> None:
        mid_metrics = GraphMetrics(
            density=0.5,
            max_depth=3,
            orphan_ratio=0.2,
            broken_ref_count=2,
            definition_coverage=0.8,
        )
        default = compute_health(mid_metrics)
        custom = compute_health(mid_metrics, weights=[0.5, 0.1, 0.1, 0.2, 0.1])
        assert default.score != custom.score or default.weights != custom.weights

    def test_all_zero_weights_fall_back(self) -> None:
        result = compute_health(_perfect_metrics(), weights=[0.0, 0.0, 0.0, 0.0, 0.0])
        assert result.score == 98

    def test_wrong_weight_count_raises(self) -> None:
        with pytest.raises(ValueError, match="Expected 5 weights"):
            compute_health(_perfect_metrics(), weights=[0.2, 0.2, 0.2])

    def test_normalised_weights_warning(self, capsys: pytest.CaptureFixture[str]) -> None:
        metrics = _perfect_metrics()
        result = compute_health(metrics, weights=[0.2, 0.2, 0.2, 0.3, 0.3])
        stderr = capsys.readouterr().err
        assert "Warning: weights normalised from" in stderr
        assert result.score == 98
