"""Loader for the NDA benchmark corpus.

Loads generated pair JSON files for use in tests and evaluation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from tests.fixtures.nda_corpus.generate import PAIRS_DIR


@dataclass(frozen=True)
class GroundTruthDiff:
    """A single ground-truth diff span between base and mutated clause."""

    clause_id: str
    change_type: str
    span_start: int
    span_end: int
    old_text: str
    new_text: str


@dataclass(frozen=True)
class CorpusPair:
    """One NDA pair (base + mutated) with known ground-truth diff."""

    pair_id: str
    base_id: str
    mutated_id: str
    template: str
    category: str
    mutation_name: str
    expected_diff_type: str
    base_text: str
    mutated_text: str
    ground_truth_diff: list[GroundTruthDiff]
    metadata: dict[str, Any] = field(default_factory=dict)


def load_corpus_pairs(
    max_pairs: int | None = None,
    category: str | None = None,
    template: str | None = None,
) -> list[CorpusPair]:
    """Load corpus pairs from the generated JSON files.

    Parameters
    ----------
    max_pairs : int | None
        Maximum number of pairs to load (``None`` = all).
    category : str | None
        Filter by clause category.
    template : str | None
        Filter by template ID.

    Returns
    -------
    list[CorpusPair]
    """
    pairs_dir = PAIRS_DIR
    if not pairs_dir.is_dir():
        raise FileNotFoundError(f"Corpus pairs directory not found: {pairs_dir}")

    pairs: list[CorpusPair] = []
    for fpath in sorted(pairs_dir.glob("*.json")):
        if fpath.name == "manifest.json":
            continue
        data = json.loads(fpath.read_text(encoding="utf-8"))

        # Apply filters
        if category is not None and data.get("category") != category:
            continue
        if template is not None and data.get("template") != template:
            continue

        diffs = [GroundTruthDiff(**d) for d in data.get("ground_truth_diff", [])]
        pair = CorpusPair(
            pair_id=data["pair_id"],
            base_id=data.get("base_id", ""),
            mutated_id=data.get("mutated_id", ""),
            template=data.get("template", ""),
            category=data.get("category", ""),
            mutation_name=data.get("mutation_name", ""),
            expected_diff_type=data.get("expected_diff_type", ""),
            base_text=data.get("base_text", ""),
            mutated_text=data.get("mutated_text", ""),
            ground_truth_diff=diffs,
            metadata=data.get("metadata", {}),
        )
        pairs.append(pair)

        if max_pairs is not None and len(pairs) >= max_pairs:
            break

    return pairs
