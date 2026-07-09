"""Integration tests for playbook CLI (D-46 undelete, D-47 --json, D-48 bulk).

End-to-end CLI round-trips via CliRunner.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()

_COUNTER: list[int] = [0]
_RUN_ID: str = os.urandom(2).hex()


def _unique_id(base: str) -> str:
    _COUNTER[0] += 1
    return f"{base}-{_RUN_ID}-{_COUNTER[0]}"


def _make_yaml_v1(pb_id: str) -> str:
    """Produce minimal valid playbook YAML with given id."""
    return f"""id: {pb_id}
mode: precheck
metadata:
  version: "1.0"
  description: Test playbook
  author: Tester
categories:
  - id: confidentiality
    name: Confidentiality
    description: NDA terms
    preferred:
      description: Mutual protection
      exemplars:
        - mutual NDA
    acceptable:
      description: Standard one-way
      exemplars:
        - standard NDA
    walkaway:
      description: No confidentiality
      exemplars:
        - no NDA
    default_position: preferred
"""


def _make_yaml_v2(pb_id: str) -> str:
    """Produce a second version with added category."""
    return f"""id: {pb_id}
mode: precheck
metadata:
  version: "2.0"
  description: Updated playbook
  author: Tester
categories:
  - id: confidentiality
    name: Confidentiality
    description: Broader NDA terms
    preferred:
      description: Mutual protection
      exemplars:
        - mutual NDA
        - enhanced mutual NDA
    acceptable:
      description: Standard one-way
      exemplars:
        - standard NDA
    walkaway:
      description: No confidentiality
      exemplars:
        - no NDA
    default_position: preferred
  - id: indemnification
    name: Indemnification
    description: Indemnification terms
    preferred:
      description: Mutual indemnity
      exemplars:
        - mutual indemnity
    acceptable:
      description: One-way
      exemplars:
        - one-way indemnity
    walkaway:
      description: No indemnity
      exemplars:
        - no indemnity
    default_position: preferred
"""


def _import_yaml(tmp_path: Path, yaml_str: str) -> str:
    """Write YAML to a temp file and import. Returns playbook id from YAML."""
    path = tmp_path / f"{_COUNTER[0]}.yaml"
    path.write_text(yaml_str)
    result = runner.invoke(app, ["playbook", "import", str(path)])
    assert result.exit_code == 0, f"Import failed: {result.output}"
    # Extract the playbook id from the last non-log line
    for line in result.output.splitlines():
        if "Imported playbook" in line:
            parts = line.split("'")
            if len(parts) >= 2:
                return parts[1]
    raise AssertionError(f"Could not extract playbook id from: {result.output}")


class TestUndeleteCLI:
    """D-46: End-to-end undelete via CLI."""

    def test_undelete_restores_listing(self, tmp_path: Path) -> None:
        pb_id = _unique_id("undelete-test")
        yaml_content = _make_yaml_v1(pb_id)
        imported_id = _import_yaml(tmp_path, yaml_content)
        assert imported_id == pb_id

        # Delete
        result = runner.invoke(app, ["playbook", "delete", pb_id])
        assert result.exit_code == 0, f"Delete failed: {result.output}"

        # Hidden from list
        result = runner.invoke(app, ["playbook", "list"])
        assert pb_id not in result.output

        # Undelete
        result = runner.invoke(app, ["playbook", "undelete", pb_id])
        assert result.exit_code == 0, f"Undelete failed: {result.output}"
        assert "Undeleted" in result.output

        # Visible again
        result = runner.invoke(app, ["playbook", "list"])
        assert pb_id in result.output

    def test_undelete_nonexistent(self) -> None:
        result = runner.invoke(app, ["playbook", "undelete", "no-such-pb"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_undelete_requires_id(self) -> None:
        result = runner.invoke(app, ["playbook", "undelete"])
        assert result.exit_code != 0


class TestDiffJsonCLI:
    """D-47: --json flag for playbook diff."""

    def test_diff_json_flag(self, tmp_path: Path) -> None:
        pb_id = _unique_id("diff-json")
        _import_yaml(tmp_path, _make_yaml_v1(pb_id))
        _import_yaml(tmp_path, _make_yaml_v2(pb_id))

        result = runner.invoke(app, ["playbook", "diff", pb_id, "1", "2", "--json"])
        assert result.exit_code == 0, f"Diff failed: {result.output}"

        # Output has logging noise before JSON; extract from first '{'
        json_start = result.output.index("{")
        data = json.loads(result.output[json_start:])
        assert "added_categories" in data
        assert "removed_categories" in data
        assert "changed_categories" in data
        assert "indemnification" in data["added_categories"]

    def test_diff_default_text_output(self, tmp_path: Path) -> None:
        pb_id = _unique_id("diff-text")
        _import_yaml(tmp_path, _make_yaml_v1(pb_id))
        _import_yaml(tmp_path, _make_yaml_v2(pb_id))

        result = runner.invoke(app, ["playbook", "diff", pb_id, "1", "2"])
        assert result.exit_code == 0
        assert "Changes between" in result.output
        assert "New categories:" in result.output


class TestBulkExportCLI:
    """D-48: --all flag for playbook export."""

    def test_bulk_export_all(self, tmp_path: Path) -> None:
        pb1 = _unique_id("bulk-export-1")
        pb2 = _unique_id("bulk-export-2")
        _import_yaml(tmp_path, _make_yaml_v1(pb1))
        _import_yaml(tmp_path, _make_yaml_v1(pb2))

        out_dir = tmp_path / "bulk_out"
        out_dir.mkdir()

        result = runner.invoke(app, ["playbook", "export", "--all", "--output", str(out_dir)])
        assert result.exit_code == 0, f"Bulk export failed: {result.output}"
        assert "Exported" in result.output

    def test_bulk_export_no_output(self, tmp_path: Path) -> None:
        pb1 = _unique_id("bulk-export-no-out")
        _import_yaml(tmp_path, _make_yaml_v1(pb1))

        result = runner.invoke(app, ["playbook", "export", "--all"])
        assert result.exit_code == 0
        assert "Exported" in result.output


class TestBulkDeleteCLI:
    """D-48: --all flag for playbook delete."""

    def test_bulk_delete_with_force(self, tmp_path: Path) -> None:
        pb1 = _unique_id("bulk-del-1")
        pb2 = _unique_id("bulk-del-2")
        _import_yaml(tmp_path, _make_yaml_v1(pb1))
        _import_yaml(tmp_path, _make_yaml_v1(pb2))

        result = runner.invoke(app, ["playbook", "delete", "--all", "--force"])
        assert result.exit_code == 0, f"Bulk delete failed: {result.output}"
        assert "Deleted" in result.output

        # Both gone from default list
        result = runner.invoke(app, ["playbook", "list"])
        assert pb1 not in result.output
        assert pb2 not in result.output
