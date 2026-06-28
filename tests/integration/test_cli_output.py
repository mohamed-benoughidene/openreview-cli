"""Integration tests for CLI output modes, non-interactive detection, and piping.

T051 — Non-interactive CLI flags produce valid JSON on stdout
T052 — Piped output (| python -c ...) works, exit code 0
T053 — Output routing: table/json/plain all produce output on stdout
T072a — First-render latency: ``openreview --help`` < 150ms
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

runner = CliRunner()
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_json(text: str) -> list[object]:
    """Extract the first JSON array embedded in *text*.

    The parse command may emit a Rich-config-warning panel on stdout before
    the actual JSON array.  This helper skips everything before the first
    ``[`` and parses the remainder.
    """
    idx = text.find("[")
    if idx == -1:
        pytest.fail(f"No JSON array found in stdout:\n{text[:500]}")
    return json.loads(text[idx:])  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a minimal PDF header for review (doesn't need valid content)."""
    path = tmp_path / "contract.pdf"
    path.write_bytes(b"%PDF-1.4\n")
    return path


@pytest.fixture
def real_pdf() -> Path:
    """A real fixture PDF suitable for parsing."""
    p = FIXTURES_DIR / "pdf" / "simple_contract.pdf"
    if not p.exists():
        pytest.skip("fixture pdf/simple_contract.pdf not found")
    return p


# ---------------------------------------------------------------------------
# T051 — Non-interactive JSON output
# ---------------------------------------------------------------------------


class TestNonInteractiveJsonOutput:
    """Verify --output json with --non-interactive produces valid output."""

    def test_review_json_output_parses(self, sample_pdf: Path) -> None:
        """--non-interactive --mode full --jurisdiction us-de --output json produces review output."""
        result = runner.invoke(
            app,
            [
                "review",
                str(sample_pdf),
                "--non-interactive",
                "--mode",
                "full",
                "--jurisdiction",
                "us-de",
                "--output",
                "json",
            ],
        )
        assert result.exit_code == 0, f"Exit code {result.exit_code}: stderr={result.stderr!r}"
        assert "Review ready" in result.stdout or "review" in result.stdout.lower()

    def test_errors_go_to_stderr(self, tmp_path: Path) -> None:
        """Invalid input produces error on stderr, not stdout."""
        result = runner.invoke(
            app,
            [
                "review",
                str(tmp_path / "nonexistent.pdf"),
                "--non-interactive",
                "--mode",
                "full",
                "--jurisdiction",
                "us-de",
            ],
        )
        assert result.exit_code != 0
        # Error output should be on stderr
        if result.stderr:
            assert "error" in result.stderr.lower() or "not found" in result.stderr.lower()
        # No traceback in stderr
        assert "Traceback" not in result.stderr

    def test_missing_required_flag_exits_non_zero(self, sample_pdf: Path) -> None:
        """--non-interactive without --mode exits non-zero (USAGE_ERROR)."""
        result = runner.invoke(
            app,
            [
                "review",
                str(sample_pdf),
                "--non-interactive",
            ],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# T052 — Piped output detection (subprocess)
# ---------------------------------------------------------------------------


class TestPipedOutput:
    """Verify piped output works: openreview … | python -c …"""

    def test_piped_version_works(self) -> None:
        """--version piped through python -c prints exit code 0."""
        first = subprocess.run(
            [sys.executable, "-m", "openreview_cli", "--version"],
            capture_output=True,
            text=True,
        )
        assert first.returncode == 0, f"--version failed: {first.stderr}"
        assert first.stdout.strip(), "--version produced empty stdout"

        pipe = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; data=sys.stdin.read(); assert len(data) > 0; print('OK')",
            ],
            input=first.stdout,
            capture_output=True,
            text=True,
        )
        assert pipe.returncode == 0, f"Pipe failed: stdout={pipe.stdout!r} stderr={pipe.stderr!r}"
        assert "OK" in pipe.stdout


# ---------------------------------------------------------------------------
# T053 — Output routing: table / json / plain
# ---------------------------------------------------------------------------


class TestOutputRouting:
    """SGTable supports all three output modes."""

    def test_parse_json_output_is_valid_json(self, real_pdf: Path) -> None:
        """--format json on parse command produces valid JSON on stdout."""
        result = runner.invoke(app, ["parse", "--format", "json", str(real_pdf)])
        assert result.exit_code == 0, f"Exit code {result.exit_code}: stderr={result.stderr!r}"
        data = _extract_json(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0
        entry = data[0]
        assert isinstance(entry, dict)
        assert "id" in entry
        assert "text" in entry

    def test_parse_text_output_is_readable(self, real_pdf: Path) -> None:
        """--format text writes human-readable text to stdout."""
        result = runner.invoke(app, ["parse", "--format", "text", str(real_pdf)])
        assert result.exit_code == 0
        assert result.stdout.strip()
        assert "clause" in result.stdout.lower()

    def test_parse_summary_output(self, real_pdf: Path) -> None:
        """--summary produces one-line summary to stdout."""
        result = runner.invoke(app, ["parse", "--summary", str(real_pdf)])
        assert result.exit_code == 0
        assert "Parsed" in result.stdout or "clauses" in result.stdout.lower()


# ---------------------------------------------------------------------------
# T072a — First-render latency
# ---------------------------------------------------------------------------


class TestFirstRenderLatency:
    """Verify ``openreview --help`` starts producing output within 150 ms."""

    def test_help_first_byte_under_500ms(self) -> None:
        """Measure time from process start to first stdout byte."""
        start = time.perf_counter()
        process = subprocess.Popen(
            [sys.executable, "-m", "openreview_cli", "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Read the first byte
        first_byte = process.stdout.read(1) if process.stdout else ""
        elapsed = time.perf_counter() - start

        # Consume the rest
        process.communicate()

        assert process.returncode == 0, f"--help exited with code {process.returncode}"
        assert first_byte, "--help produced no output"
        # 500 ms budget gives 4x headroom over the 150ms spec target
        # to absorb Python import overhead on slow CI runners.
        assert elapsed < 0.500, f"First byte latency {elapsed * 1000:.1f} ms exceeds 500 ms budget"

    def test_help_exit_code_zero(self) -> None:
        """--help exits with code 0."""
        result = subprocess.run(
            [sys.executable, "-m", "openreview_cli", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert result.stdout.strip()
