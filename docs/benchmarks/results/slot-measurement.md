# Slot measurement

Measurement of the three AI-gateway slots on 2026-09-30. The product ships exactly `extraction` (the reader), `reasoning` (the checker) and `grounding` (the fact-checker) (`src/openreview_cli/slots.py:8`), and all three default to `ollama/granite4:3b` (`src/openreview_cli/config/loader.py:20-37`). Each slot is either **measured** (a number from a real run) or **not measurable** today, with the reason. Everything below is a single-sample smoke measurement on fixtures, not a benchmark; local and cloud models are non-deterministic.

## Slot coverage

| slot | status | how | result |
|---|---|---|---|
| `extraction` | measured | `run_review` on the `indemnitycheck` fixtures (reader) | position accuracy 0.9/0.7/0.7 (local×3) |
| `reasoning` | has a caller; not scored on its own | the QA step of the same `run_review` (`review/runner.py:97`, `review/qa.py:75`) | runs with the model under test; no separate accuracy |
| `grounding` | measured | `--grounding-accuracy --arm local` (CI run 36757625645) | 27/40 bad caught, 1/20 good accepted, 19 + 13 uncertain |

## extraction — position accuracy (5 `indemnitycheck` docs)

| model | run | position accuracy | extraction failures | review s |
|---|---|---|---|---|
| `ollama/granite4:3b` | local-models (CI run 36757625645) | 0.9 | 0 | 454.8 |
| `ollama/gemma3:4b` | local-models (CI run 36757625645) | 0.7 | 0 | 311.9 |
| `ollama/phi4-mini:3.8b` | local-models (CI run 36757625645) | 0.7 | 0 | 499.5 |

These are the three models whose CI jobs completed in run 36757625645 (git `38bd61263f3d`); each ran 5 documents × 2 expected categories. The earlier run's cloud row (`claude-sonnet-4.6`, 0.7) and its `ollama/qwen3:4b` row (0.0, 11 extraction failures) are superseded: the cloud row cannot be re-run (see below) and the `qwen3:4b` job had not finished when this was written.

Category recall is **not** a model metric: `match_category()` resolves the category by lexical matching before any model call (`review/extraction.py:31-56`) and the fixtures embed the category name. The model only picks the position. QA runs on the separate `reasoning` slot, so the reader and the checker no longer share one socket.

## reasoning — the checker (no longer a dead slot)

- The slot now has a product caller: `run_review` points `qa_model` at `reasoning` (`review/runner.py:96-97`) and every assessment is verified through it (`review/qa.py:75`), so the old "no caller in `src/`; only `gateway test reasoning`" reading is obsolete.
- The slot matrix routes all three slots to the model under test (`scripts/measure_slm_slots.py:66-70`), so the QA calls in the extraction run above go through `reasoning` with that model. No reasoning-only accuracy is published, and because both slots ship the same default, out-of-the-box behaviour is unchanged — the point is that the checker is now independently configurable.

## grounding — known-good/known-bad confusion matrix

The harness (`scripts/measure_slm_slots.py --grounding-accuracy`) builds known-good positives and generated known-bad negatives, drops the negatives its guard rejects, and scores a confusion matrix. The product's default `strict` mode removes ungrounded claims before the report and the structural metric returns 1.0 when nothing is grounded, so verdict counts from an ordinary review run (the earlier "7 claims assessed, all grounded") cannot show a miss — that is why this harness exists.

CI run 36757625645, job `grounding-accuracy`, artifact `grounding-accuracy-local.json`, git `38bd61263f3d`, measured 2026-09-30T18:29:23Z, `--arm local`, `ollama/granite4:3b`:

| quantity | value |
|---|---|
| units (sample) | 20 (`--limit 20`, from a 96-unit corpus assembled out of 17 tracked fixture documents) |
| good claims (positives) | 20 |
| bad claims kept (negatives) | 40 (20 `unsupported_claim` + 20 `hallucination`) |
| bad claims dropped by the guard | 0 |
| bad caught | 27 / 40 (`caught_rate` 0.675) |
| bad called grounded | 0 |
| good accepted | 1 / 20 |
| good wrongly rejected | 0 (`false_reject_rate` 0.0) |
| uncertain (good / bad) | 19 / 13 |
| latency (60 calls) | mean 7.72 s, median 7.74 s, p95 9.14 s, max 10.22 s |

**Headline, honestly:** the model almost never commits to `grounded`. On the 20 known-good claims it answered `uncertain` 19 times and `grounded` once; the `false_reject_rate` of 0.0 is carried by that `uncertain`, not by confident acceptance. On the negative arm it caught 27 of 40 and answered `uncertain` on the other 13, and it never called a bad claim grounded. On this sample the fact-checker defers rather than confirms or rejects — a finding about the model, not a defect of the harness.

## Removed slots (with reason)

- **`embedding`** — removed: the dense path was deleted with it (meaning-based search had no caller and lost to keyword search). Retrieval is now keyword-only FTS5, `tokenize='porter unicode61'` (`src/openreview_cli/retrieval/storage.py:74`); the committed evidence is `docs/benchmarks/results/cuad-retrieval-porter.json` (hit@1 0.0435, hit@5 0.3206, MRR@5 0.1274 over 4,042 queries / 462 contracts) against `cuad-retrieval-unicode61.json`.
- **`reranking`** — removed: no reranker beat plain BM25 + `porter`, so the slot, its flags and the `router` wrapper were deleted (spec 035 FR-009); no dense/rerank path remains (`docs/BENCHMARKS.md:242`, `src/openreview_cli/gateway/router.py:218`).
- **`graph`** — removed: the clause graph is rule-based and makes no model call (`src/openreview_cli/graph/` has no gateway call), so the slot had no caller; the feature itself is unchanged.
- Also gone: the **`performance`** privacy tier, which existed only to keep the removed embeddings local (`specs/035-post-measurement-cleanup/research.md`, Q9). Two tiers ship (`maximum`, `balanced`); an old `privacy.tier: performance` value still loads and is normalized to `balanced` (`src/openreview_cli/config/loader.py`).

## Not measurable today

- **Cloud arms (every slot)** — still blocked by the OpenRouter key's spend limit. The last grounding cloud attempt failed with `403 Key limit exceeded`; until the key limit is raised the cloud grounding arm and any cloud slot re-run stay blocked (`docs/specs/plans/2026-09-30-grounding-accuracy-harness-design.md` §9). The local arm is unaffected. This is why the extraction table above has no cloud row.
- **`reasoning` on its own** — the slot runs, but no dedicated number is published; its calls share the model under test.

## Method and limits
- One run per document/query; local and cloud models are non-deterministic → single samples.
- n = 5 docs × 2 expected categories (extraction) and `--limit 20` units (grounding). **Smoke measurements.**
- The grounding run used a corpus assembled from the repository's tracked fixture documents (96 clause units from 17 documents: `tests/fixtures/**.txt` verbatim plus fixture PDFs/DOCX parsed with `openreview_cli.parsing`) — **not** the CUAD corpus, which is gitignored and absent in CI. It ran `--arm local` with PII stripping disabled (`--no-pii`, because CI has no spaCy), so raw clause text was sent to the model and the cloud tiers would refuse those calls. It ran on a GitHub-hosted 2-vCPU `ubuntu-latest` runner (`.github/workflows/slm-measurement.yml:348`), so the latencies are CPU-bound and machine-specific.
- Positives are verbatim sentences from the cited clause as sent to the model, so they are trivially grounded — an easier set than a human-labelled one; the negative arm is the signal, and no real-world false-positive rate may be quoted from this.
- Extraction ran with grounding off (`grounding_mode: null`) for the model comparison (grounding is measured separately).
- Not run: the cloud grounding arm (see above); the SLM-vs-cloud comparison is unchanged from the earlier run.

## Raw data

The six-slot dump `docs/benchmarks/results/slot-measurement.json` (and the earlier text of this file) is **superseded and historical**: it describes slots that no longer exist, and its provenance pins `scripts/measure_retrieval_slots.py`, which was deleted with the dense path (`b781a1a`), so it cannot be honestly re-registered and the repo's receipt guard (`tests/unit/test_benchmark_receipts.py`) rejects it (tracked in issue #180). The evidence that exists now:

- **grounding** — CI run 36757625645, job `grounding-accuracy`; receipt artifact `grounding-accuracy-local.json` (`gh run download 36757625645 -n grounding-accuracy-local`).
- **extraction / slot matrix** — the same run's `measure` jobs; artifacts `slm-result-<slug>`.
- **retrieval** — the committed receipts `docs/benchmarks/results/cuad-retrieval-porter.json` and `docs/benchmarks/results/cuad-retrieval-unicode61.json`, cited in `docs/BENCHMARKS.md` §[CUAD keyword retrieval](../../BENCHMARKS.md#cuad-keyword-retrieval-tokenizer-comparison).
