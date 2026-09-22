"""CUAD clause-segmentation benchmark (span containment + enclosure tightness).

Promotes the CUAD segmentation run into a reproducible script. For every
expert-labeled clause span in ``data/legalbenchrag/benchmarks/cuad.json`` this
measures whether the span falls fully inside a single detected clause (span
containment) and how tightly that clause encloses the span (token-level F1).

Segmentation uses the same segmentation functions
(``nupunkt_detect_boundaries`` -> ``detect_clause_starts`` -> ``build_hierarchy``)
that ``PdfParser.parse`` uses, called here on whole-document text with
``headings=[]`` and ``page_num=1``, with no LLM calls and no network.

This is a *segmentation* measurement (span containment / enclosure tightness),
NOT query-answering accuracy.

Measured 2026-09-22: 462 of 462 documents, 6,247 spans, 90.67% containment,
token-F1 0.307, query coverage 91.64%. See
``docs/benchmarks/results/cuad-segmentation.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import unicodedata
from collections.abc import Sequence
from pathlib import Path
from typing import Any

# Make the package importable when the script is run straight from the tree.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from openreview_cli.benchmark.metrics import extraction_f1
from openreview_cli.parsing.clause_detector import (
    build_hierarchy,
    detect_clause_starts,
    nupunkt_detect_boundaries,
)
from openreview_cli.parsing.models import Clause

DEFAULT_CORPUS = "data/legalbenchrag/benchmarks/cuad.json"
DEFAULT_CORPUS_ROOT = "data/legalbenchrag/corpus"
DEFAULT_OUTPUT = ".benchmark-reports/cuad-segmentation.json"


def load_document_text(corpus_root: Path, file_path: str) -> str | None:
    """Return the document text for a corpus-relative ``file_path``.

    The literal path is tried first; Unicode NFC normalization then covers a
    corpus JSON that stores a filename in NFD (decomposed) form while the file
    on disk is NFC (composed). Returns ``None`` when neither path resolves, so
    the caller can report the unreadable ``file_path`` rather than silently
    dropping its snippets.
    """
    literal = corpus_root / file_path
    if literal.is_file():
        return literal.read_text(encoding="utf-8", errors="replace")
    normalized = corpus_root / unicodedata.normalize("NFC", file_path)
    if normalized.is_file():
        return normalized.read_text(encoding="utf-8", errors="replace")
    return None


def segment(text: str) -> list[Clause]:
    """Segment ``text`` using the same functions ``PdfParser.parse`` uses."""
    boundaries = nupunkt_detect_boundaries(text)
    clause_starts = detect_clause_starts(text)
    return build_hierarchy(boundaries, clause_starts, [], 1, 0, text)


def containing_clause(clauses: list[Clause], start: int, end: int) -> Clause | None:
    """Return the detected clause whose span fully contains ``[start, end)``.

    A gold span is contained when it lies fully inside one detected clause's
    ``source_span``. ``build_hierarchy`` emits a flat, non-overlapping partition,
    so at most one clause can contain a span; returns ``None`` when none does.
    """
    return next(
        (
            clause
            for clause in clauses
            if clause.source_span is not None
            and clause.source_span[0] <= start
            and clause.source_span[1] >= end
        ),
        None,
    )


def evaluate(corpus_path: Path, corpus_root: Path, corpus_label: str) -> dict[str, Any]:
    """Run the segmentation benchmark and return a JSON-serializable result."""
    payload: Any = json.loads(corpus_path.read_text(encoding="utf-8"))
    tests: list[Any] = payload["tests"]

    # Document text + clauses are cached: each file is reused by many snippets.
    cache: dict[str, tuple[str, list[Clause]] | None] = {}
    unreadable: set[str] = set()

    spans_evaluated = 0
    spans_contained = 0
    token_f1_total = 0.0
    missing_snippets = 0
    tests_with_span = 0
    tests_any_span_contained = 0

    start_time = time.monotonic()
    for test in tests:
        test_has_span = False
        test_has_contained = False
        for snippet in test["snippets"]:
            file_path: str = snippet["file_path"]
            if file_path not in cache:
                text = load_document_text(corpus_root, file_path)
                cache[file_path] = None if text is None else (text, segment(text))
                if text is None:
                    unreadable.add(file_path)

            entry = cache[file_path]
            if entry is None:
                missing_snippets += 1
                continue

            text, clauses = entry
            span_start, span_end = snippet["span"]
            spans_evaluated += 1
            test_has_span = True

            enclosing = containing_clause(clauses, span_start, span_end)
            if enclosing is None:
                continue

            spans_contained += 1
            test_has_contained = True
            enclosing_span = enclosing.source_span
            if enclosing_span is not None:
                f1 = extraction_f1([enclosing_span], [(span_start, span_end)], text)
                token_f1_total += f1.value

        if test_has_span:
            tests_with_span += 1
        if test_has_contained:
            tests_any_span_contained += 1
    elapsed = time.monotonic() - start_time

    documents_loaded = sum(1 for entry in cache.values() if entry is not None)
    return {
        "benchmark": "cuad-segmentation",
        "corpus": corpus_label,
        "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        "documents_loaded": documents_loaded,
        "spans_evaluated": spans_evaluated,
        "spans_contained": spans_contained,
        "containment_rate": round(spans_contained / spans_evaluated, 6) if spans_evaluated else 0.0,
        "token_f1_mean": round(token_f1_total / spans_evaluated, 6) if spans_evaluated else 0.0,
        "tests_with_span": tests_with_span,
        "tests_any_span_contained": tests_any_span_contained,
        "test_coverage_rate": round(tests_any_span_contained / tests_with_span, 6)
        if tests_with_span
        else 0.0,
        "missing_snippets": missing_snippets,
        "unreadable_file_paths": sorted(unreadable),
        "elapsed_seconds": round(elapsed, 2),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        default=DEFAULT_CORPUS,
        help=f"Path to the CUAD benchmark JSON (default: {DEFAULT_CORPUS}).",
    )
    parser.add_argument(
        "--corpus-root",
        default=DEFAULT_CORPUS_ROOT,
        help=f"Root directory of the corpus text files (default: {DEFAULT_CORPUS_ROOT}).",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Where to write the raw result JSON (default: {DEFAULT_OUTPUT}).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the CUAD segmentation benchmark and write the raw result JSON."""
    args = parse_args(argv)
    result = evaluate(Path(args.corpus), Path(args.corpus_root), args.corpus)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print("--- CUAD clause-segmentation results ---")
    print(f"Documents loaded:     {result['documents_loaded']}")
    print(f"Spans evaluated:      {result['spans_evaluated']}")
    print(
        f"Span containment:     {result['containment_rate']:.2%} "
        f"({result['spans_contained']} / {result['spans_evaluated']})"
    )
    print(f"Token F1 (mean):      {result['token_f1_mean']:.4f}")
    print(
        f"Query coverage:       {result['test_coverage_rate']:.2%} "
        f"({result['tests_any_span_contained']} / {result['tests_with_span']})"
    )
    print(f"Missing snippets:     {result['missing_snippets']}")
    unreadable = result["unreadable_file_paths"]
    if unreadable:
        print("Unreadable file_path values (text could not be loaded):")
        for file_path in unreadable:
            print(f"  - {file_path}")
    print(f"Elapsed:              {result['elapsed_seconds']} s")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
