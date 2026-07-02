"""Unit tests for metric calculators (T005)."""

from openreview_cli.benchmark.metrics import (
    avg_latency,
    classification_f1,
    comparison_f1,
    extraction_f1,
    peak_memory,
)


class TestExtractionF1:
    def test_exact_match(self) -> None:
        text = "The quick brown fox jumps over the lazy dog."
        mv = extraction_f1(
            predicted_spans=[(4, 9)],  # "quick"
            ground_truth_spans=[(4, 9)],
            text=text,
        )
        assert mv.value == 1.0
        assert mv.unit == "f1"

    def test_no_match(self) -> None:
        text = "The quick brown fox."
        mv = extraction_f1(
            predicted_spans=[(0, 3)],  # "The"
            ground_truth_spans=[(10, 15)],  # "brown"
            text=text,
        )
        assert mv.value == 0.0

    def test_partial_overlap(self) -> None:
        text = "quick brown fox jumps"
        mv = extraction_f1(
            predicted_spans=[(0, 11)],  # "quick brown"
            ground_truth_spans=[(6, 17)],  # "brown fox"
            text=text,
        )
        assert mv.unit == "f1"
        assert 0 < mv.value < 1.0


class TestComparisonF1:
    def test_perfect(self) -> None:
        mv = comparison_f1(
            predicted_labels=[True, False, True],
            ground_truth_labels=[True, False, True],
        )
        assert mv.value == 1.0

    def test_no_match(self) -> None:
        mv = comparison_f1(
            predicted_labels=[True, True],
            ground_truth_labels=[False, False],
        )
        assert mv.value == 0.0

    def test_partial(self) -> None:
        mv = comparison_f1(
            predicted_labels=[True, False],
            ground_truth_labels=[True, True],
        )
        # tp=1, fp=0, fn=1 => precision=1.0, recall=0.5, f1=0.666...
        assert 0.66 < mv.value < 0.67

    def test_empty(self) -> None:
        mv = comparison_f1(predicted_labels=[], ground_truth_labels=[])
        assert mv.value == 0.0


class TestClassificationF1:
    def test_perfect(self) -> None:
        mv = classification_f1(
            predicted_labels=["A", "B", "C"],
            ground_truth_labels=["A", "B", "C"],
        )
        assert mv.value == 1.0

    def test_all_wrong(self) -> None:
        mv = classification_f1(
            predicted_labels=["A", "A"],
            ground_truth_labels=["B", "B"],
        )
        assert mv.value == 0.0

    def test_partial(self) -> None:
        mv = classification_f1(
            predicted_labels=["A", "B", "A"],
            ground_truth_labels=["A", "A", "B"],
        )
        assert 0 < mv.value < 1.0

    def test_custom_classes(self) -> None:
        mv = classification_f1(
            predicted_labels=["A", "B"],
            ground_truth_labels=["A", "A"],
            classes=["A", "B", "C"],
        )
        # Only A has predictions/ground truth, B and C have zeroes
        assert mv.unit == "f1"


class TestAvgLatency:
    def test_average(self) -> None:
        mv = avg_latency([100, 200, 300])
        assert mv.value == 200.0
        assert mv.unit == "ms"

    def test_empty(self) -> None:
        mv = avg_latency([])
        assert mv.value == 0.0


class TestPeakMemory:
    def test_max(self) -> None:
        mv = peak_memory([10.0, 25.0, 15.0])
        assert mv.value == 25.0
        assert mv.unit == "MB"

    def test_empty(self) -> None:
        mv = peak_memory([])
        assert mv.value == 0.0
