"""Benchmark script for ContractNLI dataset (95 NDAs, 977 tests).

Evaluates clause detection, span coverage, and playbook category alignment
across real-world Non-Disclosure Agreements in data/legalbenchrag.
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from openreview_cli.benchmark.datasets.contract_nli import (
    load_contract_nli_dataset,
)
from openreview_cli.parsing.clause_detector import nupunkt_detect_boundaries


def evaluate_contractnli_coverage(max_examples: int | None = None) -> dict:
    """Evaluate clause extraction coverage against ground-truth ContractNLI spans."""
    items = list(load_contract_nli_dataset())
    if max_examples:
        items = items[:max_examples]

    total_tests = len(items)
    unique_files = {item.get("file_path") for item in items if item.get("file_path")}

    start_time = time.monotonic()
    covered = 0
    total_spans = 0

    category_counts: dict[str, int] = {}
    category_covered: dict[str, int] = {}

    for item in items:
        cat = item.get("category", "unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

        doc_text = item.get("document_text", "")
        gt_answer = item.get("ground_truth_answer", "").strip()

        if not doc_text or not gt_answer:
            continue

        total_spans += 1

        # Detect sentence/clause boundaries using NUPunkt
        spans = nupunkt_detect_boundaries(doc_text)
        clause_texts = [doc_text[s:e].strip() for s, e in spans]

        # Check if ground truth snippet is captured within detected sentences/clauses
        is_covered = any(
            gt_answer in ct
            or ct in gt_answer
            or any(part in ct for part in gt_answer.split("\n") if len(part.strip()) > 25)
            for ct in clause_texts
        )

        if is_covered:
            covered += 1
            category_covered[cat] = category_covered.get(cat, 0) + 1

    elapsed = time.monotonic() - start_time
    coverage_rate = covered / total_spans if total_spans > 0 else 0.0

    category_rates = {
        cat: category_covered.get(cat, 0) / count
        for cat, count in category_counts.items()
        if count > 0
    }

    return {
        "dataset": "ContractNLI",
        "total_examples": total_tests,
        "unique_ndas": len(unique_files),
        "total_evaluated_spans": total_spans,
        "covered_spans": covered,
        "overall_coverage_rate": round(coverage_rate, 4),
        "category_coverage_rates": category_rates,
        "elapsed_seconds": round(elapsed, 2),
    }


def main() -> None:
    print("Running ContractNLI evaluation over real-world NDA dataset...")
    results = evaluate_contractnli_coverage()
    print("\n--- ContractNLI Evaluation Results ---")
    print(f"Total Tests / Spans: {results['total_evaluated_spans']}")
    print(f"Unique NDAs: {results['unique_ndas']}")
    print(f"Overall Span Coverage: {results['overall_coverage_rate']:.2%}")
    print(f"Time Taken: {results['elapsed_seconds']}s")
    print("\nCategory Breakdown:")
    for cat, rate in sorted(results["category_coverage_rates"].items()):
        print(f"  - {cat:25s}: {rate:.2%}")


if __name__ == "__main__":
    main()
