from pathlib import Path

import pytest

from openreview_cli.config.paths import (
    get_cache_dir,
    get_config_dir,
    get_data_dir,
    get_log_dir,
    get_review_dir,
)


def test_get_config_dir_respects_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    base = Path("/tmp/test-xdg-config")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(base))
    result = get_config_dir()
    assert str(base) in str(result)
    assert "openreview" in str(result).lower()


def test_get_config_dir_creates_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    base = Path("/tmp/test-config-create")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(base))
    result = get_config_dir()
    assert result.exists()
    assert result.is_dir()


def test_get_data_dir_respects_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    base = Path("/tmp/test-xdg-data")
    monkeypatch.setenv("XDG_DATA_HOME", str(base))
    result = get_data_dir()
    assert str(base) in str(result)
    assert "openreview" in str(result).lower()


def test_get_data_dir_creates_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    base = Path("/tmp/test-data-create")
    monkeypatch.setenv("XDG_DATA_HOME", str(base))
    result = get_data_dir()
    assert result.exists()
    assert result.is_dir()


def test_get_cache_dir_respects_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    base = Path("/tmp/test-xdg-cache")
    monkeypatch.setenv("XDG_CACHE_HOME", str(base))
    result = get_cache_dir()
    assert str(base) in str(result)
    assert "openreview" in str(result).lower()


def test_get_cache_dir_creates_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    base = Path("/tmp/test-cache-create")
    monkeypatch.setenv("XDG_CACHE_HOME", str(base))
    result = get_cache_dir()
    assert result.exists()
    assert result.is_dir()


def test_get_log_dir_respects_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    base = Path("/tmp/test-xdg-log")
    monkeypatch.setenv("XDG_LOG_HOME", str(base))
    result = get_log_dir()
    assert str(base) in str(result) or "log" in str(result).lower()


def test_get_log_dir_creates_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    base = Path("/tmp/test-log-create")
    monkeypatch.setenv("XDG_LOG_HOME", str(base))
    result = get_log_dir()
    assert result.exists()
    assert result.is_dir()


def test_get_review_dir_nests_under_data(monkeypatch: pytest.MonkeyPatch) -> None:
    base = Path("/tmp/test-review-dir")
    monkeypatch.setenv("XDG_DATA_HOME", str(base))
    result = get_review_dir("abc-123")
    assert str(base) in str(result)
    assert result.name == "abc-123"
    assert result.parent.name == "reviews"


def test_all_dirs_are_unique(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/uniq-cfg")
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/uniq-data")
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/uniq-cache")
    monkeypatch.setenv("XDG_LOG_HOME", "/tmp/uniq-log")
    dirs = {get_config_dir(), get_data_dir(), get_cache_dir(), get_log_dir()}
    assert len(dirs) == 4, "All four directories should be distinct"
