# Slot measurement — clause-position accuracy

One measurement of the bundled `indemnitycheck` fixtures: 5 synthetic contracts with known risky clauses and their expected positions. Two runs, same fixtures and same scoring.

**Scope: this measures the `extraction` slot only** (the QA call shares that slot, `runner.py:59-62`). The review path is Parse → (Strip) → Review (`runner.py:317-320`), so `reasoning`, `graph`, `grounding`, `embedding` and `reranking` are never called and are **not** measured here.

- **Run A — local models** (`ollama/*`): GitHub-hosted `ubuntu-latest`, CPU-only, local Ollama; PII stripping skipped; run commit `9e7f9b201485`. The model is set on every text slot, but only the `extraction` slot is called.
- **Run B — cloud slots** (`openrouter/anthropic/claude-sonnet-4.6`): developer machine, privacy tier `balanced`, PII stripping ON (required before cloud egress); `embedding` = `voyage/voyage-3.5`, `reranking` = `voyage/rerank-2.5` (neither is used by the review pipeline).

## Results

| model | run | position accuracy | extraction failures | review seconds | cost |
|---|---|---|---|---|---|
| `ollama/granite4:3b` | local-models (CI matrix) | 0.9 | 0 | 279.6 | free (local compute) |
| `ollama/gemma3:4b` | local-models (CI matrix) | 0.7 | 0 | 554.1 | free (local compute) |
| `ollama/phi4-mini:3.8b` | local-models (CI matrix) | 0.7 | 0 | 486.7 | free (local compute) |
| openrouter/anthropic/claude-sonnet-4.6 | cloud slots (configured) | 0.7 | 0 | 116.0 | 22¢ |
| `ollama/qwen3:4b` | local-models (CI matrix) | 0.0 | 11 | 4015.9 | free (local compute) |

Category recall is 1.0 for every model that produced usable extractions and 0.0 for `qwen3:4b`; it is **not** a model metric (see Finding 1).

## Per document (position ok / expected)

| model | doc_1 | doc_2 | doc_3 | doc_4 | doc_5 |
|---|---|---|---|---|---|
| `ollama/granite4:3b` | 2/2 | 2/2 | 2/2 | 1/2 | 2/2 |
| `ollama/gemma3:4b` | 2/2 | 2/2 | 1/2 | 1/2 | 1/2 |
| `ollama/phi4-mini:3.8b` | 1/2 | 2/2 | 2/2 | 0/2 | 2/2 |
| `openrouter/anthropic/claude-sonnet-4.6` | 1/2 | 2/2 | 2/2 | 0/2 | 2/2 |
| `ollama/qwen3:4b` | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |

## Findings

1. **Category recall is not a model metric in this pipeline.** `match_category()` resolves the playbook category by lexical substring matching *before* any model call (`review/extraction.py:31-56`, documented as "no model inference needed"), and the fixtures embed the category name in the clause text. The model only chooses the *position*, so **position accuracy is the signal**; ignore the 1.0 recalls.
2. **`granite4:3b` scored highest** (0.9, 9/10) among the local models; the cloud `claude-sonnet-4.6` and the two other local models all scored 0.7 (7/10), and `qwen3:4b` produced nothing.
3. **The cloud-vs-local gap is not meaningful at this sample size.** The best-to-typical difference is 2 scored items out of 10 (n = 5 docs × 2 expected categories).
4. **`qwen3:4b` — the repo's extraction default — produced no usable extractions**: all 11 attempts failed with `litellm.Timeout: Connection timed out after 60.0 seconds`, and it burned ~67 min doing it (4016 s vs 280 s for `granite4:3b`). Size/timeout mismatch on CPU, not an answer-quality result.
5. **Cost/speed:** the cloud run was ~2.4× faster per document (116 s vs 280 s total) at 22¢ for 5 contracts (22 calls, 14 039 in / 3 319 out tokens); local models are free but slower, and `qwen3:4b` is unusable on CPU with the default 60 s timeout.
6. **The two runs differ on privacy, not just on model**: the cloud run strips PII (tier `balanced` requires it before egress); the local runs skip stripping. Same fixtures, different pipeline work.

## Method and limits
- Pipeline: product review (parse → review) per document; synthetic fixtures only.
- One run per document; local and cloud models are non-deterministic, so these are single samples.
- n = 5 documents × 2 expected categories = 10 scored items per model. Treat as a **smoke measurement, not a benchmark**.
- The fixtures embed the category name, so this measures *position choice given the category*, not clause discovery.
- Reranking is excluded: no local Ollama rerank support, and the review pipeline does not call the rerank slot.
- **Not measured:** `embedding` (retrieval path only), `grounding` (needs `grounding_mode`), `reasoning` and `graph` (no caller in `src/`). This is an `extraction`-slot measurement.
- Harness bugs found and fixed before these numbers were valid: the missing app DB (`no such table: cost_logs`) and the failure fallback faking category matches (commit `9e7f9b2`).
- Raw data: `docs/benchmarks/results/slot-measurement.json`.
