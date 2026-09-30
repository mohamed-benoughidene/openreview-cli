"""Reproducible keyword-retrieval accuracy measurement over the CUAD benchmark.

WHY THIS EXISTS
---------------
The decision to drop meaning-based (dense) search and keep keyword search was
made on a comparison over CUAD queries, but that comparison was never
committed: it lived in a session scratch directory and is gone. The committed
retrieval script scored a 5-query fixture instead, so the repository had no
reproducible retrieval measurement at all. This script is that measurement.

WHAT IT MEASURES
----------------
For each benchmark query it indexes that query's source contract with the
*shipped* keyword configuration -- SQLite FTS5 with
``tokenize='porter unicode61'``, ``prefix='2 3'`` and the product's
``ORDER BY bm25(chunk_fts)`` ordering -- searches it, and asks whether a chunk
whose document span overlaps the query's CUAD answer span is retrieved. It
reports ``hit@1``, ``hit@5`` and ``MRR@5`` as averages over the whole sample,
always alongside the sample size (queries scored, contracts used).

TOKENIZER ARM
-------------
``--tokenizer`` selects the FTS5 tokenizer (default ``porter``, matching the
shipped index DDL in ``retrieval/storage.py``). The choice shipped on a
1,536-query comparison whose harness was never committed, so this switch exists
so the choice can be re-derived on the committed benchmark. ``src/`` is not
edited: the product schema is created first, and for a non-default tokenizer the
``chunk_fts`` virtual table is recreated with the chosen tokenizer (the same
columns, ``UNINDEXED`` flag, external content and ``prefix`` options as
``storage.py``) and its index rebuilt from the ``chunks`` content table.

CHUNKING (approximation, stated in the receipt)
-----------------------------------------------
The product parses ``.pdf``/``.docx`` only and cannot read the CUAD ``.txt``
corpus, so this harness cannot reuse the product *parser*. It does reuse the
product *chunker*: it builds one ``Clause`` per blank-line-separated paragraph
and feeds them to ``openreview_cli.chunking.stream_chunks(ChunkConfig())``
(512-token chunks, 50-token overlap). Chunk character offsets are translated
to document-global offsets through each clause's ``source_span``; this is exact
because ``flatten_tables`` is a no-op on every CUAD paragraph (verified across
all 462 contracts).

GRACEFUL SKIP
-------------
Both the corpus and the benchmark are gitignored. When either is missing (or
the corpus has no ``.txt`` contracts) the harness prints one line, writes a
receipt recording the skip, and exits 0.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Any, NamedTuple

from openreview_cli.chunking import ChunkConfig, stream_chunks
from openreview_cli.parsing.models import Clause
from openreview_cli.retrieval.engine import RetrievalEngine
from openreview_cli.retrieval.ingest import ingest_document
from openreview_cli.retrieval.models import RetrievalQuery
from openreview_cli.retrieval.storage import RetrievalStorage

DEFAULT_BENCHMARK = Path("data/legalbenchrag/benchmarks/cuad.json")
DEFAULT_CORPUS_ROOT = Path("data/legalbenchrag/corpus")
DEFAULT_OUT = Path(".benchmark-reports/retrieval-accuracy.json")

#: ``retrieval.top_k`` default, read from the product in two places:
#: ``tui/domain/retrieval.py`` (``_DEFAULT_TOP_K = 5``) and
#: ``config/loader.py`` (``RetrievalConfig.top_k`` default 5). Re-stated here so
#: the receipt can contrast it with the depth this measurement actually uses.
PRODUCT_DEFAULT_TOP_K = 5

#: Deeper than the product default so hit@5/MRR@5 are not an artifact of the
#: cut; the receipt records both numbers.
DEFAULT_DEPTH = 20

#: Ported from storage.py's FTS5 definition, recorded in the receipt so a
#: reader can see exactly which keyword configuration produced the numbers.
#: ``porter`` is the shipped default; ``unicode61`` is the comparison arm.
DEFAULT_TOKENIZER = "porter"
TOKENIZER_CHOICES = ("porter", "unicode61")
FTS_PREFIX = "2 3"
FTS_ORDERING = "ORDER BY bm25(chunk_fts)"
#: storage.py's ``chunk_fts`` column/option list, minus the tokenizer, so the
#: comparison arm recreates the shipped table shape exactly.
FTS_COLUMNS = """
    chunk_id UNINDEXED,
    text,
    clause_heading,
    content='chunks',
    content_rowid='rowid',
    tokenize='{tokenize}',
    prefix='{prefix}'
"""


#: The FTS5 ``tokenize=`` value per arm. In FTS5 the first word names the
#: tokenizer and the rest are its arguments, so storage.py's shipped value
#: ``'porter unicode61'`` is the *porter* tokenizer wrapping unicode61; the
#: comparison arm is plain ``unicode61`` (accepting no arguments).
TOKENIZE_BY_TOKENIZER = {"porter": "porter unicode61", "unicode61": "unicode61"}


def fts_tokenize(tokenizer: str) -> str:
    """The FTS5 ``tokenize=`` value for ``tokenizer`` (mirrors storage.py)."""
    return TOKENIZE_BY_TOKENIZER[tokenizer]


CHUNKING_RULE = (
    "one chunk per blank-line-separated paragraph via "
    "openreview_cli.chunking.stream_chunks(ChunkConfig()) "
    "(chunk_size=512 tokens, chunk_overlap=50, group_short_clauses=True); "
    "paragraphs longer than 512 tokens are split by the product splitter. "
    "Offsets are document-global, translated through each clause's source_span."
)
GROUND_TRUTH_RULE = (
    "a chunk is relevant if its document character span [char_start, char_end) "
    "overlaps the query's CUAD answer span [start, end): "
    "char_start < end and char_end > start"
)

_PARAGRAPH_SEP_RE = re.compile(r"\n[ \t]*\n")


class QueryRef(NamedTuple):
    """One answerable benchmark query and the spans that count as relevant."""

    query: str
    file_path: str
    spans: list[tuple[int, int]]


# ── input loading ───────────────────────────────────────────────────────────


def load_document_text(corpus_root: Path, file_path: str) -> str | None:
    """Return the contract text for a corpus-relative ``file_path``.

    The literal path is tried first; an NFC-normalized retry covers a benchmark
    that stores a filename decomposed (NFD) while the file on disk is composed.
    Returns ``None`` when neither resolves.
    """
    literal = corpus_root / file_path
    if literal.is_file():
        return literal.read_text(encoding="utf-8", errors="replace")
    normalized = corpus_root / unicodedata.normalize("NFC", file_path)
    if normalized.is_file():
        return normalized.read_text(encoding="utf-8", errors="replace")
    return None


def _is_usable_span(span: object) -> bool:
    return (
        isinstance(span, (list, tuple))
        and len(span) == 2
        and all(isinstance(v, int) for v in span)
        and int(span[1]) > int(span[0])
    )


def _select_file_and_spans(
    snippets: list[Any],
) -> tuple[str, list[tuple[int, int]]] | None:
    """Pick the contract for a test and collect its answer spans.

    Every CUAD test references a single file, but grouping by ``file_path`` and
    keeping the file with the most usable spans is defensive and deterministic.
    """
    by_file: dict[str, list[tuple[int, int]]] = {}
    order: list[str] = []
    for snippet in snippets:
        if not isinstance(snippet, dict):
            continue
        file_path = snippet.get("file_path")
        span = snippet.get("span")
        if not isinstance(file_path, str) or not _is_usable_span(span):
            continue
        if file_path not in by_file:
            by_file[file_path] = []
            order.append(file_path)
        by_file[file_path].append((int(span[0]), int(span[1])))
    if not order:
        return None
    best = max(order, key=lambda name: (len(by_file[name]), -order.index(name)))
    return best, by_file[best]


def load_queries(benchmark_path: Path) -> tuple[list[QueryRef], int]:
    """Load answerable queries and count tests with no usable answer span."""
    payload = json.loads(Path(benchmark_path).read_text(encoding="utf-8"))
    tests = payload.get("tests") if isinstance(payload, dict) else None
    if not isinstance(tests, list):
        return [], 0

    queries: list[QueryRef] = []
    skipped_no_span = 0
    for test in tests:
        query = test.get("query") if isinstance(test, dict) else None
        selected = (
            _select_file_and_spans(test.get("snippets") or []) if isinstance(test, dict) else None
        )
        if selected is None or not isinstance(query, str) or not query.strip():
            skipped_no_span += 1
            continue
        file_path, spans = selected
        queries.append(QueryRef(query=query, file_path=file_path, spans=spans))
    return queries, skipped_no_span


# ── chunking + indexing (reuses the shipped chunker and FTS schema) ─────────


def build_clauses(text: str) -> list[Clause]:
    """One ``Clause`` per blank-line-separated paragraph, with document spans."""
    clauses: list[Clause] = []
    start = 0
    for index, match in enumerate(_PARAGRAPH_SEP_RE.finditer(text)):
        clauses.append(_clause_or_none(text, start, match.start(), index))
        start = match.end()
    clauses.append(_clause_or_none(text, start, len(text), len(clauses)))
    return [clause for clause in clauses if clause is not None]


def _clause_or_none(text: str, start: int, end: int, index: int) -> Clause | None:
    paragraph = text[start:end]
    if not paragraph.strip():
        return None
    return Clause(
        id=f"para-{index}",
        title=None,
        text=paragraph,
        level=0,
        parent_id=None,
        source_page=None,
        source_paragraph=index,
        source_span=(start, end),
    )


def build_chunks(text: str, document_id: str) -> list[dict[str, Any]]:
    """Chunk ``text`` with the product chunker, mapping offsets to the document."""
    clauses = build_clauses(text)
    offsets = {clause.id: clause.source_span for clause in clauses}
    chunks: list[dict[str, Any]] = []
    for chunk in stream_chunks(clauses, ChunkConfig(), show_progress=False):
        span = offsets.get(chunk.source_clause_id)
        base = span[0] if span is not None else 0
        chunks.append(
            {
                "chunk_id": f"{document_id[:12]}-{chunk.id}",
                "text": chunk.text,
                "clause_heading": chunk.source_clause_title or "",
                "clause_level": chunk.source_clause_level,
                "char_start": base + chunk.char_offset_start,
                "char_end": base + chunk.char_offset_end,
            }
        )
    return chunks


def configure_fts_tokenizer(db_path: Path, tokenizer: str) -> None:
    """Rebuild ``chunk_fts`` with ``tokenizer``, mirroring storage.py's DDL.

    ``RetrievalStorage.create_schema`` (the product's, unedited) hardcodes
    ``tokenize='porter unicode61'``. For the default arm nothing happens here --
    the shipped table is left exactly as ingest created it. For any other arm
    the virtual table is dropped and recreated with the chosen tokenizer using
    the same columns, ``UNINDEXED`` flag, external content table and ``prefix``
    options, then repopulated with ``rebuild``.
    """
    tokenize = fts_tokenize(tokenizer)
    if tokenizer == DEFAULT_TOKENIZER:
        return
    with RetrievalStorage(db_path) as storage:
        storage.conn.execute("DROP TABLE IF EXISTS chunk_fts")
        storage.conn.execute(
            "CREATE VIRTUAL TABLE chunk_fts USING fts5("
            + FTS_COLUMNS.format(tokenize=tokenize, prefix=FTS_PREFIX)
            + ")"
        )
        storage.conn.execute("INSERT INTO chunk_fts(chunk_fts) VALUES('rebuild')")
        storage.conn.commit()


def index_contract(
    text: str,
    db_path: Path,
    document_id: str,
    *,
    tokenizer: str = DEFAULT_TOKENIZER,
) -> list[dict[str, Any]]:
    """Build a per-contract FTS5 index with the product's ingest path."""
    chunks = build_chunks(text, document_id)
    ingest_document(chunks, db_path, document_id=document_id)
    configure_fts_tokenizer(db_path, tokenizer)
    return chunks


# ── scoring ─────────────────────────────────────────────────────────────────


def _overlaps(chunk_start: int, chunk_end: int, gold_start: int, gold_end: int) -> bool:
    return chunk_start < gold_end and chunk_end > gold_start


def score_query(
    db_path: Path,
    query_text: str,
    gold_spans: list[tuple[int, int]],
    depth: int,
) -> dict[str, Any]:
    """Retrieve ``query_text`` and score rank of the first relevant chunk."""
    results = RetrievalEngine(db_path).retrieve(
        RetrievalQuery(query_text=query_text, method="sparse", top_k=depth)
    )
    first_rank: int | None = None
    for rank, result in enumerate(results, start=1):
        if any(
            _overlaps(result.char_start, result.char_end, gold_start, gold_end)
            for gold_start, gold_end in gold_spans
        ):
            first_rank = rank
            break
    in_top_5 = first_rank is not None and first_rank <= 5
    return {
        "first_rank": first_rank,
        "hit_at_1": 1.0 if first_rank == 1 else 0.0,
        "hit_at_5": 1.0 if in_top_5 else 0.0,
        "reciprocal_rank_at_5": (1.0 / first_rank) if in_top_5 else 0.0,
    }


def _has_contracts(corpus_root: Path) -> bool:
    return any(corpus_root.glob("**/*.txt"))


def _missing_input_reason(benchmark_path: Path, corpus_root: Path) -> str | None:
    if not benchmark_path.is_file():
        return f"benchmark file not found: {benchmark_path}"
    if not corpus_root.is_dir():
        return f"corpus root not found: {corpus_root}"
    if not _has_contracts(corpus_root):
        return f"no .txt contracts under corpus root: {corpus_root}"
    return None


def _receipt_skeleton(
    benchmark_path: Path,
    corpus_root: Path,
    depth: int,
    *,
    tokenizer: str,
    skipped: bool,
) -> dict[str, Any]:
    return {
        "skipped": skipped,
        "reason": None,
        "benchmark": str(benchmark_path),
        "corpus_root": str(corpus_root),
        "method": "sparse: BM25 over SQLite FTS5",
        "fts": {
            "tokenizer": tokenizer,
            "tokenize": fts_tokenize(tokenizer),
            "prefix": FTS_PREFIX,
            "ordering": FTS_ORDERING,
            "default_tokenizer": DEFAULT_TOKENIZER,
        },
        "chunking_rule": CHUNKING_RULE,
        "ground_truth_rule": GROUND_TRUTH_RULE,
        "retrieval_depth": depth,
        "product_default_top_k": PRODUCT_DEFAULT_TOP_K,
        "metrics": {"hit_at_1": 0.0, "hit_at_5": 0.0, "mrr_at_5": 0.0},
        "sample": {
            "queries_total": 0,
            "queries_with_usable_span": 0,
            "queries_scored": 0,
            "queries_skipped_missing_contract": 0,
            "queries_skipped_no_span": 0,
            "queries_with_no_relevant_chunk": 0,
            "contracts_used": 0,
            "chunks_indexed_total": 0,
        },
        "caveats": [
            "Ground truth is character-span overlap, not semantic answer correctness; a chunk "
            "that merely touches an answer span counts as relevant. This is the weakest link.",
            "The product parses PDF/DOCX only; the CUAD .txt corpus is chunked by building "
            "paragraph-level Clause objects and driving the product chunker directly, so "
            "chunk boundaries approximate -- but do not equal -- a real product parse.",
            "Each contract is indexed alone and its index reused across its queries, matching "
            "the product's per-document index; there is no cross-document retrieval.",
            "hit@1/hit@5/MRR@5 are macro-averages over queries (each query weighs equally).",
            "Equal BM25 scores are ordered by SQLite without a stable tiebreak.",
        ],
    }


def evaluate(
    benchmark_path: str | Path,
    corpus_root: str | Path,
    *,
    limit: int | None = None,
    depth: int = DEFAULT_DEPTH,
    tokenizer: str = DEFAULT_TOKENIZER,
) -> dict[str, Any]:
    """Run the measurement and return a JSON-serializable receipt."""
    benchmark_path = Path(benchmark_path)
    corpus_root = Path(corpus_root)
    if not 5 <= depth <= 50:
        raise ValueError(f"depth must be between 5 and 50, got {depth}")
    if tokenizer not in TOKENIZER_CHOICES:
        raise ValueError(f"tokenizer must be one of {sorted(TOKENIZER_CHOICES)}, got {tokenizer!r}")

    reason = _missing_input_reason(benchmark_path, corpus_root)
    if reason is not None:
        receipt = _receipt_skeleton(
            benchmark_path, corpus_root, depth, tokenizer=tokenizer, skipped=True
        )
        receipt["reason"] = reason
        return receipt

    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
    total_tests = len(payload.get("tests", [])) if isinstance(payload, dict) else 0
    queries, skipped_no_span = load_queries(benchmark_path)
    if not queries:
        receipt = _receipt_skeleton(
            benchmark_path, corpus_root, depth, tokenizer=tokenizer, skipped=True
        )
        receipt["reason"] = "no benchmark query has a usable answer span"
        receipt["sample"]["queries_total"] = total_tests
        receipt["sample"]["queries_skipped_no_span"] = skipped_no_span
        return receipt

    hit_at_1 = 0.0
    hit_at_5 = 0.0
    mrr_at_5 = 0.0
    scored = 0
    skipped_missing = 0
    no_relevant = 0
    contracts_used = 0
    chunks_indexed = 0
    cache: dict[str, tuple[Path, list[dict[str, Any]]] | None] = {}

    with tempfile.TemporaryDirectory(prefix="retrieval-accuracy-") as tmp:
        work_dir = Path(tmp)
        for ref in queries:
            if limit is not None and scored >= limit:
                break
            if ref.file_path not in cache:
                text = load_document_text(corpus_root, ref.file_path)
                if text is None:
                    cache[ref.file_path] = None
                else:
                    document_id = hashlib.sha256(ref.file_path.encode("utf-8")).hexdigest()
                    db_path = work_dir / f"{document_id[:16]}.db"
                    chunks = index_contract(text, db_path, document_id, tokenizer=tokenizer)
                    cache[ref.file_path] = (db_path, chunks)
                    contracts_used += 1
                    chunks_indexed += len(chunks)

            entry = cache[ref.file_path]
            if entry is None:
                skipped_missing += 1
                continue
            db_path, chunks = entry

            if not any(
                _overlaps(chunk["char_start"], chunk["char_end"], gold_start, gold_end)
                for chunk in chunks
                for gold_start, gold_end in ref.spans
            ):
                no_relevant += 1

            score = score_query(db_path, ref.query, ref.spans, depth)
            hit_at_1 += score["hit_at_1"]
            hit_at_5 += score["hit_at_5"]
            mrr_at_5 += score["reciprocal_rank_at_5"]
            scored += 1

    receipt = _receipt_skeleton(
        benchmark_path, corpus_root, depth, tokenizer=tokenizer, skipped=False
    )
    if scored:
        receipt["metrics"] = {
            "hit_at_1": round(hit_at_1 / scored, 6),
            "hit_at_5": round(hit_at_5 / scored, 6),
            "mrr_at_5": round(mrr_at_5 / scored, 6),
        }
    receipt["sample"] = {
        "queries_total": total_tests,
        "queries_with_usable_span": len(queries),
        "queries_scored": scored,
        "queries_skipped_missing_contract": skipped_missing,
        "queries_skipped_no_span": skipped_no_span,
        "queries_with_no_relevant_chunk": no_relevant,
        "contracts_used": contracts_used,
        "chunks_indexed_total": chunks_indexed,
    }
    return receipt


# ── CLI ─────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--corpus-root", default=str(DEFAULT_CORPUS_ROOT))
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="JSON receipt path.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum queries to score (default: all queries that have a usable span).",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=DEFAULT_DEPTH,
        help=f"Retrieval depth; product default is {PRODUCT_DEFAULT_TOP_K} (default: %(default)s).",
    )
    parser.add_argument(
        "--tokenizer",
        choices=TOKENIZER_CHOICES,
        default=DEFAULT_TOKENIZER,
        help=(
            "FTS5 tokenizer arm; the shipped index DDL uses "
            f"'{fts_tokenize(DEFAULT_TOKENIZER)}' (default: %(default)s)."
        ),
    )
    return parser.parse_args(argv)


def _print_summary(receipt: dict[str, Any], out_path: Path) -> None:
    if receipt["skipped"]:
        print(f"SKIP: {receipt['reason']}")
        print(f"Output: {out_path}")
        return

    metrics = receipt["metrics"]
    sample = receipt["sample"]
    print(f"--- CUAD keyword-retrieval accuracy (tokenizer: {receipt['fts']['tokenizer']}) ---")
    print(
        f"Queries scored:       {sample['queries_scored']} "
        f"(contracts used: {sample['contracts_used']})"
    )
    print(f"hit@1:                {metrics['hit_at_1']:.4f}")
    print(f"hit@5:                {metrics['hit_at_5']:.4f}")
    print(f"MRR@5:                {metrics['mrr_at_5']:.4f}")
    print(
        f"Retrieval depth:      {receipt['retrieval_depth']} "
        f"(product default: {receipt['product_default_top_k']})"
    )
    print(f"Output: {out_path}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.monotonic()
    receipt = evaluate(
        args.benchmark,
        args.corpus_root,
        limit=args.limit,
        depth=args.depth,
        tokenizer=args.tokenizer,
    )
    receipt["elapsed_seconds"] = round(time.monotonic() - started, 2)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _print_summary(receipt, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
