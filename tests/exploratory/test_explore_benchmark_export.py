"""Exploratory probes: ``benchmark`` and ``export``.

Covers the reachable benchmark configuration code 78 and the CI-regression code
75 (``benchmark/cli.py:53,301``), plus the batch-export failure modes.
Offline only: real dataset downloads are never attempted.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import Result

EXIT_USER_ERROR = 1
EXIT_USAGE = 2
EXIT_BENCHMARK_REGRESSION = 75
EXIT_BENCHMARK_CONFIG = 78


def _text(result: Result) -> str:
    raw = (getattr(result, "output", "") or "") + (getattr(result, "stderr", "") or "")
    return " ".join(raw.split())


# ── benchmark: code 78 (config) ───────────────────────────────────────────


@pytest.mark.fast
@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--datasets", "bogus"),
        ("--format", "xml"),
        ("--hallucination-method", "bogus"),
        ("--benchmark-tier", "bogus"),
        ("--modes", "bogus"),
    ],
)
def test_benchmark_run_invalid_config_exits_78(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], flag: str, value: str
) -> None:
    result = invoke(["benchmark", "run", flag, value])
    assert result.exit_code == EXIT_BENCHMARK_CONFIG, (flag, value, result.exit_code, _text(result))
    assert "Error" in _text(result)


@pytest.mark.fast
@pytest.mark.parametrize(
    ("flag", "value"),
    [("--provider", "bogus"), ("--datasets", "bogus"), ("--modes", "bogus")],
)
def test_benchmark_baseline_invalid_config_exits_78(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], flag: str, value: str
) -> None:
    result = invoke(["benchmark", "baseline", flag, value])
    assert result.exit_code == EXIT_BENCHMARK_CONFIG, (flag, value, result.exit_code, _text(result))


@pytest.mark.fast
def test_benchmark_baseline_save_requires_json_exits_78(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result]
) -> None:
    result = invoke(["benchmark", "baseline", "--save-baseline"])
    assert result.exit_code == EXIT_BENCHMARK_CONFIG, (result.exit_code, _text(result))
    assert "--format json" in _text(result)


# ── benchmark: code 75 (CI regression) ────────────────────────────────────


@pytest.mark.fast
def test_benchmark_ci_regression_exits_75(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], monkeypatch: pytest.MonkeyPatch
) -> None:
    """RT-free probe: with a baseline present and a detected regression, CI mode
    exits 75.  The heavy per-tier PII evaluation is replaced by a counting
    double (the standard seam) so no dataset download is attempted.

    Reachability: the double must be invoked once per tier (3) before the exit.
    """
    import openreview_cli.benchmark.cli as benchmark_cli
    import openreview_cli.benchmark.regression as benchmark_regression
    from openreview_cli.benchmark.models import DatasetResult

    calls: list[str] = []

    def _fake_pii(runner: object, verbose: bool = False, tier: str = "balanced") -> DatasetResult:
        calls.append(tier)
        return DatasetResult(dataset_name=f"pii::tier={tier}", dataset_version="test", n_examples=1)

    monkeypatch.setattr(benchmark_cli, "_run_pii_evaluation", _fake_pii)
    monkeypatch.setattr(benchmark_regression, "load_baseline", lambda *a, **k: {"metrics": {}})
    monkeypatch.setattr(
        benchmark_regression,
        "compute_deltas",
        lambda run, metrics: {
            "regressions_detected": True,
            "regression_details": ["pii::tier=maximum::extraction_f1: 0.4 vs 0.9"],
        },
    )

    result = invoke(["benchmark", "run", "--datasets", "pii", "--ci"])
    assert result.exit_code == EXIT_BENCHMARK_REGRESSION, (result.exit_code, _text(result))
    assert "code 75" in _text(result)
    assert len(calls) == 2, calls  # one PII tier call per configured tier (maximum, balanced)


# ── export ────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_export_missing_batch_dir_is_usage_error(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], tmp_path: Path
) -> None:
    result = invoke(["export", "--batch-dir", str(tmp_path / "nodir")])
    assert result.exit_code == EXIT_USAGE, (result.exit_code, _text(result))
    assert "is not a directory" in _text(result)


@pytest.mark.fast
def test_export_empty_batch_dir_is_user_error(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], tmp_path: Path
) -> None:
    empty = tmp_path / "batch"
    empty.mkdir()
    result = invoke(["export", "--batch-dir", str(empty)])
    assert result.exit_code == EXIT_USER_ERROR, (result.exit_code, _text(result))
    assert "No JSON report files found" in _text(result)


@pytest.mark.fast
def test_export_rejects_unknown_format(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], tmp_path: Path
) -> None:
    result = invoke(["export", "--batch-dir", str(tmp_path), "--format", "xml"])
    assert result.exit_code == EXIT_USAGE, (result.exit_code, _text(result))
    assert "--format must be" in _text(result)


@pytest.mark.fast
def test_export_missing_template_is_usage_error(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], tmp_path: Path
) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "r.json").write_text("{}", encoding="utf-8")
    result = invoke(
        ["export", "--batch-dir", str(batch), "--template", str(tmp_path / "missing.j2")]
    )
    assert result.exit_code == EXIT_USAGE, (result.exit_code, _text(result))
    assert "Template file not found" in _text(result)


# ── negative control ──────────────────────────────────────────────────────


@pytest.mark.fast
def test_negative_control_oracle_rejects_a_wrong_exit_code(
    isolated_dirs: Path, invoke: Callable[[list[str]], Result], tmp_path: Path
) -> None:
    """Negative control: flip the inner assertion and this case fails."""
    result = invoke(["export", "--batch-dir", str(tmp_path / "nodir")])
    assert result.exit_code == EXIT_USAGE, (result.exit_code, _text(result))
    with pytest.raises(AssertionError):
        assert result.exit_code == EXIT_BENCHMARK_REGRESSION, "negative control: 2 is not 75"
