# Slot measurement

Measurement of the three AI-gateway slots on 2026-09-30, on **both arms** — a local model and a cloud model. The product ships exactly `extraction` (the reader), `reasoning` (the checker) and `grounding` (the fact-checker) (`src/openreview_cli/slots.py:8`), and all three default to `ollama/granite4:3b` (`src/openreview_cli/config/loader.py:20-37`). Each slot is either **measured** (a number from a real run) or **not measurable** today, with the reason. Everything below is a single-sample smoke measurement on fixtures or a bounded corpus sample, not a benchmark; local and cloud models are non-deterministic.

## Slot coverage

| slot | status | how | result |
|---|---|---|---|
| `extraction` | measured, both arms | `run_review` on the `indemnitycheck` fixtures (reader) | position accuracy 0.9 local / 0.8 cloud |
| `reasoning` | has a caller; not scored on its own | the QA step of the same `run_review` (`review/runner.py:97`, `review/qa.py:75`) | runs with the model under test; no separate accuracy |
| `grounding` | measured, both arms | `--grounding-accuracy` (local via CI, cloud locally on CUAD) | local 27/40 bad caught, 1/20 good accepted; **cloud 39/40 caught, 20/20 accepted** |

## extraction — position accuracy (5 `indemnitycheck` docs)

| model | run | position accuracy | extraction failures | review s |
|---|---|---|---|---|
| `ollama/granite4:3b` | local-models (CI run 36757625645) | 0.9 | 0 | 454.8 |
| `ollama/gemma3:4b` | local-models (CI run 36757625645) | 0.7 | 0 | 311.9 |
| `ollama/phi4-mini:3.8b` | local-models (CI run 36757625645) | 0.7 | 0 | 499.5 |
| openrouter/anthropic/claude-sonnet-4.6 | cloud slots (configured, run locally 2026-09-30) | 0.8 | 0 | 110.4 |

The three local rows are the models whose CI jobs completed in run 36757625645 (git `38bd61263f3d`); each ran 5 documents × 2 expected categories. The cloud row is a configured-slots run on this machine the same day (5 documents, 17–29 s per document, 110.4 s total, PII stripped before each call). The `ollama/qwen3:4b` row from the earlier run (0.0 with 11 extraction failures) is kept in history only: its current job was still measuring when this was written.

**The cloud row and the shipped local default differ by one position out of ten** (8/10 vs 9/10) — that is noise at this sample size, not a verdict on the two models. What does separate them is speed (110 s vs 455 s for the same five documents) and the grounding behaviour below.

Category recall is **not** a model metric: `match_category()` resolves the category by lexical matching before any model call (`review/extraction.py:31-56`) and the fixtures embed the category name. The model only picks the position. QA runs on the separate `reasoning` slot, so the reader and the checker no longer share one socket.

## reasoning — the checker (no longer a dead slot)

- The slot now has a product caller: `run_review` points `qa_model` at `reasoning` (`review/runner.py:96-97`) and every assessment is verified through it (`review/qa.py:75`), so the old "no caller in `src/`; only `gateway test reasoning`" reading is obsolete.
- The slot matrix routes all three slots to the model under test (`scripts/measure_slm_slots.py:66-70`), so the QA calls in the extraction run above go through `reasoning` with that model. No reasoning-only accuracy is published, and because both slots ship the same default, out-of-the-box behaviour is unchanged — the point is that the checker is now independently configurable.

## grounding — known-good/known-bad confusion matrix

The harness (`scripts/measure_slm_slots.py --grounding-accuracy`) builds known-good positives and generated known-bad negatives, drops the negatives its guard rejects, and scores a confusion matrix. The product's default `strict` mode removes ungrounded claims before the report and the structural metric returns 1.0 when nothing is grounded, so verdict counts from an ordinary review run (the earlier "7 claims assessed, all grounded") cannot show a miss — that is why this harness exists.

**Local arm** — CI run 36757625645, job `grounding-accuracy`, artifact `grounding-accuracy-local.json`, git `38bd61263f3d`, measured 2026-09-30T18:29:23Z, on a corpus assembled from the repository's tracked fixtures (96 units from 17 documents):

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

**Cloud arm** — `--arm cloud`, run on this machine on 2026-09-30 against `openrouter/anthropic/claude-sonnet-4.6`, over the real CUAD corpus (`data/legalbenchrag/corpus/cuad`, 462 contracts), same sample size, with PII stripped (43 entities replaced) before every call:

| quantity | value |
|---|---|
| units (sample) | 20 (`--limit 20`, from the CUAD corpus) |
| good claims (positives) | 20 |
| bad claims kept (negatives) | 40 (20 `unsupported_claim` + 20 `hallucination`) |
| bad claims dropped by the guard | 0 |
| bad caught | 39 / 40 (`caught_rate` 0.975) |
| bad called grounded | 0 |
| good accepted | 20 / 20 |
| good wrongly rejected | 0 (`false_reject_rate` 0.0) |
| uncertain (good / bad) | 0 / 1 |
| latency (60 calls) | mean 2.96 s, median 3.11 s, p95 4.12 s, max 5.31 s |

**Headline, honestly:** the two arms differ in kind, not just degree. The cloud model **decides** — it confirmed all 20 known-good claims and called 39 of 40 known-bad claims ungrounded, leaving one bad claim uncertain. The local 3B model **defers**: it answered `uncertain` on 19 of 20 good claims, so its `false_reject_rate` of 0.0 is carried by hesitation, not by confident acceptance. On the negative arm it caught 27 of 40 and never called a bad claim grounded. Same harness, same labels, same page. The positives are trivially grounded by construction, so the negative arm is the discriminating signal.

## Removed slots (with reason)

- **`embedding`** — removed: the dense path was deleted with it (meaning-based search had no caller and lost to keyword search). Retrieval is now keyword-only FTS5, `tokenize='porter unicode61'` (`src/openreview_cli/retrieval/storage.py:74`); the committed evidence is `docs/benchmarks/results/cuad-retrieval-porter.json` (hit@1 0.0435, hit@5 0.3206, MRR@5 0.1274 over 4,042 queries / 462 contracts) against `cuad-retrieval-unicode61.json`.
- **`reranking`** — removed: no reranker beat plain BM25 + `porter`, so the slot, its flags and the `router` wrapper were deleted (spec 035 FR-009); no dense/rerank path remains (`docs/BENCHMARKS.md:242`, `src/openreview_cli/gateway/router.py:218`).
- **`graph`** — removed: the clause graph is rule-based and makes no model call (`src/openreview_cli/graph/` has no gateway call), so the slot had no caller; the feature itself is unchanged.
- Also gone: the **`performance`** privacy tier, which existed only to keep the removed embeddings local (`specs/035-post-measurement-cleanup/research.md`, Q9). Two tiers ship (`maximum`, `balanced`); an old `privacy.tier: performance` value still loads and is normalized to `balanced` (`src/openreview_cli/config/loader.py`).

## Not measured today

- **`reasoning` on its own** — the slot runs in every review above, but no dedicated number is published; its calls share the model under test.
- **Human-labelled grounding positives** — the positive arm is verbatim clause sentences, which are trivially grounded, so it cannot measure the false-rejection side the way a labelled set would.
- **Samples larger than a smoke measurement** — 5 documents (extraction) and 20 units (grounding), single runs, non-deterministic models.

The cloud arms are **no longer blocked**: the OpenRouter key works as of 2026-09-30, and both cloud measurements above ran on it.

## Method and limits
- One run per document/query; local and cloud models are non-deterministic → single samples.
- n = 5 docs × 2 expected categories (extraction) and `--limit 20` units (grounding). **Smoke measurements.**
- The grounding run used a corpus assembled from the repository's tracked fixture documents (96 clause units from 17 documents: `tests/fixtures/**.txt` verbatim plus fixture PDFs/DOCX parsed with `openreview_cli.parsing`) — **not** the CUAD corpus, which is gitignored and absent in CI. It ran `--arm local` with PII stripping disabled (`--no-pii`, because CI has no spaCy), so raw clause text was sent to the model and the cloud tiers would refuse those calls. It ran on a GitHub-hosted 2-vCPU `ubuntu-latest` runner (`.github/workflows/slm-measurement.yml:348`), so the latencies are CPU-bound and machine-specific.
- Positives are verbatim sentences from the cited clause as sent to the model, so they are trivially grounded — an easier set than a human-labelled one; the negative arm is the signal, and no real-world false-positive rate may be quoted from this.
- Extraction ran with grounding off (`grounding_mode: null`) for the model comparison (grounding is measured separately).
- The cloud runs above used the configured slots on this machine (privacy tier `balanced`, so PII was stripped locally before every cloud call — 43 entities in the grounding sample). They cost **91 cents for 86 cloud calls** that day, read from the cost ledger. The local CI run, by contrast, used `--no-pii` because CI has no spaCy model.
- The cloud grounding arm ran over the CUAD corpus (462 real contracts); the local arm ran over a corpus assembled from the repository's tracked fixtures. The two are therefore not the same documents — the comparison is of arms, not of a single corpus.

## Raw data

The six-slot dump `docs/benchmarks/results/slot-measurement.json` (and the earlier text of this file) is **superseded and historical**: it describes slots that no longer exist, and its provenance pins `scripts/measure_retrieval_slots.py`, which was deleted with the dense path (`b781a1a`), so it cannot be honestly re-registered and the repo's receipt guard (`tests/unit/test_benchmark_receipts.py`) rejects it (tracked in issue #180). The evidence that exists now:

- **grounding (local)** — CI run 36757625645, job `grounding-accuracy`; receipt artifact `grounding-accuracy-local.json` (`gh run download 36757625645 -n grounding-accuracy-local`).
- **grounding (cloud) and extraction (cloud)** — run locally on 2026-09-30; the JSON receipts are session artifacts, **not yet committed**. Landing them in this directory requires registering them in the receipt guard (`tests/unit/test_benchmark_receipts.py`) with provenance, metadata and a citation, which is a separate piece of work.
- **extraction / slot matrix** — the same run's `measure` jobs; artifacts `slm-result-<slug>`.
- **retrieval** — the committed receipts `docs/benchmarks/results/cuad-retrieval-porter.json` and `docs/benchmarks/results/cuad-retrieval-unicode61.json`, cited in `docs/BENCHMARKS.md` §[CUAD keyword retrieval](../../BENCHMARKS.md#cuad-keyword-retrieval-tokenizer-comparison).
