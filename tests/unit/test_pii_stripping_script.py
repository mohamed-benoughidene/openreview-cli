"""Regression test for scripts/benchmark_pii_stripping.py (4-tuple unpacking).

The script crashed with `ValueError: too many values to unpack (expected 2)`
because PiiEngine.detect_all_pages returns (entities, warnings, failed_pages,
error_messages) and the script unpacked two values at four call sites.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "benchmark_pii_stripping.py"


def _load_script() -> Any:
    """Load the benchmark script as a module without executing main()."""
    spec = importlib.util.spec_from_file_location("benchmark_pii_stripping", SCRIPT_PATH)
    assert spec is not None, f"cannot build a module spec for {SCRIPT_PATH}"
    assert spec.loader is not None, f"no loader for {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _StubEntity:
    def __init__(self, entity_type: str) -> None:
        self.entity_type = entity_type


class _StubEngine:
    """Duck-type PiiEngine whose detect_all_pages returns the real 4-tuple."""

    def __init__(self, threshold: float = 0.7) -> None:
        self.threshold = threshold
        self.calls = 0

    def detect_all_pages(
        self,
        clauses: list[Any],
        threshold: float | None = None,
        **_: Any,
    ) -> tuple[list[Any], list[str], list[int], dict[int, str]]:
        self.calls += 1
        return ([_StubEntity("PERSON") for _ in clauses], ["stub warning"], [], {})

    def close(self) -> None:
        pass


def test_pii_benchmark_script_runs_with_four_tuple_engine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script()
    monkeypatch.setattr("openreview_cli.pii.engine.PiiEngine", _StubEngine)

    seeded = tmp_path / "seeded_contracts"
    seeded.mkdir(parents=True, exist_ok=True)
    (seeded / "doc_a.txt").write_text("Name One works at Acme.", encoding="utf-8")
    (seeded / "no_pii_document.txt").write_text("Nothing personal here.", encoding="utf-8")
    monkeypatch.setattr(module, "SEEDED_DIR", seeded)

    output = tmp_path / "summary.json"
    module.main(["--output", str(output)])

    payload = json.loads(output.read_text(encoding="utf-8"))
    summary = payload["summary"]
    assert summary["failed"] == 0, f"unexpected errors: {payload['errors']}"
    assert summary["success"] == summary["total_documents"]
    # Two corpus files plus the part-3 edge-case pass over no_pii_document.txt.
    assert summary["total_documents"] == 3
    assert summary["total_entities_detected"] == 3
    assert summary["50_page_performance"]["entity_count"] == 50


def test_pii_benchmark_script_default_output_is_gitignored() -> None:
    module = _load_script()
    assert Path(".benchmark-reports/metrics-pii.json") == module.DEFAULT_OUTPUT
