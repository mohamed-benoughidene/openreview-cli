# Slot measurement

Measurement of the six AI-gateway slots on 2026-09-29. Each slot is either **measured** (a number from a real run) or **not measurable** today, with the reason. Everything below is a single-sample smoke measurement on synthetic fixtures, not a benchmark.

## Slot coverage

| slot | status | how | result |
|---|---|---|---|
| `extraction` | measured | run_review (extract + QA share this slot) | position accuracy 0.9/0.7/0.7/0.7 (local×4, cloud×1) |
| `grounding` | measured (no ground truth) | run_review(grounding_mode='strict') | 7 claims assessed, all grounded after strict filtering |
| `embedding` | measured | ingest + retrieve on tests/fixtures/retrieval (local Ollama) | mean P@k 0.32, dense used |
| `reranking` | NOT MEASURABLE | cloud blocked by both tiers in the retrieval path; no local Ollama rerank | balanced: 'requires a local provider for reranking'; performance: 'requires PII stripping before cloud calls' |
| `reasoning` | NOT MEASURABLE | no caller in src/ (only `openreview gateway test reasoning`) | no code path to score |
| `graph` | NOT MEASURABLE | src/openreview_cli/graph/ makes no model calls (pure regex) | no gateway call exists |

## extraction — position accuracy (5 `indemnitycheck` docs)

| model | run | position accuracy | extraction failures | review s |
|---|---|---|---|---|
| `ollama/granite4:3b` | local-models (CI matrix) | 0.9 | 0 | 279.6 |
| `ollama/gemma3:4b` | local-models (CI matrix) | 0.7 | 0 | 554.1 |
| `ollama/phi4-mini:3.8b` | local-models (CI matrix) | 0.7 | 0 | 486.7 |
| openrouter/anthropic/claude-sonnet-4.6 | cloud slots (configured) | 0.7 | 0 | 116.0 |
| `ollama/qwen3:4b` | local-models (CI matrix) | 0.0 | 11 | 4015.9 |

Category recall is **not** a model metric: `match_category()` resolves the category by lexical matching before any model call (`review/extraction.py:31-56`) and the fixtures embed the category name. The model only picks the position.

## embedding — Precision@k (retrieval fixture, 5 labeled queries)

- `ollama/nomic-embed-text` (local Ollama): **mean P@k = 0.32** · dense used: True · ingest 1.43s · notices: []
- Cloud embeddings are unreachable through `retrieve`: tier `balanced` requires a *local* provider (`dense_used=False`, BM25-only P@k 0.24 with the configured `voyage/voyage-3.5`), and tier `performance` requires a PII strip the retrieval path never performs.

## grounding — verdicts (`run_review(grounding_mode='strict')`, cloud text slots)

- 7 claims assessed, 7 grounded, 0 ungrounded, 0 uncertain (after strict filtering).
- **No ground truth exists for grounding accuracy** (`tests/fixtures/grounding/seeded_claims.json` carries labels but nothing loads it), and `strict` mode removes ungrounded claims before the report, so the surviving counts cannot show them. A lenient re-run was blocked (OpenRouter key limit).

## Not measurable (with proof)

- **`reranking`** — cloud rerank is gated in the retrieval path under *both* tiers: `balanced` → "requires a local provider for reranking"; `performance` → "requires PII stripping before cloud calls". Local Ollama rerank does not exist (#175/#179).
- **`reasoning`** — no caller in `src/`; only `openreview gateway test reasoning` sends it.
- **`graph`** — `src/openreview_cli/graph/` contains no gateway call at all (pure regex computation); only `openreview gateway test graph` sends the slot.

## Method and limits
- One run per document/query; local and cloud models are non-deterministic → single samples.
- n = 5 docs × 2 expected categories (extraction) and 5 queries × P@5 (embedding). **Smoke measurement.**
- Extraction ran with grounding off for the model comparison (grounding is measured separately).
- The cloud numbers were produced before the OpenRouter key hit its spend limit; re-running them needs the key limit raised.
- Not run: reranking (see above), and the SLM-vs-cloud comparison is unchanged from the earlier run.
- Raw data: `docs/benchmarks/results/slot-measurement.json`.
