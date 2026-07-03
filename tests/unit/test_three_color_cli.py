"""Unit tests for --confidence-threshold CLI flag and validation."""

import inspect

import pytest
import typer

from openreview_cli.app import DEFAULT_CONFIDENCE_THRESHOLD, _validate_threshold


class TestHelpTextDisclosure:
    def test_help_text_contains_accuracy_disclosure(self) -> None:
        """Accuracy ceiling disclosure appears in help text."""
        from openreview_cli.app import review

        src = inspect.getsource(review)
        assert "accuracy" in src.lower(), "help text should mention accuracy ceiling"


class TestThresholdValidation:
    def test_default_constant(self) -> None:
        assert DEFAULT_CONFIDENCE_THRESHOLD == 0.7

    def test_valid_values_accepted(self) -> None:
        assert _validate_threshold(0.0) == 0.0
        assert _validate_threshold(0.3) == 0.3
        assert _validate_threshold(0.5) == 0.5
        assert _validate_threshold(0.7) == 0.7
        assert _validate_threshold(0.9) == 0.9
        assert _validate_threshold(1.0) == 1.0

    def test_negative_rejected(self) -> None:
        with pytest.raises(typer.BadParameter):
            _validate_threshold(-0.1)

    def test_above_one_rejected(self) -> None:
        with pytest.raises(typer.BadParameter):
            _validate_threshold(1.5)
