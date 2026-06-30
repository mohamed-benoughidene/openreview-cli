"""Integration tests for precheck command with automatic PII stripping."""

import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PDF = FIXTURES / "pdf"


def run_precheck(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "openreview_cli", "precheck", *args],
        capture_output=True,
        text=True,
    )


class TestPrecheckPii:
    def test_precheck_basic(self) -> None:
        result = run_precheck(str(PDF / "simple_contract.pdf"))
        assert result.returncode == 0
        assert "Review memo generated" in result.stdout

    def test_precheck_no_pii_flag(self) -> None:
        result = run_precheck("--no-pii", str(PDF / "simple_contract.pdf"))
        assert result.returncode == 0
        assert "Review memo generated" in result.stdout

    def test_precheck_file_not_found(self) -> None:
        result = run_precheck(str(FIXTURES / "nonexistent.pdf"))
        assert result.returncode == 1
        assert "Error" in result.stderr or "Error" in result.stdout
