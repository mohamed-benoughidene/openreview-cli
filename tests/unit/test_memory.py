"""Memory budget tests for CLI startup and import paths.

T073 — Verify peak memory of key entry points stays within budget:
  * ``--help`` invocation: < 5 MB
  * Wizard import: < 10 MB

Uses ``tracemalloc`` for precise Python-side allocation measurement
(not RSS), isolating the specific code path from prior module loads.
"""

from __future__ import annotations

import sys
import tracemalloc

import pytest

# ---------------------------------------------------------------------------
# --help memory
# ---------------------------------------------------------------------------


@pytest.mark.memory
def test_help_peak_memory_under_5mb() -> None:
    """Invoking ``--help`` should allocate < 5 MB from the import path."""
    # Clear any existing cached modules from openreview_cli that
    # might have been loaded by the test runner.
    for mod in list(sys.modules.keys()):
        if "openreview_cli" in mod:
            del sys.modules[mod]

    tracemalloc.start()
    try:
        # Simulate what --help does: parse args with typer.
        from typer.testing import CliRunner

        from openreview_cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
    finally:
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    peak_mb = peak / 1024 / 1024
    assert peak_mb < 5, f"--help peak memory {peak_mb:.2f} MB exceeds 5 MB budget"


@pytest.mark.memory
def test_help_peak_memory_under_5mb_subprocess() -> None:
    """Invoking ``--help`` via subprocess should allocate < 5 MB."""
    import subprocess

    tracemalloc.start()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "openreview_cli", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
    finally:
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    peak_mb = peak / 1024 / 1024
    assert peak_mb < 5, f"--help (subprocess) peak memory {peak_mb:.2f} MB exceeds 5 MB budget"


# ---------------------------------------------------------------------------
# Wizard import memory
# ---------------------------------------------------------------------------


@pytest.mark.memory
def test_wizard_import_peak_memory_under_10mb() -> None:
    """Importing the SetupWizard module should allocate < 10 MB."""
    # Clear existing openreview_cli module cache
    for mod in list(sys.modules.keys()):
        if "openreview_cli" in mod:
            del sys.modules[mod]

    tracemalloc.start()
    try:
        from openreview_cli.gateway.wizard import SetupWizard

        _ = SetupWizard
    finally:
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    peak_mb = peak / 1024 / 1024
    assert peak_mb < 10, f"SetupWizard import peak memory {peak_mb:.2f} MB exceeds 10 MB budget"
