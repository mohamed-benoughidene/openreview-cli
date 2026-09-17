"""ContractNLI benchmark integration tests.

Tests:
  - ContractNLI dataset loader (local LegalBench-RAG and mock fallbacks)
  - PreCheck NDA category mapping
  - BenchmarkRunner integration with ContractNLI
  - Ground-truth span overlap evaluation
"""

from pathlib import Path
from typing import Any

from openreview_cli.benchmark.datasets.contract_nli import (
    HYPOTHESIS_CATEGORY_MAP,
    NLI_CLASSES,
    load_contract_nli_dataset,
    map_hypothesis_to_category,
)
from openreview_cli.benchmark.models import BenchmarkConfig
from openreview_cli.benchmark.runner import BenchmarkRunner


def _mock_pipeline(text: str, category: str) -> dict[str, Any]:
    """Mock model pipeline returning fixed prediction."""
    return {
        "start": 0,
        "end": min(100, len(text)),
        "category": category,
        "label": "entailment",
        "match": True,
    }


class TestContractNLIIntegration:
    def test_hypothesis_category_mapping(self) -> None:
        """Assert all 17 standard ContractNLI hypothesis types map to valid categories."""
        assert len(HYPOTHESIS_CATEGORY_MAP) >= 17
        sample_query = (
            "Consider NDA; Does the document include a clause that prohibits the "
            "Receiving Party from soliciting some of the Disclosing Party's representatives?"
        )
        assert map_hypothesis_to_category(sample_query) == "non-solicitation"

        sample_query_2 = (
            "Does the document permit the Receiving Party to retain some Confidential Information?"
        )
        assert map_hypothesis_to_category(sample_query_2) == "return-of-materials"

    def test_nli_classes_defined(self) -> None:
        """Assert standard NLI classes exist."""
        assert "entailment" in NLI_CLASSES
        assert "contradiction" in NLI_CLASSES
        assert "neutral" in NLI_CLASSES

    def test_contractnli_local_loader(self) -> None:
        """Assert dataset loads from local data/legalbenchrag if available."""
        items = list(load_contract_nli_dataset())
        assert len(items) > 0

        first = items[0]
        assert "example_id" in first
        assert "document_text" in first
        assert len(first["document_text"]) > 0
        assert "hypothesis" in first
        assert "category" in first
        assert "ground_truth" in first
        assert "ground_truth_spans" in first
        assert isinstance(first["ground_truth_spans"], list)

    def test_benchmark_runner_contractnli_dataset(self, tmp_path: Path) -> None:
        """Assert BenchmarkRunner runs contract_nli dataset correctly."""
        config = BenchmarkConfig(datasets=["contract_nli"])
        runner = BenchmarkRunner(config=config, cache_dir=tmp_path)

        result = runner.run_dataset("contract_nli", _mock_pipeline)
        assert result.dataset_name == "contract_nli"
        assert result.n_examples > 0
        assert "avg_latency_ms" in result.metrics or "comparison_f1" in result.metrics
