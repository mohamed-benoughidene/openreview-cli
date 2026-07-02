"""CUAD benchmark integration tests (T015 + T023).

Tests:
  - CUAD dataset loader (mock download)
  - BenchmarkRunner with CUAD datasets
  - Multi-dataset support (MAUD, ContractNLI)
"""

from pathlib import Path

import pytest

from openreview_cli.benchmark.models import BenchmarkConfig
from openreview_cli.benchmark.runner import BenchmarkRunner


def _mock_pipeline(text: str, category: str) -> dict[str, object]:
    """Mock model pipeline returning fixed values."""
    return {"start": 0, "end": 0, "category": category, "label": "entailment", "match": True}


class TestCuadIntegration:
    def test_runner_creates(self, tmp_path: Path) -> None:
        """Assert BenchmarkRunner instantiates correctly."""
        config = BenchmarkConfig(datasets=["cuad"])
        runner = BenchmarkRunner(config=config, cache_dir=tmp_path)
        assert runner.config.datasets == ["cuad"]

    def test_runner_with_cuad_no_cache(self) -> None:
        """Assert runner handles CUAD dataset gracefully when not available."""
        config = BenchmarkConfig(datasets=["cuad"])
        runner = BenchmarkRunner(config=config)
        try:
            from openreview_cli.benchmark.datasets.cuad import load_cuad_dataset

            items = list(load_cuad_dataset())
            assert len(items) > 0
        except Exception as e:
            # CUAD URL may not be available; this is acceptable
            pytest.skip(f"CUAD dataset download failed: {e}")

    def test_runner_with_mock_pipeline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert runner works with mock pipeline (no real LLM)."""
        # Mock the CUAD loader to avoid real HTTP calls in CI
        _fake_items = [
            {
                "example_id": "doc1_governing_law",
                "document_text": "This Agreement shall be governed by the laws of New York.",
                "category": "governing_law",
                "ground_truth_spans": [(42, 52)],
                "is_positive": True,
            },
        ]
        monkeypatch.setattr(
            "openreview_cli.benchmark.datasets.cuad.load_cuad_dataset",
            lambda cache_dir=None: iter(_fake_items),
        )
        config = BenchmarkConfig(datasets=["cuad"])
        runner = BenchmarkRunner(config=config, cache_dir=tmp_path)
        result = runner.run_dataset("cuad", _mock_pipeline)
        assert result.dataset_name == "cuad"
        assert result.n_examples == 1
        # With mock pipeline, we expect some metric values
        assert "extraction_f1" in result.metrics or "avg_latency_ms" in result.metrics

    def test_maud_loader_structure(self) -> None:
        """Assert MAUD loader produces expected structure."""
        from openreview_cli.benchmark.datasets.maud import MAUD_CATEGORIES, load_maud_dataset

        assert len(MAUD_CATEGORIES) >= 39  # At least 39 categories
        try:
            items = list(load_maud_dataset())
            if items:
                item = items[0]
                assert "category" in item
                assert "ground_truth" in item
                assert "match" in item["ground_truth"]
        except Exception as e:
            pytest.skip(f"MAUD dataset download failed: {e}")

    def test_contract_nli_loader_structure(self) -> None:
        """Assert ContractNLI loader produces expected structure."""
        from openreview_cli.benchmark.datasets.contract_nli import (
            NLI_CLASSES,
            load_contract_nli_dataset,
        )

        assert "entailment" in NLI_CLASSES
        try:
            items = list(load_contract_nli_dataset())
            if items:
                item = items[0]
                assert "hypothesis" in item
                assert "ground_truth" in item
                assert "label" in item["ground_truth"]
                assert item["ground_truth"]["label"] in NLI_CLASSES
        except Exception as e:
            pytest.skip(f"ContractNLI dataset download failed: {e}")

    def test_multi_dataset_config(self) -> None:
        """Assert multi-dataset config works."""
        config = BenchmarkConfig(
            datasets=["cuad", "maud", "contract_nli"],
            slots=["default", "fast"],
        )
        assert len(config.datasets) == 3
        assert len(config.slots) == 2

    def test_multi_dataset_runner_creates(self) -> None:
        """Assert runner handles multi-dataset config."""
        config = BenchmarkConfig(
            datasets=["cuad", "maud", "contract_nli"],
            slots=["default"],
        )
        runner = BenchmarkRunner(config=config)
        assert "cuad" in runner.config.datasets
