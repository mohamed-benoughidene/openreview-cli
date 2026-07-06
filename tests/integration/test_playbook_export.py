"""Integration tests for Playbook Export (T016).

Tests the full CLI round-trip: import → export → verify YAML output,
version-specific export, overwrite warnings, error handling.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
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


class TestExport:
    """T016: Integration tests for playbook export."""

    def _import_yaml(self, tmp_path: Path, yaml_str: str, pb_id: str) -> Path:
        path = tmp_path / "import.yaml"
        path.write_text(yaml_str.replace("integ-test-pb", pb_id))
        r = runner.invoke(app, ["playbook", "import", str(path)])
        assert r.exit_code == 0, f"import failed: {r.stderr}"
        return path

    def test_export_valid_playbook(self, tmp_path: Path) -> None:
        pb_id = _unique_id("export-valid")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)
        out_path = tmp_path / "exported.yaml"

        result = runner.invoke(
            app,
            [
                "playbook",
                "export",
                pb_id,
                "--output",
                str(out_path),
            ],
        )
        assert result.exit_code == 0, f"export failed: {result.stderr}"
        assert out_path.exists()
        content = out_path.read_text()
        loaded = yaml.safe_load(content)
        assert loaded["id"] == pb_id
        assert len(loaded["categories"]) == 1

    def test_export_with_version(self, tmp_path: Path) -> None:
        pb_id = _unique_id("export-ver")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)
        self._import_yaml(tmp_path, SAMPLE_YAML_V2, pb_id)

        # Export version 1
        out1 = tmp_path / "v1.yaml"
        r1 = runner.invoke(
            app,
            [
                "playbook",
                "export",
                pb_id,
                "--version",
                "1",
                "--output",
                str(out1),
            ],
        )
        assert r1.exit_code == 0
        loaded1 = yaml.safe_load(out1.read_text())
        assert loaded1["id"] == pb_id
        assert len(loaded1["categories"]) == 1

        # Export version 2
        out2 = tmp_path / "v2.yaml"
        r2 = runner.invoke(
            app,
            [
                "playbook",
                "export",
                pb_id,
                "--version",
                "2",
                "--output",
                str(out2),
            ],
        )
        assert r2.exit_code == 0
        loaded2 = yaml.safe_load(out2.read_text())
        assert loaded2["id"] == pb_id
        assert len(loaded2["categories"]) == 2

    def test_export_default_version(self, tmp_path: Path) -> None:
        """Without --version, exports the current/latest version."""
        pb_id = _unique_id("export-default")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)
        self._import_yaml(tmp_path, SAMPLE_YAML_V2, pb_id)

        out = tmp_path / "default.yaml"
        result = runner.invoke(
            app,
            [
                "playbook",
                "export",
                pb_id,
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0
        loaded = yaml.safe_load(out.read_text())
        assert len(loaded["categories"]) == 2  # latest (v2)

    def test_export_nonexistent_playbook(self, tmp_path: Path) -> None:
        out = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            [
                "playbook",
                "export",
                "nonexistent-pb",
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.stderr.lower()

    def test_export_bad_version(self, tmp_path: Path) -> None:
        pb_id = _unique_id("export-bad-ver")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)
        out = tmp_path / "out.yaml"

        result = runner.invoke(
            app,
            [
                "playbook",
                "export",
                pb_id,
                "--version",
                "99",
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.stderr.lower()

    def test_export_missing_parent_dir(self, tmp_path: Path) -> None:
        pb_id = _unique_id("export-missing-dir")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)
        bad_path = tmp_path / "does_not_exist" / "out.yaml"

        result = runner.invoke(
            app,
            [
                "playbook",
                "export",
                pb_id,
                "--output",
                str(bad_path),
            ],
        )
        assert result.exit_code == 1
        assert "parent directory" in result.stderr.lower()

    def test_export_overwrite_warning(self, tmp_path: Path) -> None:
        pb_id = _unique_id("export-overwrite")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)
        out = tmp_path / "out.yaml"
        out.write_text("existing content")

        result = runner.invoke(
            app,
            [
                "playbook",
                "export",
                pb_id,
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0
        assert "Overwriting" in result.stderr
        # File should contain the exported YAML, not the old content
        loaded = yaml.safe_load(out.read_text())
        assert loaded["id"] == pb_id

    def test_export_with_force_suppresses_warning(self, tmp_path: Path) -> None:
        pb_id = _unique_id("export-force")
        self._import_yaml(tmp_path, SAMPLE_YAML, pb_id)
        out = tmp_path / "out.yaml"
        out.write_text("existing")

        result = runner.invoke(
            app,
            [
                "playbook",
                "export",
                pb_id,
                "--output",
                str(out),
                "--force",
            ],
        )
        assert result.exit_code == 0
        assert "Overwriting" not in result.stderr
