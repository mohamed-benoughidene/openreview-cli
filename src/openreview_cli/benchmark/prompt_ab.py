"""Prompt A/B infrastructure.

Variant execution against same dataset+slot, comparative metric
aggregation, and McNemar's test for statistical significance.

McNemar's test is implemented manually (~20 lines) to avoid a scipy
dependency, per research.md decision.
"""

import math
from typing import Any


def mcnemar_test(
    results_a: list[bool],
    results_b: list[bool],
) -> float:
    """McNemar's test for paired nominal data.

    Tests whether the marginal frequencies of two binary outcomes
    are significantly different (i.e., whether one prompt produces
    more correct results than the other).

    Returns p-value (two-tailed) using the binomial exact test,
    which works for all sample sizes. No chi-squared approximation needed.

    Args:
        results_a: Correctness flags for prompt variant A
        results_b: Correctness flags for prompt variant B (paired)

    Returns:
        p-value (two-tailed). p < 0.05 is considered significant.
    """
    if len(results_a) != len(results_b):
        raise ValueError("Paired results must have same length")

    # Contingency table cells:
    # b: A wrong, B correct
    # c: A correct, B wrong
    b = sum(1 for a, b_val in zip(results_a, results_b, strict=False) if not a and b_val)
    c = sum(1 for a, b_val in zip(results_a, results_b, strict=False) if a and not b_val)

    n_discordant = b + c
    if n_discordant == 0:
        return 1.0  # No disagreement — p = 1.0

    # Binomial exact test (two-tailed)
    # Under H0, discordant pairs split equally: P(b > c) = P(c > b)
    # Two-tailed p = 2 * P(X <= min(b,c)) where X ~ Binomial(n_discordant, 0.5)
    k = min(b, c)
    p_val = 0.0
    for i in range(k + 1):
        p_val += _binomial_pmf(i, n_discordant, 0.5)
    p_val = min(2 * p_val, 1.0)

    return p_val


def _binomial_pmf(k: int, n: int, p: float) -> float:
    """Binomial probability mass function."""
    if k < 0 or k > n:
        return 0.0
    return math.comb(n, k) * (p**k) * ((1 - p) ** (n - k))


def compare_variants(
    variant_results: dict[str, list[bool]],
) -> dict[str, Any]:
    """Compare multiple prompt variant results.

    Args:
        variant_results: Dict mapping variant name -> list of correctness flags

    Returns:
        Dict with:
          - per_variant_summary: dict of variant -> {correct, total, accuracy}
          - comparisons: list of {variant_a, variant_b, p_value, significant}
    """
    variant_names = list(variant_results.keys())
    summaries: dict[str, dict[str, float | int]] = {}
    for name, results in variant_results.items():
        correct = sum(1 for r in results if r)
        total = len(results)
        summaries[name] = {
            "correct": correct,
            "total": total,
            "accuracy": correct / total if total > 0 else 0.0,
        }

    comparisons: list[dict[str, Any]] = []
    for i in range(len(variant_names)):
        for j in range(i + 1, len(variant_names)):
            a_name = variant_names[i]
            b_name = variant_names[j]
            p_val = mcnemar_test(
                list(variant_results[a_name]),
                list(variant_results[b_name]),
            )
            comparisons.append(
                {
                    "variant_a": a_name,
                    "variant_b": b_name,
                    "p_value": round(p_val, 6),
                    "significant": p_val < 0.05,
                }
            )

    return {
        "per_variant_summary": summaries,
        "comparisons": comparisons,
    }
