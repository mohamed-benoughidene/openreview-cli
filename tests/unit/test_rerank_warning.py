"""Unit tests for the retrieve reranker degradation warning (B-warning)."""

from __future__ import annotations

import pytest

from openreview_cli.app import _should_warn_reranker_degradation


@pytest.mark.parametrize(
    ("val", "force_rerank", "expected"),
    [
        # Improvement: degradation_pp > 0 -> NO warning
        ({"degradation_pp": 20.0}, False, False),
        # Degradation: degradation_pp <= 0 -> warning
        ({"degradation_pp": 0.0}, False, True),
        ({"degradation_pp": -10.0}, False, True),
        # Degradation but --force-rerank suppresses
        ({"degradation_pp": -10.0}, True, False),
        # No validation record -> no warning
        (None, False, False),
        # Record present but degradation_pp missing -> no warning
        ({}, False, False),
        # Non-numeric degradation_pp -> no warning (defensive)
        ({"degradation_pp": "n/a"}, False, False),
    ],
)
def test_should_warn_reranker_degradation(
    val: dict[str, object] | None, force_rerank: bool, expected: bool
) -> None:
    assert _should_warn_reranker_degradation(val, force_rerank) is expected
