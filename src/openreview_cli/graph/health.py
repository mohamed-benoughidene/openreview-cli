from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openreview_cli.graph.metrics import GraphMetrics

#: Upper bound for depth normalisation. Depth >= this is scored as worst.
MAX_EXPECTED_DEPTH = 10
#: Upper bound for broken-ref count normalisation. Count >= this is worst.
MAX_EXPECTED_BROKEN_REFS = 10

#: Default weights: [density, depth, orphans, broken_refs, coverage]
DEFAULT_WEIGHTS: list[float] = [0.15, 0.20, 0.20, 0.25, 0.20]


@dataclass
class HealthScore:
    """A single 0-100 score summarising contract structural quality."""

    score: int
    weights: list[float]


def normalise_weights(weights: list[float]) -> list[float]:
    """Normalise weights to sum to 1.0, or fall back to defaults if all zero.

    Emits a warning on stderr if sum != 1.0.
    """
    total = sum(weights)
    if total <= 0:
        return list(DEFAULT_WEIGHTS)
    if abs(total - 1.0) > 1e-9:
        print(
            f"Warning: weights normalised from {total:.4f} to 1.0",
            file=sys.stderr,
        )
        return [w / total for w in weights]
    return weights


def compute_health(
    metrics: GraphMetrics,
    weights: list[float] | None = None,
) -> HealthScore:
    """Compute a 0-100 health score from graph metrics.

    Takes five metrics (density, max_depth, orphan_ratio, broken_ref_count,
    definition_coverage) and combines them with configurable weights.

    Args:
        metrics: Computed graph metrics.
        weights: Five weights. None = use defaults.
            Zero-sum weights = use defaults.

    Returns:
        HealthScore with integer 0-100 score and weights used.

    Raises:
        ValueError: If weights has a length other than 5.
    """
    if weights is None:
        resolved_weights = list(DEFAULT_WEIGHTS)
    else:
        if len(weights) != 5:
            raise ValueError(f"Expected 5 weights, got {len(weights)}")
        resolved_weights = normalise_weights(weights)

    # Components (all normalised to [0,1], higher = better)
    c1 = 1.0 - metrics.density  # Low density is good
    c2 = 1.0 - min(metrics.max_depth / MAX_EXPECTED_DEPTH, 1.0)
    c3 = 1.0 - metrics.orphan_ratio
    c4 = 1.0 - min(metrics.broken_ref_count / MAX_EXPECTED_BROKEN_REFS, 1.0)
    c5 = metrics.definition_coverage

    raw = (
        resolved_weights[0] * c1
        + resolved_weights[1] * c2
        + resolved_weights[2] * c3
        + resolved_weights[3] * c4
        + resolved_weights[4] * c5
    )

    score = max(0, min(100, round(raw * 100)))
    return HealthScore(score=score, weights=resolved_weights)


__all__ = [
    "DEFAULT_WEIGHTS",
    "HealthScore",
    "compute_health",
]
