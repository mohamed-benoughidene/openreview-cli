"""R10/D6: the mock baseline must not score every mode identically.

On HEAD ``_mock_pipeline`` returns a constant ``match: True`` and the mode never
reaches ``run_dataset``, so every mode scores the same on every dataset. These
tests fail on HEAD and pass once the mode is carried end-to-end and the stub's
prediction comes from the mode's own bundled playbook.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from openreview_cli.benchmark.baseline import mock_pipeline_for_mode, run_mock_baseline
from openreview_cli.benchmark.models import BenchmarkConfig
from openreview_cli.benchmark.runner import BenchmarkRunner

# One category that belongs to the precheck NDA playbook and one that belongs to
# the settlement playbook, so the two modes disagree on the same dataset.
PRECHECK_CATEGORY = "confidentiality-term"
SETTLEMENT_CATEGORY = "release-scope"


def _loader(items: list[dict[str, Any]]) -> Any:
    def load(cache_dir: str | Path | None = None) -> Iterator[dict[str, Any]]:
        return iter(items)

    return load


def _item(category: str) -> dict[str, Any]:
    return {
        "example_id": f"doc_{category}",
        "document_text": "Clause text.",
        "category": category,
        "ground_truth": {"match": True},
    }


def test_mock_pipeline_matches_only_its_own_playbook_categories() -> None:
    precheck = mock_pipeline_for_mode("precheck")
    settlement = mock_pipeline_for_mode("settlementcheck")
    assert precheck("text", PRECHECK_CATEGORY)["match"] is True
    assert precheck("text", SETTLEMENT_CATEGORY)["match"] is False
    assert settlement("text", SETTLEMENT_CATEGORY)["match"] is True
    assert settlement("text", PRECHECK_CATEGORY)["match"] is False


def test_mock_baseline_no_longer_scores_every_mode_identically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The false floor: constant match=True made every mode's F1 identical."""
    items = [
        _item(PRECHECK_CATEGORY),
        _item(PRECHECK_CATEGORY),
        _item(SETTLEMENT_CATEGORY),
    ]
    monkeypatch.setattr("openreview_cli.benchmark.datasets.maud.load_maud_dataset", _loader(items))
    results = run_mock_baseline(["precheck", "settlementcheck"], datasets=["maud"])
    scores = {result.mode: result.comparison_f1 for result in results}
    assert set(scores) == {"precheck", "settlementcheck"}
    assert all(score is not None for score in scores.values()), scores
    assert len(set(scores.values())) > 1, f"every mode scored identically: {scores}"


def test_run_dataset_records_the_mode_it_was_given(monkeypatch: pytest.MonkeyPatch) -> None:
    """R10: ``mode`` is a first-class, *used* argument — not the dead param D-75 removed."""
    signature = inspect.signature(BenchmarkRunner.run_dataset)
    assert "mode" in signature.parameters, f"run_dataset() has no mode param: {signature}"
    assert signature.parameters["mode"].default is None

    monkeypatch.setattr(
        "openreview_cli.benchmark.datasets.maud.load_maud_dataset",
        _loader([_item(PRECHECK_CATEGORY)]),
    )
    runner = BenchmarkRunner(config=BenchmarkConfig(datasets=["maud"]))
    result = runner.run_dataset("maud", mock_pipeline_for_mode("hirecheck"), mode="hirecheck")
    assert result.dataset_name == "maud::hirecheck"


def test_maud_ground_truth_reaches_the_comparison_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A MAUD item's ground_truth dict (not an empty span list) must reach comparison_f1."""
    monkeypatch.setattr(
        "openreview_cli.benchmark.datasets.maud.load_maud_dataset",
        _loader([_item(SETTLEMENT_CATEGORY)]),
    )
    runner = BenchmarkRunner(config=BenchmarkConfig(datasets=["maud"]))
    result = runner.run_dataset("maud", mock_pipeline_for_mode("settlementcheck"))
    assert result.metrics["comparison_f1"].value == 1.0
