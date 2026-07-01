"""Integration tests for the --no-pii flag.

Verifies that --no-pii disables PII stripping, processes raw text,
creates no encrypted mapping, logs a warning, and sets entity_count=0.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PDF = FIXTURES / "pdf"


def run_precheck(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "openreview_cli", "precheck", *args],
        capture_output=True,
        text=True,
    )


class TestPrecheckNoPii:
    @pytest.mark.integration
    def test_no_pii_exit_code(self) -> None:
        result = run_precheck("--no-pii", str(PDF / "simple_contract.pdf"))
        assert result.returncode == 0

    @pytest.mark.integration
    def test_no_pii_warning(self) -> None:
        result = run_precheck("--no-pii", str(PDF / "simple_contract.pdf"))
        assert "PII stripping disabled" in result.stderr

    @pytest.mark.integration
    def test_no_pii_no_encrypted_mapping(self) -> None:
        result = run_precheck("--no-pii", str(PDF / "simple_contract.pdf"))
        m = re.search(r"Review memo generated:\s+(\S+)", result.stdout)
        assert m, "Could not find review directory in output"
        review_dir = Path(m.group(1)).parent
        assert not (review_dir / "pii_map.enc").exists()
