# Benchmarks

Every number on this page was measured against the source tree this session, or is explicitly labeled otherwise. Nothing is extrapolated from vendor claims. This is a pre-alpha project; treat these as a baseline, not a promise.

- [Methodology](#methodology)
- [Latency](#latency)
- [Resource footprint](#resource-footprint)
- [Throughput](#throughput)
- [Pipeline-wiring recall (mocked)](#pipeline-wiring-recall-mocked)
- [PII accuracy](#pii-accuracy-measured-50-seeded-contracts)
- [ContractNLI public benchmark (real-world NDAs)](#contractnli-public-benchmark-real-world-ndas-measured)
  - [Live LLM extraction + QA verification on real ContractNLI NDAs](#live-llm-extraction--qa-verification-on-real-contractnli-ndas)
- [CUAD public benchmark (scale and timing)](#cuad-public-benchmark-scale-and-timing)
- [Review accuracy (12 labeled NDA clauses)](#review-accuracy-measured-12-labeled-nda-clauses)
- [Measured vs. not measured](#measured-vs-not-measured)
- [Environment artifact: offline registry refresh](#environment-artifact-offline-registry-refresh)

## Methodology

**Environment (this session):** 4-core x86_64, 7.7 GB RAM, no GPU, no Ollama server, no outbound network. Python 3.12 under uv, running from the source tree.

**Reproduction:**

| Metric | Command / script |
|---|---|
| CLI startup | `uv run openreview --help` under `/usr/bin/time -v`, 3 runs |
| PDF / DOCX parse | in-process timing of the parsing library (see `tests/` + `src/openreview_cli/parsing/`) |
| PII corpus + stress | `uv run python scripts/benchmark_pii_stripping.py --output .benchmark-reports/pii-throughput-raw.json` (real `PiiEngine`) |
| PII accuracy | `uv run pytest tests/integration/test_benchmark_pii_accuracy.py` |
| ContractNLI 95 NDAs | `uv run python scripts/benchmark_contractnli.py` |
| Product-mode recall | `uv run python scripts/benchmark_product_modes.py` (mocked gateway, deterministic) |
| Test collection | `uv run pytest --collect-only` |

Run outputs are **never committed** (decision D5): `review_results/` and `.benchmark-reports/` are
gitignored, and the committed evidence for every number on this page is a receipt under
`docs/benchmarks/results/`, cited from the relevant section's `Last verified:` line.

Run each benchmark on your own machine to get comparable numbers; the offline note below shows how much environment can matter.

## Latency

| Metric | Value | Notes |
|---|---|---|
| CLI startup (`--help`) | 0.59 / 0.68 / 0.76 s, median 0.68 | 3 runs, peak RSS ~43 MB |
| Parse 1-page PDF, library level, cold | 3.1–3.2 s | one-time nupunkt model load per process |
| Parse 1-page PDF, library level, warm | 0.004 s | second parse in same process |
| Parse 37 KB DOCX, warm process | 0.016 s, 3 clauses | in-process timing; median of 6 warm runs |
| PII strip, 50-page synthetic stress | 2.3823 s | 395 entities (see footprint below) |

The cold-PDF number is dominated by a one-time sentence-segmentation model load (~3 s per process), not by PDF parsing itself.

No receipt by design: these rows are wall-clock on the [methodology](#methodology) sandbox, and the parse row is dominated by the offline registry-refresh stall documented under [the environment artifact](#environment-artifact-offline-registry-refresh), so a committed receipt would pin an environment artifact rather than a product number. The `--help` row does not pay that stall: Click's eager `--help` exits before the root callback runs its registry refresh (`app.py`). The PII-stress row derives from [docs/benchmarks/results/pii-throughput.json](benchmarks/results/pii-throughput.json).

## Resource footprint

| Path | Peak RSS | Context |
|---|---|---|
| CLI `--help` | ~43 MB | measurement above |
| CLI parse (this sandbox) | ~410 MB | wall 14.0–44.4 s see [offline artifact](#environment-artifact-offline-registry-refresh) |
| PII 50-page stress | ~1724 MB | 395 entities, 2.3823 s |

The project's 100 MiB streaming memory target, with a 110 MiB hard ceiling enforced by the memory tests, applies to streaming pipeline paths; parsers stream page-by-page and never load a full document. The parse CLI process peaked ~410 MB and the spaCy/PII path ~1724 MB on the 50-page stress; both include one-time model loads, reported factually.

No receipt by design: peak RSS includes one-time model loads and the offline registry-refresh stall (see the [environment artifact](#environment-artifact-offline-registry-refresh)), so it is sandbox-specific rather than a product number. The PII-stress row derives from [docs/benchmarks/results/pii-throughput.json](benchmarks/results/pii-throughput.json).

## Throughput

| Metric | Value | Method |
|---|---|---|
| PII corpus, 54 processed rows | 54/54 success, 1,918 entities, 73.906 s total (~1.4 s/row avg) | `scripts/benchmark_pii_stripping.py`, real `PiiEngine` |
| PII derived rate | ~ 44 docs/min | derived: 54 rows / 73.906 s, single-process, engine init amortized across all rows |

Last verified: 2026-09-22 @ b5f051a (receipt: docs/benchmarks/results/pii-throughput.json).

Processed rows are not distinct files: `tests/fixtures/pii/seeded_contracts/` holds 53 `.txt` files
(50 with ground-truth labels) and `no_pii_document.txt` is processed twice, once in the corpus loop
and once in the part-3 edge-case pass. See
[docs/benchmarks/results/pii-throughput.json](benchmarks/results/pii-throughput.json) for the
file-level detail.

Not measured: dense-retrieval/embedding throughput (needs a local Ollama server), graph clustering (needs a one-time legal-bert download).

## Pipeline-wiring recall (mocked)

| Metric | Value | Notes |
|---|---|---|
| Product-mode recall, synthetic ground truth + MOCKED gateway | 23 modes x 5 docs, 100% recall (10 expected flags per mode: 2 per synthetic doc) | 0.4-0.9 s/mode after the first; first mode 29.8 s (one-time engine init) |

Last verified: 2026-09-22 @ 859402f (receipt: docs/benchmarks/results/product-modes.json).

**Label this correctly:** this validates pipeline wiring (mode → playbook → match/extract/QA → flag) with a deterministic mocked gateway. All 23 named modes are covered by this mechanism. Both mock paths — `openreview benchmark baseline --provider mock` and `openreview benchmark run --ci` — are **mode-aware**: a mode's prediction is derived from its own bundled playbook, so a mode only "matches" the categories that playbook declares; only that per-mode `match` signal (surfaced as MAUD `comparison_f1`) diverges across modes, while the label/span metrics stay identical on the ContractNLI/CUAD mock datasets. It is a **wiring** stub: it proves that mode → playbook → category selection is wired end to end, and it proves nothing about model quality. Five modes have a declared baseline (`distrocheck`, `franchisecheck`, `opcheck`, `partnercheck`, `sponsorcheck` in `docs/benchmarks/*.json`) which publishes a fixture, an expected overall assessment and time budgets but **no accuracy number** — no model runs, so nothing is scored. Every other named mode has no declared baseline and is covered only by the mocked wiring run. Real-model accuracy was measured separately (provider not recorded); see [Review accuracy](#review-accuracy-measured-12-labeled-nda-clauses) below. The `scripts/benchmark_review_accuracy.py` script is structural-only (it does not make real LLM calls and reads `predicted_position` from the corpus).

## Accuracy signals

Accuracy-tagged tests run in the standard test suite. Most are structural checks (binary pass/fail assertions), not numeric precision/recall on a labeled corpus. The exception is `tests/integration/test_benchmark_pii_accuracy.py`, which runs the real `PiiEngine` against the labeled seeded corpus and computes precision/recall (see [PII accuracy](#pii-accuracy-measured-50-seeded-contracts)).

**21 passed, 0 failed, 0 skipped** (76.13 s) for the four files below, run as `uv run pytest tests/integration/test_pii_accuracy.py tests/unit/test_tier_accuracy.py tests/integration/test_review_accuracy.py tests/integration/test_benchmark_pii_accuracy.py -q`.

Last verified: 2026-09-24 @ 882568c (receipt: docs/benchmarks/results/accuracy-suite.json).

| Test file | What it validates | Result |
|---|---|---|
| `tests/integration/test_pii_accuracy.py` (2 tests) | Detects ≥5 PII entities on up-to-10 real CUAD contracts; 0 false positives on clean text | ✓ pass |
| `tests/unit/test_tier_accuracy.py` (9 tests) | Tier precision/recall/F1 targets frozen + monotonically increasing + threshold ordering | ✓ pass |
| `tests/integration/test_review_accuracy.py` (7 tests) | F1 / amber-rate / QA-catch formulas correct; benchmark script exists + has required structure | ✓ pass |
| `tests/integration/test_benchmark_pii_accuracy.py` (3 tests) | Labeled-corpus PII precision/recall (span-level) | ✓ pass: recall 96.4% and precision 95.3%, above the 95% spec target |

**Tier accuracy targets** (design goals, not measured source: `gateway/tier_accuracy.py:41-60`):

| Tier | F1 | Precision | Recall |
|---|---|---|---|
| Maximum (fully local) | 0.70 | 0.65 | 0.75 |
| Balanced (default) | 0.80 | 0.75 | 0.85 |
| Performance (cloud-assisted) | 0.90 | 0.85 | 0.95 |

**Honest caveat:** these tier targets are design goals; see [Review accuracy](#review-accuracy-measured-12-labeled-nda-clauses) below for actual measured numbers (90.9% F1, 100% QA error-catch on 12 NDA clauses; provider not recorded).

## PII accuracy (measured 50 seeded contracts)

Real `PiiEngine` (Presidio + spaCy `en_core_web_lg`) evaluated against `tests/fixtures/pii/seeded_contracts/` with `BenchmarkRunner.run_pii()`.

Matching is span-level (type-agnostic): a detection counts as correct when its value overlaps a ground-truth value, whatever entity type label it carries, so a right span with a wrong label still counts as correct. That labelling limitation is tracked separately as D-82 in `specs/archive/DEFERRED.md` and issue 115.

**Overall:** 717 detections across 50 contracts, 584 ground-truth entities.

| Metric | Value | Notes |
|---|---|---|
| Recall | 96.4% | 563 / 584 ground-truth entities matched |
| Precision | 95.3% | 683 / 717 predictions matched ground truth |
| F1 | 95.8% | |
| Per-type recall (structured recognizers) | AMOUNT 100%, TAX_ID 100%, REG_NUMBER 100%, EMAIL_ADDRESS 100%, PHONE_NUMBER 100%, ACCT 100%, ID_DOCUMENT 100%, DATE_TIME 100%, LOCATION 100% | Exact on the seeded corpus |
| Per-type recall (NER) | ORGANIZATION 83.3% (70 / 84), PERSON 86.0% (43 / 50) | spaCy NER on **synthetic** entity names (e.g. `Name3 Smith`, `AutoCompanyB1`); real contract accuracy is expected to differ |

Last verified: 2026-09-24 @ 882568c (receipt: docs/benchmarks/results/pii-accuracy.json).

**Synthetic-data caveat:** the seeded corpus is artificially generated (`Name3 Smith`, `AutoCompanyB1`), so 96.4% describes synthetic documents, not real contracts. The remaining misses are concentrated in `PERSON` (86%) and `ORGANIZATION` (83%) — exactly the entities whose names are artificial. Treat these numbers as a baseline on synthetic data, not a real-contract guarantee.

## Review accuracy (measured 12 labeled NDA clauses)

Real extraction + QA pipeline (provider and model were not recorded in the source artifact) against `tests/fixtures/review/nda-corpus-v1/nda-corpus-v1.json` with `precheck-nda-v1` playbook. 24 API calls (per-clause extraction + QA).

| Metric | Value | Target (spec) | Status |
|---|---|---|---|
| F1 | 90.91% | ≥ 70% | ✓ exceeds |
| Precision | 83.33% | | 10/12 correct |
| Recall | 100.00% | | 0 clauses left uncertain |
| QA error-catch rate | 100.00% | ≥ 80% | ✓ QA disagreed on both wrong extractions |
| Amber rate | 16.67% | ≤ 10% | ⚠ 2/12 flagged (both were actually wrong, so the flag is correct, but the rate is above target) |
| Total latency | 80.7 s | | avg 6.72 s/clause, 24 API calls |

Last verified: 2026-09-21 @ unknown (re-run predates this branch; the source artifact is gitignored) (receipt: docs/benchmarks/results/review-accuracy.json).

**Per-clause:** 10 correct positions, 2 wrong (both predicted `walkaway`/`preferred` when expected was `acceptable`). QA caught both wrong predictions. All 10 correct predictions had QA agree + no amber. (Per-clause detail comes from the gitignored source artifact; the committed receipt carries aggregates only.)

**Small-corpus caveat:** 12 clauses is too small for high-confidence F1. These numbers are directionally correct but the true F1 confidence interval is wide. A larger corpus (>100 clauses) would tighten the estimate.

## Full pipeline demo (qualitative measured)

End-to-end `openreview precheck review` on `tests/fixtures/nda_with_pii.pdf` (1 page, 5 clauses) through all configured providers:

| Stage | Provider | Model | Status |
|---|---|---|---|
| Parse | PyMuPDF (local) | | 5 clauses, 1 page |
| PII strip | Presidio + spaCy (local) | `en_core_web_lg` | PII replaced with `[PAR]`, `[NAME_1]`, `[EMAIL_1]`, `[DATE_2]` |
| Extraction | OpenRouter (cloud) | `claude-sonnet-4.6`* | 5/5 clauses assessed |
| QA | OpenRouter (cloud) | `claude-sonnet-4.6`* | amber flags raised |
| Embedding | Voyage (cloud) | `voyage-3.5` | 1024-dimensional vectors |
| Reranking | Voyage (cloud) | `rerank-2.5` | correct clause ranking confirmed |

* `claude-sonnet-4.6` is the OpenRouter model id recorded for the run; it is not an entry in the bundled `gateway/models.json` registry (which offers `claude-sonnet-latest`).

**Result:** 0 matches, 5 differences, avg confidence 0.95, recommendation: revise. Full cost report via `openreview gateway costs --today`. Total wall time ~2.5 min (includes cold API connection overhead).

**Note:** this is a qualitative pipeline integration test, not an accuracy measurement; the fixture PDF has no ground-truth labels. **No receipt by design:** the run needs OpenRouter and Voyage (network) and the fixture carries no labels, so no reproducible JSON artifact exists to commit; the measured accuracy numbers live in the [Review accuracy](#review-accuracy-measured-12-labeled-nda-clauses) section above.

## ContractNLI public benchmark (real-world NDAs measured)

Span extraction and category coverage across the [ContractNLI](https://github.com/stanford-crfm/legalbench) dataset (95 real-world Non-Disclosure Agreements, 977 annotated tests / 1,389 ground-truth evidence spans) mapped to standard `precheck` playbook categories.

Evaluated using `scripts/benchmark_contractnli.py` with NUPunkt sentence segmentation (no clause detection):

| Metric | Value |
|---|---|
| Real-world NDAs | 95 documents |
| Total evaluated spans | 1,389 spans across 977 tests |
| **Overall span coverage** | **97.84%** (1,359 / 1,389 spans captured) |
| Wall time | 5.79 s (~0.061 s / NDA) |

Last verified: 2026-09-22 @ unknown (source corpus is gitignored; commit of the corpus snapshot is not recorded) (receipt: docs/benchmarks/results/contractnli-coverage.json).

**Category coverage breakdown:**
- `non-solicitation`: **100.00%**
- `return-of-materials`: **100.00%**
- `boilerplate`: **99.33%**
- `permitted-disclosures`: **97.62%**
- `confidentiality-term`: **96.57%**

Every standard NDA hypothesis question in ContractNLI is successfully resolved to a corresponding `precheck` category, demonstrating high coverage across diverse real-world NDA drafting variations.

### Live LLM extraction + QA verification on real ContractNLI NDAs

End-to-end extraction + QA on 15 distinct clauses drawn from 5 real ContractNLI NDA documents (round-robin, so no single NDA dominates). `anthropic/claude-sonnet-4.6` via OpenRouter (one extraction call + one QA verification call per clause).

| Metric | Value |
|---|---|
| Model | `anthropic/claude-sonnet-4.6` (via OpenRouter) |
| Distinct clauses evaluated | 15 across 5 NDAs |
| Preferred | 1 |
| Acceptable | 14 |
| Walkaway | 0 |
| Uncertain | 0 |
| QA agreement rate | 6.67% (1 / 15 QA-verified) |
| Amber rate | 93.33% (14 / 15 flagged) |
| Steady-state latency | ~7.8 s / clause (extraction + QA) |

Last verified: 2026-09-21 @ unknown (frozen live run predates this branch; the source artifact is gitignored) (receipt: docs/benchmarks/results/contractnli-live.json).

**Interpretation:** extraction coverage is strong (all 15 clauses resolved, 0 uncertain), but the QA verifier is extremely conservative on real-world clause phrasing; it disagreed with 14 of 15, flagging nearly every clause even where the extractor was confident. This is a known pre-alpha signal: QA calibration is intentionally cautious and will tighten as the labeled corpus grows. Latency (~7.8 s/clause) is well within interactive-review tolerance. The QA disagreement rate is far higher than on the synthetic NDA corpus (see [Review accuracy](#review-accuracy-measured-12-labeled-nda-clauses)), so it is most likely a corpus/phrasing effect rather than a model-quality signal.

**Reproduction:** `uv run python scripts/benchmark_contractnli_llm.py` with a configured OpenRouter API key. The run writes the exact model and the identity (SHA-256) of every evaluated clause into the output JSON; pass that file back with `--pin <report.json>` to re-evaluate the identical clause set.

## CUAD public benchmark (scale and timing)

Parsing scale against the [CUAD v1](https://www.atticusprojectai.org/cuad) dataset (CC BY 4.0): 462 commercial legal contracts with 4,042 expert-labeled queries spanning 6,247 gold spans from The Atticus Project. Sentence segmentation via nupunkt (no LLM calls, local only).

| Metric | Value |
|---|---|
| Contracts | 462 (4,042 queries / 6,247 spans, all readable) |
| Time | 85.3 s for the full clause-segmentation pass over 462 documents (~0.18 s/contract) |

Last verified: 2026-09-22 @ f7b08ba (receipt: docs/benchmarks/results/cuad-segmentation.json).

**Clause segmentation (measured).** A reproducible run (`scripts/benchmark_cuad_segmentation.py`) loaded 462 of 462 documents and measured **90.67% of 6,247 spans** fully contained in a single detected clause, with query coverage of **91.64% of 4,042 queries** (at least one span contained). Enclosure tightness is low: mean **token-F1 0.307**, because the detector groups whole sentences under section headings (7 regex patterns), so one detected clause often swallows several labeled spans. Mean **token-F1** is taken over **every** evaluated span with a non-contained span counted as **0**, so it is a deliberate conservative floor rather than an average over only the spans that were successfully contained. One corpus `file_path` is stored in NFD (decomposed) Unicode form while the file on disk is NFC; the script retries the path under Unicode NFC normalization, so every referenced document loads.

This measures **segmentation** (whether an expert-labeled span lies fully inside one detected clause, and how tightly that clause encloses it), **not query-answering accuracy**. High containment with coarse enclosures is the expected shape for a section-heading segmenter; the low token-F1 is the honest cost of that grouping, not a contradiction of the containment number.

**Reproduction:** run `uv run python scripts/benchmark_cuad_segmentation.py` (writes `.benchmark-reports/cuad-segmentation.json`). To obtain the corpus, download CUAD v1 from [atticusprojectai.org/cuad](https://www.atticusprojectai.org/cuad) (CC BY 4.0). (Note: `scripts/benchmark_legalbenchrag.py` does not download a corpus — it only reads an already-present one from `/tmp/opencode/legalbenchrag_data/`.) The corpus is gitignored (`data/` in `.gitignore`).

## MAUD public benchmark (segmentation and timing)

Parsing scale against the [MAUD](https://www.atticusprojectai.org/maud) dataset (CC BY 4.0): 150
mergers-and-acquisitions agreement text files with 1,676 expert-labeled queries spanning 2,839 gold
spans. Sentence segmentation via nupunkt (no LLM calls, local only).

| Metric | Value |
|---|---|
| Documents | 150 (1,676 queries / 2,839 spans, all readable) |
| Time | 160.6 s for the full clause-segmentation pass over 150 documents (~1.07 s/document) |

Last verified: 2026-09-22 @ f7b08ba (receipt: docs/benchmarks/results/maud-segmentation.json).

**Clause segmentation (measured).** The same reproducible run (`uv run python scripts/benchmark_cuad_segmentation.py --dataset maud`) loaded 150 of 150 documents and measured **80.38% of 2,839 spans** fully contained in a single detected clause, with query coverage of **85.62% of 1,676 queries** (at least one span contained). Enclosure tightness is low: mean **token-F1 0.183**, because the detector groups whole sentences under section headings (7 regex patterns). Mean token-F1 is taken over every evaluated span with a non-contained span counted as 0, so it is a deliberate conservative floor.

This measures **segmentation**, not query-answering accuracy and not deal-point accuracy. The same corpus hash (`82ef159b87f73a9c68e7143fac88bf47ac212713b56617d7e87d6f1f0a781daf`) is pinned in the receipt. The corpus is gitignored (`data/` in `.gitignore`); MAUD is published by The Atticus Project (CC BY 4.0).

## Measured vs. not measured

**Measured this session:** CLI startup, PDF/DOCX parse, PII corpus + stress (real `PiiEngine`), PII accuracy on 50 seeded contracts (96.4% recall, span-level predicate), review accuracy on 12 NDA clauses (90.9% F1; provider not recorded), live LLM extraction + QA verification on 15 real ContractNLI NDA clauses across 5 NDAs (0 uncertain, 6.67% QA agreement, 93.33% amber, ~7.8 s/clause), CUAD public benchmark on 462 contracts (scale, timing, and clause segmentation), MAUD public benchmark on 150 M&A documents (scale, timing, and clause segmentation), product-mode wiring, 23 named modes (mocked, playbook-aware), test collection (3,935 tests), accuracy-test suite (21 passed, 0 failed).

Last verified: 2026-09-25 @ fdea262 (receipt: docs/benchmarks/results/test-collection.json).
Last verified: 2026-09-24 @ 882568c (receipt: docs/benchmarks/results/accuracy-suite.json).

**Not measured (methodology documented, no numbers invented):**

| Metric | Why | How to measure |
|---|---|---|
| Full LLM review latency + cost per review | needs API keys | `openreview gateway costs` (SQLite `cost_logs`) + `scripts/benchmark_review_accuracy.py` |
| Dense-retrieval / embedding throughput | needs local Ollama | run the retrieval path with `nomic-embed-text` |
| Graph clustering | needs legal-bert download | `openreview graph` with `--cluster-clauses` |
| Reranker effect | unmeasured — disabled by default | opt-in `--rerank` on a labeled retrieval corpus (a 26-query pilot was inconclusive) |
| MAUD deal-point accuracy | no bundled playbook's category taxonomy matches MAUD's deal-point labels: the nearest mode, `buycheck`, scores against the `asset-purchase-v1` playbook (purchase price, included/excluded assets, liabilities, reps and warranties, closing conditions), not MAUD's merger-agreement deal points | map the deal points onto a playbook whose categories match, then run `openreview benchmark baseline --modes=buycheck` (or a new M&A mode) |
| CUAD query-answering accuracy | the CUAD section measures clause segmentation (span containment and enclosure tightness), not answering the 4,042 expert queries | score predicted answers against the CUAD query labels, e.g. extend `scripts/benchmark_cuad_segmentation.py` with an answer-scoring pass |
| ContractNLI query-answering accuracy | the ContractNLI section measures span extraction and playbook-category coverage, not the entailment question itself | score entailment (entailment / contradiction / not-mentioned) against the 977 annotated tests |
| Hallucination detection accuracy | the shipped detector is a ROUGE-L lexical-overlap placeholder (EXPERIMENTAL); a CG-DPO detector is planned but not shipped | run the detector on a labeled grounded/ungrounded corpus and score precision/recall (`--hallucination-method` selects the detector) |
| Bilateral comparison accuracy | documented only as a ceiling of 64% F1 (recorded in `PRODUCT.md`), not measured here (`docs/ARCHITECTURE.md:120`) | run `openreview precheck compare` on a labeled divergence corpus and score against the RCBSF taxonomy |

Benchmark-harness honesty: the `openreview benchmark run --all --ci` CLI uses a **mock pipeline by default** for CUAD/MAUD/ContractNLI datasets (real LLM integration deferred). The ContractNLI coverage benchmark above was run manually against the real nupunkt parser, not through the mock harness. PII benchmarks use the real `PiiEngine`. Hallucination detection uses a ROUGE-L lexical-overlap placeholder (EXPERIMENTAL default); a CG-DPO detector is planned but not shipped.

Historical numbers from earlier project READMEs (e.g. 860 docs, 2.28M chars/sec) are **not** reproduced this session and are deliberately omitted.

## Environment artifact: offline registry refresh

The CLI in this sandbox took 14.0–44.4 s wall to parse a PDF, an artifact of environment, not product performance. On startup the CLI refreshes the provider model registry over HTTPS; with no outbound network the connect stalls until timeout (debug log: `connect_tcp to raw.githubusercontent.com failed after 40s`, then "registry refresh skipped") before proceeding. On a networked machine this is a short request; the 410 MB peak RSS also reflects this process. The stall is a real improvement area (registry refresh should be fast-failing/timeout-aware when offline), but it is not representative of parse throughput.

**No receipt by design:** the 14.0–44.4 s and ~410 MB figures describe this sandbox's offline registry-refresh stall, not product performance, and cannot be reproduced off the sandbox.

## Cost tracking

Per-review and per-day cost limits are configurable (defaults: 100¢/review, 1,000¢/day). Breaching a limit is a hard exit, not a warning: the gateway calls `cost_limit_error` and exits with code 6. Costs are computed from response tokens via `litellm.completion_cost` and written to the SQLite `cost_logs` table (non-fatal on error). See `openreview gateway costs` and `openreview gateway set --help`.

**No receipt by design:** these are configuration defaults, not measured benchmark results, so there is no reproducible artifact to pin. For actual spend, read the `cost_logs` table via `openreview gateway costs --today`.

See also: [README.md](README.md) (overview) · [ARCHITECTURE.md](ARCHITECTURE.md) (how the pieces fit).
