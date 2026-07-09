"""Shared utilities for benchmark modules."""

import importlib.resources
import subprocess
from pathlib import Path

_FIXTURES_DIR = (
    Path(str(importlib.resources.files("openreview_cli"))).resolve().parent.parent
    / "tests"
    / "fixtures"
)


def _detect_git_commit() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.STDOUT
            )
            .decode()
            .strip()
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def _detect_git_branch() -> str | None:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.STDOUT
            )
            .decode()
            .strip()
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
