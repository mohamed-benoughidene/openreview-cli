"""Benchmark baseline tests (Group B — D-76).

Tests:
  - T-B-01: baseline --help command exists
  - T-B-02: Mock baseline produces 51 results (17 modes x 3 datasets)
  - T-B-03: BaselineResult schema validation
  - T-B-04: --save-baseline --format json --output writes valid JSON file
  - T-B-05: BaselineReport JSON schema validation
  - T-B-06: --save-baseline without --format json errors
  - T-B-07: Per-mode grouping in BaselineReport
"""

import json
import subprocess
import sys
from pathlib import Path

from openreview_cli.benchmark.baseline import (
    BaselineReport,
    BaselineResult,
    run_mock_baseline,
)
from openreview_cli.benchmark.cli import VALID_MODES


class TestBaselineCommand:
    """T-B-01: baseline --help command exists."""

    def test_baseline_command_exists(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "openreview_cli",
                "benchmark",
                "baseline",
                "--help",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Run accuracy baseline" in result.stdout


class TestMockBaseline:
    """T-B-02, T-B-03: mock baseline result count and schema."""

    def test_mock_baseline_produces_51_results(self) -> None:
        results = run_mock_baseline(list(VALID_MODES))
        assert len(results) == 51, f"Expected 51, got {len(results)}"
        for r in results:
            assert "::" in r.dataset, f"Missing :: separator: {r.dataset}"

    def test_mock_baseline_result_schema(self) -> None:
        results = run_mock_baseline(["precheck"])
        assert len(results) == 3
        for r in results:
            assert isinstance(r, BaselineResult)
            assert r.mode == "precheck"
            assert r.dataset in (
                "cuad::precheck",
                "maud::precheck",
                "contract_nli::precheck",
            )
            assert isinstance(r.extraction_f1, float | None)
            assert isinstance(r.comparison_f1, float | None)
            assert isinstance(r.classification_f1, float | None)
            assert isinstance(r.latency_ms, int | float | None)
            assert isinstance(r.peak_memory_mb, float | None)
            assert r.hallucination_rate is None
            assert r.pii_recall is None


class TestBaselineOutput:
    """T-B-04, T-B-05, T-B-06: CLI output flags."""

    def test_baseline_save_flag_and_schema(self, tmp_path: Path) -> None:
        output = tmp_path / "test-baseline.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "openreview_cli",
                "benchmark",
                "baseline",
                "--modes=precheck",
                "--save-baseline",
                "--format=json",
                f"--output={output}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert output.exists(), "Output file not created"
        data = json.loads(output.read_text())
        assert "mode_results" in data
        assert "git_commit" in data
        assert "provider" in data
        assert "model" in data
        assert "timestamp" in data
        assert isinstance(data["mode_results"], list)
        for mr in data["mode_results"]:
            assert "mode" in mr
            assert "dataset" in mr

    def test_baseline_save_flag_conflict(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "openreview_cli",
                "benchmark",
                "baseline",
                "--modes=precheck",
                "--save-baseline",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0
        assert (
            "format" in result.stderr.lower()
            or "json" in result.stderr.lower()
            or "save-baseline" in result.stderr.lower()
        )


class TestPerModeGrouping:
    """T-B-07: BaselineReport groups results by mode."""

    def test_report_per_mode_grouping(self) -> None:
        results = run_mock_baseline(["precheck", "hirecheck"])
        assert len(results) == 6

        report = BaselineReport(
            mode_results=results,
            git_commit="test123",
            git_branch="test-branch",
            provider="mock",
            model="mock",
            timestamp="2024-01-01T00:00:00",
        )
        assert len(report.mode_results) == 6
        precheck_results = [r for r in report.mode_results if r.mode == "precheck"]
        hirecheck_results = [r for r in report.mode_results if r.mode == "hirecheck"]
        assert len(precheck_results) == 3
        assert len(hirecheck_results) == 3
        for r in report.mode_results:
            assert "::" in r.dataset
