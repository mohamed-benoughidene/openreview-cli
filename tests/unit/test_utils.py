import os
from pathlib import Path

import pytest

from openreview_cli.gateway.utils import atomic_write


def test_atomic_write_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "subdir" / "config.yml"
    atomic_write(target, "key: value\n")
    assert target.exists()
    assert target.read_text() == "key: value\n"


def test_atomic_write_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "c" / "config.yml"
    atomic_write(target, "nested")
    assert target.parent.exists()
    assert target.read_text() == "nested"


def test_atomic_write_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "data.txt"
    target.write_text("old content")
    atomic_write(target, "new content")
    assert target.read_text() == "new content"


def test_atomic_write_cleans_up_temp_on_error(tmp_path: Path) -> None:
    target = tmp_path / "write_protected" / "config.yml"
    target.parent.mkdir()
    target.parent.chmod(0o444)

    with pytest.raises(PermissionError):
        atomic_write(target, "fail")

    temp_files = list(tmp_path.rglob("*.tmp"))
    assert len(temp_files) == 0, f"Temp file not cleaned up: {temp_files}"
    target.parent.chmod(0o755)


def test_atomic_write_empty_string(tmp_path: Path) -> None:
    target = tmp_path / "empty.txt"
    atomic_write(target, "")
    assert target.exists()
    assert target.read_text() == ""


def test_atomic_write_cleanup_on_rename_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "config.yml"

    def failing_rename(*args: object, **kwargs: object) -> None:
        raise OSError("Rename failed")

    monkeypatch.setattr(os, "rename", failing_rename)

    with pytest.raises(OSError, match="Rename failed"):
        atomic_write(target, "content")

    temp_files = list(tmp_path.rglob("*.tmp"))
    assert len(temp_files) == 0, f"Temp file not cleaned up: {temp_files}"
    assert not target.exists()
