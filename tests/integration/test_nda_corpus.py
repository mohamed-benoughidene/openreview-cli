"""Integration tests for the NDA benchmark corpus.

Tests cover:
- Corpus generation produces expected pair count
- Each pair has valid ground_truth_diff (non-empty, spans valid)
- Mutations are reversible (round-trip)
- Ground truth diffs have valid change types
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures.nda_corpus.generate import (
    CORPUS_SIZE,
    generate_corpus,
    load_templates,
)
from tests.fixtures.nda_corpus.mutations import (
    ALL_MUTATIONS,
)

# Valid change types for ground truth diffs
VALID_CHANGE_TYPES = {"addition", "contradiction", "equivalent"}

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "nda_corpus"
PAIRS_DIR = FIXTURES_DIR / "pairs"


@pytest.fixture(scope="module")
def corpus_pairs(tmp_path_factory: pytest.TempPathFactory) -> list[dict[str, Any]]:
    """Generate the full corpus once per test module."""
    import tests.fixtures.nda_corpus.generate as _gen

    _original_pairs_dir = _gen.PAIRS_DIR
    _gen.PAIRS_DIR = tmp_path_factory.mktemp("corpus_pairs") / "pairs"
    try:
        return generate_corpus()
    finally:
        _gen.PAIRS_DIR = _original_pairs_dir


def test_corpus_size(corpus_pairs: list[dict[str, Any]]) -> None:
    """Corpus must produce at least CORPUS_SIZE pairs."""
    assert len(corpus_pairs) >= CORPUS_SIZE, (
        f"Expected ≥{CORPUS_SIZE} pairs, got {len(corpus_pairs)}"
    )


def test_corpus_has_forward_and_reverse(corpus_pairs: list[dict[str, Any]]) -> None:
    """Corpus must contain both forward and reverse pairs."""
    forward = [p for p in corpus_pairs if p.get("metadata", {}).get("direction") == "forward"]
    reverse = [p for p in corpus_pairs if p.get("metadata", {}).get("direction") == "reverse"]
    assert len(forward) > 0
    assert len(reverse) > 0
    assert len(forward) == len(reverse)


def test_manifest_written() -> None:
    """Manifest JSON must exist after generation."""
    manifest_path = PAIRS_DIR / "manifest.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["total_pairs"] >= CORPUS_SIZE
    assert data["template_count"] >= 2


def test_each_pair_has_valid_diff(corpus_pairs: list[dict[str, Any]]) -> None:
    """Every pair must have non-empty ground_truth_diff with valid spans."""
    for pair in corpus_pairs:
        assert len(pair["ground_truth_diff"]) > 0, (
            f"Pair {pair['pair_id']} has empty ground_truth_diff"
        )
        for diff in pair["ground_truth_diff"]:
            assert diff["change_type"] in VALID_CHANGE_TYPES, (
                f"Invalid change_type {diff['change_type']} in {pair['pair_id']}"
            )
            assert isinstance(diff["span_start"], int)
            assert isinstance(diff["span_end"], int)
            assert diff["span_start"] >= 0
            assert diff["span_end"] >= diff["span_start"]
            assert isinstance(diff["old_text"], str)
            assert isinstance(diff["new_text"], str)


def test_diff_spans_valid_range(corpus_pairs: list[dict[str, Any]]) -> None:
    """Verify diff spans are within bounds of the base text."""
    for pair in corpus_pairs:
        bt = pair["base_text"]
        bt_len = len(bt)
        for diff in pair["ground_truth_diff"]:
            assert 0 <= diff["span_start"] <= bt_len, (
                f"span_start out of range in {pair['pair_id']}"
            )
            assert 0 <= diff["span_end"] <= bt_len, f"span_end out of range in {pair['pair_id']}"
            assert diff["span_start"] <= diff["span_end"], (
                f"span_start > span_end in {pair['pair_id']}"
            )


def test_mutations_reversible_round_trip() -> None:
    """Each mutation should be reversible when find_text appears only once.

    Skip deletions (empty replace_text) and mutations where the matched
    text appears multiple times in the clause (multiple-occurrence
    round-trips require cleverer logic).
    """
    templates = load_templates()
    template_id = next(iter(templates.keys()))
    clauses = templates[template_id]

    for mutation in ALL_MUTATIONS:
        if mutation.replace_text == "":
            continue  # deletion mutations not reversible via simple replace
        if mutation.category.value not in clauses:
            continue

        clause_text = clauses[mutation.category.value]
        if mutation.find_text not in clause_text and not any(
            alt in clause_text for alt in mutation.find_text_alternatives
        ):
            continue

        # Find what text was matched
        matched = mutation.find_text if mutation.find_text in clause_text else None
        if matched is None:
            for alt in mutation.find_text_alternatives:
                if alt in clause_text:
                    matched = alt
                    break
        if matched is None:
            continue

        # Skip if matched text appears more than once (ambiguous round-trip)
        if clause_text.count(matched) > 1:
            continue

        # Apply forward mutation (replace only the first occurrence)
        mutated = clause_text.replace(matched, mutation.replace_text, 1)

        # Apply reverse mutation (replace only the first occurrence)
        restored = mutated.replace(mutation.replace_text, matched, 1)

        assert restored == clause_text, (
            f"Round-trip failed for {mutation.name}: expected {clause_text!r}, got {restored!r}"
        )


def test_all_templates_have_required_clauses() -> None:
    """Each template should have at minimum: confidentiality_definition and obligations."""
    templates = load_templates()
    for tid, clauses in templates.items():
        assert "confidentiality_definition" in clauses, (
            f"Template {tid} missing confidentiality_definition"
        )
        assert "obligations" in clauses, f"Template {tid} missing obligations"
        assert "exclusions" in clauses, f"Template {tid} missing exclusions"


def test_pairs_json_files_exist() -> None:
    """Sample forward pairs should exist as JSON files in pairs directory."""
    json_files = list(PAIRS_DIR.glob("*.json"))
    assert len(json_files) >= 2  # at least manifest + 1 sample


def test_loader_loads_pairs() -> None:
    """The loader should successfully load corpus pairs."""
    from tests.fixtures.nda_corpus.loader import load_corpus_pairs

    pairs = load_corpus_pairs(max_pairs=5)
    assert len(pairs) > 0
    assert all(p.ground_truth_diff for p in pairs)
    assert all(len(p.ground_truth_diff) > 0 for p in pairs)


def test_loader_filters_by_category() -> None:
    """Loader should filter by category correctly."""
    from tests.fixtures.nda_corpus.loader import load_corpus_pairs

    pairs = load_corpus_pairs(max_pairs=5, category="governing_law")
    assert all(p.category == "governing_law" for p in pairs)


def test_loader_filters_by_template() -> None:
    """Loader should filter by template correctly."""
    from tests.fixtures.nda_corpus.loader import load_corpus_pairs

    pairs = load_corpus_pairs(max_pairs=5, template="onenda_v2.1")
    assert all(p.template == "onenda_v2.1" for p in pairs)


def test_mutation_change_types_covered() -> None:
    """All change types (addition, contradiction, equivalent) should appear."""
    seen_types = set()
    for mutation in ALL_MUTATIONS:
        seen_types.add(mutation.expected_diff_type)
    assert "addition" in seen_types
    assert "contradiction" in seen_types
    assert "equivalent" in seen_types


@pytest.mark.parametrize(
    "category_name",
    [
        "confidentiality_definition",
        "exclusions",
        "obligations",
        "term",
        "return_obligations",
        "governing_law",
    ],
)
def test_category_has_mutations(category_name: str) -> None:
    """Each key clause category must have at least one mutation."""
    cat_mutations = [m for m in ALL_MUTATIONS if m.category.value == category_name]
    assert len(cat_mutations) >= 1, f"Category {category_name} has no mutations"
