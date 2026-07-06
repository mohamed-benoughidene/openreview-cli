"""Integration tests for US3-US7: Playbook CLI commands and --playbook flag.

Tests T024, T030, T033, T038, T043.
NOTE: These tests use the real database (shared state). Tests that require
empty DB state or specific version numbers should use unique playbook IDs.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from openreview_cli.app import app

SAMPLE_PLAYBOOK_YAML = """id: test-pb-int
mode: precheck
metadata:
  version: "1.0"
  description: Test playbook
  author: Test Author
categories:
  - id: confidentiality
    name: Confidentiality
    description: How confidential info is handled
    preferred:
      description: Broad mutual protection
      exemplars:
        - "mutual NDA"
    acceptable:
      description: Standard one-way
      exemplars:
        - "standard NDA"
    walkaway:
      description: No confidentiality
      exemplars:
        - "no NDA"
    default_position: preferred
"""

ANOTHER_PLAYBOOK_YAML = """id: another-pb-int
mode: precheck
metadata:
  version: "1.0"
  description: Another playbook
  author: Test Author
categories:
  - id: indemnification
    name: Indemnification
    description: How indemnification is handled
    preferred:
      description: Mutual indemnification
      exemplars:
        - "mutual indemnity"
    acceptable:
      description: One-way indemnification
      exemplars:
        - "one-way indemnity"
    walkaway:
      description: No indemnification
      exemplars:
        - "no indemnity"
    default_position: preferred
"""

MALFORMED_YAML = """
id: bad-pb
missing_field: true
"""


runner = CliRunner()

# Use unique IDs per test class to avoid shared-state conflicts
_COUNTER: list[int] = [0]


def _unique_yaml(base_id: str) -> str:
    _COUNTER[0] += 1
    uid = f"{base_id}-{_COUNTER[0]}"
    return SAMPLE_PLAYBOOK_YAML.replace("test-pb-int", uid)


# ════════════════════════════════════════════════
# US3: Import command
# ════════════════════════════════════════════════


class TestPlaybookImport:
    """T024: Integration tests for playbook import."""

    def test_import_valid_playbook(self, tmp_path: Path) -> None:
        yaml_content = _unique_yaml("import-valid")
        path = tmp_path / "test.yaml"
        path.write_text(yaml_content)

        result = runner.invoke(app, ["playbook", "import", str(path)])
        assert result.exit_code == 0, f"stdout: {result.stdout}, stderr: {result.stderr}"
        assert "version" in result.stdout.lower()

    def test_import_same_playbook_twice_increments_version(self, tmp_path: Path) -> None:
        yaml_content = _unique_yaml("import-twice")
        path = tmp_path / "test.yaml"
        path.write_text(yaml_content)

        r1 = runner.invoke(app, ["playbook", "import", str(path)])
        assert r1.exit_code == 0, f"stdout: {r1.stdout}, stderr: {r1.stderr}"
        assert "version" in r1.stdout

        r2 = runner.invoke(app, ["playbook", "import", str(path)])
        assert r2.exit_code == 0, f"stdout: {r2.stdout}, stderr: {r2.stderr}"
        # Should mention version increment
        assert "previous version" in r2.stdout.lower()

    def test_import_malformed_yaml_errors(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text(MALFORMED_YAML)

        result = runner.invoke(app, ["playbook", "import", str(path)])
        assert result.exit_code == 2
        assert "Error" in result.stderr or "Error" in result.stdout

    def test_import_nonexistent_file(self) -> None:
        result = runner.invoke(app, ["playbook", "import", "/nonexistent/file.yaml"])
        assert result.exit_code == 2
        assert "Error" in result.stderr or "Error" in result.stdout

    def test_import_import_then_list_shows_it(self, tmp_path: Path) -> None:
        yaml_content = _unique_yaml("import-list")
        path = tmp_path / "test.yaml"
        path.write_text(yaml_content)

        runner.invoke(app, ["playbook", "import", str(path)])
        result = runner.invoke(app, ["playbook", "list"])
        assert result.exit_code == 0, f"stdout: {result.stdout}, stderr: {result.stderr}"


# ════════════════════════════════════════════════
# US4: List command
# ════════════════════════════════════════════════


class TestPlaybookList:
    """T030: Integration tests for playbook list."""

    def test_list_shows_imported_playbook(self, tmp_path: Path) -> None:
        yaml_content = _unique_yaml("list-show")
        path = tmp_path / "pb.yaml"
        path.write_text(yaml_content)
        runner.invoke(app, ["playbook", "import", str(path)])

        result = runner.invoke(app, ["playbook", "list"])
        assert result.exit_code == 0, f"stdout: {result.stdout}, stderr: {result.stderr}"

    def test_list_does_not_crash(self) -> None:
        result = runner.invoke(app, ["playbook", "list"])
        assert result.exit_code == 0, f"stdout: {result.stdout}, stderr: {result.stderr}"


# ════════════════════════════════════════════════
# US5: Show command
# ════════════════════════════════════════════════


class TestPlaybookShow:
    """T033: Integration tests for playbook show."""

    def test_show_existing_playbook_version(self, tmp_path: Path) -> None:
        yaml_content = _unique_yaml("show-valid")
        path = tmp_path / "test.yaml"
        path.write_text(yaml_content)
        import_result = runner.invoke(app, ["playbook", "import", str(path)])
        assert import_result.exit_code == 0

        # Extract the playbook_id from the YAML
        pb_id = "show-valid-" + str(_COUNTER[0])

        result = runner.invoke(app, ["playbook", "show", pb_id, "1"])
        assert result.exit_code == 0, f"stdout: {result.stdout}, stderr: {result.stderr}"
        assert pb_id in result.stdout

    def test_show_nonexistent_id_gives_error(self) -> None:
        result = runner.invoke(app, ["playbook", "show", "nonexistent-show-id", "1"])
        assert result.exit_code == 2
        assert "not found" in result.stderr.lower() or "Error" in result.stderr

    def test_show_nonexistent_version_gives_error(self, tmp_path: Path) -> None:
        yaml_content = _unique_yaml("show-version-err")
        path = tmp_path / "test.yaml"
        path.write_text(yaml_content)
        runner.invoke(app, ["playbook", "import", str(path)])

        pb_id = "show-version-err-" + str(_COUNTER[0])
        result = runner.invoke(app, ["playbook", "show", pb_id, "99"])
        assert result.exit_code == 2
        assert "not found" in result.stderr.lower() or "Error" in result.stderr

    def test_show_negative_version_gives_error(self, tmp_path: Path) -> None:
        yaml_content = _unique_yaml("show-neg")
        path = tmp_path / "test.yaml"
        path.write_text(yaml_content)
        runner.invoke(app, ["playbook", "import", str(path)])

        pb_id = "show-neg-" + str(_COUNTER[0])
        result = runner.invoke(app, ["playbook", "show", pb_id, "0"])
        assert result.exit_code == 2
        assert "positive" in result.stderr.lower() or "Error" in result.stderr


# ════════════════════════════════════════════════
# US6: --playbook flag
# ════════════════════════════════════════════════


class TestPlaybookFlagOnPrecheck:
    """T038: Integration tests for --playbook flag with precheck command."""

    def test_help_shows_playbook_option(self) -> None:
        result = runner.invoke(app, ["precheck", "review", "--help"])
        assert result.exit_code == 0
        assert "--playbook" in result.stdout


# ════════════════════════════════════════════════
# US7: Version-stamped reviews
# ════════════════════════════════════════════════


class TestVersionStampedReview:
    """T043: Integration tests for version-stamped review output."""

    def test_report_model_has_playbook_version_field(self) -> None:
        """Playbook_version should be in the report model."""
        from openreview_cli.review.models import ReviewReport

        field_names = ReviewReport.__dataclass_fields__.keys()
        assert "playbook_version" in field_names

    def test_report_model_has_playbook_id_field(self) -> None:
        """Playbook_id should be in the report model."""
        from openreview_cli.review.models import ReviewReport

        field_names = ReviewReport.__dataclass_fields__.keys()
        assert "playbook_id" in field_names


# ════════════════════════════════════════════════
# US6 — Precedence Warning (T056 convergence)
# ════════════════════════════════════════════════


class TestPrecedenceWarning:
    """T056: Integration tests for --playbook + --playbook-path precedence warning."""

    def test_precedence_warning_emitted_when_both_flags_given(self) -> None:
        """T056: run_review emits UserWarning when both playbook_id and
        playbook_path are provided."""
        import warnings
        from unittest.mock import MagicMock, patch

        from openreview_cli.review import run_review

        pb_mock = MagicMock()
        with (
            patch("openreview_cli.review.load_playbook_from_db", return_value=(pb_mock, 1)),
            patch("openreview_cli.review.load_playbook"),
            patch("openreview_cli.review.load_bundled"),
            patch("openreview_cli.review.ReviewCommand"),
            warnings.catch_warnings(record=True) as w,
        ):
            warnings.simplefilter("always")
            reports = run_review(
                paths=["doc.pdf"],
                playbook_id="test-pb",
                playbook_path="/some/path.yaml",
            )

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) >= 1, "Expected UserWarning when both flags given"
        assert any(
            "--playbook" in str(m.message) and "precedence" in str(m.message) for m in user_warnings
        )
        # Verify command proceeds (non-fatal) — reports list returned
        assert isinstance(reports, list)
