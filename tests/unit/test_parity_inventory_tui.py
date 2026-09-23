"""Unit tests for scripts/parity/inventory_tui.py.

The TUI inventory must prove the framework it detected, cite real source for
every row, and surface the app key bindings.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "parity" / "inventory_tui.py"


def _load_script(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def inventory() -> dict[str, Any]:
    module = _load_script("parity_inventory_tui", SCRIPT_PATH)
    data = module.collect()
    assert isinstance(data, dict)
    return data


def _rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows = inventory["rows"]
    assert isinstance(rows, list)
    assert rows
    return rows


def test_collect_exposes_meta_and_rows(inventory: dict[str, Any]) -> None:
    assert set(inventory) >= {"meta", "rows"}
    assert inventory["meta"]["row_count"] == len(inventory["rows"])


def test_textual_framework_is_detected(inventory: dict[str, Any]) -> None:
    meta = inventory["meta"]
    assert meta["framework"] == "Textual"
    assert meta["detection"] == "ok"
    assert meta["framework_version"]
    assert meta["app"] == "OpenReviewApp"


def test_every_row_is_located_in_real_source(inventory: dict[str, Any]) -> None:
    for row in _rows(inventory):
        source_file = row["source_file"]
        assert source_file, f"row without a source file: {row['name']}"
        path = REPO_ROOT / source_file
        assert path.is_file(), f"missing source file {source_file}"
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert 1 <= row["line_number"] <= line_count, f"line out of range: {row}"


def test_app_class_is_discovered(inventory: dict[str, Any]) -> None:
    rows = [row for row in _rows(inventory) if row["type"] == "app"]
    assert len(rows) == 1
    assert rows[0]["name"] == "OpenReviewApp"
    assert rows[0]["source_file"] == "src/openreview_cli/tui/app.py"
    source = (REPO_ROOT / rows[0]["source_file"]).read_text(encoding="utf-8").splitlines()
    assert "class OpenReviewApp" in source[rows[0]["line_number"] - 1]


def test_screens_are_discovered(inventory: dict[str, Any]) -> None:
    screens = [row for row in _rows(inventory) if row["type"] == "screen"]
    names = {row["name"] for row in screens}
    assert len(screens) >= 10
    assert {"ReviewWizard", "ResultScreen", "SearchScreen"} <= names
    assert not names & {"Screen", "App", "ModalScreen"}


def test_search_binding_row(inventory: dict[str, Any]) -> None:
    rows = [
        row
        for row in _rows(inventory)
        if row["type"] == "binding"
        and row["owner"] == "OpenReviewApp"
        and row["flags_or_actions"][0] == "/"
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["flags_or_actions"][1] == "open_search"
    assert row["flags_or_actions"][2] == "Search"
    assert row["source_file"] == "src/openreview_cli/tui/app.py"
    source = (REPO_ROOT / row["source_file"]).read_text(encoding="utf-8").splitlines()
    assert "open_search" in source[row["line_number"] - 1]


def test_action_rows_list_their_bindings(inventory: dict[str, Any]) -> None:
    rows = [
        row
        for row in _rows(inventory)
        if row["type"] == "action"
        and row["owner"] == "OpenReviewApp"
        and row["name"] == "action_open_search"
    ]
    assert len(rows) == 1
    assert "/" in rows[0]["flags_or_actions"]


def test_default_state_rows_carry_literals(inventory: dict[str, Any]) -> None:
    rows = [row for row in _rows(inventory) if row["type"] == "default-state"]
    assert rows
    for row in rows:
        assert row["default_value"] != ""
        assert row["owner"] != ""


def test_main_prints_json_and_writes_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_script("parity_inventory_tui_main", SCRIPT_PATH)
    out_path = tmp_path / "tui-inventory.json"
    status = module.main(["--out", str(out_path)])
    assert status == 0
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["rows"]
    printed = json.loads(capsys.readouterr().out)
    assert printed["rows"] == written["rows"]
