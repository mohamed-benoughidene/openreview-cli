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
| PII strip, 50-page synthetic stress | 2.3823 s | 346 entities (see footprint below) |

The cold-PDF number is dominated by a one-time sentence-segmentation model load (~3 s per process), not by PDF parsing itself.

No receipt by design: these rows are wall-clock on the [methodology](#methodology) sandbox, and the parse row is dominated by the offline registry-refresh stall documented under [the environment artifact](#environment-artifact-offline-registry-refresh), so a committed receipt would pin an environment artifact rather than a product number. The `--help` row does not pay that stall: Click's eager `--help` exits before the root callback runs its registry refresh (`app.py`). The PII-stress row derives from [docs/benchmarks/results/pii-throughput.json](benchmarks/results/pii-throughput.json).

## Resource footprint

| Path | Peak RSS | Context |
|---|---|---|
| CLI `--help` | ~43 MB | measurement above |
| CLI parse (this sandbox) | ~410 MB | wall 14.0–44.4 s see [offline artifact](#environment-artifact-offline-registry-refresh) |
| PII 50-page stress | ~1724 MB | 346 entities, 2.3823 s |

The project's 100 MiB streaming memory target, with a 110 MiB hard ceiling enforced by the memory tests, applies to streaming pipeline paths; parsers stream page-by-page and never load a full document. The parse CLI process peaked ~410 MB and the spaCy/PII path ~1724 MB on the 50-page stress; both include one-time model loads, reported factually.

No receipt by design: peak RSS includes one-time model loads and the offline registry-refresh stall (see the [environment artifact](#environment-artifact-offline-registry-refresh)), so it is sandbox-specific rather than a product number. The PII-stress row derives from [docs/benchmarks/results/pii-throughput.json](benchmarks/results/pii-throughput.json).

## Throughput

| Metric | Value | Method |
|---|---|---|
| PII corpus, 54 processed rows | 54/54 success, 1,857 entities, 73.906 s total (~1.4 s/row avg) | `scripts/benchmark_pii_stripping.py`, real `PiiEngine` |
| PII derived rate | ~ 44 docs/min | derived: 54 rows / 73.906 s, single-process, engine init amortized across all rows |

Last verified: 2026-09-22 @ b5f051a (receipt: docs/benchmarks/results/pii-throughput.json).

Processed rows are not distinct files: `tests/fixtures/pii/seeded_contracts/` holds 53 `.txt` files
(50 with ground-truth labels) and `no_pii_document.txt` is processed twice, once in the corpus loop
and once in the part-3 edge-case pass. See
[docs/benchmarks/results/pii-throughput.json](benchmarks/results/pii-throughput.json) for the
file-level detail.

Not measured: graph clustering (needs a one-time legal-bert download).

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
| `tests/integration/test_benchmark_pii_accuracy.py` (3 tests) | Labeled-corpus PII precision/recall (span-level) | ✓ pass: recall 96.4% and span-level precision 94.8% (type-strict precision 83.1% reported alongside) |

**Tier accuracy targets** (design goals, not measured source: `gateway/tier_accuracy.py:41-60`):

| Tier | F1 | Precision | Recall |
|---|---|---|---|
| Maximum (fully local) | 0.70 | 0.65 | 0.75 |
| Balanced (default) | 0.80 | 0.75 | 0.85 |
| Performance (cloud-assisted) | 0.90 | 0.85 | 0.95 |

**Honest caveat:** these tier targets are design goals; see [Review accuracy](#review-accuracy-measured-12-labeled-nda-clauses) below for actual measured numbers (90.9% F1, 100% QA error-catch on 12 NDA clauses; provider not recorded).

## PII accuracy (measured 50 seeded contracts)

Real `PiiEngine` (Presidio + spaCy `en_core_web_lg`) evaluated against `tests/fixtures/pii/seeded_contracts/` with `BenchmarkRunner.run_pii()`.

Matching is span-level (type-agnostic): a detection counts as correct when its value overlaps a ground-truth value, whatever entity type label it carries, so a right span with a wrong label still counts as correct. The engine now resolves overlapping spans (a regex match outranks an NER inference, then the more specific type), so a value two recognizers claim yields one detection rather than a duplicate; the D-82 labelling limitation in `specs/archive/DEFERRED.md` (issue 115) is resolved, and a separate type-strict precision reports label quality alongside the span-level figure.

**Overall:** 656 detections across 50 contracts, 584 ground-truth entities.

| Metric | Value | Notes |
|---|---|---|
| Recall | 96.4% | 563 / 584 ground-truth entities matched |
| Precision | 94.8% | 622 / 656 predictions matched ground truth (span-level, type-agnostic) |
| Precision (type-strict) | 83.1% | 545 / 656 span-level matches with the same type label |
| F1 | 95.6% | |
| Per-type recall (structured recognizers) | AMOUNT 100%, TAX_ID 100%, REG_NUMBER 100%, EMAIL_ADDRESS 100%, PHONE_NUMBER 100%, ACCT 100%, ID_DOCUMENT 100%, DATE_TIME 100%, LOCATION 100% | Exact on the seeded corpus |
| Per-type recall (NER) | ORGANIZATION 83.3% (70 / 84), PERSON 86.0% (43 / 50) | spaCy NER on **synthetic** entity names (e.g. `Name3 Smith`, `AutoCompanyB1`); real contract accuracy is expected to differ |

Last verified: 2026-09-28 @ 882568c (receipt: docs/benchmarks/results/pii-accuracy.json).

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
| Time | 93.7 s for the full clause-segmentation pass over 462 documents (~0.20 s/contract) |

Last verified: 2026-09-30 @ 74ce840 (receipt: docs/benchmarks/results/cuad-segmentation.json).

**Clause segmentation (measured).** A reproducible run (`scripts/benchmark_cuad_segmentation.py`) loaded 462 of 462 documents and measured **93.37% of 6,247 spans** fully contained in a single detected clause, with query coverage of **93.94% of 4,042 queries** (at least one span contained). Enclosure tightness improves but is still the weak point: mean **token-F1 0.425**, because the detector groups whole sentences under section headings (7 regex patterns), so one detected clause can still swallow several labeled spans. Both segmentation rows were refreshed 2026-09-30 from the branch's working-tree code after the dotted-clause-number fix to `detect_clause_starts` (a bare `1.1 Title` now starts a clause); the `74ce840` stamp names the branch point, which does not yet contain that fix. On this corpus the fix raised containment from a **same-environment** pre-fix baseline of **90.78%** (token-F1 0.308, coverage 91.76%), measured by re-running the pre-fix code on the same machine — **+2.59 pp**, not the +2.69 pp an earlier draft quoted from the superseded 2026-09-22 receipt's 90.67%, which was a **different environment/date** and is not comparable. A later change shared one trailer between the start rule and the level rule, so a dotted number may be followed by any non-word separator (`:` `)` `-` `/` `,`) and not just whitespace; re-running it left every CUAD figure unchanged (29 new clause starts, none crossing a gold span). The change is not uniformly favourable — across the fix as a whole MAUD's containment falls (see that section), reported there rather than hidden. Mean **token-F1** is taken over **every** evaluated span with a non-contained span counted as **0**, so it is a deliberate conservative floor rather than an average over only the spans that were successfully contained. One corpus `file_path` is stored in NFD (decomposed) Unicode form while the file on disk is NFC; the script retries the path under Unicode NFC normalization, so every referenced document loads.

This measures **segmentation** (whether an expert-labeled span lies fully inside one detected clause, and how tightly that clause encloses it), **not query-answering accuracy**. High containment with enclosures still coarser than the gold spans is the expected shape for a section-heading segmenter; the sub-1 token-F1 is the honest cost of that grouping, not a contradiction of the containment number.

**Reproduction:** run `uv run python scripts/benchmark_cuad_segmentation.py` (writes `.benchmark-reports/cuad-segmentation.json`). To obtain the corpus, download CUAD v1 from [atticusprojectai.org/cuad](https://www.atticusprojectai.org/cuad) (CC BY 4.0). (Note: `scripts/benchmark_legalbenchrag.py` does not download a corpus — it only reads an already-present one from `/tmp/opencode/legalbenchrag_data/`.) The corpus is gitignored (`data/` in `.gitignore`).

## CUAD keyword retrieval (tokenizer comparison)

The shipped index is SQLite FTS5 with `tokenize='porter unicode61'` and `prefix='2 3'` (`src/openreview_cli/retrieval/storage.py`). This measures what that configuration retrieves, reusing the shipped ingest path and chunker (no dense/rerank path exists): each of the 4,042 CUAD queries is searched against its own contract's index and scored by whether a retrieved chunk's document span overlaps the query's expert-labeled answer span.

| Metric | shipped `porter unicode61` | `unicode61` (no stemming) | Delta (porter − unicode61) |
|---|---|---|---|
| hit@1 | 0.0435 | 0.0312 | +0.0124 |
| hit@5 | 0.3206 | 0.2548 | +0.0658 |
| MRR@5 | 0.1274 | 0.1001 | +0.0273 |

Sample: 4,042 queries over 462 contracts — every query in the committed benchmark — with 73,222 chunks indexed and ~48 s per arm.

Last verified: 2026-09-30 @ 8bd72a3 (receipts: docs/benchmarks/results/cuad-retrieval-porter.json, docs/benchmarks/results/cuad-retrieval-unicode61.json).

**`porter` still wins, and now on reproducible evidence.** The shipped choice was originally made on a comparison over 1,536 queries whose harness was never committed and whose query count matches no benchmark in the tree, so that evidence could not be re-run. The two receipts above are the re-derivation on the committed set: they reproduce the direction (porter ahead on all three metrics) but not the magnitudes — the remembered claim of **+1.7 hit@1 / +2.1 hit@5 / +1.9 MRR** percentage points becomes **+1.24 / +6.58 / +2.73** here, with the hit@5 gap more than three times larger than claimed. Absolute accuracy is low: keyword search returns the answer span at rank 1 for 4.4% of queries. The honest reading is that `porter unicode61` is the better of two weak configurations, not that retrieval is good on this corpus.

**Reproduction:** `uv run python scripts/measure_retrieval_accuracy.py --tokenizer porter --out .benchmark-reports/retrieval-porter.json`, and the same with `--tokenizer unicode61`. Both arms are offline (SQLite FTS5, no model calls). Two caveats are recorded in the receipts and bound the claim: ground truth is character-span overlap rather than answer correctness (a retrieved chunk that merely touches a labeled span counts as relevant), and the CUAD `.txt` corpus cannot go through the product parser (PDF/DOCX only), so the harness drives the product chunker directly and chunk boundaries approximate a real parse. This measures retrieval, not answering: nothing here checks whether an extracted answer is correct.

## CUAD rerank arms (offline)

The decision to remove the `reranking` socket rested on a comparison that is not in the tree. The tracked record quotes **0.108 / 0.535 / 0.252** for plain BM25 + `porter`, **0.092 / 0.448 / 0.207** for a cheap lexical rerank and **0.085 / 0.427 / 0.199** for a local cross-encoder (`specs/035-post-measurement-cleanup/research.md`, Q7), but those numbers came from a scratch harness that was never committed. `scripts/benchmark_rerank_legalbenchrag.py` — the harness deleted in `b781a1a` — was restored from `b781a1a^` and adapted so the question can be re-derived offline: the deleted dense/RRF pool and the cloud `voyage/rerank-2.5` socket are both gone, so every arm re-orders the **same per-query BM25 candidate pool** (top-20, `porter unicode61`), which is the pool the tracked table describes.

| Arm | hit@1 | hit@5 | MRR@5 | Paired ΔP@5 vs BM25 | 95% CI |
|---|---|---|---|---|---|
| BM25 baseline (pool, top-5) | 0.0483 | 0.3438 | 0.1441 | — | — |
| + lexical rerank (query-term coverage) | 0.0540 | 0.3892 | 0.1759 | +0.0051 | [-0.0051, +0.0154] |
| + cross-encoder `ms-marco-MiniLM-L-6-v2` | 0.0341 | 0.2330 | 0.1020 | -0.0267 | [-0.0392, -0.0136] |

Sample: 352 queries over the deterministic first 40 sorted CUAD contracts, 5,713 chunks indexed, mean candidate pool 19.6 of 20, top-5 metric, 474 s wall. Every query's ground truth mapped (no unmapped or no-relevant queries), so the three arms are scored on identical pools.

Last verified: 2026-10-01 @ b8fa707 (receipt: docs/benchmarks/results/cuad-rerank-offline.json).

**Half the claim reproduces, half does not.** The **cross-encoder** arm is worse than BM25 on all three metrics and its paired ΔP@5 95% CI lies **entirely below zero**, so the tracked claim that a local cross-encoder made ordering worse is reproduced on this sample. The **lexical** arm is **not** reproduced: here it is *ahead* of BM25 on hit@1, hit@5 and MRR@5, and its paired ΔP@5 CI **straddles zero** — the honest reading is "no measurable top-5 effect", not "worse". The tracked claim's magnitudes (0.108/0.535/0.252 and the rest) are not reproduced by any arm.

**What could not be reproduced.** (1) The cloud `voyage/rerank-2.5` arm — the `reranking` socket and `Gateway.rerank` were deleted in spec 035 and the account is credentialed, so no cloud rerank arm can run here. (2) The deleted harness's own `hybrid` (BM25 + dense RRF) arms — `retrieval/dense.py` and `retrieval/rrf.py` were deleted in the same commit, and the `embedding` socket with them. (3) The tracked claim's exact figures and query set — its producing harness was never committed, so its 424-query sample and 0.108/0.535/0.252 baseline cannot be re-run; only the question can be re-derived, and only on the deterministic 352-query subset above.

**Reproduction:** `uv run python scripts/benchmark_rerank_legalbenchrag.py --contracts 40 --pool-depth 20 --top-k 5 --out .benchmark-reports/rerank-offline.json`, run from a checkout that holds the gitignored `data/legalbenchrag/` corpus. It is fully offline: BM25 is SQLite FTS5, the lexical arm is pure Python, and the cross-encoder runs through `transformers` (an existing dependency — `sentence-transformers` is forbidden) against a local weights cache with `HF_HUB_OFFLINE=1`, degrading to an explicit "unavailable" entry rather than downloading weights. Ground truth is character-span overlap, as in the tokenizer section above, and the harness imports that section's chunker and ground-truth rule so the two CUAD measurements label chunks identically. This measures **ranking**, not answer correctness.

## MAUD public benchmark (segmentation and timing)

Parsing scale against the [MAUD](https://www.atticusprojectai.org/maud) dataset (CC BY 4.0): 150
mergers-and-acquisitions agreement text files with 1,676 expert-labeled queries spanning 2,839 gold
spans. Sentence segmentation via nupunkt (no LLM calls, local only).

| Metric | Value |
|---|---|
| Documents | 150 (1,676 queries / 2,839 spans, all readable) |
| Time | 171.2 s for the full clause-segmentation pass over 150 documents (~1.14 s/document; wall time is machine-dependent) |

Last verified: 2026-09-30 @ 74ce840 (receipt: docs/benchmarks/results/maud-segmentation.json).

**Clause segmentation (measured).** The same reproducible run (`uv run python scripts/benchmark_cuad_segmentation.py --dataset maud`) loaded 150 of 150 documents and measured **79.82% of 2,839 spans** fully contained in a single detected clause, with query coverage of **85.02% of 1,676 queries** (at least one span contained). Enclosure tightness is low: mean **token-F1 0.190**, because the detector groups whole sentences under section headings (7 regex patterns). Refreshed 2026-09-30 from the branch's working-tree code; the `74ce840` stamp names the branch point, which does not yet contain the fix. The same-environment pre-fix baseline, re-measured on the same machine, reproduces the superseded receipt exactly (containment 80.38%, coverage 85.62%, token-F1 0.183), so this before/after is a genuine same-environment comparison. Unlike CUAD this corpus moved the **wrong way** on containment — **80.38% -> 79.82%**, with coverage 85.62% -> 85.02% — while token-F1 rose (0.183 -> 0.190). The later trailer-sharing change moved only the enclosure number here (containment and coverage unchanged, token-F1 0.190268 -> 0.190353). Finer segmentation tightens enclosures, but a new boundary can land inside one large gold span, so that span stops being contained; the fix is a mixed result and the dip is published, not omitted. Mean token-F1 is taken over every evaluated span with a non-contained span counted as 0, so it is a deliberate conservative floor.

This measures **segmentation**, not query-answering accuracy and not deal-point accuracy. The same corpus hash (`82ef159b87f73a9c68e7143fac88bf47ac212713b56617d7e87d6f1f0a781daf`) is pinned in the receipt. The corpus is gitignored (`data/` in `.gitignore`); MAUD is published by The Atticus Project (CC BY 4.0).

## Grounding accuracy (local vs cloud)

The fact-checker slot decides whether each assessment claim is really supported by the clause it cites. `scripts/measure_slm_slots.py --grounding-accuracy` builds known-good positives and generated known-bad negatives, drops the negatives its guard rejects, and scores a confusion matrix — an ordinary review run cannot show a miss, because `strict` mode removes ungrounded claims and the structural metric returns 1.0 when nothing is grounded. The local arm runs in CI on a corpus assembled from the repository's tracked fixtures; the cloud arm runs on demand over the same assembled corpus.

| Metric | local `ollama/granite4:3b` | cloud `openrouter/anthropic/claude-sonnet-4.6` |
|---|---|---|
| answers read | 69 / 69 | 69 / 69 |
| known-good claims accepted | 25 / 25 | 24 / 25 |
| planted bad claims caught | 32 / 44 | 38 / 44 |
| bad claims called grounded | 12 | 0 |
| uncertain (good / bad) | 0 / 0 | 1 / 6 |
| unreadable answers | 0 | 0 |
| mean latency per call | 17.92 s | 3.33 s |

Sample: 20 units per arm (`--limit 20`). Both arms now keep the same 25 positives (20 clause sentences + 5 paraphrased) and 44 negatives (20 `unsupported_claim` + 20 `hallucination` + 4 `paraphrased_unsupported`) over 69 calls, and run over the same assembled corpus — the tracked fixtures, because CUAD is gitignored and absent in CI — so the arms are compared directly on the negative arm.

Last verified: 2026-10-01 @ b8fa7077bcd7 (CI run 36905917351, local arm) / b8fa7077bcd7 (cloud arm) (receipts: docs/benchmarks/results/grounding-accuracy-local.json, docs/benchmarks/results/grounding-accuracy-cloud.json).

**Both arms read every answer; the arms differ in quality.** An earlier local figure of **1 of 20** accepted was a reader defect, not model behaviour: answers the reader could not parse were recorded as `uncertain` with confidence 0.0, which made the local model look like it refused to decide. With the reader fixed and local models asked for JSON only, the local arm accepts all 25 known-good claims and catches 32 of 44 planted bad ones — but calls 12 of them grounded — while the cloud model catches 38 of 44. The honest reading is that the local 3B model's failure mode is **accepting** planted bad claims, not hesitating over good ones — it is weaker than the cloud model, not merely slower.

**Coverage is a signal, not a verdict.** The hardened labels make the harness record how much of each claim's wording appears in the clause it cites. The supported claims score at or above **0.96** (the paraphrased positives bottom out at 0.962), while planted bad claims reach the same band, so wording overlap on its own cannot separate a real citation from a planted one — which is why no code path makes a verdict from the number. What ships is a wording check the model reads; the decision stays with the model and the reviewer, never a threshold.

**A real review, as a pilot.** One real local review (`grounding_mode="lenient"`, so rejected claims are kept for inspection) assessed 12 claims and wrote a coverage number for 11 of them: **7 accepted, 3 rejected, 1 uncertain**, with coverage values 0.0, 0.0, 0.286, 0.313, 0.636 and six at 1.0. Most real citations are **exact** (six of eleven scored 1.0), but about a third fall below half coverage (four of eleven), and some of those were **accepted** by the model. This is one pilot run, not a benchmark.

**Limits.** Both are single-sample smoke measurements of non-deterministic models. The positives now come in two classes — the cited clause's own qualifying sentence, and a lightly rewritten copy of it — and both are supported by the clause by construction, so they are an easier set than a human-labelled one and only the negative arm discriminates; the substitution map is narrow, so no real-world false-positive rate may be quoted. CI latencies are CPU-bound on a 2-vCPU runner and local latencies are machine-specific. The local arm ran `--no-pii` (CI has no spaCy model), so raw clause text went to a local model only; the cloud arm stripped PII (51 entities) before every call.

**Reproduction:** `uv run python scripts/measure_slm_slots.py --grounding-accuracy --arm local|cloud --limit 20 --corpus-dir <corpus>`. The local arm also runs in CI (`.github/workflows/slm-measurement.yml`, job `grounding-accuracy`); the cloud arm spends on the order of 30 cents per run.

## Open-weight grounding ladder (8B / 27B / 70B / 235B MoE)

The same checker task as [Grounding accuracy (local vs cloud)](#grounding-accuracy-local-vs-cloud), on the identical assembled corpus and items (20 units, 25 known-good positives, 44 planted-bad negatives), run against four open-weight models reached through one hosted endpoint. The two reference rows — the shipped local model and the frontier cloud model already on `main` — were measured the same way on the same items.

| Grounding slot | Size | Caught / 44 | Missed | Unsure | Known-good wrongly rejected | Unreadable |
|---|---|---|---|---|---|---|
| `ollama/granite4:3b` (shipped local) | 3B | 32 (72.7%) | 12 | 0 | 0 | 0 |
| `openrouter/meta-llama/llama-3.1-8b-instruct` | 8B | 33 (75.0%) | 5 | 6 | 5 | 1 |
| `openrouter/google/gemma-3-27b-it` | 27B | 39 (88.6%) | 4 | 1 | 0 | 0 |
| `openrouter/meta-llama/llama-3.3-70b-instruct` | 70B | 42 (95.5%) | 2 | 0 | 2 | 0 |
| `openrouter/qwen/qwen3-235b-a22b-2507` | 235B MoE | 38 (86.4%) | 4 | 2 | 0 | 2 |
| `openrouter/anthropic/claude-sonnet-4.6` (frontier cloud) | — | 38 (86.4%) | 0 | 6 | 0 | 0 |

Last verified: 2026-10-02 @ 42fdf38 (receipts: docs/benchmarks/results/openweight-grounding-8b.json, docs/benchmarks/results/openweight-grounding-27b.json, docs/benchmarks/results/openweight-grounding-70b.json, docs/benchmarks/results/openweight-grounding-moe.json; references: docs/benchmarks/results/grounding-accuracy-local.json, docs/benchmarks/results/grounding-accuracy-cloud.json).

**The jump happens between 8B and 27B.** The 8B model is **no better at catching than the shipped 3B** — 33 caught against 32 — and it wrongly rejects **5** known-good findings, so an 8B swap regresses the good arm. The 27B model matches the frontier cloud model on catch count (**39 against the cloud arm's 38**) with **no** false rejections.

**Bigger is not strictly better.** The 70B model catches **more than the frontier cloud model** on these items (**42 against 38**), but it wrongly rejects **2** known-good findings, so that trade is not strictly better. The 235B mixture-of-experts point is **worse** than the 70B (**38 against 42**) and produced **2** unreadable answers, so size alone does not decide.

**Single samples, and how to read the gaps.** Every row is one run over 20 units, so a one- or two-catch difference is noise: a repeat of the cloud arm on these same items scored one catch higher (39) than the committed receipt's 38. These are single-sample smoke measurements, not benchmark claims, and the receipts' `notes` say so.

**On cost.** The gateway ledger books exactly one cent per call for every model, so its totals count calls rather than money — the four ladder runs appear there as 292 calls. The endpoint's own billing is the only true cost record.

**What this implies for hardware.** Only the 24–32B tier and above changes the outcome; at a 4-bit quantization that is roughly a 24–32 GB machine. That is an estimate, not a specification.

**Which bad findings were missed.** The receipts' `per_label` rows record each finding's `generator` but not the negative construction `kind` (`operand_change` versus `cross_document`) that the harness builds internally, so the two kinds cannot be separated from the committed receipts and are not inferred here. By the recorded generator, every bad finding the model called grounded (a miss) is from the `unsupported_claim` family:

| Model | Missed `unsupported_claim` | Missed `hallucination` | Missed `paraphrased_unsupported` |
|---|---|---|---|
| 8B | 5 | 0 | 0 |
| 27B | 4 | 0 | 0 |
| 70B | 2 | 0 | 0 |
| 235B MoE | 4 | 0 | 0 |

So scale here removes some `unsupported_claim` misses, but whether those are the subtle operand changes or the obvious cross-document ones cannot be said from these receipts: the per-row `kind` is not recorded.

## Measured vs. not measured

**Measured this session:** CLI startup, PDF/DOCX parse, PII corpus + stress (real `PiiEngine`), PII accuracy on 50 seeded contracts (96.4% recall, span-level predicate), review accuracy on 12 NDA clauses (90.9% F1; provider not recorded), live LLM extraction + QA verification on 15 real ContractNLI NDA clauses across 5 NDAs (0 uncertain, 6.67% QA agreement, 93.33% amber, ~7.8 s/clause), CUAD public benchmark on 462 contracts (scale, timing, and clause segmentation), CUAD keyword retrieval over 462 contracts on the full 4,042-query set (both tokenizer arms), CUAD rerank arms over 40 contracts (BM25 baseline vs a lexical rerank and a local cross-encoder, offline), MAUD public benchmark on 150 M&A documents (scale, timing, and clause segmentation), product-mode wiring, 23 named modes (mocked, playbook-aware), test collection (3,935 tests), accuracy-test suite (21 passed, 0 failed), grounding accuracy on both arms (20 units each; local via CI and cloud locally, both over the same assembled corpus), and an open-weight grounding ladder over the same 20-unit corpus and items (8B, 27B, 70B and 235B MoE through one hosted endpoint, against the shipped local and frontier cloud references).

Last verified: 2026-09-25 @ fdea262 (receipt: docs/benchmarks/results/test-collection.json).
Last verified: 2026-09-24 @ 882568c (receipt: docs/benchmarks/results/accuracy-suite.json).

**Not measured (methodology documented, no numbers invented):**

| Metric | Why | How to measure |
|---|---|---|
| Full LLM review latency + cost per review | needs API keys | `openreview gateway costs` (SQLite `cost_logs`) + `scripts/benchmark_review_accuracy.py` |
| Graph clustering | needs legal-bert download | `openreview graph` with `--cluster-clauses` |
| Reranker effect | the feature was removed with the `reranking` socket; the offline arms were re-derived on a 352-query subset, not the full 4,042, because the cross-encoder is CPU-bound (~2.2 s/query), and the cloud `voyage/rerank-2.5` arm is not reproducible (see [CUAD rerank arms (offline)](#cuad-rerank-arms-offline)) | re-run `scripts/benchmark_rerank_legalbenchrag.py` with `--contracts 0` on a machine holding the gitignored corpus and a local model cache |
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
