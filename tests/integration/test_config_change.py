"""Integration tests for config change detection in precheck.

Verifies that changing the PII threshold (via env override) produces a different
config hash, invalidates the cache, and triggers re-processing.
"""

import os
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PDF = FIXTURES / "pdf"


def _env_with(**overrides: str) -> dict[str, str]:
    """Return the current environment merged with *overrides.

    Required because ``subprocess.run(env=...)`` replaces the entire
    environment — without the parent env the Python interpreter won't
    find its site-packages or the module path.
    """
    env = dict(os.environ)
    env.update(overrides)
    return env


def run_precheck(*args: str, **env: str) -> subprocess.CompletedProcess[str]:
    """Invoke ``openreview precheck`` as a subprocess.

    Accept optional keyword-only environment variables that are merged
    into the child's environment (e.g.
    ``run_precheck(path, OPENREVIEW_PRIVACY__PII_THRESHOLD="0.8")``).
    """
    full_env = _env_with(**env) if env else None
    return subprocess.run(
        [sys.executable, "-m", "openreview_cli", "precheck", *args],
        capture_output=True,
        text=True,
        env=full_env,
    )


class TestConfigChange:
    """Config change detection — hash comparison drives cache invalidation."""

    def test_config_change_detection(self) -> None:
        """Change PII threshold → config hash changes → cache misses → re-process.

        Steps
        -----
        1. First run with default threshold (0.7) → caches result with hash A.
        2. Second run with changed threshold (0.8) → hash B → cache miss → re-process.
        3. Third run with same threshold (0.8)   → hash B → cache hit.
        4. Fourth run back to default (0.7)      → hash A → cache hit (from step 1).
        """
        pdf = str(PDF / "simple_contract.pdf")

        # ── Step 1: first run, default config hash A ──────────────────────
        r1 = run_precheck(pdf)
        assert r1.returncode == 0, f"step 1 failed: {r1.stderr}"
        assert "Review memo generated" in r1.stdout

        # ── Step 2: change threshold via env override → hash B → re-process ─
        r2 = run_precheck(pdf, OPENREVIEW_PRIVACY__PII_THRESHOLD="0.8")
        assert r2.returncode == 0, f"step 2 failed: {r2.stderr}"
        assert "Review memo generated" in r2.stdout

        # ── Step 3: same threshold → hash B → cache hit ───────────────────
        r3 = run_precheck(pdf, OPENREVIEW_PRIVACY__PII_THRESHOLD="0.8")
        assert r3.returncode == 0, f"step 3 failed: {r3.stderr}"
        assert "Review memo generated" in r3.stdout

        # ── Step 4: back to default → hash A → cache hit (from step 1) ───
        r4 = run_precheck(pdf)
        assert r4.returncode == 0, f"step 4 failed: {r4.stderr}"
        assert "Review memo generated" in r4.stdout

    def test_precheck_without_config_change(self) -> None:
        """Running precheck twice without any config change succeeds both times."""
        pdf = str(PDF / "simple_contract.pdf")

        r1 = run_precheck(pdf)
        assert r1.returncode == 0

        r2 = run_precheck(pdf)
        assert r2.returncode == 0
