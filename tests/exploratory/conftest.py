"""Shared fixtures for the exploratory probes.

Every CLI probe redirects platformdirs to a throwaway tmp tree so the real
user data/config/log directories are never touched by ``_init``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from openreview_cli.app import app


@pytest.fixture
def isolated_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point platformdirs at a fresh tmp tree and return the tmp root."""
    for var in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(var, str(tmp_path / var.lower()))
    monkeypatch.delenv("OPENREVIEW_OUTPUT_DIR", raising=False)
    return tmp_path


@pytest.fixture
def invoke() -> Callable[[list[str]], Result]:
    """Return a CliRunner-backed ``invoke(args)`` callable."""
    runner = CliRunner()
    return lambda args: runner.invoke(app, args)
