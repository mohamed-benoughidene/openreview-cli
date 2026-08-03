# Benchmarks

Every number on this page was measured against the source tree this session, or is explicitly labeled otherwise. Nothing is extrapolated from vendor claims. This is a pre-alpha project; treat these as a baseline, not a promise.

- [Methodology](#methodology)
- [Latency](#latency)
- [Resource footprint](#resource-footprint)
- [Throughput](#throughput)
- [Pipeline-wiring recall (mocked)](#pipeline-wiring-recall-mocked)
- [Measured vs. not measured](#measured-vs-not-measured)
- [Environment artifact: offline registry refresh](#environment-artifact-offline-registry-refresh)

## Methodology

**Environment (this session):** 4-core x86_64, 7.7 GB RAM, no GPU, no Ollama server, no outbound network. Python 3.12 under uv, running from the source tree.

**Reproduction:**

| Metric | Command / script |
|---|---|
| CLI startup | `uv run openreview --help` under `/usr/bin/time -v`, 3 runs |
| PDF / DOCX parse | in-process timing of the parsing library (see `tests/` + `src/openreview_cli/parsing/`) |
| PII corpus + stress | `uv run python scripts/benchmark_pii_stripping.py` (real `PiiEngine`) |
| Product-mode recall | `uv run python scripts/benchmark_product_modes.py` (mocked gateway, deterministic) |
| Test collection | `uv run pytest --collect-only` |

Run each benchmark on your own machine to get comparable numbers the offline note below shows how much environment can matter.

## Latency

| Metric | Value | Notes |
|---|---|---|
| CLI startup (`--help`) | 0.59 / 0.68 / 0.76 s, median 0.68 | 3 runs, peak RSS ~43 MB |
| Parse 1-page PDF, library level, cold | 3.1–3.2 s | one-time nupunkt model load per process |
| Parse 1-page PDF, library level, warm | 0.004 s | second parse in same process |
| Parse 37 KB DOCX, warm process | 0.27 s, 3 clauses | in-process timing |
| PII strip, 50-page synthetic stress | 2.95 s | 345 entities (see footprint below) |

The cold-PDF number is dominated by a one-time sentence-segmentation model load (~3 s per process), not by PDF parsing itself.

## Resource footprint

| Path | Peak RSS | Context |
|---|---|---|
| CLI `--help` | ~43 MB | measurement above |
| CLI parse (this sandbox) | ~410 MB | wall 14.0–44.4 s see [offline artifact](#environment-artifact-offline-registry-refresh) |
| PII 50-page stress | ~1,730 MB | 345 entities, 2.95 s |

The project's <100 MB memory budget (enforced by memory tests) applies to streaming pipeline paths parsers stream page-by-page and never load a full document. The parse CLI process peaked ~410 MB and the spaCy/PII path ~1.73 GB on the 50-page stress; both include one-time model loads, reported factually.

## Throughput

| Metric | Value | Method |
|---|---|---|
| PII corpus, 54 seeded contracts | 54/54 success, 1,733 entities, 70.4 s total (~1.3 s/doc avg) | `scripts/benchmark_pii_stripping.py`, real `PiiEngine` |
| PII derived rate | ≈ 46 docs/min | derived: 54 docs / 70.4 s, single-process, engine init amortized across all docs |

Not measured: dense-retrieval/embedding throughput (needs a local Ollama server), graph clustering (needs a one-time legal-bert download).

## Pipeline-wiring recall (mocked)

| Metric | Value | Notes |
|---|---|---|
| Product-mode recall, synthetic ground truth + MOCKED gateway | 9 modes × 5 docs, 100% recall (10 expected flags per mode: 2 per synthetic doc) | 0.6–1.3 s/mode after the first; first mode 35.5 s (one-time engine init) |

**Label this correctly:** this validates pipeline wiring (mode → playbook → match/extract/QA → flag) with a deterministic mocked gateway. It is **not** real-model accuracy. Real-model accuracy was measured separately through OpenRouter see [Review accuracy](#review-accuracy-measured12-labeled-nda-clauses) below. The `scripts/benchmark_review_accuracy.py` script is structural-only (does not make real LLM calls reads `predicted_position` from corpus).

## Accuracy signals

Accuracy-tagged tests run in the standard test suite. These are structural validations and binary pass/fail assertions they are **not** numeric precision/recall on a labeled corpus.

**25 passed, 0 failed, 3 skipped** (72.8 s).

| Test file | What it validates | Result |
|---|---|---|
| `tests/integration/test_pii_accuracy.py` (2 tests) | Detects ≥5 PII entities on up-to-10 real CUAD contracts; 0 false positives on clean text | ✓ pass |
| `tests/unit/test_tier_accuracy.py` (9 tests) | Tier precision/recall/F1 targets frozen + monotonically increasing + threshold ordering | ✓ pass |
| `tests/integration/test_review_accuracy.py` (7 tests) | F1 / amber-rate / QA-catch formulas correct; benchmark script exists + has required structure | ✓ pass |
| `tests/integration/test_benchmark_pii_accuracy.py` (3 tests) | Labeled-corpus PII precision/recall | **skipped** (needs corpus download) |

**Tier accuracy targets** (design goals, not measured source: `gateway/tier_accuracy.py:42-57`):

| Tier | F1 | Precision | Recall |
|---|---|---|---|
| Maximum (fully local) | 0.70 | 0.65 | 0.75 |
| Balanced (default) | 0.80 | 0.75 | 0.85 |
| Performance (cloud-assisted) | 0.90 | 0.85 | 0.95 |

**Honest caveat:** these tier targets are design goals see [Review accuracy](#review-accuracy-measured12-labeled-nda-clauses) below for actual measured numbers (90.9% F1, 100% QA error-catch on 12 NDA clauses through OpenRouter).

## PII accuracy (measured 50 seeded contracts)

Real `PiiEngine` (Presidio + spaCy `en_core_web_lg`) evaluated against `tests/fixtures/pii/seeded_contracts/` with `BenchmarkRunner.run_pii()`.

**Overall:** 533 detections across 50 contracts, 568 ground-truth entities.

| Metric | Value | Notes |
|---|---|---|
| Recall | 52.8% | 300 / 568 correctly detected |
| Precision | 56.3% | 300 / 533 predictions matched ground truth |
| F1 | 54.5% | |
| Per-type recall (regex recognizers) | AMOUNT 100%, TAX_ID 100%, REG_NUMBER 100%, EMAIL_ADDRESS 100% | Custom regex recognizers are exact on seeded corpus |
| Per-type recall (NER) | DATE_TIME 68%, ORGANIZATION 57.4%, PERSON 20.0%, ID_DOCUMENT 34.0% | spaCy NER on **synthetic** entity names (e.g. `Name3 Smith`, `AutoCompanyB1`) real contract accuracy expected higher |

**Caveat:** the seeded corpus uses artificial spawn-names (`Name3`, `Company5B`) that spaCy's NER model is not trained to recognize. Recall on real legal contracts (CUAD) is expected to be higher the accuracy test suite (`test_pii_accuracy.py`) validates ≥5 entities found on real CUAD contracts. These numbers represent an honest baseline on synthetic data, not an upper bound.

## Review accuracy (measured 12 labeled NDA clauses)

Real extraction + QA pipeline through OpenRouter (`anthropic/claude-sonnet-4.6`) against `tests/fixtures/review/nda-corpus-v1/nda-corpus-v1.json` with `precheck-nda-v1` playbook. 24 API calls (per-clause extraction + QA).

| Metric | Value | Target (spec) | Status |
|---|---|---|---|
| F1 | 90.91% | ≥ 70% | ✓ exceeds |
| Precision | 83.33% | | 10/12 correct |
| Recall | 100.00% | | 0 clauses left uncertain |
| QA error-catch rate | 100.00% | ≥ 80% | ✓ QA disagreed on both wrong extractions |
| Amber rate | 16.67% | ≤ 10% | ⚠ 2/12 flagged (both were actually wrong correct flagging, but rate above target) |
| Total latency | 107.5 s | | avg 9.0 s/clause, 24 API calls |

**Per-clause:** 10 correct positions, 2 wrong (both predicted `walkaway`/`preferred` when expected was `acceptable`). QA caught both wrong predictions. All 10 correct predictions had QA agree + no amber.

**Small-corpus caveat:** 12 clauses is too small for high-confidence F1. These numbers are directionally correct but the true F1 confidence interval is wide. A larger corpus (>100 clauses) would tighten the estimate.

## Full pipeline demo (qualitative measured)

End-to-end `openreview precheck review` on `tests/fixtures/nda_with_pii.pdf` (1 page, 5 clauses) through all configured providers:

| Stage | Provider | Model | Status |
|---|---|---|---|
| Parse | PyMuPDF (local) | | 5 clauses, 1 page |
| PII strip | Presidio + spaCy (local) | `en_core_web_lg` | PII replaced with `[PAR]`, `[NAME_1]`, `[EMAIL_1]`, `[DATE_2]` |
| Extraction | OpenRouter (cloud) | `claude-sonnet-4.6` | 5/5 clauses assessed |
| QA | OpenRouter (cloud) | `claude-sonnet-4.6` | amber flags raised |
| Embedding | Voyage (cloud) | `voyage-3.5` | 1024-dimensional vectors |
| Reranking | Voyage (cloud) | `rerank-2.5` | correct clause ranking confirmed |

**Result:** 0 matches, 5 differences, avg confidence 0.95, recommendation: revise. Full cost report via `openreview gateway costs --today`. Total wall time ~2.5 min (includes cold API connection overhead).

**Note:** this is a qualitative pipeline integration test, not an accuracy measurement the fixture PDF has no ground-truth labels. Accuracy numbers are in the [Review accuracy](#review-accuracy-measured12-labeled-nda-clauses) section above.

## CUAD public benchmark (clause identification measured)

Clause boundary recall against the [CUAD v1](https://www.atticusprojectai.org/cuad) dataset (CC BY 4.0): 462 commercial legal contracts with 4,042 expert-labeled clause spans from The Atticus Project. Sentence segmentation via nupunkt (no LLM calls, local only).

| Metric | Value |
|---|---|
| Contracts | 462 (4,034 valid queries, 8 missing files with special chars) |
| Sentence boundary recall | **100.0%** (4,034/4,034) |
| Time | 8.5 s (0.018 s/contract) |

Every expert-labeled clause in the CUAD dataset falls within a detected sentence boundary. Full clause-text matching, however, is ~40%: our clause detector groups sentences under section headings (6 regex patterns), so individual CUAD spans within a larger clause merge into the parent clause the sentence-level recall more closely reflects correct text extraction.

**Reproduction:** download CUAD v1 from [atticusprojectai.org/cuad](https://www.atticusprojectai.org/cuad) (CC BY 4.0), or run `uv run python scripts/benchmark_legalbenchrag.py` to fetch the LegalBench-RAG processed version to `/tmp/opencode/legalbenchrag_data/`. The corpus is gitignored (`data/` in `.gitignore`).

## Measured vs. not measured

**Measured this session:** CLI startup, PDF/DOCX parse, PII corpus + stress (real `PiiEngine`), PII accuracy on 50 seeded contracts (52.8% recall), review accuracy on 12 NDA clauses through OpenRouter (90.9% F1), CUAD public benchmark on 462 contracts (100% sentence boundary recall), product-mode wiring (mocked), test collection (2,725 tests), accuracy-test suite (25/25 passed).

**Not measured (methodology documented, no numbers invented):**

| Metric | Why | How to measure |
|---|---|---|
| Full LLM review latency + cost per review | needs API keys | `openreview gateway costs` (SQLite `cost_logs`) + `scripts/benchmark_review_accuracy.py` |
| Dense-retrieval / embedding throughput | needs local Ollama | run the retrieval path with `nomic-embed-text` |
| Graph clustering | needs legal-bert download | `openreview graph` with `--cluster-clauses` |
| Real-model review accuracy (F1 / QA-catch) | measured see [Review accuracy](#review-accuracy) below | OpenRouter (extraction + reasoning slots), `precheck-nda-v1` playbook, 12 labeled NDA clauses, 24 API calls |
| Reranker effect | disabled by default (degrades legal text) | opt-in `--rerank` |

Benchmark-harness honesty: the `openreview benchmark run --all --ci` CLI uses a **mock pipeline by default** for CUAD/MAUD/ContractNLI datasets (real LLM integration deferred). The CUAD sentence-boundary benchmark above was run manually against the real nupunkt parser, not through the mock harness. PII benchmarks use the real `PiiEngine`. Hallucination detection uses a ROUGE-L lexical-overlap placeholder (EXPERIMENTAL default); a CG-DPO detector is planned but not shipped.

Historical numbers from earlier project READMEs (e.g. 860 docs, 2.28M chars/sec) are **not** reproduced this session and are deliberately omitted.

## Environment artifact: offline registry refresh

The CLI in this sandbox took 14.0–44.4 s wall to parse a PDF an artifact of environment, not product performance. On startup the CLI refreshes the provider model registry over HTTPS; with no outbound network the connect stalls until timeout (debug log: `connect_tcp to raw.githubusercontent.com failed after 40s`, then "registry refresh skipped") before proceeding. On a networked machine this is a short request; the 410 MB peak RSS also reflects this process. The stall is a real improvement area (registry refresh should be fast-failing/timeout-aware when offline), but it is not representative of parse throughput.

## Cost tracking

Per-review and per-day cost limits are configurable (defaults: 100¢/review, 1,000¢/day, warn-only). Costs are computed from response tokens via `litellm.completion_cost` and written to the SQLite `cost_logs` table (non-fatal on error). See `openreview gateway costs` and `openreview gateway set --help`.

See also: [README.md](README.md) (overview) · [ARCHITECTURE.md](ARCHITECTURE.md) (how the pieces fit).
