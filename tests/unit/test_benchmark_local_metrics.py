"""R7: the offline local-metrics script parses pytest output deterministically."""

from __future__ import annotations

from tests.helpers.benchmark_scripts import load_benchmark_script

LOCAL = load_benchmark_script("benchmark_local_metrics")


def test_parse_summary_reads_counts_and_wall_time() -> None:
    output = "........\n1 failed, 20 passed, 2 skipped in 55.36s\n"
    expected: dict[str, int | float] = {
        "passed": 20,
        "failed": 1,
        "skipped": 2,
        "errors": 0,
        "elapsed_seconds": 55.36,
    }
    assert LOCAL.parse_summary(output) == expected


def test_parse_summary_tolerates_a_space_before_the_unit() -> None:
    assert LOCAL.parse_summary("20 passed in 55.36 s")["elapsed_seconds"] == 55.36


def test_parse_collected_reads_the_collection_line() -> None:
    expected: dict[str, int | float] = {"total_tests": 3514, "elapsed_seconds": 5.97}
    assert LOCAL.parse_collected("3514 tests collected in 5.97s\n") == expected


def test_accuracy_suite_covers_the_four_documented_files() -> None:
    assert LOCAL.ACCURACY_SUITE_FILES == (
        "tests/integration/test_pii_accuracy.py",
        "tests/unit/test_tier_accuracy.py",
        "tests/integration/test_review_accuracy.py",
        "tests/integration/test_benchmark_pii_accuracy.py",
    )
