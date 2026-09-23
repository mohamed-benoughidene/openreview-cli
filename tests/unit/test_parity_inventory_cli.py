"""Unit tests for scripts/parity/inventory_cli.py.

The CLI inventory must cite a real source file and line for every row it
emits, and it must carry the declared default of every Typer option.
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
SCRIPT_PATH = REPO_ROOT / "scripts" / "parity" / "inventory_cli.py"


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
    module = _load_script("parity_inventory_cli", SCRIPT_PATH)
    data = module.collect()
    assert isinstance(data, dict)
    return data


def _rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows = inventory["rows"]
    assert isinstance(rows, list)
    assert rows
    return rows


def _precheck_review_grounding_option(inventory: dict[str, Any]) -> dict[str, Any]:
    for row in _rows(inventory):
        if (
            row["type"] == "option"
            and row["owner"] == "precheck review"
            and "--grounding-mode" in row["flags_or_actions"]
        ):
            return row
    pytest.fail("no --grounding-mode option row under 'precheck review'")


def test_collect_exposes_meta_and_rows(inventory: dict[str, Any]) -> None:
    assert set(inventory) >= {"meta", "rows"}
    assert inventory["meta"]["row_count"] == len(inventory["rows"])


def test_meta_records_the_typer_framework(inventory: dict[str, Any]) -> None:
    assert inventory["meta"]["framework"] == "Typer"
    assert inventory["meta"]["framework_version"]
    assert inventory["meta"]["root_command"] == "openreview"


def test_every_row_is_located_in_real_source(inventory: dict[str, Any]) -> None:
    for row in _rows(inventory):
        source_file = row["source_file"]
        assert source_file, f"row without a source file: {row['name']}"
        path = REPO_ROOT / source_file
        assert path.is_file(), f"missing source file {source_file}"
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert 1 <= row["line_number"] <= line_count, f"line out of range: {row}"


def test_grounding_mode_option_default_is_strict(inventory: dict[str, Any]) -> None:
    row = _precheck_review_grounding_option(inventory)
    assert row["default_value"] == "strict"
    assert row["source_file"] == "src/openreview_cli/app.py"


def test_grounding_mode_option_cites_the_flag_line(inventory: dict[str, Any]) -> None:
    row = _precheck_review_grounding_option(inventory)
    lines = (REPO_ROOT / row["source_file"]).read_text(encoding="utf-8").splitlines()
    assert "grounding-mode" in lines[row["line_number"] - 1]
    assert "strict" in lines[row["default_line"] - 1]


def test_required_argument_row(inventory: dict[str, Any]) -> None:
    rows = [
        row
        for row in _rows(inventory)
        if row["type"] == "argument"
        and row["owner"] == "precheck review"
        and row["name"] == "paths"
    ]
    assert rows
    assert rows[0]["default_value"] == "REQUIRED"


def test_product_mode_commands_are_marked_dynamic(inventory: dict[str, Any]) -> None:
    rows = [row for row in _rows(inventory) if row["name"] == "licensecheck"]
    assert len(rows) == 1
    assert rows[0]["type"] == "command"
    assert rows[0]["dynamic"] is True
    assert rows[0]["source_file"] == "src/openreview_cli/app.py"


def test_group_rows_are_located_without_a_callback(inventory: dict[str, Any]) -> None:
    rows = [row for row in _rows(inventory) if row["name"] == "client"]
    assert len(rows) == 1
    assert rows[0]["type"] == "group"
    assert rows[0]["source_file"] == "src/openreview_cli/app.py"
    assert rows[0]["line_number"] > 0


def test_main_prints_json_and_writes_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_script("parity_inventory_cli_main", SCRIPT_PATH)
    out_path = tmp_path / "cli-inventory.json"
    status = module.main(["--out", str(out_path)])
    assert status == 0
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["rows"]
    printed = json.loads(capsys.readouterr().out)
    assert printed["rows"] == written["rows"]
