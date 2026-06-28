"""Unit tests for the first-run detection module.

Tests for ``is_first_run()`` and ``mark_first_run_done()`` in
``openreview_cli.config.first_run``.
"""

from __future__ import annotations

import threading
from pathlib import Path

from openreview_cli.config.first_run import is_first_run, mark_first_run_done

# ---------------------------------------------------------------------------
# is_first_run
# ---------------------------------------------------------------------------


def test_is_first_run_true_when_no_config(tmp_path: Path) -> None:
    """is_first_run returns True when the config file does not exist."""
    config_path = tmp_path / "config.yml"
    assert is_first_run(config_path) is True


def test_is_first_run_false_when_config_exists(tmp_path: Path) -> None:
    """is_first_run returns False when the config file exists."""
    config_path = tmp_path / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("version: 1\n")
    assert is_first_run(config_path) is False


def test_is_first_run_true_when_dir_does_not_exist(tmp_path: Path) -> None:
    """is_first_run returns True when the parent directory does not exist."""
    config_path = tmp_path / "nonexistent" / "dir" / "config.yml"
    assert is_first_run(config_path) is True


# ---------------------------------------------------------------------------
# mark_first_run_done
# ---------------------------------------------------------------------------


def test_mark_first_run_done_creates_config_file(tmp_path: Path) -> None:
    """mark_first_run_done creates the config file."""
    config_path = tmp_path / "config.yml"
    mark_first_run_done(config_path)
    assert config_path.exists()
    assert config_path.is_file()


def test_mark_first_run_done_creates_parent_directory(tmp_path: Path) -> None:
    """mark_first_run_done creates parent directories as needed."""
    config_path = tmp_path / "a" / "b" / "c" / "config.yml"
    mark_first_run_done(config_path)
    assert config_path.exists()


def test_mark_first_run_done_writes_minimal_config(tmp_path: Path) -> None:
    """mark_first_run_done writes a minimal YAML config with version key."""
    config_path = tmp_path / "config.yml"
    mark_first_run_done(config_path)
    import yaml

    data = yaml.safe_load(config_path.read_text())
    assert isinstance(data, dict)
    assert data.get("version") == 1


def test_mark_first_run_done_idempotent(tmp_path: Path) -> None:
    """Calling mark_first_run_done twice does not error."""
    config_path = tmp_path / "config.yml"
    mark_first_run_done(config_path)
    mark_first_run_done(config_path)  # second call should not raise
    assert config_path.exists()


# ---------------------------------------------------------------------------
# Parallel safety
# ---------------------------------------------------------------------------


def test_mark_first_run_done_parallel_safety(tmp_path: Path) -> None:
    """Two threads racing to mark first run done should both succeed."""
    config_path = tmp_path / "config.yml"
    errors: list[Exception] = []

    def _mark() -> None:
        try:
            mark_first_run_done(config_path)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_mark) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"unexpected errors: {errors}"
    assert config_path.exists()
    import yaml

    data = yaml.safe_load(config_path.read_text())
    assert data.get("version") == 1
