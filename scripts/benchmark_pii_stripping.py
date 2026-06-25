"""Run PII stripping against seeded corpus and collect metrics.

Uses PiiEngine.detect_all_pages directly to avoid the text-replacement
pipeline that can fail on overlapping Presidio detections. Reports entity
detection stats, processing time, and memory.
"""

import json
import resource
import sys
import time
import tracemalloc
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openreview_cli.parsing.models import Clause, Document

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "pii"
SEEDED_DIR = FIXTURES_DIR / "seeded_contracts"


def get_rusage_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def generate_50_page_benchmark() -> tuple[list[Clause], Document]:
    """Generate a synthetic 50-page document for performance testing."""
    clauses = []
    for page in range(1, 51):
        pii_items = [
            f"Company{page}A Inc.",
            f"Name{page} Smith",
            f"email{page}@example.com",
            f"555-01{page:02d}",
            f"{page}00 Main Street, Suite {page}, San Francisco, CA 9410{page % 10}",
            f"$1{page:02d},000.00",
            f"{10 + page % 89:02d}-{7654321 - page:07d}",
        ]
        text = f"This is page {page} of the test document. " + " ".join(
            f"The entity is {v}." for v in pii_items
        )
        clauses.append(
            Clause(
                id=str(page),
                title=f"Page {page}",
                text=text,
                level=1,
                parent_id=None,
                source_page=page,
                source_paragraph=None,
                source_span=None,
            )
        )
    doc = Document(
        source_path=Path("synthetic_50_page.pdf"),
        format="pdf",
        page_count=50,
        clause_count=50,
        parse_duration_seconds=0.0,
        warnings=[],
    )
    return clauses, doc


def main() -> None:
    tracemalloc.start()
    from openreview_cli.pii.engine import PiiEngine

    results = []
    errors = []

    # Create ONE engine and reuse across all documents (avoids 3-8s model load each time)
    engine = PiiEngine(threshold=0.7)

    # --- Part 1: Seeded corpus ---
    print("=== Part 1: Seeded corpus (50 documents) ===", file=sys.stderr)

    text_files = sorted(SEEDED_DIR.rglob("*.txt"))

    for i, fpath in enumerate(text_files, 1):
        try:
            text = fpath.read_text("utf-8", errors="replace")
            clause = Clause(
                id="1",
                title=fpath.stem,
                text=text,
                level=1,
                parent_id=None,
                source_page=1,
                source_paragraph=None,
                source_span=(0, len(text)),
            )
            t0 = time.perf_counter()
            entities, warnings = engine.detect_all_pages([clause], threshold=0.7)
            duration = time.perf_counter() - t0

            type_counts = defaultdict(int)
            for e in entities:
                type_counts[e.entity_type] += 1

            results.append(
                {
                    "file": str(fpath.relative_to(SEEDED_DIR)),
                    "text_size_kb": round(len(text) / 1024, 2),
                    "entity_count": len(entities),
                    "entity_types": dict(sorted(type_counts.items(), key=lambda x: -x[1])),
                    "duration_s": round(duration, 4),
                    "warnings": warnings,
                }
            )

            print(
                f"  [{i}/{len(text_files)}] {fpath.name} — "
                f"{len(entities)} entities in {duration:.3f}s",
                file=sys.stderr,
            )
        except Exception as e:
            errors.append({"file": fpath.name, "error": str(e)})
            print(f"  [ERR] {fpath.name}: {e}", file=sys.stderr)

    # --- Part 2: 50-page synthetic benchmark ---
    print("\n=== Part 2: 50-page synthetic document ===", file=sys.stderr)

    clauses_50, doc_50 = generate_50_page_benchmark()

    # Warm-up
    _, _ = engine.detect_all_pages(clauses_50, threshold=0.7)

    t0 = time.perf_counter()
    entities_50, warnings_50 = engine.detect_all_pages(clauses_50, threshold=0.7)
    duration_50 = time.perf_counter() - t0
    mem_mb_50 = get_rusage_mb()

    type_counts_50 = defaultdict(int)
    for e in entities_50:
        type_counts_50[e.entity_type] += 1

    perf_result = {
        "test": "50-page synthetic document",
        "entity_count": len(entities_50),
        "entity_types": dict(sorted(type_counts_50.items(), key=lambda x: -x[1])),
        "duration_s": round(duration_50, 4),
        "peak_memory_rss_mb": round(mem_mb_50, 1),
    }
    print(
        f"  50 pages: {perf_result['entity_count']} entities, "
        f"{perf_result['duration_s']:.3f}s, "
        f"{perf_result['peak_memory_rss_mb']} MB RSS",
        file=sys.stderr,
    )

    # --- Part 3: No-PII pass-through ---
    print("\n=== Part 3: No-PII edge case ===", file=sys.stderr)
    no_pii_path = SEEDED_DIR / "no_pii_document.txt"
    if no_pii_path.exists():
        text = no_pii_path.read_text()
        nc = Clause(
            id="1",
            title="no_pii",
            text=text,
            level=1,
            parent_id=None,
            source_page=1,
            source_paragraph=None,
            source_span=(0, len(text)),
        )
        entities, w = engine.detect_all_pages([nc], threshold=0.7)
        print(f"  no_pii_document.txt: {len(entities)} entities, {w}", file=sys.stderr)
        results.append(
            {
                "file": "seeded_contracts/no_pii_document.txt",
                "text_size_kb": round(len(text) / 1024, 2),
                "entity_count": len(entities),
                "entity_types": {e.entity_type: 1 for e in entities},
                "duration_s": 0.0,
                "warnings": w,
            }
        )

    engine.close()

    _current_mem, peak_trace = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Entity type breakdown across the full corpus
    global_type_counts: dict[str, int] = defaultdict(int)
    for r in results:
        for et, cnt in r.get("entity_types", {}).items():
            global_type_counts[et] += cnt

    total_duration = sum(r["duration_s"] for r in results)

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_documents": len(results),
        "success": len(results),
        "failed": len(errors),
        "total_entities_detected": sum(r["entity_count"] for r in results),
        "total_duration_s": round(total_duration, 3),
        "entity_type_distribution": dict(sorted(global_type_counts.items(), key=lambda x: -x[1])),
        "50_page_performance": perf_result,
        "peak_memory_rss_mb": round(mem_mb_50, 1),
        "peak_memory_tracemalloc_mb": round(peak_trace / 1024 / 1024, 1),
    }

    out_path = Path("metrics-pii-v0.1.0.json")
    with open(out_path, "w") as f:
        json.dump(
            {"summary": summary, "results": results, "errors": errors},
            f,
            indent=2,
            default=str,
        )

    print(f"\nOutput: {out_path.resolve()}", file=sys.stderr)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
