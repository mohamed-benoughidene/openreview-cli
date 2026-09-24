"""PII accuracy integration test (T010).

Runs the seeded corpus via the benchmark runner and asserts the
authoritative targets from specs/004-complete-pii-stripping FR-008/FR-009:
recall ≥ 0.95 and precision ≥ 0.95.

The evaluator uses span-level (type-agnostic) matching (spec FR-006, R8
amendment): a detection is correct when its value overlaps a
ground-truth value, whatever the type label. On the current engine
(``PiiEngine(threshold=0.7)``) the seeded corpus measures recall 0.9640
(563/584) and precision 0.9526 (683/717), so both gates pass.
"""

from pathlib import Path

from openreview_cli.benchmark.models import BenchmarkConfig
from openreview_cli.benchmark.runner import BenchmarkRunner


def _mock_pii_engine(text: str) -> list[dict[str, str]]:
    """Mock PII engine that returns known entities from the text."""
    # This is a simplified mock for integration testing.
    # In production, the real PiiEngine would be used.
    known_entities: list[dict[str, str]] = []

    # Return empty — in real tests this would use the actual PII engine
    # ponytail: mock returns nothing. Replace with real PiiEngine when
    # the spacy model is available in CI.
    return known_entities


class TestPiiAccuracyIntegration:
    """Integration tests for PII accuracy benchmark.

    These tests require the spacy model to be installed (it is available
    in this repo's dev environment).
    """

    def test_pii_recall_above_threshold(self, fixtures_dir: Path) -> None:
        """Assert recall ≥ 0.95 on seeded corpus."""
        config = BenchmarkConfig(
            datasets=["pii"],
            slots=["default"],
            modes=["precheck"],
        )
        runner = BenchmarkRunner(config=config, fixtures_root=fixtures_dir)

        # This would use the real PiiEngine
        from openreview_cli.pii.engine import PiiEngine

        engine = PiiEngine(threshold=0.7)

        def detect_fn(text: str) -> list[dict[str, str]]:
            results = []
            entities = engine.detect_on_page(text)
            for ent in entities:
                results.append(
                    {
                        "value": ent.original_value,
                        "type": ent.entity_type,
                    }
                )
            return results

        result = runner.run_pii(detect_fn)
        recall = result.metrics.get("pii_recall")
        precision = result.metrics.get("pii_precision")

        # Authoritative target: specs/004 FR-008 (recall ≥95%) / FR-009
        # (precision ≥95%). Passes under span-level (type-agnostic) matching.
        assert recall is not None, "pii_recall metric not computed"
        assert precision is not None, "pii_precision metric not computed"
        assert recall.value >= 0.95, f"PII recall {recall.value:.4f} < 0.95"
        assert precision.value >= 0.95, f"PII precision {precision.value:.4f} < 0.95"

    def test_pii_returns_per_type_breakdown(self, fixtures_dir: Path) -> None:
        """Assert per-entity-type breakdown is reported."""
        config = BenchmarkConfig(datasets=["pii"])
        runner = BenchmarkRunner(config=config, fixtures_root=fixtures_dir)
        from openreview_cli.pii.engine import PiiEngine

        engine = PiiEngine(threshold=0.7)

        def detect_fn(text: str) -> list[dict[str, str]]:
            results = []
            entities = engine.detect_on_page(text)
            for ent in entities:
                results.append(
                    {
                        "value": ent.original_value,
                        "type": ent.entity_type,
                    }
                )
            return results

        result = runner.run_pii(detect_fn)

        # Check for at least PERSON type recall
        person_recall = result.metrics.get("pii_recall_person")
        assert person_recall is not None, "No per-type PERSON recall metric"

    def test_pii_with_mock_engine_no_crash(self, fixtures_dir: Path) -> None:
        """Assert the PII runner works without crash even with mock engine."""
        config = BenchmarkConfig(datasets=["pii"])
        runner = BenchmarkRunner(config=config, fixtures_root=fixtures_dir)
        result = runner.run_pii(_mock_pii_engine)
        # Should complete without error
        assert result.dataset_name == "pii"
        assert result.n_examples > 0
