"""PII seeded-contract dataset loader.

Loads `ground_truth.json` and corresponding `.txt` files from the
fixtures directory. Yields per-document text and expected entity sets.

The dataset lives in-repo, no HTTP download needed.
"""

import json
from collections.abc import Iterator
from pathlib import Path

from openreview_cli.benchmark.models import MetricDatum

FIXTURES_SUBDIR = "pii/seeded_contracts"


def load_pii_dataset(fixtures_root: str | Path) -> Iterator[MetricDatum]:
    """Load PII seeded contracts from the fixtures directory.

    Yields MetricDatum instances with:
      - example_id: relative path within the PII corpus
      - predicted: None (filled by evaluator)
      - ground_truth: list of dicts with 'value' and 'type'
      - is_correct: False (filled by evaluator)
    """
    base = Path(fixtures_root) / FIXTURES_SUBDIR
    gt_path = base / "ground_truth.json"
    if not gt_path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {gt_path}")

    with open(gt_path) as f:
        annotations: dict[str, list[dict[str, str]]] = json.load(f)

    for rel_path, entities in annotations.items():
        txt_path = base / rel_path
        if not txt_path.exists():
            # Some annotations may reference files that don't exist; skip gracefully
            continue

        yield MetricDatum(
            example_id=str(rel_path),
            predicted=None,
            ground_truth=entities,
            is_correct=False,
        )
