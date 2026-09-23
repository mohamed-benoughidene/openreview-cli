"""Unit tests for the prompts TUI domain wrapper (Task 1).

Exercises ``openreview_cli.tui.domain.prompts`` against the REAL
``PromptStore`` over a real temp SQLite DB created by the ``isolated_xdg``
fixture — no mocks.  The wrapper must resolve ``get_data_dir()`` at call time,
so the file the wrapper touches is exactly ``isolated_xdg["db_path"]``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openreview_cli.prompts.store import PromptStore
from openreview_cli.tui.domain.prompts import (
    _normalize_created_at,
    get_prompt_history_via_tui,
    get_prompt_version_diff,
    list_prompts_via_tui,
)


@pytest.fixture
def store(isolated_xdg: dict[str, Path]) -> PromptStore:
    """A real PromptStore bound to the isolated per-test database."""
    s = PromptStore(isolated_xdg["db_path"])
    s.init()
    return s


# --- list_prompts_via_tui --------------------------------------------------


def test_list_empty_returns_empty_list(isolated_xdg: dict[str, Path]) -> None:
    assert list_prompts_via_tui() == []


def test_list_returns_expected_shape(store: PromptStore) -> None:
    pv = store.create("greeting", "hi")
    rows = list_prompts_via_tui()
    assert rows == [{"name": "greeting", "latest_version": 1, "created_at": pv.created_at}]


def test_list_is_not_capped_by_default_page_size(store: PromptStore) -> None:
    """The wrapper requests an explicit page size so >25 prompts are visible."""
    for i in range(30):
        store.create(f"prompt-{i:02d}", f"content {i}")
    rows = list_prompts_via_tui()
    assert len(rows) == 30


# --- get_prompt_history_via_tui --------------------------------------------


def test_history_three_versions_in_order(store: PromptStore) -> None:
    v1 = store.create("greeting", "one")
    v2 = store.update("greeting", "two")
    v3 = store.update("greeting", "three")

    result = get_prompt_history_via_tui("greeting")

    assert result["found"] is True
    assert result["current_version"] == 3
    rows = result["rows"]
    assert [r["version"] for r in rows] == [1, 2, 3]
    assert [r["created_at"] for r in rows] == [
        v1.created_at,
        v2.created_at,
        v3.created_at,
    ]
    assert all(r["created_at"] for r in rows)


def test_history_sparse_non_1_based_versions(store: PromptStore) -> None:
    """Imported prompts can have gaps; range(1, latest + 1) would raise here."""
    store.import_prompt(
        {
            "name": "imported",
            "versions": [
                {"version": 2, "content": "two", "created_at": "2026-01-02T00:00:00Z"},
                {"version": 5, "content": "five", "created_at": "2026-01-05T00:00:00Z"},
            ],
        }
    )

    result = get_prompt_history_via_tui("imported")

    assert result["found"] is True
    assert result["current_version"] == 5
    assert result["rows"] == [
        {"version": 2, "created_at": "2026-01-02T00:00:00Z"},
        {"version": 5, "created_at": "2026-01-05T00:00:00Z"},
    ]


def test_history_missing_prompt(isolated_xdg: dict[str, Path]) -> None:
    result = get_prompt_history_via_tui("does-not-exist")
    assert result == {"rows": [], "current_version": 0, "found": False}


def test_normalize_created_at_handles_sql_null_string() -> None:
    assert _normalize_created_at("None") == ""
    assert _normalize_created_at(None) == ""
    assert _normalize_created_at("2026-01-02T00:00:00Z") == "2026-01-02T00:00:00Z"


# --- get_prompt_version_diff -----------------------------------------------


def test_diff_contains_old_and_new_content_lines(store: PromptStore) -> None:
    store.create("doc", "alpha\nbeta\n")
    store.update("doc", "alpha\ngamma\n")

    diff = get_prompt_version_diff("doc", 1, 2)

    assert diff.startswith("--- v1")
    assert "+++ v2" in diff
    assert "-beta" in diff
    assert "+gamma" in diff


def test_diff_missing_version_raises(store: PromptStore) -> None:
    store.create("doc", "alpha\n")
    with pytest.raises(ValueError):
        get_prompt_version_diff("doc", 1, 2)
