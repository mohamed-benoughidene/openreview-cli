"""Benchmark mode validation tests (Group A — D-75).

Tests:
  - VALID_MODES frozenset membership (17 modes)
  - Parse-time mode validation (reject unknown, accept all 17)
  - Dead mode param removal from run_dataset()
  - Multi-mode dataset name convention
"""

import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.benchmark.cli import VALID_MODES
from openreview_cli.benchmark.models import BenchmarkConfig, DatasetResult
from openreview_cli.benchmark.runner import BenchmarkRunner

# 22 known modes from spec FR-1 (17 prior + 5 new L-4c)
_KNOWN_MODES: frozenset[str] = frozenset(
    {
        "precheck",
        "hirecheck",
        "dealcheck",
        "assetcheck",
        "buycheck",
        "engagecheck",
        "guaranteecheck",
        "loancheck",
        "licensecheck",
        "leasecheck",
        "privacycheck",
        "indemnitycheck",
        "consultcheck",
        "workcheck",
        "loicheck",
        "subcheck",
        "settlementcheck",
        "franchisecheck",
        "opcheck",
        "partnercheck",
        "sponsorcheck",
        "distrocheck",
    }
)


def _mock_pipeline(text: str, category: str) -> dict[str, object]:
    return {"start": 0, "end": 0, "category": category, "label": "entailment", "match": True}


class TestValidModes:
    """VALID_MODES frozenset tests (T-A-03)."""

    def test_valid_modes_contains_22_entries(self) -> None:
        """Assert VALID_MODES has exactly 22 entries, all known."""
        assert len(VALID_MODES) == 22
        for mode in _KNOWN_MODES:
            assert mode in VALID_MODES, f"Missing mode: {mode}"


class TestModeValidation:
    """Mode validation at CLI level (T-A-01, T-A-02)."""

    def test_modes_validation_rejects_unknown(self) -> None:
        """Assert --modes=invalidmode exits code 78 with error on stderr."""
        result = subprocess.run(
            [sys.executable, "-m", "openreview_cli", "benchmark", "run", "--modes=invalidmode"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 78, (
            f"Expected 78, got {result.returncode}. stderr: {result.stderr}"
        )
        assert "Unknown mode" in result.stderr, f"stderr: {result.stderr}"

    def test_modes_validation_accepts_all_22(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Assert --modes=<all 22> succeeds (exit 0)."""
        _fake_items = [
            {
                "example_id": "doc1_governing_law",
                "document_text": "This Agreement shall be governed by the laws of New York.",
                "category": "governing_law",
                "ground_truth_spans": [(42, 52)],
                "is_positive": True,
            }
        ]
        for module, loader in (
            ("cuad", "load_cuad_dataset"),
            ("maud", "load_maud_dataset"),
            ("contract_nli", "load_contract_nli_dataset"),
        ):
            monkeypatch.setattr(
                f"openreview_cli.benchmark.datasets.{module}.{loader}",
                lambda cache_dir=None, _items=_fake_items: iter(_items),
            )
        modes_str = ",".join(sorted(_KNOWN_MODES))
        runner = CliRunner()
        result = runner.invoke(app, ["benchmark", "run", f"--modes={modes_str}"])
        assert result.exit_code == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


class TestDeadParam:
    """run_dataset() mode param tests (T-A-04)."""

    def test_run_dataset_no_mode_param(self) -> None:
        """Assert run_dataset signature does not accept mode= keyword."""
        sig = inspect.signature(BenchmarkRunner.run_dataset)
        assert "mode" not in sig.parameters, f"run_dataset() still has mode param: {sig}"

    def test_run_dataset_call_without_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert run_dataset works without mode= keyword."""
        monkeypatch.setattr(
            "openreview_cli.benchmark.datasets.cuad.load_cuad_dataset",
            lambda cache_dir=None: iter(
                [
                    {
                        "example_id": "doc1_clause",
                        "document_text": "Test clause text.",
                        "category": "governing_law",
                        "ground_truth_spans": [(0, 5)],
                        "is_positive": True,
                    },
                ]
            ),
        )
        config = BenchmarkConfig(datasets=["cuad"])
        runner = BenchmarkRunner(config=config, cache_dir=tmp_path)
        result = runner.run_dataset("cuad", _mock_pipeline)
        assert isinstance(result, DatasetResult)
        assert result.dataset_name == "cuad"


class TestMultiMode:
    """Multi-mode iteration tests (T-A-05)."""

    def test_dataset_name_convention(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert dataset_name contains :: mode separator with multi-mode."""
        monkeypatch.setattr(
            "openreview_cli.benchmark.datasets.cuad.load_cuad_dataset",
            lambda cache_dir=None: iter(
                [
                    {
                        "example_id": "doc1_clause",
                        "document_text": "Test clause text.",
                        "category": "governing_law",
                        "ground_truth_spans": [(0, 5)],
                        "is_positive": True,
                    },
                ]
            ),
        )
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "benchmark",
                "run",
                "--datasets=cuad",
                "--modes=precheck,hirecheck",
                "--format=json",
            ],
        )
        assert result.exit_code == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        data = json.loads(result.stdout)
        results = data.get("results", [])
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        for entry in results:
            name = entry.get("dataset_name", "")
            assert "::" in name, f"dataset_name '{name}' missing :: mode separator"
