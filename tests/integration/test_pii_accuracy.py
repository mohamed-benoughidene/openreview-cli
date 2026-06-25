"""Accuracy validation skeleton for PII detection (SC-001, SC-002)."""

import pytest


@pytest.mark.accuracy
class TestPiiAccuracy:
    """Accuracy benchmark placeholders (SC-001 / SC-002)."""

    def test_accuracy_skeleton(self) -> None:
        """Placeholder for SC-001/SC-002 accuracy validation.

        Will load 50 seeded documents from
        tests/fixtures/pii/seeded_contracts/ and compare detection
        results against ground_truth.json for recall and precision.
        """
