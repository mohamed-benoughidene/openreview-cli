# Cloud (configured slots) slot measurement

- date: 2026-09-29 · run locally on the developer machine (not CI)
- slots: every text slot = `openrouter/anthropic/claude-sonnet-4.6`; `embedding` = `voyage/voyage-3.5`, `reranking` = `voyage/rerank-2.5` (neither is used by the review pipeline)
- privacy: tier `balanced`, **PII stripping ON** (the tier requires a successful strip before cloud egress)
- mode `indemnitycheck`, 5 documents, one run each

## Result

- position accuracy: **0.7** (7/10)
- extraction failures: 0
- review time: 116.0 s for 5 documents
- cost: 22¢ (22 calls, 14039 in / 3319 out tokens, claude-sonnet-4.6 via OpenRouter)

| doc | position ok | extraction failures | seconds |
|---|---|---|---|
| doc_1.pdf | 1/2 | 0 | 30.3 |
| doc_2.pdf | 2/2 | 0 | 19.91 |
| doc_3.pdf | 2/2 | 0 | 20.04 |
| doc_4.pdf | 0/2 | 0 | 25.53 |
| doc_5.pdf | 2/2 | 0 | 20.25 |

## Comparison with the local SLM run (same fixtures, same scoring)

| model | position accuracy | extraction failures | review seconds | cost |
|---|---|---|---|---|
| `ollama/granite4:3b` | 0.9 | 0 | 279.6 | free |
| claude-sonnet-4.6 (cloud) | 0.7 | 0 | 116.0 | 22¢ |
| `ollama/gemma3:4b` | 0.7 | 0 | 554.1 | free |
| `ollama/phi4-mini:3.8b` | 0.7 | 0 | 486.7 | free |
| `ollama/qwen3:4b` | 0.0 | 11 | 4015.9 | free |

## Findings

1. **The cloud model scored the same as two of the small local models** (0.7 = 7/10). With n = 10 scored items the difference from `granite4:3b` (0.9) is 2 items — **not a meaningful gap**.
2. **Category recall is not a model metric** here: `match_category()` resolves the category by lexical matching before any model call (`review/extraction.py:31-56`), and the fixtures embed the category name. The model only picks the position, so position accuracy is the signal.
3. **Mixing tiers changes the answer.** The cloud run must strip PII (`balanced` requires it before egress); the CI SLM run used `--no-pii` on local models. Same fixtures, different pipeline cost.
4. **`qwen3:4b` remains the outlier**: 11 extraction failures (60 s gateway timeouts) in the SLM run.

## Method and limits
- One run per document; both cloud and local models are non-deterministic — single samples.
- n = 5 documents × 2 expected categories = 10 scored items per model. Treat as a smoke measurement.
- The fixtures are synthetic and embed the category name; this measures position choice, not clause discovery.
- Reranking is excluded (no local Ollama rerank; the rerank slot is not exercised by the review pipeline).
- Raw data: `docs/benchmarks/results/cloud-slot-measurement.json` and `slm-slot-measurement.json`.
