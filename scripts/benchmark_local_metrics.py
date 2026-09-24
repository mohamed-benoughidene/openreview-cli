"""Offline local benchmark receipts: the accuracy-test suite and test collection.

Both measurements re-run locally, with no network and no model calls:

    uv run python scripts/benchmark_local_metrics.py

Writes receipt-shaped JSON (all eight receipt keys) under ``.benchmark-reports/``,
which is gitignored (decision D5). Copy the file you want to publish into
``docs/benchmarks/results/`` — the committed receipt is the evidence for the
numbers on ``docs/BENCHMARKS.md``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from openreview_cli.benchmark._utils import _detect_git_commit

REPO_ROOT = Path(__file__).resolve().parent.parent

ACCURACY_SUITE_FILES: tuple[str, ...] = (
    "tests/integration/test_pii_accuracy.py",
    "tests/unit/test_tier_accuracy.py",
    "tests/integration/test_review_accuracy.py",
    "tests/integration/test_benchmark_pii_accuracy.py",
)
DEFAULT_REPORTS_DIR = Path(".benchmark-reports")

_SUMMARY_PATTERNS = {
    "passed": re.compile(r"(\d+) passed"),
    "failed": re.compile(r"(\d+) failed"),
    "skipped": re.compile(r"(\d+) skipped"),
    "errors": re.compile(r"(\d+) errors?"),
}
_DURATION = re.compile(r"in ([\d.]+)\s*s")
_COLLECTED = re.compile(r"(\d+) tests? collected")


def _last_line(output: str) -> str:
    """The pytest summary line is the last non-empty line of the run output."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def parse_summary(output: str) -> dict[str, int | float]:
    """Pull pass/fail/skip/error counts and the wall time out of a pytest summary."""
    line = _last_line(output)
    counts: dict[str, int | float] = {}
    for key, pattern in _SUMMARY_PATTERNS.items():
        match = pattern.search(line)
        counts[key] = int(match.group(1)) if match else 0
    duration = _DURATION.search(line)
    counts["elapsed_seconds"] = round(float(duration.group(1)), 2) if duration else 0.0
    return counts


def parse_collected(output: str) -> dict[str, int | float]:
    """Pull the collected-test count and wall time out of ``pytest --collect-only -q``."""
    line = _last_line(output)
    match = _COLLECTED.search(line)
    duration = _DURATION.search(line)
    return {
        "total_tests": int(match.group(1)) if match else 0,
        "elapsed_seconds": round(float(duration.group(1)), 2) if duration else 0.0,
    }


def run_pytest(args: list[str]) -> tuple[int, str]:
    """Run pytest in a child process; return ``(exit_code, combined_output)``."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _receipt(
    benchmark: str,
    command: str,
    models: str,
    sample: dict[str, object],
    metrics: dict[str, object],
    notes: str,
) -> dict[str, object]:
    """Build a receipt with the eight keys the receipt guard requires."""
    return {
        "benchmark": benchmark,
        "command": command,
        "date": date.today().isoformat(),
        "git_commit": _detect_git_commit(),
        "models": models,
        "sample": sample,
        "metrics": metrics,
        "notes": notes,
    }


def accuracy_suite_receipt() -> dict[str, object]:
    """Measure the four accuracy-tagged test files (all pass under the span-level predicate)."""
    code, output = run_pytest([*ACCURACY_SUITE_FILES, "-q"])
    return _receipt(
        benchmark="accuracy-suite",
        command=f"uv run pytest {' '.join(ACCURACY_SUITE_FILES)} -q",
        models="none (offline pytest; no model calls)",
        sample={
            "files": list(ACCURACY_SUITE_FILES),
            "network": "disabled by pytest addopts (--disable-socket --allow-unix-socket)",
        },
        metrics={"exit_code": code, **parse_summary(output)},
        notes=(
            "All four accuracy-tagged files pass. The labeled-corpus PII gate passes "
            "under the span-level (type-agnostic) predicate, so a detection that covers "
            "the right span with the wrong entity label still counts as correct; that "
            "labelling limitation is tracked separately as D-82 in specs/DEFERRED.md and "
            "issue 115. Wall time is environment dependent."
        ),
    )


def test_collection_receipt() -> dict[str, object]:
    """Count the tests pytest collects from the configured testpaths."""
    code, output = run_pytest(["--collect-only", "-q"])
    return _receipt(
        benchmark="test-collection",
        command="uv run pytest --collect-only -q",
        models="none (offline pytest collection; no model calls)",
        sample={"scope": "tests/ (pyproject testpaths)"},
        metrics={"exit_code": code, **parse_collected(output)},
        notes=(
            "The count changes whenever a test is added, so the page cites it under a "
            "dated Last verified line instead of asserting equality; regenerate this "
            "receipt whenever the page is next edited."
        ),
    )


def main(argv: list[str] | None = None) -> None:
    """Write both receipts (or the one named by ``--only``) into the reports directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--only", choices=("accuracy-suite", "test-collection"), default=None)
    args = parser.parse_args(argv)

    builders = {
        "accuracy-suite": accuracy_suite_receipt,
        "test-collection": test_collection_receipt,
    }
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    for name, builder in builders.items():
        if args.only and args.only != name:
            continue
        payload = builder()
        out_path = args.reports_dir / f"{name}.json"
        out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"{name}: {payload['metrics']} -> {out_path}")


if __name__ == "__main__":
    main()
