"""Unit tests for scripts/parity/build_parity_matrix.py.

The headline acceptance criterion lives here: the CLI default ``strict`` for
citation grounding against the TUI's ``NOT PASSED`` must be detected as a
default-value mismatch and must appear in the markdown column
``Default mismatch``.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "parity" / "build_parity_matrix.py"
CLI_APP = REPO_ROOT / "src" / "openreview_cli" / "app.py"
TUI_CALL = REPO_ROOT / "src" / "openreview_cli" / "tui" / "domain" / "review.py"


def _load_script(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def matrix() -> dict[str, Any]:
    module = _load_script("parity_build_matrix", SCRIPT_PATH)
    data = module.collect()
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def markdown() -> str:
    module = _load_script("parity_build_matrix_render", SCRIPT_PATH)
    return cast("str", module.render_markdown(module.collect()))


def _rows(data: dict[str, Any], row_type: str) -> list[dict[str, Any]]:
    return [row for row in data["rows"] if row["type"] == row_type]


def _cli_grounding_ifexp_line() -> int:
    """Line of the CLI `grounding_mode=None if no_grounding else grounding_mode`."""
    tree = ast.parse(CLI_APP.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.IfExp)
            and isinstance(node.test, ast.Name)
            and node.test.id == "no_grounding"
        ):
            return node.lineno
    pytest.fail("no grounding IfExp found in app.py")


def _tui_run_review_call_line() -> int:
    """Line of the TUI `run_review(...)` call in tui/domain/review.py."""
    tree = ast.parse(TUI_CALL.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "run_review"
        ):
            return node.lineno
    pytest.fail("no run_review call found in tui/domain/review.py")


def test_collect_exposes_meta_and_rows(matrix: dict[str, Any]) -> None:
    assert set(matrix) >= {"meta", "rows"}
    assert matrix["meta"]["row_count"] == len(matrix["rows"])


def test_every_row_carries_the_six_mandated_keys(matrix: dict[str, Any]) -> None:
    for row in matrix["rows"]:
        assert set(row) >= {
            "name",
            "type",
            "flags_or_actions",
            "default_value",
            "source_file",
            "line_number",
        }
        assert isinstance(row["name"], str)
        assert isinstance(row["flags_or_actions"], list)
        assert isinstance(row["default_value"], str)


def test_every_row_is_located_in_real_source(matrix: dict[str, Any]) -> None:
    for row in matrix["rows"]:
        path = REPO_ROOT / row["source_file"]
        assert row["source_file"], f"row without a source file: {row['name']}"
        assert path.is_file(), f"missing source file {row['source_file']}"
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert 1 <= row["line_number"] <= line_count, f"line out of range: {row}"


def test_cli_conditional_resolves_to_strict(matrix: dict[str, Any]) -> None:
    rows = [
        row
        for row in _rows(matrix, "shared-call-arg")
        if row["target"] == "run_review"
        and row["name"] == "grounding_mode"
        and row["entry_point"] == "precheck review"
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["lane"] == "cli"
    assert row["value_kind"] == "conditional"
    assert row["effective_value"] == "strict"
    assert row["source_file"] == "src/openreview_cli/app.py"
    assert row["line_number"] == _cli_grounding_ifexp_line()
    assert "no_grounding" in row["call_expr_src"]
    assert row["branch_false"] == "strict"
    assert row["branch_true"] == "None"
    assert row["guard_default"] == "False"


def test_cli_absent_grounding_never_stores_the_branch_body(matrix: dict[str, Any]) -> None:
    """The `None` branch body must never be reported as the effective value."""
    rows = [
        row
        for row in _rows(matrix, "shared-call-arg")
        if row["target"] == "run_review"
        and row["name"] == "grounding_mode"
        and row["lane"] == "cli"
    ]
    assert rows
    for row in rows:
        if row["value_kind"] == "conditional":
            assert row["effective_value"] != "None"
        else:
            assert row["effective_value"] == "NOT PASSED"


def test_tui_grounding_is_not_passed_with_callee_default(matrix: dict[str, Any]) -> None:
    rows = [
        row
        for row in _rows(matrix, "shared-call-arg")
        if row["target"] == "run_review"
        and row["name"] == "grounding_mode"
        and row["lane"] == "tui"
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["value_kind"] == "absent"
    assert row["effective_value"] == "NOT PASSED"
    assert row["callee_default"] == "None"
    assert row["source_file"] == "src/openreview_cli/tui/domain/review.py"
    assert row["line_number"] == _tui_run_review_call_line()


def test_grounding_mismatch_row_cites_both_locations(matrix: dict[str, Any]) -> None:
    rows = [
        row
        for row in _rows(matrix, "mismatch")
        if row["target"] == "run_review" and row["param"] == "grounding_mode"
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["cli_value"] == "strict"
    assert row["tui_value"] == "NOT PASSED"
    assert row["cli_source"] == f"src/openreview_cli/app.py:{_cli_grounding_ifexp_line()}"
    assert (
        row["tui_source"]
        == f"src/openreview_cli/tui/domain/review.py:{_tui_run_review_call_line()}"
    )
    assert row["status"] in {"MISMATCH", "MISMATCH-ABSENT"}


def test_markdown_has_a_default_mismatch_column(markdown: str) -> None:
    assert "Default mismatch" in markdown
    mismatch_lines = [
        line for line in markdown.splitlines() if line.startswith("|") and "NOT PASSED" in line
    ]
    assert mismatch_lines, "the grounding mismatch never reached the markdown"
    assert any("strict" in line for line in mismatch_lines)
    assert any("src/openreview_cli/app.py:" in line for line in mismatch_lines)
    assert any("src/openreview_cli/tui/domain/review.py:" in line for line in mismatch_lines)


def test_markdown_is_pure_ascii(markdown: str) -> None:
    offending = sorted({char for char in markdown if ord(char) > 127})
    assert offending == []


def test_markdown_has_the_required_sections(markdown: str) -> None:
    for heading in (
        "## Table A: CLI inventory",
        "## Table B: TUI inventory",
        "## Table C: parity join",
        "## Default-value mismatches",
        "## Shared call sites without a counterpart",
        "## Needs human confirmation",
        "## Unmatched CLI items",
        "## Unmatched TUI items",
        "## Semantic collisions",
        "## Row counts",
    ):
        assert heading in markdown, f"missing section: {heading}"


def test_only_the_grounding_parameter_mismatches(matrix: dict[str, Any]) -> None:
    params = {row["param"] for row in _rows(matrix, "mismatch")}
    assert params == {"grounding_mode"}


def test_product_mode_call_site_is_labelled(matrix: dict[str, Any]) -> None:
    tree = ast.parse(CLI_APP.read_text(encoding="utf-8"))
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "run_review"
        and node.lineno > 3000
    )
    rows = [
        row
        for row in _rows(matrix, "shared-call-arg")
        if row["target"] == "run_review" and row["line_number"] == call.lineno
    ]
    assert rows
    assert {row["entry_point"] for row in rows} == {"product modes"}
    assert {row["lane"] for row in rows} == {"cli"}


def test_shared_call_rows_never_borrow_an_unrelated_flag() -> None:
    """A `no_pii` comparison must be reported against `--no-pii`."""
    module = _load_script("parity_build_matrix_flags", SCRIPT_PATH)
    markdown = module.render_markdown(module.collect())
    rows = [
        line
        for line in markdown.splitlines()
        if line.startswith("| ") and "(precheck review)" in line
    ]
    assert sum(1 for line in rows if "--allow-partial-pii (precheck review)" in line) == 1
    assert sum(1 for line in rows if "--no-pii (precheck review)" in line) == 1


def test_generic_mode_token_never_creates_a_certain_match(matrix: dict[str, Any]) -> None:
    for pair in matrix["join"]:
        if pair["match"] != "CERTAIN":
            continue
        assert "--mode-threshold" not in pair["cli_item"]
        assert "--mode-threshold" not in pair["cli_flags"]


def _command_row(name: str, line_number: int) -> dict[str, Any]:
    return {
        "name": name,
        "type": "command",
        "owner": "prompt",
        "help_text": "",
        "flags_or_actions": [],
        "default_value": "",
        "source_file": "src/openreview_cli/prompts/cli.py",
        "line_number": line_number,
    }


def _screen_row(name: str, line_number: int) -> dict[str, Any]:
    return {
        "name": name,
        "type": "screen",
        "owner": "openreview_cli.tui.screens.prompt_detail",
        "help_text": "",
        "flags_or_actions": [],
        "default_value": "",
        "source_file": "src/openreview_cli/tui/screens/prompt_detail.py",
        "line_number": line_number,
    }


def test_prompt_domain_noun_joins_prompt_commands_to_prompt_screens() -> None:
    """``prompt`` is a domain noun, so the prompt commands match the prompt screens.

    Regression guard for the GENERIC_TOKENS entry: while ``prompt`` was generic
    the CLI ``prompt history`` could only ever reach ``NEEDS-HUMAN`` against
    ``PromptHistoryScreen``.
    """
    module = _load_script("parity_build_matrix_prompt_tokens", SCRIPT_PATH)
    join = module.build_join(
        [_command_row("prompt history", 189), _command_row("prompt diff", 127)],
        [_screen_row("PromptHistoryScreen", 23), _screen_row("PromptDiffScreen", 49)],
    )
    pairs = {(pair["cli_item"], pair["tui_item"]): pair for pair in join["certain"]}
    for cli_item, tui_item in (
        ("prompt history", "PromptHistoryScreen"),
        ("prompt diff", "PromptDiffScreen"),
    ):
        assert (cli_item, tui_item) in pairs, f"{cli_item} never became CERTAIN"
        pair = pairs[(cli_item, tui_item)]
        assert pair["match"] == "CERTAIN"
        assert "prompt" in pair["shared_tokens"]


def test_certain_match_suppresses_the_generic_overlap_human_row() -> None:
    """A certain match is the strongest classification; its generic overlap is dropped.

    ``prompt history`` matches ``PromptHistoryScreen`` on the ``prompt`` domain
    noun. The unrelated playbook ``VersionHistoryScreen`` shares only the generic
    ``history`` token, so that generic-overlap human row must not be reported
    once the CLI item is already matched with certainty.
    """
    module = _load_script("parity_build_matrix_generic_overlap", SCRIPT_PATH)
    join = module.build_join(
        [_command_row("prompt history", 189)],
        [_screen_row("PromptHistoryScreen", 23), _screen_row("VersionHistoryScreen", 166)],
    )
    pairs = {(pair["cli_item"], pair["tui_item"]): pair for pair in join["certain"]}
    assert ("prompt history", "PromptHistoryScreen") in pairs
    assert pairs[("prompt history", "PromptHistoryScreen")]["match"] == "CERTAIN"
    assert all(pair["cli_item"] != "prompt history" for pair in join["human"])


def test_prompt_history_is_certain_and_absent_from_needs_human(matrix: dict[str, Any]) -> None:
    """``prompt history`` is matched against the prompt screens, never a human row."""
    certain = {
        (pair["cli_item"], pair["tui_item"])
        for pair in matrix["join"]
        if pair["match"] == "CERTAIN"
    }
    assert ("prompt history", "PromptHistoryScreen") in certain
    assert ("prompt history", "PromptDiffScreen") in certain
    human_cli = {pair["cli_item"] for pair in matrix["needs_human_confirmation"]}
    assert "prompt history" not in human_cli


def test_needs_human_confirmation_is_populated(matrix: dict[str, Any]) -> None:
    human = matrix["needs_human_confirmation"]
    assert human
    for pair in human:
        assert pair["match"] == "NEEDS-HUMAN"
        assert pair["reason"]
    assert any("generic" in pair["reason"] for pair in human)


def test_playbook_flag_semantic_collision_is_reported(matrix: dict[str, Any]) -> None:
    collisions = {collision["flag"]: collision for collision in matrix["semantic_collisions"]}
    assert "--playbook" in collisions
    meanings = collisions["--playbook"]["meanings"]
    assert len(meanings) >= 2
    helps = " ".join(meaning["help"] for meaning in meanings)
    assert "database" in helps
    assert "YAML playbook override" in helps


def test_unmatched_lists_are_reported(matrix: dict[str, Any]) -> None:
    assert matrix["unmatched_cli"]
    assert matrix["unmatched_tui"]


def test_render_rejects_unlocated_rows() -> None:
    module = _load_script("parity_build_matrix_guard", SCRIPT_PATH)
    good = {
        "name": "ok",
        "type": "command",
        "flags_or_actions": [],
        "default_value": "",
        "source_file": "src/openreview_cli/app.py",
        "line_number": 1,
    }
    assert module.check_rows([good]) == []
    bad = dict(good, source_file="", line_number=0)
    assert module.check_rows([bad])
    with pytest.raises(SystemExit):
        module.render_markdown({"meta": {}, "rows": [bad]})


def test_main_writes_markdown_and_prints_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_script("parity_build_matrix_main", SCRIPT_PATH)
    cli_json = tmp_path / "cli.json"
    tui_json = tmp_path / "tui.json"
    cli_json.write_text(json.dumps({"meta": {"row_count": 0}, "rows": []}), encoding="utf-8")
    tui_json.write_text(json.dumps({"meta": {"row_count": 0}, "rows": []}), encoding="utf-8")
    out_path = tmp_path / "matrix.md"
    status = module.main(
        [
            "--cli-json",
            str(cli_json),
            "--tui-json",
            str(tui_json),
            "--out",
            str(out_path),
        ]
    )
    assert status == 0
    written = out_path.read_text(encoding="utf-8")
    assert "CLI and TUI parity matrix" in written
    printed = json.loads(capsys.readouterr().out)
    assert printed["meta"]["row_count"] == len(printed["rows"])


def test_pre_generated_json_is_used(tmp_path: Path) -> None:
    module = _load_script("parity_build_matrix_json_in", SCRIPT_PATH)
    cli_json = tmp_path / "cli.json"
    tui_json = tmp_path / "tui.json"
    fixture_row = {
        "name": "injected-command",
        "type": "command",
        "flags_or_actions": [],
        "default_value": "",
        "source_file": "src/openreview_cli/app.py",
        "line_number": 1,
        "owner": "",
        "help_text": "",
        "dynamic": False,
    }
    cli_json.write_text(
        json.dumps({"meta": {"row_count": 1}, "rows": [fixture_row]}), encoding="utf-8"
    )
    tui_json.write_text(json.dumps({"meta": {"row_count": 0}, "rows": []}), encoding="utf-8")
    data = module.collect(cli_json=cli_json, tui_json=tui_json)
    assert any(row["name"] == "injected-command" for row in data["rows"])
    assert data["meta"]["cli_rows"] == 1
