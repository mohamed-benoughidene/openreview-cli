#!/usr/bin/env python
"""PILOT measurement: does the cloud reranker `voyage/rerank-2.5` help or hurt
legal-contract retrieval on LegalBenchRAG-CUAD?

Throwaway measurement harness (item 6). It does NOT touch production code; it stages a
scratch corpus, builds per-contract retrieval indexes with the REAL product chunker +
PII engine, and compares two arms over an identical candidate pool:

    sparse              (product BM25/FTS5 query, no fusion — standalone arm)
    hybrid              (RRF of BM25 + dense, no rerank)
    hybrid + rerank-2.5 (same fused pool, reordered by voyage/rerank-2.5)

The sparse and hybrid arms call the PRODUCT retrieval path directly (`search_bm25`) —
since the BM25 operator fix `preprocess_query` quotes each term and OR-joins them, so
natural-language and hyphenated CUAD queries (e.g. "i-escrow") build a valid, non-empty
FTS5 expression (the old implicit-AND build returned zero rows for every query).

Ground truth = chunks whose [char_start, char_end) overlaps a query snippet span.

Reproduction (from the repo root, inside the project venv):

    # default full pilot: 20 deterministic contracts + all their queries (~156)
    .venv/bin/python scripts/benchmark_rerank_legalbenchrag.py --contracts 20
    # quick end-to-end smoke (1 contract)
    .venv/bin/python scripts/benchmark_rerank_legalbenchrag.py --contracts 1

Outputs (all gitignored scratch, no raw contract text is written):
    data/legalbenchrag/rerank_eval/            indexes, gateway db, per_query.jsonl
    draft/reranker_pilot_results.json          raw per-query numbers
    draft/reranker_pilot_report.md             human report

Privacy: contract chunks AND queries are stripped with the real PiiEngine (config
`privacy.pii_threshold`) before any cloud call; `mark_pii_available()` is recorded in
process only after a real strip. PII is stripped with the documented threshold.

Rate limits: this Voyage account has NO payment method, so it is hard-throttled to
~3 RPM / 10K TPM (see the run log). The harness therefore paces every cloud call to a
token budget and retries on 429. POOL DEPTH is capped because a depth-20 request at the
product's 512-token chunking (~14K tokens) is rejected outright under a 10K TPM cap.

Cost limits: the gateway hard-exits (code 6) past `gateway.cost_limits`; this script
passes a session id and lifts the caps via env overrides (config is never edited) and
reports the measured cost.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import unicodedata
from collections import defaultdict, deque
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from openreview_cli.chunking.models import ChunkConfig  # noqa: E402
from openreview_cli.chunking.splitter import (  # noqa: E402
    flatten_tables,
    reset_chunk_counter,
    split_clause,
)
from openreview_cli.config.loader import load_config  # noqa: E402
from openreview_cli.config.paths import get_config_dir  # noqa: E402
from openreview_cli.gateway.errors import RateLimitError  # noqa: E402
from openreview_cli.gateway.router import Gateway, mark_pii_available  # noqa: E402
from openreview_cli.parsing.models import Clause, Document  # noqa: E402
from openreview_cli.pii.engine import PiiEngine, strip_pii_clauses  # noqa: E402

CORPUS_DIR = REPO / "data/legalbenchrag/corpus"
BENCH_PATH = REPO / "data/legalbenchrag/benchmarks/cuad.json"
EVAL_DIR = REPO / "data/legalbenchrag/rerank_eval"
INDEX_DIR = EVAL_DIR / "indexes"
GATEWAY_DB = EVAL_DIR / "gateway.db"
PER_QUERY_JSONL = EVAL_DIR / "per_query.jsonl"
RUN_META_PATH = EVAL_DIR / "run_meta.json"
RESULTS_PATH = REPO / "draft/reranker_pilot_results.json"
REPORT_PATH = REPO / "draft/reranker_pilot_report.md"

CHUNK_SIZE = 512  # product ChunkConfig default
CHUNK_OVERLAP = 50
# Voyage list pricing (docs.voyageai.com/docs/pricing), USD per 1M tokens.
PRICE_EMBED_PER_MTOK = 0.06  # voyage-3.5
PRICE_RERANK_PER_MTOK = 0.05  # rerank-2.5


# ─────────────────────────────── helpers ──────────────────────────────────────


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    return sum(1 for c in retrieved[:k] if c in relevant) / k if k else 0.0


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    return sum(1 for c in retrieved[:k] if c in relevant) / len(relevant) if relevant else 0.0


def mrr_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    for i, c in enumerate(retrieved[:k], start=1):
        if c in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    dcg = sum(1.0 / math.log2(i + 1) for i, c in enumerate(retrieved[:k], start=1) if c in relevant)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(k, len(relevant)) + 1))
    return dcg / ideal if ideal > 0 else 0.0


def bootstrap_ci(deltas: list[float], n: int, seed: int) -> tuple[float, float]:
    import numpy as np

    arr = np.asarray(deltas, dtype=float)
    if arr.size == 0:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    means = arr[rng.integers(0, arr.size, size=(n, arr.size))].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return (float(lo), float(hi))


class RateLimitPacer:
    """Keep cloud calls inside a token/request budget per sliding window.

    The account is hard-throttled (no payment method); this paces to `tpm` tokens and
    `rpm` requests per `window` seconds and lets the caller retry on 429.
    """

    def __init__(self, tpm: int, rpm: int, window: float = 60.0) -> None:
        self.tpm, self.rpm, self.window = tpm, rpm, window
        self._events: deque[tuple[float, int]] = deque()
        self._last_wait = 0.0

    def _prune(self, now: float) -> None:
        while self._events and now - self._events[0][0] > self.window:
            self._events.popleft()

    def acquire(self, tokens: int) -> None:
        while True:
            now = time.monotonic()
            self._prune(now)
            used = sum(t for _, t in self._events)
            if len(self._events) < self.rpm and used + tokens <= self.tpm:
                return
            if not self._events:  # oversized request, empty window: let retry handle it
                return
            wait = self._events[0][0] + self.window - now + 0.5
            self._last_wait = max(0.0, wait)
            time.sleep(max(0.5, wait))

    def record(self, tokens: int) -> None:
        self._events.append((time.monotonic(), tokens))


def call_paced(pacer: RateLimitPacer, fn, est_tokens: int, tries: int = 6):
    """Run a cloud call under the pacer; retry on 429 with backoff."""
    last_exc: Exception | None = None
    for attempt in range(tries):
        pacer.acquire(est_tokens)
        try:
            result = fn()
        except RateLimitError as exc:
            last_exc = exc
            backoff = min(60.0, 15.0 * (attempt + 1))
            print(f"    [throttled] retry {attempt + 1}/{tries} in {backoff:.0f}s", file=sys.stderr)
            time.sleep(backoff)
        else:
            pacer.record(est_tokens)
            return result
    raise last_exc  # type: ignore[misc]


# ─────────────────────────────── data ─────────────────────────────────────────


def load_benchmark() -> tuple[dict[str, list[dict]], dict[str, Path]]:
    tests = json.loads(BENCH_PATH.read_text())["tests"]
    by_file: dict[str, list[dict]] = defaultdict(list)
    for t in tests:
        by_file[nfc(t["snippets"][0]["file_path"])].append(t)
    disk = {nfc(p.name): p for p in CORPUS_DIR.glob("cuad/*.txt")}
    return dict(by_file), disk


def select_pilot(by_file, disk, n_contracts, max_queries):
    files = sorted(f for f in by_file if nfc(f).split("/", 1)[1] in disk)
    pilot = files[:n_contracts]
    paths = {f: disk[nfc(f).split("/", 1)[1]] for f in pilot}
    per_file = {f: by_file[f] for f in pilot}
    if max_queries:
        kept, total = {}, 0
        for f in pilot:
            take = per_file[f][: max(0, max_queries - total)]
            if take:
                kept[f] = take
                total += len(take)
        per_file = kept
    return list(per_file), paths, per_file


# ─────────────────────────────── indexing ─────────────────────────────────────


def make_document(path: Path, clause_count: int) -> Document:
    return Document(
        source_path=path,
        format="pdf",
        page_count=1,
        clause_count=clause_count,
        parse_duration_seconds=0.0,
        warnings=[],
    )


def build_index(
    gateway, file_key, path, pii_engine, pii_threshold, session_id, embed_fn, pacer
) -> dict:
    """Chunk + PII-strip + embed one contract into its own SQLite index."""
    from openreview_cli.retrieval.dense import compute_l2_norm, serialize_embedding
    from openreview_cli.retrieval.storage import RetrievalStorage

    raw = path.read_text("utf-8", errors="replace")
    if not raw.strip():
        raise RuntimeError(f"empty contract text: {file_key}")
    if flatten_tables(raw) != raw:
        raise RuntimeError(f"flatten_tables changed text for {file_key}; offsets unsafe")

    reset_chunk_counter()
    clause = Clause(
        id="contract",
        title=path.name,
        text=raw,
        level=0,
        parent_id=None,
        source_page=None,
        source_paragraph=0,
        source_span=(0, len(raw)),
    )
    chunks = list(split_clause(clause, ChunkConfig(CHUNK_SIZE, CHUNK_OVERLAP)))
    pii_clauses = [
        Clause(
            id=c.id,
            title=path.name,
            text=c.text,
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=i,
            source_span=None,
        )
        for i, c in enumerate(chunks)
    ]
    stripped, pii_result = strip_pii_clauses(
        pii_clauses,
        make_document(path, len(chunks)),
        threshold=pii_threshold,
        strip_metadata=False,
        engine=pii_engine,
    )
    stripped_text = {sc.id: sc.text for sc in stripped}
    mark_pii_available()  # a real strip just completed; cloud egress may proceed

    document_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    db_path = INDEX_DIR / f"{document_id[:32]}.sqlite"
    db_path.unlink(missing_ok=True)  # drop any half-built index from an aborted run
    with RetrievalStorage(db_path) as storage:
        storage.create_schema()
        storage.conn.execute(
            """INSERT OR REPLACE INTO index_meta
                 (document_id, document_path, index_version, index_status, index_timestamp,
                  chunk_count, method, embedding_model, embedding_dim, db_size_bytes)
               VALUES (?, ?, 1, 'ingesting', ?, ?, 'hybrid', ?, ?, 0)""",
            (
                document_id,
                file_key,
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                len(chunks),
                gateway.slot_primary_model("embedding"),
                1024,
            ),
        )
        storage.conn.commit()
        records = []
        for c in chunks:
            text = stripped_text[c.id]
            storage.insert_chunk(
                {
                    "chunk_id": c.id,
                    "document_id": document_id,
                    "text": text,
                    "clause_heading": path.name,
                    "clause_level": 0,
                    "heading_chain": [path.name],
                    "char_start": c.char_offset_start,
                    "char_end": c.char_offset_end,
                }
            )
            records.append(
                {
                    "chunk_id": c.id,
                    "char_start": c.char_offset_start,
                    "char_end": c.char_offset_end,
                    "text": text,
                }
            )
        vectors = embed_fn([r["text"] for r in records], session_id, pacer)
        for rec, vec in zip(records, vectors, strict=True):
            storage.insert_embedding(
                rec["chunk_id"],
                serialize_embedding(vec),
                gateway.slot_primary_model("embedding") or "unknown",
                len(vec),
                compute_l2_norm(vec),
            )
        storage.set_index_status("indexed")
    # Proof that stripping ran: entities detected, chunks whose text actually changed,
    # and distinct PII values replaced (the mapping keys).
    masked_chunks = sum(1 for c, sc in zip(chunks, stripped, strict=True) if c.text != sc.text)
    return {
        "document_id": document_id,
        "db_path": str(db_path),
        "chunks": records,
        "pii_entities": len(pii_result.entities),
        "masked_chunks": masked_chunks,
        "masked_values": len(pii_result.mapping),
    }


# ─────────────────────────────── retrieval ────────────────────────────────────


def retrieve_arms(
    gateway,
    db_path,
    query_text,
    query_vec,
    pool_depth,
    top_k,
    rrf_k,
    session_id,
    pacer,
    tries: int = 12,
) -> dict:
    """Build the fused pool once; score the no-rerank and rerank arms on the SAME pool."""
    from openreview_cli.retrieval.bm25 import normalize_bm25_scores, search_bm25
    from openreview_cli.retrieval.dense import (
        compute_l2_norm,
        cosine_similarity,
        deserialize_embedding,
    )
    from openreview_cli.retrieval.rrf import rrf_fuse
    from openreview_cli.retrieval.storage import RetrievalStorage

    search_depth = max(pool_depth * 3, 30)
    dim = len(query_vec)
    with RetrievalStorage(db_path) as storage:
        # Product sparse path (post BM25 operator fix): preprocess_query quotes each term
        # and OR-joins them, so natural-language/hyphenated queries build a valid FTS5
        # expression instead of the old implicit-AND (which matched nothing on CUAD).
        sparse_ranks = normalize_bm25_scores(search_bm25(storage, query_text, search_depth))
        sparse_sorted = [c for c, _ in sorted(sparse_ranks.items(), key=lambda x: x[1])]
        qnorm = compute_l2_norm(query_vec)
        scored = sorted(
            (
                (cid, cosine_similarity(query_vec, deserialize_embedding(blob, dim), qnorm, cnorm))
                for cid, blob, cnorm in storage.load_embeddings()
            ),
            key=lambda x: -x[1],
        )
        dense_ranks = {cid: r for r, (cid, _) in enumerate(scored[:search_depth], start=1)}
        pool = [c for c, _ in rrf_fuse(sparse_ranks, dense_ranks, k=rrf_k)[:pool_depth]]
        pool_texts = [(storage.load_chunk(c) or {}).get("text", "") for c in pool]

    hybrid_top = pool[:top_k]
    rerank_top: list[str] = []
    if pool_texts:
        est = (len(query_text) + sum(len(t) for t in pool_texts)) // 4 + 1
        rr = call_paced(
            pacer,
            lambda: gateway.rerank(
                "reranking", query_text, pool_texts, top_n=len(pool_texts), session_id=session_id
            ),
            est,
            tries=tries,
        )
        ordered = sorted(rr, key=lambda r: (-r["relevance_score"], r["index"]))
        rerank_top = [pool[r["index"]] for r in ordered[:top_k] if r["index"] < len(pool)]
    return {
        "pool": pool,
        "sparse_top": sparse_sorted[:top_k],
        "hybrid_top": hybrid_top,
        "rerank_top": rerank_top,
        "rerank_tokens_est": (len(query_text) + sum(len(t) for t in pool_texts)) // 4 + 1,
    }


# ─────────────────────────────── main ─────────────────────────────────────────


def batched(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def aggregate(rows: list[dict], meta: dict, index_info: dict, cost: dict) -> dict:
    def mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    cost = {
        "wall_clock_s": 0.0,
        "embedding_tokens_recorded": 0,
        "embedding_cost_usd": 0.0,
        "rerank_tokens_estimated": 0,
        "rerank_cost_usd_estimated": 0.0,
        "recorded_cost_cents": 0,
        "price_assumptions_usd_per_mtok": {
            "embedding": PRICE_EMBED_PER_MTOK,
            "rerank": PRICE_RERANK_PER_MTOK,
        },
        **cost,
    }

    deltas = [q["delta_p5"] for q in rows]
    ci_lo, ci_hi = bootstrap_ci(deltas, meta["bootstrap_resamples"], meta["seed"])
    helped = sum(1 for d in deltas if d > 1e-9)
    hurt = sum(1 for d in deltas if d < -1e-9)
    wilcoxon = None
    try:
        from scipy.stats import wilcoxon as _w

        if any(abs(d) > 1e-12 for d in deltas):
            stat, pval = _w(deltas)
            wilcoxon = {"statistic": float(stat), "pvalue": float(pval)}
    except Exception as exc:
        wilcoxon = {"error": f"{type(exc).__name__}: {exc}"}

    def arm(metric: str, which: str) -> float:
        return mean([q[f"{metric}_{which}"] for q in rows])

    mapped = sum(1 for q in rows if q["mapped"])
    return {
        "meta": meta,
        "index": index_info,
        "mapping": {
            "mapped": mapped,
            "total": len(rows),
            "rate": mapped / len(rows) if rows else 0.0,
        },
        "arms": {
            "hybrid": {m: arm(m, "without") for m in ("p5", "ndcg5", "mrr", "recall5")},
            "hybrid_rerank": {m: arm(m, "with") for m in ("p5", "ndcg5", "mrr", "recall5")},
            "sparse": {"P@5": mean([q["p5_sparse"] for q in rows])},
        },
        "paired": {
            "mean_delta_p5": mean(deltas),
            "bootstrap_ci95": [ci_lo, ci_hi],
            "wilcoxon": wilcoxon,
            "helped": helped,
            "hurt": hurt,
            "tied": len(deltas) - helped - hurt,
            "n": len(deltas),
        },
        "cost": cost,
        "queries": rows,
    }


def write_report(path: Path, r: dict) -> None:
    m, idx, mp = r["meta"], r["index"], r["mapping"]
    hy, hr, sp, pc, cost = (
        r["arms"]["hybrid"],
        r["arms"]["hybrid_rerank"],
        r["arms"]["sparse"],
        r["paired"],
        r["cost"],
    )

    def pct(x):
        return f"{100 * x:.1f}%"

    lines = [
        "# Reranker pilot — LegalBenchRAG-CUAD (`voyage/rerank-2.5`)",
        "",
        f"_Run `{m['run_id']}` — {m['timestamp_utc']}_",
        "",
        "## Scope",
        "",
        f"- Pilot: **{idx['contracts']} contracts**, **{mp['total']} queries**, "
        f"**{idx['chunks']} chunks** (product chunker {m['chunker']['chunk_size']}/"
        f"{m['chunker']['chunk_overlap']}).",
        f"- Models: embedding `{m['embedding_model']}`, reranker `{m['rerank_model']}`.",
        f"- Privacy tier `{m['privacy_tier']}`; real PII strip at threshold {m['pii_threshold']} "
        f"before any cloud call.",
        f"- PII masked before egress: **{idx.get('pii_entities_chunks', 0)} chunk entities** in "
        f"**{idx.get('masked_chunks', 0)}/{idx['chunks']} chunks** "
        f"({idx.get('masked_chunk_values', 0)} distinct values); "
        f"**{idx.get('pii_entities_queries', 0)} query entities** in "
        f"**{idx.get('masked_queries', 0)}/{mp['total']} queries** "
        f"({idx.get('masked_query_values', 0)} distinct values). "
        f"Counts cover {idx.get('pii_contracts_counted', 0)}/{idx['contracts']} indexed contracts.",
        f"- Pool depth {m['pool_depth']} (see caveats — a hard 9-10K TPM cap makes depth 20 "
        f"impossible at this chunking), metric top-{m['top_k']}, RRF k={m['rrf_k']}.",
        "",
        "## Ground-truth mapping",
        "",
        f"- Relevant chunks = overlap with the query span(s). "
        f"**Mapping rate {pct(mp['rate'])} ({mp['mapped']}/{mp['total']}).**",
        "",
        "## Arms (identical fused pool; reranker applied in fused order)",
        "",
        "| Arm | P@5 | nDCG@5 | MRR@5 | Recall@5 |",
        "|---|---|---|---|---|",
        f"| hybrid (no rerank) | {hy['p5']:.3f} | {hy['ndcg5']:.3f} | {hy['mrr']:.3f} | {hy['recall5']:.3f} |",
        f"| hybrid + rerank-2.5 | {hr['p5']:.3f} | {hr['ndcg5']:.3f} | {hr['mrr']:.3f} | {hr['recall5']:.3f} |",
        f"| sparse (product BM25, no rerank) | {sp['P@5']:.3f} | — | — | — |",
        "",
        "> Note: the `sparse` arm calls the product FTS5 path directly. Since the BM25 "
        "operator fix, `preprocess_query` quotes each term and OR-joins them, so natural-"
        "language and hyphenated CUAD queries (e.g. `i-escrow`) build a valid, non-empty "
        "FTS5 expression; the old implicit-AND build returned zero rows for every query. "
        "The two `hybrid` arms share the identical fused pool, so the reranker comparison "
        "does not depend on the sparse leg.",
        "",
        "## Paired ΔP@5 (rerank - no-rerank)",
        "",
        f"- Mean ΔP@5 = **{pc['mean_delta_p5']:+.4f}** (bootstrap 95% CI "
        f"[{pc['bootstrap_ci95'][0]:+.4f}, {pc['bootstrap_ci95'][1]:+.4f}], "
        f"{m['bootstrap_resamples']} resamples).",
        f"- Wilcoxon signed-rank: {pc['wilcoxon']}.",
        f"- Helped **{pct(pc['helped'] / pc['n'])}**, hurt **{pct(pc['hurt'] / pc['n'])}**, "
        f"tied **{pct(pc['tied'] / pc['n'])}** of {pc['n']} queries.",
        "",
        "## Cost & time",
        "",
        f"- Wall-clock **{cost['wall_clock_s']:.1f}s**.",
        f"- Embedding (recorded by the gateway): {cost['embedding_tokens_recorded']} tokens → "
        f"**${cost['embedding_cost_usd']:.4f}**.",
        f"- Rerank (estimated — Voyage returns no usage for rerank): "
        f"~{cost['rerank_tokens_estimated']:.0f} tokens → "
        f"**~${cost['rerank_cost_usd_estimated']:.4f}**.",
        f"- Cost DB recorded {cost['recorded_cost_cents']}¢.",
        "",
        "## Caveats",
        "",
        "- This is a **pilot**; the CI is wide and **cannot settle the default**.",
        "- The Voyage account is free-tier throttled (no payment method): ~3 RPM / 10K TPM. "
        "A depth-20 request at 512-token chunks is ~14K tokens and is rejected outright, so "
        "pool depth was reduced to the largest value that fits the cap.",
        "- Queries are PII-stripped too (no raw text egresses); both arms see the identical "
        "stripped query, so the paired comparison is unaffected.",
        "- Rerank token cost is estimated (~chars/4); Voyage does not return rerank usage.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--contracts",
        type=int,
        default=20,
        help="pilot contracts, deterministic sorted selection (default 20)",
    )
    ap.add_argument("--max-queries", type=int, default=0, help="cap queries (0 = all)")
    ap.add_argument("--pool-depth", type=int, default=12, help="rerank pool depth (TPM-bounded)")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--tpm", type=int, default=9000, help="pacer token budget per minute")
    ap.add_argument("--rpm", type=int, default=3, help="pacer request budget per minute")
    ap.add_argument("--embed-batch", type=int, default=8, help="texts per embedding request")
    ap.add_argument("--tries", type=int, default=12, help="paced-call retries on 429")
    ap.add_argument(
        "--resume",
        action="store_true",
        help="keep per_query.jsonl + indexes and skip contracts already done",
    )
    ap.add_argument(
        "--aggregate-only",
        action="store_true",
        help="rebuild results+report from the existing per_query.jsonl; no cloud calls",
    )
    ap.add_argument("--results", type=Path, default=RESULTS_PATH)
    ap.add_argument("--report", type=Path, default=REPORT_PATH)
    args = ap.parse_args()

    _set_cloud_env()
    if args.aggregate_only:
        _aggregate_only(args)
        return

    config_path = get_config_dir() / "config.yml"
    auth_path = get_config_dir() / "auth.json"
    config = load_config(config_path)
    pii_threshold = float(config["privacy"].get("pii_threshold", 0.7))
    rrf_k = int(config.get("retrieval", {}).get("rrf_k", 60))

    t_start = time.perf_counter()
    run_id = time.strftime("rerank-pilot-%Y%m%dT%H%M%SZ", time.gmtime())
    session_id = run_id

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    if not args.resume:
        if INDEX_DIR.exists():
            for p in INDEX_DIR.glob("*"):
                p.unlink()
        PER_QUERY_JSONL.write_text("")
        RUN_META_PATH.unlink(missing_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    from openreview_cli.storage.database import init_database

    init_database(GATEWAY_DB)
    gateway = Gateway(config_path, auth_path, GATEWAY_DB)
    # The account is request-throttled (3 RPM). The gateway's own fallback loop retries
    # 3x per call, multiplying the request count and burning the RPM budget; disable it
    # here (in-memory only) and let this harness's pacer own the retry/backoff.
    gateway._config.setdefault("gateway", {}).setdefault("fallback", {})["retries"] = 0
    embed_model = gateway.slot_primary_model("embedding")
    rerank_model = gateway.slot_primary_model("reranking")
    pacer = RateLimitPacer(args.tpm, args.rpm)
    print(f"[gateway] embedding={embed_model} reranking={rerank_model}", file=sys.stderr)
    print(
        f"[gateway] tier={config['privacy']['tier']} pii_threshold={pii_threshold} "
        f"cost_caps={config['gateway']['cost_limits']} caps_lifted_to=20000c",
        file=sys.stderr,
    )
    print(f"[pacer] tpm={args.tpm} rpm={args.rpm} window=60s tries={args.tries}", file=sys.stderr)

    by_file, disk = load_benchmark()
    pilot_files, pilot_paths, per_file = select_pilot(
        by_file, disk, args.contracts, args.max_queries
    )

    done = (
        {r["contract"] for r in _read_jsonl()}
        if args.resume and PER_QUERY_JSONL.exists()
        else set()
    )
    todo = [f for f in pilot_files if f not in done]
    n_queries = sum(len(per_file[f]) for f in todo)
    print(
        f"[pilot] contracts={len(pilot_files)} todo_contracts={len(todo)} new_queries={n_queries} "
        f"pool_depth={args.pool_depth} (already done: {len(done)})",
        file=sys.stderr,
    )

    meta = build_meta(args, config, embed_model, rerank_model, pii_threshold, rrf_k)
    prior_meta = _load_run_meta()
    run_state = {
        "meta": meta,
        "per_contract": dict(prior_meta.get("per_contract", {})),
        "pii_entities_queries": int(prior_meta.get("pii_entities_queries", 0)),
        "masked_queries": int(prior_meta.get("masked_queries", 0)),
        "masked_query_values": int(prior_meta.get("masked_query_values", 0)),
        "cost": dict(prior_meta.get("cost", {})),
    }

    pii_engine = PiiEngine(threshold=pii_threshold)
    if not pii_engine.is_available():
        raise SystemExit("PII engine unavailable — refusing to send raw text to the cloud")

    def embed_fn(texts, sid, pac):
        out: list[list[float]] = []
        for batch in batched(texts, args.embed_batch):
            est = sum(len(t) for t in batch) // 4 + 1
            out.extend(
                call_paced(
                    pac,
                    lambda b=batch: gateway.embed("embedding", b, session_id=sid),
                    est,
                    tries=args.tries,
                )
            )
        return out

    rerank_tokens_total = 0
    qid = len(_read_jsonl())
    for i, fkey in enumerate(todo, 1):
        info = build_index(
            gateway, fkey, pilot_paths[fkey], pii_engine, pii_threshold, session_id, embed_fn, pacer
        )
        print(
            f"  [index {i}/{len(todo)}] {fkey.split('/')[-1][:46]} chunks={len(info['chunks'])}",
            file=sys.stderr,
        )

        tests = per_file[fkey]
        q_clauses = [
            Clause(
                id=f"q{k}",
                title="query",
                text=t["query"],
                level=0,
                parent_id=None,
                source_page=None,
                source_paragraph=k,
                source_span=None,
            )
            for k, t in enumerate(tests)
        ]
        q_doc = make_document(Path("query"), len(q_clauses))
        q_stripped, q_pii = strip_pii_clauses(
            q_clauses, q_doc, threshold=pii_threshold, strip_metadata=False, engine=pii_engine
        )
        q_texts = [c.text for c in q_stripped]
        q_vecs = embed_fn(q_texts, session_id, pacer)

        for test, qtext, qvec in zip(tests, q_texts, q_vecs, strict=True):
            spans = [s["span"] for s in test["snippets"] if nfc(s["file_path"]) == fkey]
            relevant = {
                c["chunk_id"]
                for c in info["chunks"]
                if any(c["char_start"] < en and c["char_end"] > st for st, en in spans)
            }
            arms = retrieve_arms(
                gateway,
                Path(info["db_path"]),
                qtext,
                qvec,
                args.pool_depth,
                args.top_k,
                rrf_k,
                session_id,
                pacer,
                tries=args.tries,
            )
            rerank_tokens_total += arms["rerank_tokens_est"]
            pw = precision_at_k(arms["hybrid_top"], relevant, args.top_k)
            pwr = precision_at_k(arms["rerank_top"], relevant, args.top_k)
            row = {
                "query_id": qid,
                "contract": fkey,
                "stripped_query": qtext,
                "n_relevant": len(relevant),
                "mapped": bool(relevant),
                "pool_size": len(arms["pool"]),
                "hybrid_top5": arms["hybrid_top"],
                "rerank_top5": arms["rerank_top"],
                "sparse_top5": arms["sparse_top"],
                "p5_without": pw,
                "p5_with": pwr,
                "delta_p5": pwr - pw,
                "ndcg5_without": ndcg_at_k(arms["hybrid_top"], relevant, args.top_k),
                "ndcg5_with": ndcg_at_k(arms["rerank_top"], relevant, args.top_k),
                "mrr_without": mrr_at_k(arms["hybrid_top"], relevant, args.top_k),
                "mrr_with": mrr_at_k(arms["rerank_top"], relevant, args.top_k),
                "recall5_without": recall_at_k(arms["hybrid_top"], relevant, args.top_k),
                "recall5_with": recall_at_k(arms["rerank_top"], relevant, args.top_k),
                "p5_sparse": precision_at_k(arms["sparse_top"], relevant, args.top_k),
            }
            with PER_QUERY_JSONL.open("a") as fh:  # incremental checkpoint
                fh.write(json.dumps(row) + "\n")
            qid += 1
            if qid % 10 == 0:
                print(f"  [eval {qid}]", file=sys.stderr)

        # Persist per-contract state so a killed run can still be aggregated.
        masked_queries = sum(
            1 for c, sc in zip(q_clauses, q_stripped, strict=True) if c.text != sc.text
        )
        run_state["per_contract"][fkey] = {
            "chunks": len(info["chunks"]),
            "pii_chunk_entities": info["pii_entities"],
            "masked_chunks": info["masked_chunks"],
            "masked_chunk_values": info["masked_values"],
        }
        run_state["pii_entities_queries"] += len(q_pii.entities)
        run_state["masked_queries"] += masked_queries
        run_state["masked_query_values"] += len(q_pii.mapping)
        _save_run_meta(run_state)

    wall_clock = time.perf_counter() - t_start
    recorded = gateway.get_cost(session_id)
    embed_tokens = sum(s.get("prompt_tokens", 0) for s in recorded.get("slots", {}).values())
    prior_cost = run_state.get("cost", {})
    cost = {
        "wall_clock_s": prior_cost.get("wall_clock_s", 0.0) + wall_clock,
        "embedding_tokens_recorded": prior_cost.get("embedding_tokens_recorded", 0) + embed_tokens,
        "rerank_tokens_estimated": prior_cost.get("rerank_tokens_estimated", 0)
        + rerank_tokens_total,
        "recorded_cost_cents": prior_cost.get("recorded_cost_cents", 0)
        + recorded.get("cost_cents", 0),
    }
    cost["embedding_cost_usd"] = cost["embedding_tokens_recorded"] / 1e6 * PRICE_EMBED_PER_MTOK
    cost["rerank_cost_usd_estimated"] = (
        cost["rerank_tokens_estimated"] / 1e6 * PRICE_RERANK_PER_MTOK
    )
    cost["price_assumptions_usd_per_mtok"] = {
        "embedding": PRICE_EMBED_PER_MTOK,
        "rerank": PRICE_RERANK_PER_MTOK,
    }
    run_state["cost"] = cost
    _save_run_meta(run_state)

    rows = _read_jsonl()
    results = aggregate(rows, meta, _index_info_from_state(run_state), cost)
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(json.dumps(results, indent=2))
    write_report(args.report, results)

    pc = results["paired"]
    print(
        f"\n[done] wall={wall_clock:.0f}s rows={len(rows)} mapping={results['mapping']['mapped']} "
        f"mean_dP@5={pc['mean_delta_p5']:+.3f} CI95=[{pc['bootstrap_ci95'][0]:+.3f},"
        f"{pc['bootstrap_ci95'][1]:+.3f}]",
        file=sys.stderr,
    )
    print(f"[done] results={args.results} report={args.report}", file=sys.stderr)


def _set_cloud_env() -> None:
    """Cloud + raised cost caps via env overrides (config files are never edited).

    Env→config convention (loader.py): "__" -> ".", single "_" -> "." only when no "__".
      OPENREVIEW_PRIVACY_TIER                           -> privacy.tier
      OPENREVIEW_GATEWAY__COST_LIMITS__PER_REVIEW_CENTS -> gateway.cost_limits.per_review_cents
    """
    os.environ["OPENREVIEW_PRIVACY_TIER"] = "performance"
    os.environ["OPENREVIEW_GATEWAY__COST_LIMITS__PER_REVIEW_CENTS"] = "20000"
    os.environ["OPENREVIEW_GATEWAY__COST_LIMITS__DAILY_CENTS"] = "20000"


def build_meta(args, config, embed_model, rerank_model, pii_threshold, rrf_k) -> dict:
    return {
        "run_id": time.strftime("rerank-pilot-%Y%m%dT%H%M%SZ", time.gmtime()),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "embedding_model": embed_model,
        "rerank_model": rerank_model,
        "privacy_tier": config["privacy"]["tier"],
        "pii_threshold": pii_threshold,
        "rrf_k": rrf_k,
        "pool_depth": args.pool_depth,
        "top_k": args.top_k,
        "bootstrap_resamples": args.bootstrap,
        "seed": args.seed,
        "chunker": {"chunk_size": CHUNK_SIZE, "chunk_overlap": CHUNK_OVERLAP},
        "rate_limit": {"tpm": args.tpm, "rpm": args.rpm},
    }


def _read_jsonl() -> list[dict]:
    if not PER_QUERY_JSONL.exists():
        return []
    return [json.loads(line) for line in PER_QUERY_JSONL.read_text().splitlines() if line.strip()]


def _load_run_meta() -> dict:
    return json.loads(RUN_META_PATH.read_text()) if RUN_META_PATH.exists() else {}


def _save_run_meta(state: dict) -> None:
    RUN_META_PATH.write_text(json.dumps(state, indent=2))


def _index_info_from_state(state: dict) -> dict:
    # Contract/chunk counts come from the index DBs (accurate across resumed runs). PII
    # totals come from run_meta, which is appended after every contract so a killed run
    # still reports each contract it finished. Everything is summed unconditionally — an
    # empty run_meta yields zeros, never the old `None`/"-1" that hid whether a strip ran.
    info = _index_info_from_dbs()
    per = state.get("per_contract", {})
    info["pii_entities_chunks"] = sum(int(v.get("pii_chunk_entities", 0)) for v in per.values())
    info["masked_chunks"] = sum(int(v.get("masked_chunks", 0)) for v in per.values())
    info["masked_chunk_values"] = sum(int(v.get("masked_chunk_values", 0)) for v in per.values())
    info["pii_entities_queries"] = int(state.get("pii_entities_queries", 0))
    info["masked_queries"] = int(state.get("masked_queries", 0))
    info["masked_query_values"] = int(state.get("masked_query_values", 0))
    info["pii_contracts_counted"] = len(per)
    return info


def _index_info_from_dbs() -> dict:
    """Count indexed docs/chunks by scanning the index databases."""
    from openreview_cli.retrieval.storage import RetrievalStorage

    contracts = chunks = 0
    for db in sorted(INDEX_DIR.glob("*.sqlite")):
        with RetrievalStorage(db) as storage:
            meta = storage.get_index_meta()
        if meta and meta.get("index_status") == "indexed":
            contracts += 1
            chunks += int(meta.get("chunk_count", 0))
    return {"contracts": contracts, "chunks": chunks}


def _aggregate_only(args) -> None:
    config = load_config(get_config_dir() / "config.yml")
    state = _load_run_meta()
    rows = _read_jsonl()
    if not rows:
        raise SystemExit("nothing to aggregate: per_query.jsonl is empty")
    meta = state.get("meta") or build_meta(
        args,
        config,
        config["gateway"]["models"]["embedding"]["primary"],
        config["gateway"]["models"]["reranking"]["primary"],
        float(config["privacy"].get("pii_threshold", 0.7)),
        int(config.get("retrieval", {}).get("rrf_k", 60)),
    )
    index_info = _index_info_from_state(state)
    results = aggregate(rows, meta, index_info, state.get("cost", {}))
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(json.dumps(results, indent=2))
    write_report(args.report, results)
    print(
        f"[aggregate-only] rows={len(rows)} index={index_info} "
        f"results={args.results} report={args.report}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
