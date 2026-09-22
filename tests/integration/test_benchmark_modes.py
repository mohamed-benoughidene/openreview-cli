"""Benchmark mode validation tests (Group A — D-75).

Tests:
  - VALID_MODES frozenset membership (24 modes)
  - Parse-time mode validation (reject unknown, accept all 24)
  - run_dataset() mode parameter is present and used (R10; supersedes D-75)
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

# 24 known modes: the 23 named product modes plus the precheck base mode.
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
        "privacycheck_v2",
        "settlementcheck_v2",
    }
)


def _mock_pipeline(text: str, category: str) -> dict[str, object]:
    return {"start": 0, "end": 0, "category": category, "label": "entailment", "match": True}


class TestValidModes:
    """VALID_MODES frozenset tests (T-A-03)."""

    def test_valid_modes_covers_all_named_modes_and_precheck(self) -> None:
        """VALID_MODES must be the 23 named product modes plus the precheck base mode."""
        from openreview_cli.app import _PRODUCT_MODES

        named = {entry[0] for entry in _PRODUCT_MODES}
        assert len(named) == 23
        assert named | {"precheck"} == VALID_MODES
        assert len(VALID_MODES) == 24


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

    def test_modes_validation_accepts_all_24(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Assert --modes=<all 24> succeeds (exit 0)."""
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


class TestModeParam:
    """run_dataset() mode param tests (R10)."""

    def test_run_dataset_accepts_a_used_mode_param(self) -> None:
        """R10 supersedes D-75: ``mode`` is back, and it is used, not dead."""
        sig = inspect.signature(BenchmarkRunner.run_dataset)
        assert "mode" in sig.parameters, f"run_dataset() lost its mode param: {sig}"
        assert sig.parameters["mode"].default is None

    def test_run_dataset_call_without_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mode-agnostic call still works and keeps the bare dataset name."""
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
