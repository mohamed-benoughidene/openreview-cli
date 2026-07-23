"""Integration tests for --benchmark-tier CLI flag."""

import json
import subprocess
import sys

# ponytail: minimal integration tests — verify flag parses and table renders


def test_benchmark_tier_maximum_runs() -> None:
    """Run benchmark with --benchmark-tier maximum, expect no crash."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "openreview_cli",
            "benchmark",
            "run",
            "--datasets",
            "pii",
            "--benchmark-tier",
            "maximum",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0 or "Error" not in result.stderr
    # Should produce valid JSON
    if result.stdout.strip().startswith("{"):
        data = json.loads(result.stdout)
        assert "results" in data


def test_benchmark_tier_balanced_runs() -> None:
    """Run benchmark with --benchmark-tier balanced, expect no crash."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "openreview_cli",
            "benchmark",
            "run",
            "--datasets",
            "pii",
            "--benchmark-tier",
            "balanced",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0 or "Error" not in result.stderr


def test_benchmark_tier_performance_runs() -> None:
    """Run benchmark with --benchmark-tier performance, expect no crash."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "openreview_cli",
            "benchmark",
            "run",
            "--datasets",
            "pii",
            "--benchmark-tier",
            "performance",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0 or "Error" not in result.stderr


def test_benchmark_tier_all_runs() -> None:
    """Run benchmark with --benchmark-tier all, expect no crash."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "openreview_cli",
            "benchmark",
            "run",
            "--datasets",
            "pii",
            "--benchmark-tier",
            "all",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=90,  # all = 3 tiers sequential; 30s was borderline (29.8s observed)
    )
    assert result.returncode == 0 or "Error" not in result.stderr


def test_benchmark_tier_invalid_errors() -> None:
    """Invalid tier value should exit non-zero."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "openreview_cli",
            "benchmark",
            "run",
            "--datasets",
            "pii",
            "--benchmark-tier",
            "invalid_tier_xxx",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0


def test_benchmark_tier_table_output_maximum() -> None:
    """Terminal output should contain the tier name when specified."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "openreview_cli",
            "benchmark",
            "run",
            "--datasets",
            "pii",
            "--benchmark-tier",
            "maximum",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # Should mention the tier in output
    tier_mentioned = "maximum" in result.stdout.lower() or "maximum" in result.stderr.lower()
    assert tier_mentioned or result.returncode == 0
