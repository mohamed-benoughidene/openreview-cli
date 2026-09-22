"""Coverage guards for all 23 named product modes in the mocked mechanism."""

from __future__ import annotations

from openreview_cli.app import _PRODUCT_MODES
from openreview_cli.review.extraction import match_category
from openreview_cli.review.playbook import BUNDLED_PLAYBOOKS, load_playbook
from tests.helpers.benchmark_scripts import load_benchmark_script

BENCH = load_benchmark_script("benchmark_product_modes")
POSITIONS = ["preferred", "acceptable", "walkaway", "acceptable", "preferred"]


def test_mode_categories_covers_all_named_modes() -> None:
    expected = {entry[0] for entry in _PRODUCT_MODES}
    assert len(expected) == 23
    assert set(BENCH.MODE_CATEGORIES) == expected


def test_every_category_id_exists_in_its_playbook() -> None:
    for mode, category_ids in BENCH.MODE_CATEGORIES.items():
        playbook = load_playbook(BUNDLED_PLAYBOOKS[mode])
        known = {category.id for category in playbook.categories}
        unknown = set(category_ids) - known
        assert not unknown, f"{mode}: unknown category ids {sorted(unknown)}"


def test_every_generated_clause_matches_its_own_category() -> None:
    """No body may contain another category's name or id (match_category pass 1)."""
    for mode, category_ids in BENCH.MODE_CATEGORIES.items():
        playbook = load_playbook(BUNDLED_PLAYBOOKS[mode])
        for category_id in category_ids:
            for idx in range(5):
                text = BENCH._clause_text(category_id, POSITIONS[idx], idx)
                matched = match_category(text, playbook)
                assert matched is not None, f"{mode}/{category_id} idx={idx}: no match"
                assert matched.id == category_id, (
                    f"{mode}/{category_id} idx={idx}: matched {matched.id} instead"
                )


def test_generic_bodies_are_five_and_non_empty() -> None:
    assert len(BENCH._GENERIC_BODIES) == 5
    assert all(body.strip() for body in BENCH._GENERIC_BODIES)
