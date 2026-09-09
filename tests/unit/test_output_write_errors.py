"""Tests for D-9: clean CLI errors on --output write failures.

The precheck-family ``--output`` write sites in ``openreview_cli.app``
(``_emit_reviews``, ``compare``, ``negotiate``) previously let raw
``PermissionError``/``FileNotFoundError`` tracebacks escape. They now go
through the shared ``_write_output_file`` helper, which surfaces a clean
"Error: cannot write output file ..." message and exits with code 1.

Scenarios below use OSError subclasses that are reliable regardless of
permissions / running-as-root:
  - missing parent dir            -> FileNotFoundError
  - target path is an existing dir -> IsADirectoryError
  - valid writable file           -> writes normally

B4 (Phase 6) adds a fourth test that exercises the real Typer
``precheck review`` CLI boundary with an unwritable ``--output`` target.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from openreview_cli.app import _write_output_file, app
from openreview_cli.review.models import (
    DocMeta,
    ReviewReport,
    ReviewSummary,
)


def test_write_output_file_missing_parent_dir_clean_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Missing parent dir -> clean error on stderr, exit code 1, no traceback."""
    target = tmp_path / "missing" / "out.json"

    with pytest.raises(typer.Exit) as exc_info:
        _write_output_file(target, '{"ok": true}')

    assert exc_info.value.exit_code == 1
    stderr = capsys.readouterr().err
    assert "cannot write" in stderr
    assert str(target) in stderr
    # OS diagnostic is surfaced
    assert "No such file or directory" in stderr


def test_write_output_file_target_is_directory_clean_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Target is an existing directory -> clean error, exit code 1."""
    target = tmp_path / "out.json"
    target.mkdir()

    with pytest.raises(typer.Exit) as exc_info:
        _write_output_file(target, '{"ok": true}')

    assert exc_info.value.exit_code == 1
    stderr = capsys.readouterr().err
    assert "cannot write" in stderr
    assert str(target) in stderr
    # OS diagnostic is surfaced
    assert "Is a directory" in stderr


def test_write_output_file_valid_writable_file_writes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Valid writable target -> content written, no exception raised."""
    target = tmp_path / "out.json"
    content = '{"schema_version": "1.1.0"}'

    _write_output_file(target, content)

    assert target.read_text(encoding="utf-8") == content
    assert capsys.readouterr().err == ""


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses directory write permissions")
def test_precheck_review_unwritable_output_exits_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase-6 B4: precheck review --output <unwritable> -> clean error, no traceback.

    Proves the helper ``_write_output_file`` is wired into the real Typer
    CLI path. The test invokes ``precheck review <fixture> --format json
    --output <unwritable>`` through ``CliRunner`` (NOT the helper directly)
    and asserts the CLI exits with code 1 and surfaces the helper's
    "Error: cannot write output file ..." message on stderr, with no
    raw ``Traceback`` leak.

    The unwritable target is a file path whose parent directory is
    ``chmod 0o500`` (read+execute, no write). The OS raises
    ``PermissionError`` on ``write_text``, which the helper converts to
    ``typer.Exit(1)`` with a clean error message. The test is skipped
    when running as root because root bypasses POSIX directory write
    permissions.

    The CLI's heavy review pipeline is replaced by a synthetic
    ``ReviewReport`` returned from a stub of
    ``openreview_cli.review.run_review``. The patch targets the source
    module so the function-local ``from openreview_cli.review import
    run_review`` rebind inside the CLI command picks up the stub. The
    user config / data / log dirs are redirected to ``tmp_path``
    subdirectories both via app-module patches (for the CLI command
    body) and via XDG env vars (for deeper modules like
    ``gateway.tier_tracker`` that import the same functions at module
    load time). This isolation prevents the test from touching the
    real user ``~/.config/openreview`` directory.
    """
    # 1. Real ReviewReport constructed via the dataclass, not a dict.
    fake_report = ReviewReport(
        document=DocMeta(
            filename="nda.pdf",
            page_count=1,
            clause_count=0,
            pii_stripped=False,
        ),
        assessments=[],
        summary=ReviewSummary(amber_count=0),
        playbook_id="precheck-nda-v1",
        generated_at=datetime.now(UTC),
    )

    # 2. Stub the source module of `from openreview_cli.review import
    # run_review` inside the CLI command. Patching the source module
    # works here because the import happens at call time inside the
    # function body (app.py:1281), not at module load time, so the
    # rebind reads our stub.
    def _fake_run_review(**_kwargs: object) -> list[ReviewReport]:
        return [fake_report]

    monkeypatch.setattr("openreview_cli.review.run_review", _fake_run_review)

    # 3. Redirect the user config / data / log dirs to tmp_path. Patch
    # the app module (where the CLI command's function-local calls
    # resolve) AND set XDG env vars so deeper modules like
    # gateway.tier_tracker that imported the same functions at module
    # load time also resolve into tmp_path.
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    log_dir = tmp_path / "logs"
    for p in (config_dir, data_dir, log_dir):
        p.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg_data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg_cache"))
    import openreview_cli.app as app_mod

    monkeypatch.setattr(app_mod, "get_config_dir", lambda: config_dir)
    monkeypatch.setattr(app_mod, "get_data_dir", lambda: data_dir)
    monkeypatch.setattr(app_mod, "get_log_dir", lambda: log_dir)

    # 4. Fixture input file required by the CLI. The path must exist on
    # disk; the parser is bypassed because run_review is stubbed.
    fixture = tmp_path / "doc.pdf"
    fixture.write_text("placeholder", encoding="utf-8")

    # 5. Unwritable target: parent directory chmod 0o500 so the OS
    # denies file creation inside it.
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    target = readonly_dir / "out.json"
    os.chmod(readonly_dir, 0o500)
    try:
        runner = CliRunner()
        try:
            result = runner.invoke(
                app,
                [
                    "precheck",
                    "review",
                    str(fixture),
                    "--format",
                    "json",
                    "--output",
                    str(target),
                ],
                catch_exceptions=False,
            )
        except SystemExit as exc:
            # With catch_exceptions=False, the helper's typer.Exit(1)
            # propagates as SystemExit(1). CliRunner still captures
            # stdout/stderr into the result object via the runner
            # context manager.
            assert exc.code == 1, f"unexpected SystemExit code: {exc.code!r}"
            result = runner.invoke(
                app,
                [
                    "precheck",
                    "review",
                    str(fixture),
                    "--format",
                    "json",
                    "--output",
                    str(target),
                ],
                catch_exceptions=True,
            )
    finally:
        # Restore so subsequent tests are not affected by a read-only
        # tmp dir that pytest may try to clean up.
        os.chmod(readonly_dir, 0o755)

    # 6. Assertions: non-zero exit, helper's error message, target path
    # in output, no raw traceback.
    assert result.exit_code == 1, (
        f"expected exit 1, got {result.exit_code}\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    combined = (result.stdout or "") + (result.stderr or "")
    assert "cannot write" in combined, f"missing 'cannot write' in output:\n{combined!r}"
    assert str(target) in combined, f"missing target path in output:\n{combined!r}"
    assert "Traceback" not in combined, f"raw traceback leaked to output:\n{combined!r}"
