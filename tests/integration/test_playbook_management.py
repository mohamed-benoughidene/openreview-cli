"""Integration tests for US3 Set-Current (T029), US4 Delete (T034), US5 History (T040).

Tests the full CLI round-trip: import → set-current → delete → history.

Note: export and diff integration tests moved to test_playbook_export.py (T016)
and test_playbook_diff.py (T022).
"""

from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

from openreview_cli.app import app

SAMPLE_YAML = """id: integ-test-pb
mode: precheck
metadata:
  version: "1.0"
  description: Integration test playbook
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

SAMPLE_YAML_V2 = """id: integ-test-pb
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

runner = CliRunner()

_COUNTER: list[int] = [0]
_RUN_ID: str = os.urandom(2).hex()


def _unique_id(base: str) -> str:
    _COUNTER[0] += 1
    return f"{base}-{_RUN_ID}-{_COUNTER[0]}"


class TestSetCurrent:
    """T029: Integration tests for playbook set-current."""

    def _import_yaml(self, tmp_path: Path, yaml_str: str, pb_id: str) -> None:
        path = tmp_path / "import.yaml"
        path.write_text(yaml_str.replace("integ-test-pb", pb_id))
        r = runner.invoke(app, ["playbook", "import", str(path)])
        assert r.exit_code == 0, f"import failed: {r.stderr}"

    def test_set_current_version(self, tmp_path: Path) -> None:
        pb_id = _unique_id("set-cur")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)
        self._import_yaml(tmp_path, SAMPLE_YAML_V2, pb_id)

        result = runner.invoke(
            app,
            ["playbook", "set-current", pb_id, "1"],
        )
        assert result.exit_code == 0
        assert "Set current version" in result.stdout

    def test_set_current_idempotent(self, tmp_path: Path) -> None:
        pb_id = _unique_id("set-cur-idem")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)

        runner.invoke(app, ["playbook", "set-current", pb_id, "1"])
        result = runner.invoke(app, ["playbook", "set-current", pb_id, "1"])
        assert result.exit_code == 0
        assert "already current" in result.stdout

    def test_set_current_nonexistent_playbook(self) -> None:
        result = runner.invoke(
            app,
            ["playbook", "set-current", "no-such-pb", "1"],
        )
        assert result.exit_code == 1
        assert "not found" in result.stderr.lower()

    def test_set_current_bad_version(self, tmp_path: Path) -> None:
        pb_id = _unique_id("set-cur-bad")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)

        result = runner.invoke(
            app,
            ["playbook", "set-current", pb_id, "99"],
        )
        assert result.exit_code == 1
        assert "not found" in result.stderr.lower()


class TestDelete:
    """T034: Integration tests for playbook delete."""

    def _import_yaml(self, tmp_path: Path, yaml_str: str, pb_id: str) -> None:
        path = tmp_path / "import.yaml"
        path.write_text(yaml_str.replace("integ-test-pb", pb_id))
        r = runner.invoke(app, ["playbook", "import", str(path)])
        assert r.exit_code == 0, f"import failed: {r.stderr}"

    def test_delete_playbook(self, tmp_path: Path) -> None:
        pb_id = _unique_id("del")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)

        result = runner.invoke(app, ["playbook", "delete", pb_id])
        assert result.exit_code == 0
        assert "Deleted playbook" in result.stdout

    def test_delete_already_deleted(self, tmp_path: Path) -> None:
        pb_id = _unique_id("del-already")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)

        runner.invoke(app, ["playbook", "delete", pb_id])
        result = runner.invoke(app, ["playbook", "delete", pb_id])
        assert result.exit_code == 0
        assert "already deleted" in result.stdout

    def test_delete_nonexistent(self) -> None:
        result = runner.invoke(app, ["playbook", "delete", "no-such-pb"])
        assert result.exit_code == 1
        assert "not found" in result.stderr.lower()

    def test_delete_hides_from_list(self, tmp_path: Path) -> None:
        pb_id = _unique_id("del-list")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)

        # Should appear in list
        before = runner.invoke(app, ["playbook", "list"])
        assert pb_id in before.stdout

        # Delete
        runner.invoke(app, ["playbook", "delete", pb_id])

        # Should NOT appear in default list
        after = runner.invoke(app, ["playbook", "list"])
        assert pb_id not in after.stdout

    def test_delete_appears_in_list_with_include_deleted(self, tmp_path: Path) -> None:
        pb_id = _unique_id("del-include")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)

        runner.invoke(app, ["playbook", "delete", pb_id])

        result = runner.invoke(app, ["playbook", "list", "--include-deleted"])
        assert pb_id in result.stdout
        assert "deleted" in result.stdout.lower()

    def test_delete_restore_via_set_current(self, tmp_path: Path) -> None:
        pb_id = _unique_id("del-restore")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)

        runner.invoke(app, ["playbook", "delete", pb_id])

        # Restore via set-current
        result = runner.invoke(app, ["playbook", "set-current", pb_id, "1"])
        assert result.exit_code == 0
        assert "Set current version" in result.stdout

        # Should now appear in list
        listed = runner.invoke(app, ["playbook", "list"])
        assert pb_id in listed.stdout


class TestHistory:
    """T040: Integration tests for playbook history."""

    def _import_yaml(self, tmp_path: Path, yaml_str: str, pb_id: str) -> None:
        path = tmp_path / "import.yaml"
        path.write_text(yaml_str.replace("integ-test-pb", pb_id))
        r = runner.invoke(app, ["playbook", "import", str(path)])
        assert r.exit_code == 0, f"import failed: {r.stderr}"

    def test_history_multi_version(self, tmp_path: Path) -> None:
        pb_id = _unique_id("hist-multi")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)
        self._import_yaml(tmp_path, SAMPLE_YAML_V2, pb_id)

        result = runner.invoke(app, ["playbook", "history", pb_id])
        assert result.exit_code == 0
        assert "1" in result.stdout
        assert "2" in result.stdout

    def test_history_current_marker(self, tmp_path: Path) -> None:
        pb_id = _unique_id("hist-cur")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)
        self._import_yaml(tmp_path, SAMPLE_YAML_V2, pb_id)

        runner.invoke(app, ["playbook", "set-current", pb_id, "1"])
        result = runner.invoke(app, ["playbook", "history", pb_id])
        assert result.exit_code == 0
        assert "Current" in result.stdout

    def test_history_deleted_marker(self, tmp_path: Path) -> None:
        pb_id = _unique_id("hist-del")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)

        runner.invoke(app, ["playbook", "delete", pb_id])
        result = runner.invoke(app, ["playbook", "history", pb_id])
        assert result.exit_code == 0
        assert "deleted" in result.stdout.lower()

    def test_history_nonexistent_playbook(self) -> None:
        result = runner.invoke(app, ["playbook", "history", "no-such-pb"])
        assert result.exit_code == 1
        assert "not found" in result.stderr.lower()
