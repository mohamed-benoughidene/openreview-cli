"""Measure the retrieval slots — `embedding` (and optionally `reranking`) — on the bundled fixture.

Runs the real retrieval path: ingest the fixture contract, then query it with the
labeled queries in ``tests/fixtures/retrieval/ground_truth.json`` and score
Precision@K. The engine records a notice when dense retrieval degrades to BM25, so
the result says whether the `embedding` slot was actually used.

Reranking is cloud-only in practice (no local Ollama rerank), and both privacy
tiers gate a cloud rerank in this path, so ``--rerank`` is expected to be a no-op
unless a local rerank provider exists.

Usage:
    uv run python scripts/measure_retrieval_slots.py --out results/retrieval.json
    uv run python scripts/measure_retrieval_slots.py --embedding-model ollama/nomic-embed-text --out results/retrieval.json
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

FIXTURE = Path("tests/fixtures/retrieval/sample_contract.ndax")
GROUND_TRUTH = Path("tests/fixtures/retrieval/ground_truth.json")


def _precision_at_k(result_ids: list[str], expected_ids: list[str], k: int) -> float:
    """Precision@K = |relevant ∩ top_K| / K (mirrors tests/integration/test_retrieval_benchmark.py)."""
    if not result_ids or not expected_ids:
        return 0.0
    return sum(1 for cid in result_ids[:k] if cid in expected_ids) / k


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH)
    parser.add_argument("--method", default=None, help="Force one method; default per query.")
    parser.add_argument("--rerank", action="store_true", help="Enable the reranking slot.")
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Override the embedding slot, e.g. ollama/nomic-embed-text.",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.embedding_model:
        os.environ["OPENREVIEW_GATEWAY__MODELS__EMBEDDING__PRIMARY"] = args.embedding_model

    from openreview_cli.config.paths import get_data_dir
    from openreview_cli.gateway.router import Gateway
    from openreview_cli.retrieval.engine import RetrievalEngine
    from openreview_cli.retrieval.ingest import ingest_from_file
    from openreview_cli.retrieval.models import RetrievalQuery
    from openreview_cli.storage.database import init_database

    init_database(get_data_dir() / "openreview.db")

    ground_truth: dict[str, Any] = json.loads(args.ground_truth.read_text())
    queries: list[dict[str, Any]] = ground_truth["queries"]

    gateway = Gateway()
    embedding_slot = gateway.slot_primary_model("embedding")

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "retrieval.db"
        started = time.perf_counter()
        ingest_from_file(args.fixture, db_path, gateway=gateway, method="hybrid")
        ingest_seconds = round(time.perf_counter() - started, 2)

        engine = RetrievalEngine(db_path, gateway=gateway)
        per_query: list[dict[str, Any]] = []
        for entry in queries:
            method = args.method or entry.get("method", "hybrid")
            top_k = int(entry.get("top_k", 5))
            started = time.perf_counter()
            error: str | None = None
            ids: list[str] = []
            notices: list[str] = []
            try:
                results = engine.retrieve(
                    RetrievalQuery(
                        query_text=entry["query"],
                        method=method,
                        top_k=top_k,
                        rerank=args.rerank,
                    )
                )
                ids = [r.chunk_id for r in results]
                notices = list(getattr(engine, "notices", []) or [])
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            per_query.append(
                {
                    "query": entry["query"],
                    "method": method,
                    "top_k": top_k,
                    "expected": entry["expected_chunk_ids"],
                    "returned": ids,
                    "precision_at_k": round(
                        _precision_at_k(ids, entry["expected_chunk_ids"], top_k), 4
                    ),
                    "notices": notices,
                    "seconds": round(time.perf_counter() - started, 2),
                    "error": error,
                }
            )
            print(f"[{entry['query']}] P@{top_k}={per_query[-1]['precision_at_k']} {notices}")

    mean_p = (
        round(sum(q["precision_at_k"] for q in per_query) / len(per_query), 4) if per_query else 0.0
    )
    degraded = any(q["notices"] for q in per_query)
    result = {
        "embedding_slot": embedding_slot,
        "method_override": args.method,
        "rerank_requested": args.rerank,
        "pii_stripped": None,  # the retrieval path does not strip PII
        "ingest_seconds": ingest_seconds,
        "queries": len(per_query),
        "mean_precision_at_k": mean_p,
        "dense_used": not degraded,
        "notices_seen": sorted({n for q in per_query for n in q["notices"]}),
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_sha": os.environ.get("GITHUB_SHA", "unknown")[:12],
        "per_query": per_query,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\nembedding slot: {embedding_slot} · mean P@k = {mean_p} · dense used: {not degraded}")
    print(f"JSON written to {args.out}")


if __name__ == "__main__":
    main()
