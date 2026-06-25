import json
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PDF = FIXTURES / "pdf"


def run_openreview(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "openreview_cli", "parse", *args],
        capture_output=True,
        text=True,
    )


class TestParseCommand:
    def test_parse_without_path_shows_help(self) -> None:
        result = run_openreview()
        assert result.returncode != 0

    def test_parse_simple_contract(self) -> None:
        result = run_openreview(str(PDF / "simple_contract.pdf"))
        assert result.returncode == 0
        assert "clause-" in result.stdout

    def test_parse_json_output(self) -> None:
        result = run_openreview("--format", "json", str(PDF / "simple_contract.pdf"))
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "id" in data[0]
        assert "text" in data[0]

    def test_parse_summary(self) -> None:
        result = run_openreview("--summary", str(PDF / "simple_contract.pdf"))
        assert result.returncode == 0
        assert "Parsed" in result.stdout
        assert "clauses" in result.stdout

    def test_parse_non_existent_file(self) -> None:
        result = run_openreview(str(FIXTURES / "nonexistent.pdf"))
        assert result.returncode == 8
        assert "No file found" in result.stderr

    def test_parse_unsupported_format(self) -> None:
        result = run_openreview(str(FIXTURES / "test.txt"))
        assert result.returncode == 8
        assert "supported" in result.stderr.lower()
