# SLM slot measurement

- date: 2026-09-29 · commit: `9e7f9b201485`
- environment: GitHub-hosted `ubuntu-latest`, **CPU-only** (no GPU), local Ollama; PII stripping skipped; mode `indemnitycheck`; 5 documents per model.
- slots under test: every text slot routed to the model under test; each document run once.

## Results

| model | position accuracy | extraction failures | review seconds | job wall time |
|---|---|---|---|---|
| `ollama/granite4:3b` | 0.9 | 0 | 279.6 | 8m12s |
| `ollama/gemma3:4b` | 0.7 | 0 | 554.1 | 11m45s |
| `ollama/phi4-mini:3.8b` | 0.7 | 0 | 486.7 | 10m0s |
| `ollama/qwen3:4b` | 0.0 | 11 | 4015.9 | 69m36s |

Category recall is reported as **1.0** for the three working models and **0.0** for `qwen3:4b`; see Finding 1 for why recall is not a model metric here.

## Per document

| model | doc | position ok | extraction failures | seconds |
|---|---|---|---|---|
| `ollama/granite4:3b` | doc_1.pdf | 2/2 | 0 | 66.8 |
| `ollama/granite4:3b` | doc_2.pdf | 2/2 | 0 | 62.02 |
| `ollama/granite4:3b` | doc_3.pdf | 2/2 | 0 | 38.66 |
| `ollama/granite4:3b` | doc_4.pdf | 1/2 | 0 | 71.16 |
| `ollama/granite4:3b` | doc_5.pdf | 2/2 | 0 | 40.93 |
| `ollama/gemma3:4b` | doc_1.pdf | 2/2 | 0 | 113.16 |
| `ollama/gemma3:4b` | doc_2.pdf | 2/2 | 0 | 105.05 |
| `ollama/gemma3:4b` | doc_3.pdf | 1/2 | 0 | 94.23 |
| `ollama/gemma3:4b` | doc_4.pdf | 1/2 | 0 | 145.14 |
| `ollama/gemma3:4b` | doc_5.pdf | 1/2 | 0 | 96.51 |
| `ollama/phi4-mini:3.8b` | doc_1.pdf | 1/2 | 0 | 142.38 |
| `ollama/phi4-mini:3.8b` | doc_2.pdf | 2/2 | 0 | 134.81 |
| `ollama/phi4-mini:3.8b` | doc_3.pdf | 2/2 | 0 | 59.98 |
| `ollama/phi4-mini:3.8b` | doc_4.pdf | 0/2 | 0 | 88.08 |
| `ollama/phi4-mini:3.8b` | doc_5.pdf | 2/2 | 0 | 61.45 |
| `ollama/qwen3:4b` | doc_1.pdf | 0/2 | 2 | 734.01 |
| `ollama/qwen3:4b` | doc_2.pdf | 0/2 | 2 | 729.38 |
| `ollama/qwen3:4b` | doc_3.pdf | 0/2 | 2 | 729.31 |
| `ollama/qwen3:4b` | doc_4.pdf | 0/2 | 3 | 1093.98 |
| `ollama/qwen3:4b` | doc_5.pdf | 0/2 | 2 | 729.25 |

## Findings

1. **Category recall is not a model metric in this pipeline.** `match_category()` picks the playbook category by lexical substring matching *before* any model call (`review/extraction.py:31-56`, documented as "no model inference needed"), and the fixtures embed the category name in the clause text. The model only chooses the position, so **position accuracy** is the signal.
2. **`granite4:3b` scored best**: position accuracy 0.9 (9/10), 0 extraction failures, 280 s of review. `gemma3:4b` and `phi4-mini:3.8b` each scored 0.7 (7/10), also with 0 failures.
3. **`qwen3:4b` — the repo's current extraction default — produced no usable extractions.** All 11 attempts failed with `litellm.Timeout: Connection timed out after 60.0 seconds` (the gateway's default timeout): its thinking mode is too slow on a CPU runner. It also burned ~67 min doing it (4016 s of review vs 280 s for `granite4:3b`).
4. **Wall time** (including `uv sync`, Ollama install and model pull): granite4 8m12s, phi4-mini 10m0s, gemma3 11m45s, qwen3 69m36s.
5. **Two harness bugs were found and fixed before these numbers were valid**: the app database was never created, so the gateway's cost-limit check failed with `no such table: cost_logs` and every call failed instantly; and the pipeline's failure fallback stamps the category id, which inflated recall to a fake 10/10 (commit `9e7f9b2`).

## Method and limits
- Pipeline: product review (parse → review), PII stripping skipped; synthetic fixtures only.
- One run per document; local models are not deterministic, so these are single samples.
- n = 5 documents; each labels 2–4 categories. Treat this as a smoke measurement, not a benchmark.
- Reranking is excluded: no local Ollama rerank support.
- Raw per-model JSON: `docs/benchmarks/results/slm-slot-measurement.json` (and the CI artifacts of run 36568984266).
