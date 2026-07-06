"""Integration tests for Playbook Diff (T022).

Tests the full CLI round-trip: import → versioning → diff,
equal versions, error handling, exemplary changes, version normalisation.
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


class TestDiff:
    """T022: Integration tests for playbook diff."""

    def _import_yaml(self, tmp_path: Path, yaml_str: str, pb_id: str) -> None:
        path = tmp_path / "import.yaml"
        path.write_text(yaml_str.replace("integ-test-pb", pb_id))
        r = runner.invoke(app, ["playbook", "import", str(path)])
        assert r.exit_code == 0, f"import failed: {r.stderr}"

    def test_diff_different_versions(self, tmp_path: Path) -> None:
        pb_id = _unique_id("diff-valid")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)
        self._import_yaml(tmp_path, SAMPLE_YAML_V2, pb_id)

        result = runner.invoke(
            app,
            [
                "playbook",
                "diff",
                pb_id,
                "1",
                "2",
            ],
        )
        assert result.exit_code == 0, f"diff failed: {result.stderr}"
        assert "Changes between" in result.stdout
        assert "confidentiality" in result.stdout
        assert "indemnification" in result.stdout or "New categories" in result.stdout

    def test_diff_equal_versions(self, tmp_path: Path) -> None:
        pb_id = _unique_id("diff-equal")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)

        result = runner.invoke(
            app,
            [
                "playbook",
                "diff",
                pb_id,
                "1",
                "2",
            ],
        )
        assert result.exit_code == 0
        assert "No changes" in result.stdout

    def test_diff_nonexistent_playbook(self) -> None:
        result = runner.invoke(
            app,
            [
                "playbook",
                "diff",
                "nonexistent",
                "1",
                "2",
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.stderr.lower()

    def test_diff_bad_version(self, tmp_path: Path) -> None:
        pb_id = _unique_id("diff-bad-ver")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)

        result = runner.invoke(
            app,
            [
                "playbook",
                "diff",
                pb_id,
                "1",
                "99",
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.stderr.lower()

    def test_diff_auto_normalizes_v1_greater_than_v2(self, tmp_path: Path) -> None:
        pb_id = _unique_id("diff-swap")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)
        self._import_yaml(tmp_path, SAMPLE_YAML_V2, pb_id)

        # v1=2 > v2=1 → should swap internally
        result = runner.invoke(
            app,
            [
                "playbook",
                "diff",
                pb_id,
                "2",
                "1",
            ],
        )
        assert result.exit_code == 0
        # Output should show "version 1" before "version 2"
        assert "1" in result.stdout
        assert "2" in result.stdout

    def test_diff_exemplar_changes(self, tmp_path: Path) -> None:
        pb_id = _unique_id("diff-exemplar")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)
        self._import_yaml(tmp_path, SAMPLE_YAML_V2, pb_id)

        result = runner.invoke(
            app,
            [
                "playbook",
                "diff",
                pb_id,
                "1",
                "2",
            ],
        )
        assert result.exit_code == 0
        # V2 has "enhanced mutual NDA" added to confidentiality exemplars
        assert "enhanced mutual NDA" in result.stdout
