# Slot measurement

Measurement of the three AI-gateway slots on 2026-09-30, on **both arms** — a local model and a cloud model. The product ships exactly `extraction` (the reader), `reasoning` (the checker) and `grounding` (the fact-checker) (`src/openreview_cli/slots.py:8`), and all three default to `ollama/granite4:3b` (`src/openreview_cli/config/loader.py:20-37`). Each slot is either **measured** (a number from a real run) or **not measurable** today, with the reason. Everything below is a single-sample smoke measurement on fixtures or a bounded corpus sample, not a benchmark; local and cloud models are non-deterministic.

The `grounding` row was **re-measured on 2026-10-03** after the grounding answer reader was fixed and the branch kept only its four defect fixes; the earlier figures are kept only as history, and the headline in that section is corrected.

## Slot coverage

| slot | status | how | result |
|---|---|---|---|
| `extraction` | measured, both arms | `run_review` on the `indemnitycheck` fixtures (reader) | position accuracy 0.9 local / 0.8 cloud |
| `reasoning` | has a caller; not scored on its own | the QA step of the same `run_review` (`review/runner.py:97`, `review/qa.py:75`) | runs with the model under test; no separate accuracy |
| `grounding` | measured, both arms | `--grounding-accuracy` (local via CI, cloud locally on the same assembled corpus; paraphrased labels) | local 31/44 bad caught, **25/25 good accepted** but **12 bad called grounded**; **cloud 39/44 caught, 25/25 accepted, 5 bad uncertain** |

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

**Local arm** — current figures from **CI run 37110857197**, job `grounding-accuracy`, artifact `grounding-accuracy-local.json`, git `77cab952f508`, measured 2026-10-03, on a corpus assembled from the repository's tracked fixtures (96 clause units from 17 documents; the run scores the first 20). The labels carry paraphrase classes (a lightly rewritten copy of each clause sentence):

| quantity | value |
|---|---|
| units (sample) | 20 (`--limit 20`, from a 96-unit corpus assembled out of 17 tracked fixture documents) |
| good claims (positives) | 25 (20 clause sentences + 5 paraphrased) |
| bad claims kept (negatives) | 44 (20 `unsupported_claim` + 20 `hallucination` + 4 `paraphrased_unsupported`) |
| bad claims dropped by the guard | 0 |
| bad caught | 31 / 44 (`caught_rate` 0.705) |
| bad called grounded | **12** (the acceptance failure mode) |
| good accepted | **25 / 25** |
| good wrongly rejected | 0 (`false_reject_rate` 0.0) |
| uncertain (good / bad) | 0 / 1 |
| unreadable answers | **0** (`unreadable_answers`) |
| latency (69 calls) | mean 17.39 s, median 16.78 s, p95 21.65 s, max 26.86 s |

The earlier local figures — 27 of 40 caught, **1 of 20** accepted, 19 of 20 good claims `uncertain`, mean latency 7.72 s — came from CI run 36757625645 (`38bd61263f3d`) through a **defective reader**, and are history only. That reader discarded an answer it could not parse and returned it as `uncertain` with confidence 0.0, which is why the local model appeared to hesitate; the answers it was discarding were valid JSON that it had wrapped in its own `claims` key, and a single-claim answer that omitted `claim_index`. See the corrected headline below.

**Cloud arm** — `--arm cloud`, run on this machine on 2026-10-03 at branch tip `77cab952f508` against `openrouter/anthropic/claude-sonnet-4.6`, over the **same assembled corpus and items** as the local arm (not CUAD), with PII stripped (51 entities replaced) before every call:

| quantity | value |
|---|---|
| units (sample) | 20 |
| good claims (positives) | 25 (20 clause sentences + 5 paraphrased) |
| bad claims kept (negatives) | 44 (20 `unsupported_claim` + 20 `hallucination` + 4 `paraphrased_unsupported`) |
| bad claims dropped by the guard | 0 |
| bad caught | 39 / 44 (`caught_rate` 0.886) |
| bad called grounded | 0 |
| good accepted | 25 / 25 |
| good wrongly rejected | 0 (`false_reject_rate` 0.0) |
| uncertain (good / bad) | 0 / 5 |
| unreadable answers | **0** (`unreadable_answers`) |
| latency (69 calls) | mean 2.98 s, median 2.89 s, p95 4.83 s, max 5.91 s |

**What ships, and what the dropped changes were worth.** The shipped state keeps four defect fixes and no behaviour changes: honest measurement labels, the single-finding measurement path asking the product's question, the grounding model's configured context, and a receipt that hashes a finding's text and any raw provider error instead of publishing them. The wider clause window, sibling clauses in the prompt, the memo lines and the wrongly-cited flag were dropped because a re-run did not reward them: on the local model the change did not raise the catch rate over the shipped baseline (the re-run matched it) while the change was **slower (mean 21.5 s against 17.4 s)**; on the cloud model the change caught **more (41 of 44)** than the shipped baseline (**39 of 44**). The second narrow question measured as a **net loss on both models** — local **29 of 44** caught with **5 of 25** known-good claims wrongly rejected and 4 second-pass fallbacks; cloud **26 of 44** with **6 of 25** wrongly rejected — and the three alternative wordings tried for it lost too (**5 of 44** and **31 of 44** caught), so it was dropped on evidence, not on taste.

**Headline, honestly (corrected 2026-10-03):** the earlier claim in this file that the local model "defers rather than decides" was an artefact of the reader, not a property of the model. An answer the reader could not parse was recorded as `uncertain`, so 19 of 20 known-good claims *looked* like hesitation. With the reader fixed — and local models now asked for JSON only — the local 3B model reads and decides: it accepted **all 25** known-good claims, called 31 of 44 known-bad claims ungrounded (leaving one uncertain), and called **12 grounded**. `unreadable_answers` is 0. That 12 is not a regression: the labels now include paraphrases, which is what made the acceptance failure mode visible instead of hiding it.

What separates the arms is therefore quality, not style. The cloud model catches 39 of 44 planted bad claims and leaves 0 called grounded; the local one catches 31 of 44 and calls 12 of them grounded. The local model's failure mode is **accepting** planted bad claims, not hesitating over good ones. Same harness and now the same assembled corpus, so the arms are compared directly on the negative arm — the discriminating signal, since the positives are supported by the clause by construction.

**The coverage number (a signal, not a verdict).** The labels also record how much of each claim's wording appears in the clause it cites: the supported claims score at or above **0.96** (the paraphrased positives bottom out at 0.962) while planted bad claims reach the same band, so wording overlap on its own cannot separate a real citation from a planted one — which is why nothing in the code path decides a claim from the number.

**Pilot (a real review, from the earlier run at `460c0de5ba73`; not a benchmark).** One real local review (`grounding_mode="lenient"`) assessed **12** claims and wrote a coverage number for 11: **7 accepted, 3 rejected, 1 uncertain**, coverage values 0.0, 0.0, 0.286, 0.313, 0.636 and six at 1.0. Most real citations are exact, but **about a third fall below half coverage** (four of eleven), and **some of those were accepted**. One run, so this is a distribution, not an accuracy figure.

## Removed slots (with reason)

- **`embedding`** — removed: the dense path was deleted with it (meaning-based search had no caller and lost to keyword search). Retrieval is now keyword-only FTS5, `tokenize='porter unicode61'` (`src/openreview_cli/retrieval/storage.py:74`); the committed evidence is `docs/benchmarks/results/cuad-retrieval-porter.json` (hit@1 0.0435, hit@5 0.3206, MRR@5 0.1274 over 4,042 queries / 462 contracts) against `cuad-retrieval-unicode61.json`.
- **`reranking`** — removed: the local cross-encoder made ordering worse than plain BM25 + `porter` (hit@5 0.2330 vs 0.3438 on 352 CUAD queries; paired ΔP@5 -0.0267, 95% CI [-0.0392, -0.0136]) and the cheap lexical rerank showed no measurable top-5 effect (paired ΔP@5 +0.0051, CI straddling zero), so the slot, its flags and the `router` wrapper were deleted (spec 035 FR-009); no dense/rerank path remains (`src/openreview_cli/gateway/router.py:218`). Scope: offline arms only — the original numbers this decision quoted and the cloud `voyage/rerank-2.5` arm are **not reproducible** (harness never committed; socket deleted). Receipt: `docs/benchmarks/results/cuad-rerank-offline.json`; summary in `docs/BENCHMARKS.md` (CUAD rerank arms, offline).
- **`graph`** — removed: the clause graph is rule-based and makes no model call (`src/openreview_cli/graph/` has no gateway call), so the slot had no caller; the feature itself is unchanged.
- Also gone: the **`performance`** privacy tier, which existed only to keep the removed embeddings local (`specs/035-post-measurement-cleanup/research.md`, Q9). Two tiers ship (`maximum`, `balanced`); an old `privacy.tier: performance` value still loads and is normalized to `balanced` (`src/openreview_cli/config/loader.py`).

## Not measured today

- **`reasoning` on its own** — the slot runs in every review above, but no dedicated number is published; its calls share the model under test.
- **Human-labelled grounding positives** — the positive arm is clause sentences (verbatim plus a light constant-map rewrite), which are supported by the clause by construction, so it cannot measure the false-rejection side the way a labelled set would.
- **Samples larger than a smoke measurement** — 5 documents (extraction) and 20 units (grounding), single runs, non-deterministic models.

The cloud arms are **no longer blocked**: the OpenRouter key works as of 2026-09-30, and both cloud measurements above ran on it.

## Method and limits
- One run per document/query; local and cloud models are non-deterministic → single samples.
- n = 5 docs × 2 expected categories (extraction) and `--limit 20` units (grounding). **Smoke measurements.**
- The grounding run used a corpus assembled from the repository's tracked fixture documents (96 clause units from 17 documents: `tests/fixtures/**.txt` verbatim plus fixture PDFs/DOCX parsed with `openreview_cli.parsing`) — **not** the CUAD corpus, which is gitignored and absent in CI. It ran `--arm local` with PII stripping disabled (`--no-pii`, because CI has no spaCy), so raw clause text was sent to the model and the cloud tiers would refuse those calls. It ran on a GitHub-hosted 2-vCPU `ubuntu-latest` runner (`.github/workflows/slm-measurement.yml:348`), so the latencies are CPU-bound and machine-specific. From 2026-10-01 the local arm runs against the fixed reader, and the grounding slot asks a local model for JSON only (`config/loader.py` `DEFAULT_CONFIG`), which roughly doubled per-call latency (7.7 s → 17.4 s) on the same runner class. The cloud arm now runs locally over the same assembled corpus (39 of 44 caught, 25 of 25 accepted, 5 bad uncertain, 0 unreadable).
- Positives are the cited clause's own qualifying sentence, plus a lightly rewritten copy of it, so they are supported by the clause by construction — an easier set than a human-labelled one; the negative arm is the signal, and no real-world false-positive rate may be quoted from this.
- Extraction ran with grounding off (`grounding_mode: null`) for the model comparison (grounding is measured separately).
- The cloud runs above used the configured slots on this machine (privacy tier `balanced`, so PII was stripped locally before every cloud call — 51 entities in the grounding sample). They cost **91 cents for 75 cloud calls** that day, read from the cost ledger. The local CI run, by contrast, used `--no-pii` because CI has no spaCy model.
- Both grounding arms ran over the same assembled corpus (96 clause units from 17 tracked fixture documents), so the comparison is direct; the earlier cloud run over CUAD (462 real contracts) is superseded.

## Raw data

The six-slot dump `docs/benchmarks/results/slot-measurement.json` (and the earlier text of this file) is **superseded and historical**: it describes slots that no longer exist, and its provenance pins `scripts/measure_retrieval_slots.py`, which was deleted with the dense path (`b781a1a`), so it cannot be honestly re-registered and the repo's receipt guard (`tests/unit/test_benchmark_receipts.py`) rejects it (tracked in issue #180). The evidence that exists now:

- **grounding (local)** — CI run **37110857197**, job `grounding-accuracy`; the registered receipt `docs/benchmarks/results/grounding-accuracy-local.json` distils it (full artifact: `gh run download 37110857197 -n grounding-accuracy-local`), git `77cab952f508`. Its labels carry paraphrase classes (`paraphrased_supported` / `paraphrased_unsupported`) and it records `unreadable_answers`, so a future reader defect shows up in the numbers instead of hiding inside `uncertain`. Runs 36905917351, 36847090397, 36827583980 and the reader-defect run 36757625645 before it are superseded.
- **grounding pilot (local)** — the earlier CI run 36847090397's `grounding-pilot` job, artifact `grounding-pilot`: one real lenient local review, **12 assessments, 7 accepted, 3 rejected, 1 uncertain**, 11 with a coverage number. A distribution from one run, not an accuracy figure; it is what makes the low-coverage-accepted pattern visible.
- **grounding (cloud)** — the registered receipt `docs/benchmarks/results/grounding-accuracy-cloud.json`, run on this machine on 2026-10-03 at `77cab952f508` over the same assembled corpus as the local arm. Both grounding receipts now live in the receipt guard with sha256 provenance pins (`tests/unit/test_benchmark_receipts.py`), so a change to the harness, the reader or the dispatch-time gate invalidates them and forces a re-measure; both are published in `docs/BENCHMARKS.md` §Grounding accuracy.
- **extraction (cloud)** — run locally on 2026-09-30; that JSON receipt was a session artifact and was **not** committed, so the extraction comparison above rests on this description alone.
- **extraction / slot matrix** — the same run's `measure` jobs; artifacts `slm-result-<slug>`.
- **retrieval** — the committed receipts `docs/benchmarks/results/cuad-retrieval-porter.json` and `docs/benchmarks/results/cuad-retrieval-unicode61.json`, cited in `docs/BENCHMARKS.md` §[CUAD keyword retrieval](../../BENCHMARKS.md#cuad-keyword-retrieval-tokenizer-comparison).
