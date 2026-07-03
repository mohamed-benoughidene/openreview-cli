"""Integration tests for the `compare` CLI flags via subprocess.

Bypasses Typer's CliRunner (which cannot pass positional args through
the precheck callback's optional positional `document_path` arg).
Uses subprocess to mirror the pattern in test_parse_command.py.

Unblocks spec 014 deferred tasks: T050, T051, T052, T053, T055.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PDF = FIXTURES / "pdf"


def run_compare(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke ``openreview precheck compare`` via subprocess.

    This avoids Typer's CliRunner bug where the precheck callback's
    optional positional ``document_path`` steals subcommand args.
    """
    return subprocess.run(
        [sys.executable, "-m", "openreview_cli", "precheck", "compare", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# T050 — --align-only
# ---------------------------------------------------------------------------


class TestAlignOnly:
    """--align-only: parse + alignment only, no inference."""

    @pytest.mark.integration
    def test_align_only_produces_alignment_output(self) -> None:
        """T050: --align-only produces experimental banner and doc info, exits 0."""
        a = str(PDF / "simple_contract.pdf")
        b = str(PDF / "simple_contract.pdf")
        result = run_compare(a, b, "--align-only")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        # Output should show the experimental disclaimer and document info
        assert "experimental" in result.stdout.lower()
        assert "party a" in result.stdout.lower()


# ---------------------------------------------------------------------------
# T051 — --format json --output
# ---------------------------------------------------------------------------


class TestFormatJsonOutput:
    """--format json --output: structured JSON written to file."""

    @pytest.mark.integration
    def test_format_json_writes_valid_file(self) -> None:
        """T051: --format json --output writes valid JSON to file."""
        a = str(PDF / "simple_contract.pdf")
        b = str(PDF / "simple_contract.pdf")
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            out_path = f.name
        try:
            result = run_compare(a, b, "--align-only", "--format", "json", "--output", out_path)
            assert result.returncode == 0, f"stderr: {result.stderr}"
            data = json.loads(Path(out_path).read_text())
            assert "schema_version" in data
            assert "document_a" in data
            assert "document_b" in data
        finally:
            Path(out_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# T052 — --confidence-threshold
# ---------------------------------------------------------------------------


class TestConfidenceThreshold:
    """--confidence-threshold: custom Amber boundary."""

    @pytest.mark.integration
    def test_confidence_threshold_accepted(self) -> None:
        """T052: --confidence-threshold 0.8 is accepted and routed."""
        a = str(PDF / "simple_contract.pdf")
        b = str(PDF / "simple_contract.pdf")
        result = run_compare(a, b, "--align-only", "--confidence-threshold", "0.8")
        assert result.returncode == 0, f"stderr: {result.stderr}"

    @pytest.mark.integration
    def test_confidence_threshold_out_of_range_rejected(self) -> None:
        """T052b: --confidence-threshold 1.5 is rejected."""
        a = str(PDF / "simple_contract.pdf")
        b = str(PDF / "simple_contract.pdf")
        result = run_compare(a, b, "--confidence-threshold", "1.5")
        assert result.returncode != 0
        assert "0.0 and 1.0" in result.stderr


# ---------------------------------------------------------------------------
# T053 — --conservative
# ---------------------------------------------------------------------------


class TestConservative:
    """--conservative: shortcut for threshold 0.8 + verbose."""

    @pytest.mark.integration
    def test_conservative_accepted(self) -> None:
        """T053: --conservative is accepted and routed."""
        a = str(PDF / "simple_contract.pdf")
        b = str(PDF / "simple_contract.pdf")
        result = run_compare(a, b, "--align-only", "--conservative")
        assert result.returncode == 0, f"stderr: {result.stderr}"

    @pytest.mark.integration
    def test_conservative_and_threshold_mutually_exclusive(self) -> None:
        """T053b: --conservative and --confidence-threshold together → exit 3."""
        a = str(PDF / "simple_contract.pdf")
        b = str(PDF / "simple_contract.pdf")
        result = run_compare(a, b, "--conservative", "--confidence-threshold", "0.8")
        assert result.returncode == 3
        assert "mutually exclusive" in result.stderr


# ---------------------------------------------------------------------------
# T055 — --verbose
# ---------------------------------------------------------------------------


class TestVerbose:
    """--verbose: RCBSF taxonomy and rationale."""

    @pytest.mark.integration
    def test_verbose_accepted(self) -> None:
        """T055: --verbose is accepted and routed."""
        a = str(PDF / "simple_contract.pdf")
        b = str(PDF / "simple_contract.pdf")
        result = run_compare(a, b, "--align-only", "--verbose")
        assert result.returncode == 0, f"stderr: {result.stderr}"
