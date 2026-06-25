"""Run parser against LegalBench-RAG corpus and record metrics."""

import json
import os
import resource
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from openreview_cli.parsing.clause_detector import detect_non_english, detect_tofu
from openreview_cli.parsing.stream import stream_clauses

LEGALBENCHRAG_DIR = Path("/tmp/opencode/legalbenchrag_data")
CORPUS_DIR = LEGALBENCHRAG_DIR / "corpus"
BENCHMARKS_DIR = LEGALBENCHRAG_DIR / "benchmarks"
CACHE_DIR = Path("/tmp/opencode/lbr_pdf_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

FONTSIZE = 10
LINE_HEIGHT = 14
MARGIN = 50
PAGE_HEIGHT = 800


def text_to_pdf(text: str, cache_path: Path) -> Path:
    if cache_path.exists():
        return cache_path
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    y = MARGIN
    for line in text.split("\n"):
        if y + LINE_HEIGHT > PAGE_HEIGHT:
            page = doc.new_page()
            y = MARGIN
        page.insert_text((MARGIN, y), line, fontname="helv", fontsize=FONTSIZE)
        y += LINE_HEIGHT
    doc.save(str(cache_path))
    doc.close()
    return cache_path


def get_rusage_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def has_warnings(clauses) -> dict:
    w = {"non_english": False, "tofu": False}
    for c in clauses:
        if not w["non_english"] and detect_non_english(c.text):
            w["non_english"] = True
        if not w["tofu"] and detect_tofu(c.text):
            w["tofu"] = True
        if all(w.values()):
            break
    return w


def load_benchmarks() -> dict[str, list[dict]]:
    benchmarks = {}
    for bfile in sorted(BENCHMARKS_DIR.glob("*.json")):
        with open(bfile) as f:
            benchmarks[bfile.stem] = json.load(f)["tests"]
    return benchmarks


def accuracy_for_file(tests: list[dict], clauses, relpath: str) -> dict:
    relevant = [t for t in tests for s in t["snippets"] if s["file_path"] == relpath]
    if not relevant:
        return {"total": 0, "covered": 0, "coverage": None}

    clause_texts = [c.text.strip() for c in clauses]
    covered = 0
    for test in relevant:
        targets = {s["answer"] for s in test["snippets"]}
        if any(any(t in ct or ct in t for ct in clause_texts) for t in targets):
            covered += 1

    return {
        "total": len(relevant),
        "covered": covered,
        "coverage": round(covered / len(relevant), 4),
    }


def main() -> None:
    tracemalloc.start()
    benchmarks = load_benchmarks()
    file_to_tests: dict[str, list] = {}
    for tests in benchmarks.values():
        for t in tests:
            for s in t["snippets"]:
                file_to_tests.setdefault(s["file_path"], []).append(t)

    text_files = sorted(CORPUS_DIR.rglob("*.txt"))
    results = []
    errors = []
    total_clauses = 0
    total_duration = 0.0
    peak_mem = 0.0
    success = 0
    failed = 0
    warn_counts = {"non_english": 0, "tofu": 0}

    for i, file_path in enumerate(text_files, 1):
        relpath = str(file_path.relative_to(CORPUS_DIR))
        cache_path = CACHE_DIR / f"{relpath.replace('/', '_').replace(' ', '_')}.pdf"

        text = file_path.read_text("utf-8", errors="replace")
        if not text.strip():
            errors.append({"file": relpath, "error": "empty_text", "category": "empty"})
            failed += 1
            continue

        try:
            pdf_path = text_to_pdf(text, cache_path)
        except Exception as e:
            errors.append({"file": relpath, "error": str(e), "category": "pdf_conversion"})
            failed += 1
            continue

        if os.path.getsize(pdf_path) == 0:
            errors.append({"file": relpath, "error": "empty pdf", "category": "empty"})
            failed += 1
            continue

        try:
            t0 = time.perf_counter()
            clauses = list(stream_clauses(pdf_path))
            duration = time.perf_counter() - t0
            mem_mb = get_rusage_mb()

            peak_mem = max(peak_mem, mem_mb)
            total_duration += duration
            total_clauses += len(clauses)
            success += 1

            w = has_warnings(clauses)
            for k in warn_counts:
                if w[k]:
                    warn_counts[k] += 1

            acc = accuracy_for_file(file_to_tests.get(relpath, []), clauses, relpath)
            page_count = max((c.source_page or 0) for c in clauses) + 1 if clauses else 0

            results.append({
                "file": relpath,
                "text_size_kb": round(len(text) / 1024, 1),
                "page_count": page_count,
                "clause_count": len(clauses),
                "parse_duration_s": round(duration, 4),
                "peak_memory_mb": round(mem_mb, 1),
                "chars_per_sec": round(len(text) / duration, 0) if duration > 0 else 0,
                **{f"warn_{k}": v for k, v in w.items()},
                **{f"acc_{k}": v for k, v in acc.items()},
            })

            if i % 100 == 0:
                print(f"  [{i}/{len(text_files)}] {relpath} — {len(clauses)} cls in {duration:.2f}s", file=sys.stderr)

        except Exception as e:
            errors.append({"file": relpath, "error": str(e), "category": type(e).__name__})
            failed += 1
            print(f"  [ERR] {relpath}: {e}", file=sys.stderr)

    current_mem, peak_trace = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    acc_entries = [r for r in results if r.get("acc_total", 0) > 0]
    acc_total = sum(r["acc_total"] for r in acc_entries)
    acc_covered = sum(r["acc_covered"] for r in acc_entries)

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_files": len(text_files),
        "success": success,
        "failed": failed,
        "success_pct": round(100 * success / len(text_files), 1),
        "total_clauses": total_clauses,
        "total_duration_s": round(total_duration, 3),
        "avg_clauses_per_file": round(total_clauses / success, 1),
        "avg_duration_s": round(total_duration / success, 4),
        "avg_chars_per_sec": round(sum(r["text_size_kb"] * 1024 for r in results) / total_duration, 0),
        "peak_memory_rss_mb": round(peak_mem, 1),
        "peak_memory_tracemalloc_mb": round(peak_trace / 1024 / 1024, 1),
        "warn_non_english_files": warn_counts["non_english"],
        "warn_tofu_files": warn_counts["tofu"],
    }

    if acc_entries:
        summary["accuracy"] = {
            "files_with_queries": len(acc_entries),
            "total_queries": acc_total,
            "covered_queries": acc_covered,
            "overall_coverage": round(acc_covered / acc_total, 4) if acc_total > 0 else 0,
            "avg_file_coverage": round(
                sum(r["acc_coverage"] for r in acc_entries if r["acc_coverage"] is not None) / len(acc_entries), 4
            ),
        }

    error_cats = {}
    for e in errors:
        error_cats[e["category"]] = error_cats.get(e["category"], 0) + 1
    summary["error_categories"] = error_cats

    out_path = Path("metrics-v0.1.0.json")
    with open(out_path, "w") as f:
        json.dump({"summary": summary, "results": results, "errors": errors}, f, indent=2, default=str)

    print(f"\nOutput: {out_path.resolve()}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
