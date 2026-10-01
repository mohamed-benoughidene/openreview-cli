#!/usr/bin/env python
"""Offline rerank-arm comparison over LegalBenchRAG-CUAD.

RESTORED FROM HISTORY, ADAPTED (read this before trusting the numbers)
----------------------------------------------------------------------
This is the harness deleted in commit b781a1a, taken from
``git show b781a1a^:scripts/benchmark_rerank_legalbenchrag.py``, kept for its
original purpose -- score several rerank arms over an *identical* candidate pool
on the CUAD corpus, using the real product chunker and one SQLite FTS5 index per
contract -- and rewritten so it runs offline in this tree.

WHY IT COULD NOT RUN AS WRITTEN
-------------------------------
The deleted harness cannot execute against this tree at all:

* It imports ``openreview_cli.retrieval.dense`` and ``openreview_cli.retrieval.rrf``,
  both deleted in b781a1a with the dense/hybrid path.
* It calls ``gateway.rerank("reranking", ...)``; the ``reranking`` socket was removed
  in spec 035, so there is no model to resolve and no provider branch.
* Its two "hybrid" arms and its cloud embeddings require live Voyage credentials (the
  account recorded in the pilot report had no payment method and was throttled to
  ~3 RPM / 10K TPM), so neither arm was reproducible even before the deletion.

WHAT THIS VERSION MEASURES
--------------------------
The original harness compared ``sparse`` (product BM25), ``hybrid`` (RRF of BM25 +
dense) and ``hybrid + voyage/rerank-2.5``. Only the sparse pool survives: dense and
RRF are gone and the cloud reranker is gone. This version therefore builds the
candidate pool from product BM25 alone -- which is exactly the pool the tracked
rerank claim describes ("all arms re-ranking the *same* BM25+porter candidates") --
and re-orders that pool with local, offline arms:

    bm25_baseline          the pool as BM25 returned it, truncated to top-k
    lexical_rerank         query-term coverage (the claim's "cheap lexical rerank")
    cross_encoder_rerank   cross-encoder/ms-marco-MiniLM-L-6-v2 (the claim's local
                           cross-encoder), run through ``transformers``, which is an
                           existing project dependency -- ``sentence-transformers``
                           is forbidden by the repository rules and is NOT used

Every arm sees the same pool for a query, so the comparison is paired.

WHAT IT DOES NOT MEASURE
------------------------
The cloud arm (``voyage/rerank-2.5``) is not reproducible here: the socket is gone
and the account is network/credentialed. The original harness's PII strip and cost
accounting are dropped: this harness makes no network call, so there is no egress to
protect and no spend to record. Removing the strip also removes a confound, since a
PII strip rewrites the chunk text the pool is built from.

OFFLINE CONTRACT
----------------
``HF_HUB_OFFLINE``/``TRANSFORMERS_OFFLINE`` are forced to 1 before the cross-encoder
is loaded, so a missing or stale local model cache degrades to "arm unavailable" with
the exact error recorded in the receipt instead of silently downloading weights. The
corpus and the benchmark are both gitignored; when either is missing the harness
writes a skip receipt and exits 0, like ``scripts/measure_retrieval_accuracy.py``.

CORPUS LOADING, CHUNKING AND GROUND TRUTH
-----------------------------------------
These are imported from ``scripts/measure_retrieval_accuracy.py`` rather than
re-implemented, so this comparison and the committed tokenizer pair build their
indexes and label their chunks identically. That script cannot be imported as a
package module, so ``scripts/`` is added to ``sys.path`` here.

Usage:
    uv run python scripts/benchmark_rerank_legalbenchrag.py --out .benchmark-reports/rerank-offline.json
    uv run python scripts/benchmark_rerank_legalbenchrag.py --contracts 40 --limit 424 --out /tmp/smoke.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import measure_retrieval_accuracy as mra  # noqa: E402

from openreview_cli.retrieval.bm25 import normalize_bm25_scores, search_bm25  # noqa: E402
from openreview_cli.retrieval.storage import RetrievalStorage  # noqa: E402

DEFAULT_OUT = Path(".benchmark-reports/rerank-offline.json")
DEFAULT_CROSS_ENCODER = "cross-encoder/ms-marco-MiniLM-L-6-v2"
#: 256-token truncation, as recorded for the deleted harness's cross-encoder arm.
CE_MAX_LENGTH = 256
PRODUCT_DEFAULT_TOP_K = 5

#: Files whose bytes produce the numbers in the receipt (pinned by sha256).
PROVENANCE_PATHS = (
    "scripts/benchmark_rerank_legalbenchrag.py",
    "scripts/measure_retrieval_accuracy.py",
    "src/openreview_cli/chunking/splitter.py",
    "src/openreview_cli/retrieval/bm25.py",
    "src/openreview_cli/retrieval/storage.py",
)

_TERM_RE = re.compile(r"[a-z0-9]+")


# ── metrics ─────────────────────────────────────────────────────────────────


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    return sum(1 for c in retrieved[:k] if c in relevant) / k if k else 0.0


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    return sum(1 for c in retrieved[:k] if c in relevant) / len(relevant) if relevant else 0.0


def first_relevant_rank(retrieved: list[str], relevant: set[str], k: int) -> int | None:
    for rank, chunk in enumerate(retrieved[:k], start=1):
        if chunk in relevant:
            return rank
    return None


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    dcg = sum(1.0 / math.log2(i + 1) for i, c in enumerate(retrieved[:k], start=1) if c in relevant)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(k, len(relevant)) + 1))
    return dcg / ideal if ideal > 0 else 0.0


def score_ranking(retrieved: list[str], relevant: set[str], k: int) -> dict[str, float]:
    """Score one ranking: hit@1/hit@5/MRR@5 (the claim's metrics) plus P@5/nDCG@5/Recall@5."""
    rank = first_relevant_rank(retrieved, relevant, k)
    in_top_k = rank is not None
    return {
        "hit_at_1": 1.0 if rank == 1 else 0.0,
        "hit_at_5": 1.0 if in_top_k else 0.0,
        "mrr_at_5": (1.0 / rank) if in_top_k else 0.0,
        "precision_at_5": precision_at_k(retrieved, relevant, k),
        "ndcg_at_5": ndcg_at_k(retrieved, relevant, k),
        "recall_at_5": recall_at_k(retrieved, relevant, k),
    }


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def bootstrap_ci(deltas: list[float], resamples: int, seed: int) -> tuple[float, float]:
    import numpy as np

    if not deltas:
        return (0.0, 0.0)
    arr = np.asarray(deltas, dtype=float)
    rng = np.random.default_rng(seed)
    means = arr[rng.integers(0, arr.size, size=(resamples, arr.size))].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return (float(lo), float(hi))


# ── arms ────────────────────────────────────────────────────────────────────


def terms(value: str) -> set[str]:
    return set(_TERM_RE.findall(value.lower()))


def lexical_scores(query: str, passages: list[str]) -> list[float]:
    """Query-term coverage: fraction of the query's terms present in the passage."""
    query_terms = terms(query)
    if not query_terms:
        return [0.0] * len(passages)
    return [len(query_terms & terms(p)) / len(query_terms) for p in passages]


class CrossEncoder:
    """Local cross-encoder, loaded through ``transformers`` (never sentence-transformers)."""

    def __init__(self, model_id: str, device: str, batch_size: int) -> None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = __import__("torch")
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_id)
        self.model.to(device)
        self.model.eval()
        self.batch_size = batch_size

    def score(self, query: str, passages: list[str]) -> list[float]:
        scores: list[float] = []
        with self.torch.no_grad():
            for start in range(0, len(passages), self.batch_size):
                batch = passages[start : start + self.batch_size]
                encoded = self.tokenizer(
                    [query] * len(batch),
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=CE_MAX_LENGTH,
                    return_tensors="pt",
                )
                logits = self.model(**encoded).logits.view(-1)
                scores.extend(float(v) for v in logits.tolist())
        return scores


def order_by(scores: list[float], pool: list[str]) -> list[str]:
    """Stable re-ordering of ``pool`` by descending score (ties keep BM25 order)."""
    ranked = sorted(range(len(pool)), key=lambda i: (-scores[i], i))
    return [pool[i] for i in ranked]


# ── input selection ─────────────────────────────────────────────────────────


def select_queries(queries: list[mra.QueryRef], contracts: int, limit: int) -> list[mra.QueryRef]:
    """Deterministically select contracts (sorted first-N) and cap the query count."""
    if contracts:
        wanted = sorted({q.file_path for q in queries})[:contracts]
        allowed = set(wanted)
        queries = [q for q in queries if q.file_path in allowed]
    if limit:
        queries = queries[:limit]
    return queries


# ── measurement ─────────────────────────────────────────────────────────────


def build_receipt(
    args: argparse.Namespace,
    benchmark_path: Path,
    corpus_root: Path,
    queries: list[mra.QueryRef],
    total_tests: int,
    skipped_no_span: int,
) -> dict[str, Any]:
    """Index each selected contract, score every arm on the same pool, return a receipt."""
    per_query: dict[str, list[dict[str, float]]] = defaultdict(list)
    per_query_pool_size: list[int] = []
    per_query_delta_p5: dict[str, list[float]] = defaultdict(list)
    helped: dict[str, int] = defaultdict(int)
    hurt: dict[str, int] = defaultdict(int)
    mapped = 0
    no_relevant = 0
    skipped_missing = 0
    contracts_used = 0
    chunks_indexed = 0

    cross_encoder: CrossEncoder | None = None
    cross_encoder_error: str | None = None
    if not args.no_cross_encoder:
        try:
            cross_encoder = CrossEncoder(args.cross_encoder, args.device, args.ce_batch)
        except Exception as exc:
            cross_encoder_error = f"{type(exc).__name__}: {exc}"

    by_file: dict[str, list[mra.QueryRef]] = defaultdict(list)
    for ref in queries:
        by_file[ref.file_path].append(ref)

    with tempfile.TemporaryDirectory(prefix="rerank-offline-") as tmp:
        work_dir = Path(tmp)
        for file_path in sorted(by_file):
            document_text = mra.load_document_text(corpus_root, file_path)
            if document_text is None:
                skipped_missing += len(by_file[file_path])
                continue
            document_id = hashlib.sha256(file_path.encode("utf-8")).hexdigest()
            db_path = work_dir / f"{document_id[:16]}.db"
            chunks = mra.index_contract(document_text, db_path, document_id)
            contracts_used += 1
            chunks_indexed += len(chunks)
            spans = {
                chunk["chunk_id"]: (chunk["char_start"], chunk["char_end"]) for chunk in chunks
            }

            with RetrievalStorage(db_path) as storage:
                for ref in by_file[file_path]:
                    hits = search_bm25(storage, ref.query, args.pool_depth)
                    ranks = normalize_bm25_scores(hits)
                    pool = [chunk for chunk, _ in sorted(ranks.items(), key=lambda kv: kv[1])]
                    passages = []
                    for chunk in pool:
                        row = storage.load_chunk(chunk)
                        passages.append(row["text"] if row else "")

                    relevant = {
                        chunk
                        for chunk, (start, end) in spans.items()
                        if any(mra._overlaps(start, end, gs, ge) for gs, ge in ref.spans)
                    }
                    if relevant:
                        mapped += 1
                    else:
                        no_relevant += 1
                    if not pool:
                        continue
                    per_query_pool_size.append(len(pool))

                    arms = {
                        "bm25_baseline": pool[: args.top_k],
                        "lexical_rerank": order_by(lexical_scores(ref.query, passages), pool)[
                            : args.top_k
                        ],
                    }
                    if cross_encoder is not None:
                        arms["cross_encoder_rerank"] = order_by(
                            cross_encoder.score(ref.query, passages), pool
                        )[: args.top_k]

                    for arm, ranking in arms.items():
                        per_query[arm].append(score_ranking(ranking, relevant, args.top_k))
                    baseline_p5 = per_query["bm25_baseline"][-1]["precision_at_5"]
                    for arm in ("lexical_rerank", "cross_encoder_rerank"):
                        if arm not in arms:
                            continue
                        delta = per_query[arm][-1]["precision_at_5"] - baseline_p5
                        per_query_delta_p5[arm].append(delta)
                        if delta > 1e-9:
                            helped[arm] += 1
                        elif delta < -1e-9:
                            hurt[arm] += 1

    arms_payload: dict[str, Any] = {}
    for arm, rows in per_query.items():
        deltas = per_query_delta_p5[arm]
        ci_lo, ci_hi = bootstrap_ci(deltas, args.bootstrap, args.seed)
        arms_payload[arm] = {
            "metrics": {
                "hit_at_1": round(mean([r["hit_at_1"] for r in rows]), 6),
                "hit_at_5": round(mean([r["hit_at_5"] for r in rows]), 6),
                "mrr_at_5": round(mean([r["mrr_at_5"] for r in rows]), 6),
                "precision_at_5": round(mean([r["precision_at_5"] for r in rows]), 6),
                "ndcg_at_5": round(mean([r["ndcg_at_5"] for r in rows]), 6),
                "recall_at_5": round(mean([r["recall_at_5"] for r in rows]), 6),
            },
            "queries_scored": len(rows),
            "paired_vs_bm25": (
                None
                if not deltas
                else {
                    "mean_delta_precision_at_5": round(mean(deltas), 6),
                    "bootstrap_ci95": [round(ci_lo, 6), round(ci_hi, 6)],
                    "helped": helped[arm],
                    "hurt": hurt[arm],
                    "tied": len(deltas) - helped[arm] - hurt[arm],
                    "n": len(deltas),
                }
            ),
        }
    if cross_encoder is not None:
        arms_payload["cross_encoder_rerank"]["model"] = args.cross_encoder
    else:
        arms_payload["cross_encoder_rerank"] = {
            "available": False,
            "reason": (
                "skipped by --no-cross-encoder" if args.no_cross_encoder else cross_encoder_error
            ),
        }

    baseline = arms_payload["bm25_baseline"]["metrics"]
    metrics: dict[str, Any] = {
        "hit_at_1": baseline["hit_at_1"],
        "hit_at_5": baseline["hit_at_5"],
        "mrr_at_5": baseline["mrr_at_5"],
    }
    for arm in ("lexical_rerank", "cross_encoder_rerank"):
        entry = arms_payload[arm]
        if "metrics" in entry:
            metrics[f"{arm}_hit_at_1"] = entry["metrics"]["hit_at_1"]
            metrics[f"{arm}_hit_at_5"] = entry["metrics"]["hit_at_5"]
            metrics[f"{arm}_mrr_at_5"] = entry["metrics"]["mrr_at_5"]

    scored = len(per_query["bm25_baseline"])
    return {
        "sample": {
            "queries_total": total_tests,
            "queries_scored": scored,
            "queries_with_no_relevant_chunk": no_relevant,
            "queries_skipped_missing_contract": skipped_missing,
            "queries_skipped_no_span": skipped_no_span,
            "queries_ground_truth_mapped": mapped,
            "contracts_used": contracts_used,
            "chunks_indexed_total": chunks_indexed,
            "mean_pool_size": round(mean([float(n) for n in per_query_pool_size]), 4),
        },
        "arms": arms_payload,
        "metrics": metrics,
    }


# ── receipts ────────────────────────────────────────────────────────────────


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.strip()


def provenance() -> list[dict[str, str]]:
    return [{"path": rel, "sha256": sha256_of(REPO / rel)} for rel in PROVENANCE_PATHS]


def base_receipt(
    args: argparse.Namespace, benchmark_path: Path, corpus_root: Path
) -> dict[str, Any]:
    return {
        "benchmark": "cuad-rerank-offline",
        "command": "uv run python "
        + " ".join(["scripts/benchmark_rerank_legalbenchrag.py", *sys.argv[1:]]),
        "cwd": str(Path.cwd()),
        "date": time.strftime("%Y-%m-%d", time.gmtime()),
        "git_commit": git_commit(),
        "provenance": provenance(),
        "models": "cross-encoder/ms-marco-MiniLM-L-6-v2 (local transformers, CPU); lexical arm = query-term coverage (no model)",
        "benchmark_input": str(benchmark_path),
        "corpus_root": str(corpus_root),
        "candidate_pool": (
            f"BM25 over SQLite FTS5 (tokenize='porter unicode61') top-{args.pool_depth} per "
            "contract, ordered by bm25(chunk_fts); every arm re-orders this identical pool"
        ),
        "chunking_rule": mra.CHUNKING_RULE,
        "ground_truth_rule": mra.GROUND_TRUTH_RULE,
        "pool_depth": args.pool_depth,
        "product_default_top_k": PRODUCT_DEFAULT_TOP_K,
        "metric": f"top-{args.top_k} rankings, macro-averaged over queries",
        "sample": {},
        "metrics": {},
        "notes": "",
    }


def skipped_receipt(
    args: argparse.Namespace, benchmark_path: Path, corpus_root: Path, reason: str
) -> dict[str, Any]:
    receipt = base_receipt(args, benchmark_path, corpus_root)
    receipt["skipped"] = True
    receipt["reason"] = reason
    receipt["notes"] = "Input missing; nothing was measured and no number is published."
    return receipt


NOTES = (
    "Offline rerank-arm comparison restored from the harness deleted in b781a1a "
    "(git show b781a1a^:scripts/benchmark_rerank_legalbenchrag.py) and adapted to this tree: the "
    "deleted dense/RRF fusion and the cloud voyage/rerank-2.5 socket no longer exist, so the "
    "candidate pool is product BM25 alone (the pool the tracked rerank claim describes) and the "
    "arms are local. Arms: bm25_baseline (pool truncated to top-k), lexical_rerank (query-term "
    "coverage), cross_encoder_rerank (cross-encoder/ms-marco-MiniLM-L-6-v2 through transformers, "
    "256-token truncation, CPU). sentence-transformers is forbidden by the repository rules and is "
    "not used. All arms re-order the identical per-query pool, so every rerank arm is paired with "
    "the baseline. Corpus loading, chunking and the ground-truth rule are imported from "
    "scripts/measure_retrieval_accuracy.py so this comparison and the committed tokenizer pair "
    "build their indexes and label their chunks identically; ground truth is character-span "
    "overlap, not answer correctness. HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE are forced on: a missing "
    "local model cache degrades the cross-encoder arm to an explicit unavailable entry rather than "
    "downloading weights. The corpus and benchmark are gitignored (data/legalbenchrag/) and not "
    "redistributed. NOT REPRODUCED HERE: the cloud voyage/rerank-2.5 pilot (the reranking socket "
    "was removed and the account is credentialed) and the deleted hybrid (BM25 + dense RRF) arms "
    "(the dense path was deleted). Whether a reranker helps on a *different* corpus, pool depth or "
    "model is outside this receipt's scope. Wall time is machine-dependent and only the "
    "cross-encoder arm needs the gitignored corpus plus a local model cache."
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", default=str(mra.DEFAULT_BENCHMARK))
    parser.add_argument("--corpus-root", default=str(mra.DEFAULT_CORPUS_ROOT))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--contracts", type=int, default=0, help="first N contracts, sorted (0 = all)"
    )
    parser.add_argument("--limit", type=int, default=0, help="cap queries scored (0 = all)")
    parser.add_argument("--pool-depth", type=int, default=mra.DEFAULT_DEPTH)
    parser.add_argument("--top-k", type=int, default=PRODUCT_DEFAULT_TOP_K)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--cross-encoder", default=DEFAULT_CROSS_ENCODER)
    parser.add_argument("--ce-batch", type=int, default=64)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--no-cross-encoder", action="store_true")
    args = parser.parse_args()

    # Forced before any transformers import so a cache miss fails loudly instead of downloading.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    benchmark_path = Path(args.benchmark)
    corpus_root = Path(args.corpus_root)
    started = time.monotonic()

    reason = mra._missing_input_reason(benchmark_path, corpus_root)
    if reason is not None:
        receipt = skipped_receipt(args, benchmark_path, corpus_root, reason)
    else:
        queries, skipped_no_span = mra.load_queries(benchmark_path)
        payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
        total_tests = len(payload.get("tests", [])) if isinstance(payload, dict) else 0
        selected = select_queries(queries, args.contracts, args.limit)
        if not selected:
            receipt = skipped_receipt(args, benchmark_path, corpus_root, "no query selected")
        else:
            receipt = base_receipt(args, benchmark_path, corpus_root)
            receipt.update(
                build_receipt(
                    args, benchmark_path, corpus_root, selected, total_tests, skipped_no_span
                )
            )
            receipt["notes"] = NOTES

    receipt["elapsed_seconds"] = round(time.monotonic() - started, 2)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if receipt.get("skipped"):
        print(f"SKIP: {receipt['reason']}")
    else:
        sample = receipt["sample"]
        print(
            f"--- CUAD rerank arms ({sample['queries_scored']} queries / {sample['contracts_used']} contracts) ---"
        )
        for arm, entry in receipt["arms"].items():
            if "metrics" in entry:
                m = entry["metrics"]
                print(
                    f"{arm:>22}: hit@1 {m['hit_at_1']:.4f}  hit@5 {m['hit_at_5']:.4f}  MRR@5 {m['mrr_at_5']:.4f}"
                )
            else:
                print(f"{arm:>22}: unavailable - {entry.get('reason')}")
    print(f"Output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
