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
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from openreview_cli.app import _write_output_file


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
