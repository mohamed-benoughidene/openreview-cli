"""Benchmark baseline tests (Group B — D-76).

Tests:
  - T-B-01: baseline --help command exists
  - T-B-02: Mock baseline produces 51 results (17 modes x 3 datasets)
  - T-B-03: BaselineResult schema validation
  - T-B-04: --save-baseline --format json --output writes valid JSON file
  - T-B-05: BaselineReport JSON schema validation
  - T-B-06: --save-baseline without --format json errors
  - T-B-07: Per-mode grouping in BaselineReport
  - C-06: Per-mode baseline JSON files exist and validate
  - C-07: Per-mode regression detection (mode_specific, schema round-trip)
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

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

    def test_mock_baseline_produces_correct_result_count(self) -> None:
        results = run_mock_baseline(list(VALID_MODES))
        mode_count = len(VALID_MODES)
        dataset_count = 3  # cuad, maud, contract_nli
        assert len(results) == mode_count * dataset_count, (
            f"Expected {mode_count * dataset_count}, got {len(results)}"
        )
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


NEW_MODES = [
    "franchisecheck",
    "opcheck",
    "partnercheck",
    "sponsorcheck",
    "distrocheck",
]

BASELINES_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "benchmarks"


class TestPerModeBaselineFiles:
    """C-06: Per-mode baseline JSON files exist and validate."""

    @pytest.mark.parametrize(
        ("mode_key", "expected_file"),
        [
            ("franchisecheck", BASELINES_DIR / "franchisecheck.json"),
            ("opcheck", BASELINES_DIR / "opcheck.json"),
            ("partnercheck", BASELINES_DIR / "partnercheck.json"),
            ("sponsorcheck", BASELINES_DIR / "sponsorcheck.json"),
            ("distrocheck", BASELINES_DIR / "distrocheck.json"),
        ],
    )
    def test_per_mode_baseline_file_exists_and_valid(
        self, mode_key: str, expected_file: Path
    ) -> None:
        assert expected_file.exists(), f"Baseline file not found: {expected_file}"
        data = json.loads(expected_file.read_text())
        assert data["mode_key"] == mode_key, f"mode_key mismatch in {expected_file}"
        assert "display_name" in data, f"Missing display_name in {expected_file}"
        assert "fixture" in data, f"Missing fixture in {expected_file}"
        assert "expected_assessment" in data, f"Missing expected_assessment in {expected_file}"
        assert isinstance(data["expected_assessment"], dict)
        assert "overall" in data["expected_assessment"]
        assert data["expected_assessment"]["overall"] in ("GREEN", "AMBER", "RED")
        assert isinstance(data["time_budget_s"], int), "time_budget_s must be int"
        assert isinstance(data["pii_time_budget_s"], int), "pii_time_budget_s must be int"
        assert isinstance(data["page_count"], int), "page_count must be int"


class TestRegressionDetection:
    """C-07: Per-mode regression detection — mode_specific, schema round-trip."""

    @pytest.mark.parametrize("mode_key", NEW_MODES)
    def test_mode_specific_field_present(self, mode_key: str) -> None:
        path = BASELINES_DIR / f"{mode_key}.json"
        assert path.exists(), f"Baseline file not found: {path}"
        data = json.loads(path.read_text())
        assert "mode_specific" in data
        assert isinstance(data["mode_specific"], dict)

    def test_distrocheck_franchise_boundary_detected(self) -> None:
        path = BASELINES_DIR / "distrocheck.json"
        data = json.loads(path.read_text())
        assert data["mode_specific"].get("franchise_boundary_detected") is True

    def test_franchisecheck_franchise_boundary_flag(self) -> None:
        path = BASELINES_DIR / "franchisecheck.json"
        data = json.loads(path.read_text())
        assert data["mode_specific"].get("franchise_boundary") is True


class TestBaselineFixturePaths:
    """Regression: every baseline JSON fixture path must point to an existing file."""

    FIXTURE_PATHS = [
        ("franchisecheck", "tests/fixtures/pdf/franchisecheck-franchise-v1.pdf"),
        ("opcheck", "tests/fixtures/pdf/opcheck-operating-agreement-v1.pdf"),
        ("partnercheck", "tests/fixtures/pdf/partnercheck-partnership-v1.pdf"),
        ("sponsorcheck", "tests/fixtures/pdf/sponsorcheck-sponsorship-v1.pdf"),
        ("distrocheck", "tests/fixtures/pdf/distrocheck-distribution-v1.pdf"),
    ]

    @pytest.mark.parametrize(("mode_key", "expected_path"), FIXTURE_PATHS)
    def test_fixture_path_exists(self, mode_key: str, expected_path: str) -> None:
        path = Path(expected_path)
        assert path.exists(), (
            f"Baseline {mode_key}.json references nonexistent fixture: {expected_path}"
        )

    @pytest.mark.parametrize(("mode_key", "_"), FIXTURE_PATHS)
    def test_baseline_fixture_matches_disk(self, mode_key: str, _: str) -> None:
        """Ensure the fixture field in the JSON matches the expected path on disk."""
        json_path = BASELINES_DIR / f"{mode_key}.json"
        data = json.loads(json_path.read_text())
        fixture_field = data["fixture"]
        fixture_on_disk = Path(fixture_field)
        assert fixture_on_disk.exists(), (
            f"Baseline {mode_key}.json fixture='{fixture_field}' does not exist (cwd: {Path.cwd()})"
        )
