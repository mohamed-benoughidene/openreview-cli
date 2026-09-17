"""Live LLM/SLM Evaluation Script on ContractNLI Real-World NDAs.

Runs the full OpenReview extraction and QA pipeline (with PII stripping)
across real-world NDAs from data/legalbenchrag against precheck-nda-v1 playbook.
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from openreview_cli.benchmark.datasets.contract_nli import (
    load_contract_nli_dataset,
)
from openreview_cli.gateway.router import mark_pii_available
from openreview_cli.pii.engine import PiiEngine
from openreview_cli.review.extraction import extract_clause
from openreview_cli.review.playbook import load_bundled
from openreview_cli.review.qa import verify_assessment


def run_llm_evaluation(
    max_clauses: int = 25,
    sample_ndas: int | None = None,
    output_file: str | None = None,
) -> dict:
    """Run extraction and QA on real NDA clauses using configured Gateway models."""
    playbook = load_bundled()
    categories_by_id = {c.id: c for c in playbook.categories}

    # Load dataset items (which contain ground-truth labeled spans and mapped categories)
    items = list(load_contract_nli_dataset())
    if sample_ndas:
        unique_files = sorted({item.get("file_path") for item in items if item.get("file_path")})[
            :sample_ndas
        ]
        items = [item for item in items if item.get("file_path") in unique_files]

    # Deduplicate items by snippet text to test distinct substantive clauses
    seen_texts: set[str] = set()
    distinct_items = []
    for it in items:
        ans = it.get("ground_truth_answer", "").strip()
        if ans and ans not in seen_texts and len(ans) > 40:
            seen_texts.add(ans)
            distinct_items.append(it)

    if max_clauses and max_clauses < len(distinct_items):
        eval_items = distinct_items[:max_clauses]
    else:
        eval_items = distinct_items

    print(f"Starting live LLM evaluation on {len(eval_items)} distinct real-world NDA clauses...")
    pii_engine = PiiEngine(threshold=0.7)

    assessments_summary = {
        "preferred": 0,
        "acceptable": 0,
        "walkaway": 0,
        "uncertain": 0,
    }
    qa_verdicts = {
        "agree": 0,
        "disagree": 0,
        "uncertain": 0,
    }
    category_distribution: dict[str, int] = {}
    amber_count = 0
    all_results = []
    start_time = time.monotonic()

    for idx, item in enumerate(eval_items, 1):
        cid = item.get("example_id", f"clause_{idx}")
        cat_id = item.get("category", "confidentiality-term")
        matched_cat = categories_by_id.get(cat_id, playbook.categories[0])
        category_distribution[matched_cat.id] = category_distribution.get(matched_cat.id, 0) + 1

        raw_text = item.get("ground_truth_answer", "").strip()

        # 1. Strip PII before sending to cloud gateway
        entities = pii_engine.detect_on_page(raw_text)
        stripped_text = raw_text
        for ent in sorted(entities, key=lambda e: e.start, reverse=True):
            stripped_text = (
                stripped_text[: ent.start] + f"[{ent.entity_type}]" + stripped_text[ent.end :]
            )
        mark_pii_available()

        # 2. Extraction agent
        t0 = time.monotonic()
        assessment = extract_clause(
            clause_text=stripped_text,
            clause_id=cid,
            category=matched_cat,
            extraction_model="extraction",
            mode="precheck",
        )

        # 3. QA verification agent
        assessment = verify_assessment(
            assessment=assessment,
            category=matched_cat,
            qa_model="reasoning",
        )
        clause_elapsed = time.monotonic() - t0

        pos_val = assessment.position.value if assessment.position else "uncertain"
        assessments_summary[pos_val] = assessments_summary.get(pos_val, 0) + 1

        qa_val = assessment.qa_verdict.value if assessment.qa_verdict else "uncertain"
        qa_verdicts[qa_val] = qa_verdicts.get(qa_val, 0) + 1

        if assessment.is_amber:
            amber_count += 1

        doc_name = Path(item.get("file_path", "")).name
        print(
            f"[{idx}/{len(eval_items)}] {doc_name[:25]:25s} [{matched_cat.id:22s}]: "
            f"pos={pos_val:10s} conf={assessment.confidence:.2f} QA={qa_val:9s} "
            f"amber={assessment.is_amber!s:5s} ({clause_elapsed:.1f}s)"
        )

        all_results.append(
            {
                "id": cid,
                "document": doc_name,
                "category": matched_cat.id,
                "position": pos_val,
                "confidence": assessment.confidence,
                "qa_verdict": qa_val,
                "is_amber": assessment.is_amber,
                "citation": assessment.citation,
                "elapsed": round(clause_elapsed, 2),
            }
        )

    total_time = time.monotonic() - start_time
    total_evaluated = len(eval_items)
    avg_latency = total_time / total_evaluated if total_evaluated > 0 else 0.0

    report = {
        "dataset": "ContractNLI",
        "total_evaluated_clauses": total_evaluated,
        "category_distribution": category_distribution,
        "positions": assessments_summary,
        "qa_verdicts": qa_verdicts,
        "amber_flags": amber_count,
        "amber_rate": round(amber_count / total_evaluated, 4) if total_evaluated > 0 else 0.0,
        "qa_agreement_rate": round(qa_verdicts["agree"] / total_evaluated, 4)
        if total_evaluated > 0
        else 0.0,
        "total_elapsed_seconds": round(total_time, 2),
        "avg_seconds_per_clause": round(avg_latency, 2),
        "results": all_results,
    }

    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nSaved detailed evaluation report to {output_file}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ContractNLI NDAs with live LLM")
    parser.add_argument(
        "--clauses",
        type=int,
        default=20,
        help="Number of distinct clauses to evaluate (default: 20)",
    )
    parser.add_argument("--ndas", type=int, default=None, help="Limit to N unique NDAs")
    parser.add_argument(
        "--output",
        type=str,
        default="review_results/contractnli_llm_benchmark.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    results = run_llm_evaluation(
        max_clauses=args.clauses, sample_ndas=args.ndas, output_file=args.output
    )
    print("\n==========================================")
    print("ContractNLI Live LLM Evaluation Summary")
    print("==========================================")
    print(f"Total Evaluated Clauses: {results['total_evaluated_clauses']}")
    print(f"Category Distribution: {results['category_distribution']}")
    print(f"Position Distribution: {results['positions']}")
    print(f"QA Verdicts: {results['qa_verdicts']}")
    print(f"QA Agreement Rate: {results['qa_agreement_rate']:.2%}")
    print(f"Amber Rate: {results['amber_rate']:.2%}")
    print(
        f"Total Time: {results['total_elapsed_seconds']}s ({results['avg_seconds_per_clause']}s / clause)"
    )


if __name__ == "__main__":
    main()
