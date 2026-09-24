"""Tests for benchmark CLI --hallucination-method flag.

See D-7 in DEFERRED.md: wires HallucinationDetector selection
through the benchmark run CLI command.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from openreview_cli.benchmark.cli import _run_pii_evaluation, benchmark_app
from openreview_cli.benchmark.metrics_pii import evaluate_pii_accuracy
from openreview_cli.benchmark.models import DatasetResult
from openreview_cli.benchmark.runner import BenchmarkRunner
from openreview_cli.pii.models import PiiEntity

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures"


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text, e.g. Rich/Typer coloring in CI."""
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_runner_deps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Mock BenchmarkRunner and filesystem to isolate flag tests."""
    mock_runner = MagicMock()
    result = DatasetResult(dataset_name="mock", dataset_version="v1", n_examples=0)
    mock_runner.run_dataset.return_value = result

    monkeypatch.setattr(
        "openreview_cli.benchmark.cli.BenchmarkRunner",
        lambda config, fixtures_root, cache_dir, **kwargs: mock_runner,
    )
    monkeypatch.setattr(
        "openreview_cli.benchmark.cli._FIXTURES_DIR",
        FIXTURES,
    )
    monkeypatch.setattr(
        "openreview_cli.benchmark.cli.get_data_dir",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "openreview_cli.benchmark.cli._detect_git_branch",
        lambda: "test",
    )
    monkeypatch.setattr(
        "openreview_cli.benchmark.cli._detect_git_commit",
        lambda: "abc1234",
    )
    monkeypatch.setattr(
        "openreview_cli.benchmark.cli._run_pii_evaluation",
        lambda runner, verbose: None,
    )


class TestValidHallucinationMethods:
    """VALID_HALLUCINATION_METHODS constant."""

    def test_constant_exists(self) -> None:
        from openreview_cli.benchmark.cli import VALID_HALLUCINATION_METHODS

        assert isinstance(VALID_HALLUCINATION_METHODS, frozenset)

    def test_contains_lexical(self) -> None:
        from openreview_cli.benchmark.cli import VALID_HALLUCINATION_METHODS

        assert "lexical" in VALID_HALLUCINATION_METHODS

    def test_contains_cg_dpo(self) -> None:
        from openreview_cli.benchmark.cli import VALID_HALLUCINATION_METHODS

        assert "cg-dpo" in VALID_HALLUCINATION_METHODS

    def test_is_frozenset(self) -> None:
        from openreview_cli.benchmark.cli import VALID_HALLUCINATION_METHODS

        assert isinstance(VALID_HALLUCINATION_METHODS, frozenset)


class TestHallucinationMethodCli:
    """--hallucination-method CLI flag."""

    def test_help_shows_flag(self, cli_runner: CliRunner) -> None:
        """--hallucination-method should appear in --help output."""
        result = cli_runner.invoke(benchmark_app, ["run", "--help"])
        assert result.exit_code == 0
        assert "--hallucination-method" in _strip_ansi(result.output)

    def test_invalid_value_rejected(self, cli_runner: CliRunner) -> None:
        """Invalid value 'foo' should exit with code 78."""
        result = cli_runner.invoke(benchmark_app, ["run", "--hallucination-method=foo"])
        assert result.exit_code == 78

    def test_invalid_value_message_mentions_valid_values(self, cli_runner: CliRunner) -> None:
        """Error message should list valid options."""
        result = cli_runner.invoke(benchmark_app, ["run", "--hallucination-method=invalid"])
        assert result.exit_code == 78

    def test_valid_lexical_accepted(self, cli_runner: CliRunner, mock_runner_deps: None) -> None:
        """'lexical' should pass validation and complete."""
        result = cli_runner.invoke(benchmark_app, ["run", "--hallucination-method=lexical"])
        assert result.exit_code == 0

    def test_valid_cg_dpo_accepted(self, cli_runner: CliRunner, mock_runner_deps: None) -> None:
        """'cg-dpo' should pass validation and complete."""
        result = cli_runner.invoke(benchmark_app, ["run", "--hallucination-method=cg-dpo"])
        assert result.exit_code == 0


class _StubPiiEngine:
    """Fake PiiEngine returning one PERSON detection, using the real PiiEntity type."""

    def __init__(self, threshold: float = 0.7) -> None:
        self.threshold = threshold

    def detect_on_page(self, text: str) -> list[PiiEntity]:
        return [
            PiiEntity(
                entity_type="PERSON",
                original_value="Alice Smith",
                start=0,
                end=len("Alice Smith"),
                score=0.9,
                placeholder="[PERSON_0]",
                source="nlp",
            )
        ]


class _StubPiiRunner:
    """Captures the detect_fn the CLI builds and scores it on a tiny corpus."""

    def __init__(self) -> None:
        self.detect_fn: Callable[[str], list[dict[str, str]]] | None = None

    def run_pii(self, detect_fn: Callable[[str], list[dict[str, str]]]) -> DatasetResult:
        self.detect_fn = detect_fn
        metrics = evaluate_pii_accuracy(
            [
                (
                    "doc.txt",
                    "Alice Smith works at Acme.",
                    [{"value": "Alice Smith", "type": "PERSON"}],
                )
            ],
            detect_fn,
        )
        return DatasetResult(
            dataset_name="pii", dataset_version="v1", n_examples=1, metrics=metrics
        )


class TestPiiEvaluationEntityFieldMapping:
    """Regression: _run_pii_evaluation must read PiiEntity's real fields.

    The CLI previously read ``ent.text``/``ent.label`` (Presidio-style names that
    do not exist on PiiEntity), so every detection became
    ``{"value": str(ent), "type": "UNKNOWN"}`` and matched nothing — the CLI
    reported pii_recall/pii_precision of 0.0 even though the engine had detected
    entities. These tests pin the {value, type} contract and assert the reported
    metrics are not the degenerate zeros.
    """

    def test_detect_fn_maps_entity_type_and_original_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("openreview_cli.pii.engine.PiiEngine", _StubPiiEngine)
        runner = _StubPiiRunner()
        _run_pii_evaluation(cast("BenchmarkRunner", runner), tier="balanced")

        assert runner.detect_fn is not None
        assert runner.detect_fn("Alice Smith works at Acme.") == [
            {"value": "Alice Smith", "type": "PERSON"}
        ]

    def test_pii_metrics_are_not_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("openreview_cli.pii.engine.PiiEngine", _StubPiiEngine)
        runner = _StubPiiRunner()
        result = _run_pii_evaluation(cast("BenchmarkRunner", runner), tier="balanced")

        assert result.metrics["pii_recall"].value > 0.0
        assert result.metrics["pii_precision"].value > 0.0
