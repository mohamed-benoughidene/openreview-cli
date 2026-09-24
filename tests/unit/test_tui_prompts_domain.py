"""Unit tests for the prompts TUI domain wrapper (Task 1).

Exercises ``openreview_cli.tui.domain.prompts`` against the REAL
``PromptStore`` over a real temp SQLite DB created by the ``isolated_xdg``
fixture — no mocks.  The wrapper must resolve ``get_data_dir()`` at call time,
so the file the wrapper touches is exactly ``isolated_xdg["db_path"]``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
import yaml

from openreview_cli.prompts.store import PromptStore
from openreview_cli.tui.domain import prompts as domain_prompts
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


# --- Task 2: the total domain boundary -------------------------------------


def _new(name: str) -> Any:
    """Return a Task 2 wrapper, *failing* (not erroring) when it is missing.

    ``getattr`` keeps this module importable while the wrappers are still
    unimplemented, so a missing wrapper surfaces as a genuine assertion
    failure instead of an import-time collection error.
    """
    wrapper = getattr(domain_prompts, name, None)
    if wrapper is None:
        pytest.fail(f"tui domain wrapper {name!r} is not implemented yet")
    return wrapper


def _raiser(exc: Exception) -> Any:
    """Build a callable that raises ``exc`` whenever it is invoked."""

    def _raise(*_args: Any, **_kwargs: Any) -> Any:
        raise exc

    return _raise


# --- get_prompt_detail_via_tui ---------------------------------------------


def test_create_prompt_then_read_back(store: PromptStore) -> None:
    version = _new("create_prompt_via_tui")("greeting", "hello", tags=["a"], description="d")
    assert version == 1

    detail = _new("get_prompt_detail_via_tui")("greeting")
    assert detail == {
        "found": True,
        "name": "greeting",
        "latest_version": 1,
        "versions": [1],
        "content": "hello",
        "tags": ["a"],
        "description": "d",
    }


def test_create_duplicate_name_raises(isolated_xdg: dict[str, Path]) -> None:
    create = _new("create_prompt_via_tui")
    create("dup", "one")
    with pytest.raises(ValueError):
        create("dup", "two")


def test_detail_missing_prompt_is_found_false(isolated_xdg: dict[str, Path]) -> None:
    detail = _new("get_prompt_detail_via_tui")("does-not-exist")
    assert detail["found"] is False
    assert detail["versions"] == []
    assert detail["latest_version"] == 0


def test_detail_versions_survive_sparse_import(store: PromptStore) -> None:
    """An imported prompt numbered 1 and 3 must report ``[1, 3]``, not raise."""
    store.import_prompt(
        {
            "name": "sparse",
            "versions": [
                {"version": 1, "content": "one", "created_at": "2026-01-01T00:00:00Z"},
                {"version": 3, "content": "three", "created_at": "2026-01-03T00:00:00Z"},
            ],
        }
    )

    detail = _new("get_prompt_detail_via_tui")("sparse")

    assert detail["found"] is True
    assert detail["versions"] == [1, 3]
    assert detail["latest_version"] == 3
    assert detail["content"] == "three"


# --- create / update / delete ----------------------------------------------


def test_update_appends_version_two_and_keeps_version_one(store: PromptStore) -> None:
    create = _new("create_prompt_via_tui")
    update = _new("update_prompt_via_tui")
    detail = _new("get_prompt_detail_via_tui")

    create("doc", "one")
    assert update("doc", "two") == 2

    d = detail("doc")
    assert d["versions"] == [1, 2]
    assert d["latest_version"] == 2
    assert d["content"] == "two"
    assert store.get("doc", 1).content == "one"


def test_update_with_too_many_characters_raises_value_error(store: PromptStore) -> None:
    """The store's SQL CHECK rejects 20000 chars; the boundary must raise ValueError."""
    create = _new("create_prompt_via_tui")
    update = _new("update_prompt_via_tui")

    create("big", "seed")
    with pytest.raises(ValueError):
        update("big", "a" * 20000)


def test_update_with_multibyte_content_within_char_limit_succeeds(store: PromptStore) -> None:
    """12000 ``€`` is 36000 bytes but 12000 characters: the store accepts it."""
    create = _new("create_prompt_via_tui")
    update = _new("update_prompt_via_tui")

    create("euro", "seed")
    assert update("euro", "€" * 12000) == 2


def test_delete_removes_every_version(store: PromptStore) -> None:
    create = _new("create_prompt_via_tui")
    update = _new("update_prompt_via_tui")
    delete = _new("delete_prompt_via_tui")
    detail = _new("get_prompt_detail_via_tui")

    create("gone", "one")
    update("gone", "two")
    delete("gone")

    assert detail("gone")["found"] is False
    assert store.list() == []


# --- bindings ---------------------------------------------------------------


def test_bind_list_unbind_round_trip(isolated_xdg: dict[str, Path]) -> None:
    create = _new("create_prompt_via_tui")
    bind = _new("bind_prompt_via_tui")
    unbind = _new("unbind_prompt_via_tui")
    list_bindings = _new("list_bindings_via_tui")

    create("bound", "content")
    bind("reasoning", "bound", 1)

    bindings = list_bindings()
    assert len(bindings) == 1
    row = bindings[0]
    assert row["slot"] == "reasoning"
    assert row["prompt_name"] == "bound"
    assert row["prompt_version"] == 1
    assert row["created_at"]

    unbind("reasoning")
    assert list_bindings() == []


def test_bind_with_unknown_slot_raises(isolated_xdg: dict[str, Path]) -> None:
    with pytest.raises(ValueError):
        _new("bind_prompt_via_tui")("nope", "x", 1)


def test_unbind_without_binding_raises(isolated_xdg: dict[str, Path]) -> None:
    with pytest.raises(ValueError):
        _new("unbind_prompt_via_tui")("reasoning")


# --- validate_prompt_test_via_tui -------------------------------------------


def test_validate_prompt_test_unknown_prompt_raises(isolated_xdg: dict[str, Path]) -> None:
    with pytest.raises(ValueError):
        _new("validate_prompt_test_via_tui")("ghost", [1])


def test_validate_prompt_test_unknown_version_raises(store: PromptStore) -> None:
    create = _new("create_prompt_via_tui")
    validate = _new("validate_prompt_test_via_tui")

    create("known", "x")
    with pytest.raises(ValueError):
        validate("known", [2])


def test_validate_prompt_test_valid_versions_pass(store: PromptStore) -> None:
    create = _new("create_prompt_via_tui")
    update = _new("update_prompt_via_tui")
    validate = _new("validate_prompt_test_via_tui")

    create("known", "x")
    update("known", "y")
    assert validate("known", [1, 2]) is None


# --- export / import --------------------------------------------------------


def test_export_writes_a_file_that_parses_back(store: PromptStore, tmp_path: Path) -> None:
    create = _new("create_prompt_via_tui")
    update = _new("update_prompt_via_tui")
    export = _new("export_prompt_via_tui")

    create("exp", "one")
    update("exp", "two")
    dest = tmp_path / "exp.yaml"
    export(dest, "exp")

    data = yaml.safe_load(dest.read_text())
    assert data["name"] == "exp"
    assert [v["version"] for v in data["versions"]] == [1, 2]
    assert data["versions"][1]["content"] == "two"


# --- export_prompts_via_tui: the optional-name (export-all) form ------------


def test_export_prompts_via_tui_exports_every_prompt_and_returns_count(
    store: PromptStore, tmp_path: Path
) -> None:
    """No name exports the whole library and returns how many were written."""
    create = _new("create_prompt_via_tui")
    update = _new("update_prompt_via_tui")
    export_all = _new("export_prompts_via_tui")

    create("alpha", "a1")
    update("alpha", "a2")
    create("beta", "b1")
    create("gamma", "g1")
    dest = tmp_path / "library.yaml"

    assert export_all(dest) == 3

    data = yaml.safe_load(dest.read_text())
    assert [item["name"] for item in data] == ["alpha", "beta", "gamma"]
    alpha = next(item for item in data if item["name"] == "alpha")
    assert [v["version"] for v in alpha["versions"]] == [1, 2]
    assert alpha["versions"][1]["content"] == "a2"


def test_export_prompts_via_tui_with_name_exports_exactly_one(
    store: PromptStore, tmp_path: Path
) -> None:
    """A name still exports exactly that one prompt, and returns ``1``."""
    create = _new("create_prompt_via_tui")
    export_all = _new("export_prompts_via_tui")

    create("alpha", "a1")
    create("beta", "b1")
    dest = tmp_path / "one.yaml"

    assert export_all(dest, "beta") == 1

    data = yaml.safe_load(dest.read_text())
    assert data["name"] == "beta"
    assert [v["version"] for v in data["versions"]] == [1]
    assert data["versions"][0]["content"] == "b1"


def test_count_prompts_via_tui_is_uncapped(store: PromptStore) -> None:
    """The count source does not stop at the 100-item cap the list requests."""
    create = _new("create_prompt_via_tui")
    count = _new("count_prompts_via_tui")

    for i in range(105):
        create(f"prompt-{i:03d}", f"content {i}")

    assert count() == 105
    # The list wrapper still reports its 100-capped view; the count does not.
    assert len(list_prompts_via_tui()) == 100


def test_export_prompts_via_tui_failure_becomes_value_error(
    monkeypatch: pytest.MonkeyPatch, isolated_xdg: dict[str, Path], tmp_path: Path
) -> None:
    """A store failure on the export-all path is a ``ValueError``."""
    export_all = _new("export_prompts_via_tui")
    monkeypatch.setattr(PromptStore, "export", _raiser(sqlite3.IntegrityError("boom")))

    with pytest.raises(ValueError, match="export all prompts"):
        export_all(tmp_path / "library.yaml")


def test_export_prompts_via_tui_with_name_failure_names_the_prompt(
    monkeypatch: pytest.MonkeyPatch, isolated_xdg: dict[str, Path], tmp_path: Path
) -> None:
    """The per-prompt form still names the prompt in its ``ValueError``."""
    export_all = _new("export_prompts_via_tui")
    monkeypatch.setattr(PromptStore, "export", _raiser(sqlite3.IntegrityError("boom")))

    with pytest.raises(ValueError, match="export prompt 'alpha'"):
        export_all(tmp_path / "one.yaml", "alpha")


def test_import_reports_imported_and_failed(isolated_xdg: dict[str, Path], tmp_path: Path) -> None:
    importer = _new("import_prompts_via_tui")
    path = tmp_path / "mixed.yaml"
    path.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "fresh",
                    "versions": [
                        {
                            "version": 1,
                            "content": "a",
                            "created_at": "2026-01-01T00:00:00Z",
                        }
                    ],
                },
                {
                    "name": "existing",
                    "versions": [
                        {
                            "version": 1,
                            "content": "b",
                            "created_at": "2026-01-01T00:00:00Z",
                        }
                    ],
                },
            ]
        )
    )
    # Pre-create the second name so its import is refused by the store.
    PromptStore(isolated_xdg["db_path"]).create("existing", "old")

    result = importer(path)

    assert result["imported"] == ["fresh"]
    assert set(result["failed"]) == {"existing"}
    assert "already exists" in result["failed"]["existing"]


def test_import_collects_per_item_store_failure(
    monkeypatch: pytest.MonkeyPatch, isolated_xdg: dict[str, Path], tmp_path: Path
) -> None:
    """A store error during import is reported per item, never raised out."""
    importer = _new("import_prompts_via_tui")
    monkeypatch.setattr(PromptStore, "import_prompt", _raiser(sqlite3.IntegrityError("boom")))
    path = tmp_path / "one.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "name": "x",
                "versions": [{"version": 1, "content": "c", "created_at": "2026-01-01T00:00:00Z"}],
            }
        )
    )

    result = importer(path)

    assert result["imported"] == []
    assert "x" in result["failed"]
    assert "boom" in result["failed"]["x"]


# --- the total boundary: any store exception becomes ValueError -------------

_BOUNDARY_CASES = [
    ("create_prompt_via_tui", "create", lambda w: w("name", "content")),
    ("update_prompt_via_tui", "update", lambda w: w("name", "content")),
    ("delete_prompt_via_tui", "delete", lambda w: w("name")),
    ("get_prompt_detail_via_tui", "export", lambda w: w("name")),
    ("list_prompts_via_tui", "list", lambda w: w()),
    ("get_prompt_history_via_tui", "export", lambda w: w("name")),
    ("list_bindings_via_tui", "bindings", lambda w: w()),
    ("bind_prompt_via_tui", "bind", lambda w: w("reasoning", "name", 1)),
    ("unbind_prompt_via_tui", "unbind", lambda w: w("reasoning")),
    ("validate_prompt_test_via_tui", "get_latest", lambda w: w("name", [1])),
    ("export_prompt_via_tui", "export", lambda w: w(Path("unused.yaml"), "name")),
    ("export_prompts_via_tui", "export", lambda w: w(Path("unused.yaml"))),
    ("export_prompts_via_tui", "export", lambda w: w(Path("unused.yaml"), "name")),
    ("count_prompts_via_tui", "export", lambda w: w()),
]


@pytest.mark.parametrize("exc_type", [sqlite3.IntegrityError, KeyError, TypeError])
@pytest.mark.parametrize(
    ("wrapper_name", "store_method", "invoke"),
    _BOUNDARY_CASES,
    ids=[f"{case[0]}-{index}" for index, case in enumerate(_BOUNDARY_CASES)],
)
def test_boundary_is_total(
    monkeypatch: pytest.MonkeyPatch,
    isolated_xdg: dict[str, Path],
    exc_type: type[Exception],
    wrapper_name: str,
    store_method: str,
    invoke: Any,
) -> None:
    wrapper = _new(wrapper_name)
    monkeypatch.setattr(PromptStore, store_method, _raiser(exc_type("boom")))
    with pytest.raises(ValueError):
        invoke(wrapper)


# --- Defect 2: the read path is part of the total boundary -------------------
#
# Regression: ``list_prompts_via_tui`` had no ``try/except`` at all and
# ``get_prompt_history_via_tui`` caught only ``ValueError``, so a
# ``sqlite3.Error`` or ``OSError`` raised by the store escaped the boundary and
# could reach a Textual handler (terminating the app).  Both read wrappers now
# translate any unexpected failure into ``ValueError`` naming the operation,
# while a *missing prompt* still yields ``found=False`` instead of raising.


def test_list_translates_store_error_to_value_error(
    monkeypatch: pytest.MonkeyPatch, isolated_xdg: dict[str, Path]
) -> None:
    monkeypatch.setattr(PromptStore, "list", _raiser(sqlite3.IntegrityError("boom")))
    with pytest.raises(ValueError, match="list prompts"):
        list_prompts_via_tui()


def test_history_translates_store_error_to_value_error(
    monkeypatch: pytest.MonkeyPatch, isolated_xdg: dict[str, Path]
) -> None:
    monkeypatch.setattr(PromptStore, "export", _raiser(sqlite3.IntegrityError("boom")))
    with pytest.raises(ValueError, match="history"):
        get_prompt_history_via_tui("greeting")


def test_history_missing_prompt_still_found_false_after_boundary_fix(
    isolated_xdg: dict[str, Path],
) -> None:
    """A missing prompt is not an error: it stays ``found=False``, never raises."""
    result = get_prompt_history_via_tui("does-not-exist")
    assert result == {"rows": [], "current_version": 0, "found": False}


# --- Defect 2: import runs the SAME validator the CLI runs -------------------
#
# Regression: ``import_prompts_via_tui`` called ``yaml.safe_load`` itself, so a
# structurally invalid document reached the store (or was silently swallowed
# into ``failed``) instead of raising ``ValueError`` before any write.  The fix
# routes the wrapper through ``openreview_cli.prompts.io.parse_prompts_yaml``,
# the one structural validator the CLI's ``prompt import`` also uses.


def _write_prompts_yaml(path: Path, data: Any) -> None:
    path.write_text(yaml.safe_dump(data))


class TestImportUsesSharedValidator:
    def test_version_missing_created_at_raises_and_writes_nothing(
        self, isolated_xdg: dict[str, Path], tmp_path: Path
    ) -> None:
        path = tmp_path / "missing-created-at.yaml"
        _write_prompts_yaml(path, {"name": "alpha", "versions": [{"version": 1, "content": "x"}]})

        with pytest.raises(ValueError, match="created_at"):
            _new("import_prompts_via_tui")(path)

        assert PromptStore(isolated_xdg["db_path"]).list() == []

    def test_versions_null_raises_and_writes_nothing(
        self, isolated_xdg: dict[str, Path], tmp_path: Path
    ) -> None:
        path = tmp_path / "versions-null.yaml"
        _write_prompts_yaml(path, {"name": "alpha", "versions": None})

        with pytest.raises(ValueError, match="null 'versions'"):
            _new("import_prompts_via_tui")(path)

        assert PromptStore(isolated_xdg["db_path"]).list() == []

    def test_mixed_file_imports_first_and_reports_duplicate(
        self, isolated_xdg: dict[str, Path], tmp_path: Path
    ) -> None:
        store = PromptStore(isolated_xdg["db_path"])
        store.init()
        store.create("existing", "old")
        path = tmp_path / "mixed.yaml"
        _write_prompts_yaml(
            path,
            [
                {
                    "name": "fresh",
                    "versions": [
                        {"version": 1, "content": "a", "created_at": "2026-01-01T00:00:00Z"}
                    ],
                },
                {
                    "name": "existing",
                    "versions": [
                        {"version": 1, "content": "b", "created_at": "2026-01-01T00:00:00Z"}
                    ],
                },
            ],
        )

        result = _new("import_prompts_via_tui")(path)

        assert result["imported"] == ["fresh"]
        assert set(result["failed"]) == {"existing"}
        assert "already exists" in result["failed"]["existing"]
        # The first prompt really landed, not merely reported.
        assert store.get("fresh", 1).content == "a"

    def test_unreadable_file_raises_value_error(self, tmp_path: Path) -> None:
        directory = tmp_path / "a-directory"
        directory.mkdir()

        with pytest.raises(ValueError, match="import"):
            _new("import_prompts_via_tui")(directory)

    def test_store_init_failure_raises_value_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(domain_prompts, "_store", _raiser(sqlite3.OperationalError("boom")))
        path = tmp_path / "ok.yaml"
        _write_prompts_yaml(
            path,
            {"name": "x", "versions": [{"version": 1, "content": "c", "created_at": "z"}]},
        )

        with pytest.raises(ValueError, match="import"):
            _new("import_prompts_via_tui")(path)
