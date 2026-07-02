# Benchmark Harness — Automated Evaluation Against Research Baselines

**Feature ID**: 010-benchmark-harness
**Status**: Draft Specification
**Created**: 2026-07-02

## 1. Executive Summary

The benchmark harness provides automated, reproducible evaluation of the openreview CLI against three established research baselines: CUAD (Contract Understanding Atticus Dataset), MAUD (Merger and Acquisition Understanding Dataset), and ContractNLI (Contract Natural Language Inference). It measures per-mode accuracy across extraction, comparison, hallucination, and PII recall metrics, enabling regression testing, model selection, and prompt optimization.

This feature is the primary mechanism for answering open questions about accuracy thresholds, hardware feasibility, model selection, and gateway value — all flagged in the product blueprint [§10 Q-1, Q-3, Q-4, Q-7, Q-9].

## Clarifications

### Session 2026-07-02

- Q: Which dataset(s) should be integrated first? → A: CUAD first (Option A)
- Q: Should hardware budget verification be a PASS/FAIL gate in CI, or only a report-with-alert? → A: PASS/FAIL gate with NLP model exemption (Option A)
- Q: How should the benchmark suite be triggered? → A: New CLI subcommand `openreview benchmark` (Option A)

## 2. User Scenarios

### Scenario 1: Run Full Benchmark Suite
A developer preparing a release runs the full benchmark suite against all configured model slots. The harness downloads or loads standardised test corpora (CUAD, MAUD, ContractNLI), runs each document through the configured pipeline (parse → chunk → route → extract/compare/classify), compares results against ground-truth labels, and produces a structured report of accuracy metrics per mode per model slot.

### Scenario 2: Single-Dataset Validation
A developer debugging comparison accuracy in the DealCheck mode runs only the MAUD subset. The harness executes the 39 MAUD tasks (each a binary classification over contract spans), collects per-task true/false positives/negatives, and reports comparison F1 with confidence intervals [§6.4].

### Scenario 3: Prompt A/B Test
A developer iterating on a prompt template runs two prompt variants through the ContractNLI dataset. The harness executes both variants against the same model slot, compares per-class entailment/contradiction/neutral accuracy, and flags statistically significant differences [§6.5].

### Scenario 4: PII Recall Regression
A developer making changes to the PII stripping engine runs the PII recall benchmark (seeded documents with known PII spans) as part of the pre-commit gate. The harness reports recall, precision, and F1 per entity type, and compares against the previous run's scores [deferred T049, T050].

### Scenario 5: Regression Gate
CI runs the benchmark suite on every push to main. If any metric drops below the established floor (e.g., extraction F1 < 0.80), the pipeline fails and reports the regression to the developer before merge.

## 3. Functional Requirements

### FR-1: Dataset Integration

The harness MUST support evaluation against three research baseline datasets:

| Dataset | Domain | Task Type | Metric Primary | Blueprint Ref |
|---------|--------|-----------|----------------|---------------|
| CUAD | General contracts | Extractive QA (41 classes) | Extraction F1 | [P-7] |
| MAUD | M&A contracts | Binary classification (92 questions grouped into 39 deal-point categories; both granularities measured) | Comparison F1 | [P-7] |
| ContractNLI | NDAs | Natural language inference (3 classes) | Classification F1 | [P-7] |

Each dataset MUST include:
- A machine-readable corpus of labelled documents (or document-span pairs) [§11 seed]
- Ground-truth annotations per task type
- A well-defined evaluation protocol (splits, metrics, scoring)

**Decision**: CUAD integrated first (Option A). CUAD provides the broadest coverage of extraction accuracy (41 classes, ~500 contracts) and is the most cited contract QA benchmark, giving the fastest path to answering extraction accuracy questions [§10 Q-1]. MAUD and ContractNLI follow in subsequent iterations.

Blueprint references: [P-7], [§10 Q-1], [§11 seed]

### FR-2: Per-Mode Accuracy Measurement

The harness SHALL report accuracy metrics for each product mode [§11 seed, §6.1]:

| Metric | Modes Applicable | Definition | Blueprint Ref |
|--------|-----------------|------------|---------------|
| Extraction F1 | PreCheck, DealCheck | Token-level precision/recall of extracted spans vs ground truth | [§6.4] |
| Comparison F1 | DealCheck, HireCheck | Binary-class accuracy (match/no-match) of clause comparisons | [§6.4] |
| Classification F1 | PreCheck | 3-class entailment accuracy (entailment/contradiction/neutral) | [§6.4] |
| Hallucination Rate | All modes | Proportion of generated claims not supported by input text. **Current implementation: EXPERIMENTAL ROUGE-L lexical overlap placeholder** (see AGENTS.md §Hallucination Detection — Transition Plan). Upgraded to CG-DPO when that capability reaches TRL 7+. | [§6.3, R-2] |
| PII Recall | All modes | Proportion of seeded PII spans detected by the stripping engine | [§11 seed, R-4] |
| End-to-End Latency | All modes | Wall-clock time from document input to structured output | [§6.6] |
| Peak Memory | All modes | Maximum memory usage during evaluation (per corpus item) | [§6.6] |

### FR-3: Model Slot Routing

The harness MUST route evaluation across any configured model slot in the gateway [C-12, C-13]:
- All-local slots (Ollama, SLMs)
- Cloud provider slots (with PII stripping active, per Principle I)
- Multiple slots in a single run for comparison

This enables SLM-vs-cloud accuracy comparison [§6.1], model selection [§10 Q-7], and gateway value measurement [§10 Q-9].

### FR-4: Automated Regression Testing

The harness MUST integrate with CI so that accuracy regressions are caught before merge [§11 seed]. Specifically:
- A regression suite runs on every CI push (or nightly for large corpora)
- Results are compared against a stored baseline (previous commit or pinned release)
- A metric drop exceeding a configurable threshold (default 2 percentage points F1) fails the CI check
- The report links each regression to the specific dataset, mode, and model slot

### FR-5: Structured Report Output

Each benchmark run SHALL produce a structured report containing:
- Run metadata (timestamp, git commit, model slot config, dataset versions)
- Per-dataset metrics (F1, precision, recall, hallucination rate, latency, memory)
- Per-mode breakdown
- Per-model-slot comparison
- Change delta vs previous baseline (if available)
- Statistical significance indicators where applicable [§6.4]

Output format SHALL be machine-readable (JSON) with a human-readable summary (terminal table via Rich).

### FR-6: Prompt A/B Testing

The harness SHALL support running two or more prompt templates against the same dataset and model slot, reporting comparative accuracy metrics and flagging statistically significant differences (p < 0.05 via McNemar's test or equivalent) [§6.5].

### FR-7: Hardware Budget Verification

The harness SHALL measure and report peak memory and wall-clock time per evaluation item, enabling verification against the constitutional hardware budget (<100 MB peak processing, <110 MB floor, <3 s per 50-page document) [§6.6, Principle III, R-3, R-7].

**Decision**: PASS/FAIL gate with NLP model exemption (Option A). The constitution defines the budget as a release blocker (Principle III), so FAIL blocks merge. The NLP model (spaCy `en_core_web_lg`, ~500 MB) is exempt per constitutional amendment 1.2.0 — only non-NLP processing must stay under 100 MB peak. This aligns with the existing constitutional exemption for Phase 3 PII processing.

Blueprint references: [§6.6], [Principle III], [§9 R-3], constitution §1.2.0

### FR-8: Multi-Party Experimental Support

The harness SHALL provide a flag or configuration to run evaluation in multi-party mode (documents with multiple party roles), recording per-role accuracy and flagging mode-specific degradation [§6.7, R-11]. This is experimental — results are reported but not gated by default.

## 4. Success Criteria

| Criterion | Measure | Target | Verification |
|-----------|---------|--------|-------------|
| Return extraction F1 across CUAD | F1 score | ≥0.80 (initial), ≥0.85 (target) | Automated benchmark run |
| Return comparison F1 across MAUD | F1 score | ≥0.75 (initial), ≥0.82 (target) | Automated benchmark run |
| Return classification F1 across ContractNLI | F1 score | ≥0.80 (initial), ≥0.85 (target) | Automated benchmark run |
| Hallucination rate below floor | Rate | <5% of generated claims (measured via ROUGE-L lexical overlap placeholder; method transitions to CG-DPO per AGENTS.md transition plan) | Automated hallucination detection pass |
| PII recall above floor | Recall | ≥0.95 across all entity types | Seeded PII corpus evaluation |
| Full benchmark suite completes | Wall-clock time | <30 minutes (all-local, SLM) | Timed run on reference hardware (8 GB, 2-core, no GPU) |
| Regression detection | CI fail on drop >2pp F1 | Verified with seeded regression | Deliberately regress a metric and confirm CI blocks |
| Model slot comparison | Report delta between 2+ slots | Usable comparison table | Run with Ollama + one cloud slot |
| Prompt A/B detects difference | p < 0.05 on known-different prompt | Verified with seeded prompt pair | Run with prompts known to produce different results |
| Memory within budget | Peak processing memory | <100 MB (<110 MB floor) | tracemalloc measurement per corpus item (NLP model excluded) |

## 5. Key Entities

### BenchmarkRun
A single execution of one or more benchmark suites against one or more model slots.
- `id`: unique run identifier
- `timestamp`: ISO-8601
- `git_commit`: SHA of code under test
- `config`: benchmark configuration (datasets, slots, prompts, modes)
- `results`: list of DatasetResult

### DatasetResult
Aggregated metrics for one dataset (CUAD, MAUD, or ContractNLI) in one run.
- `dataset_name`: string
- `dataset_version`: string
- `metrics`: dict of metric_name → MetricValue
- `per_task_breakdown`: optional detailed per-task results

### MetricValue
A single measured value with statistical context.
- `value`: float
- `ci_lower`: optional float (95% confidence interval lower bound)
- `ci_upper`: optional float (95% confidence interval upper bound)
- `n`: int (sample size)
- `unit`: string ("f1", "precision", "recall", "rate", "ms", "MB")

### ModelSlotResult
Metrics for a single model slot within a run.
- `slot_name`: string
- `provider`: string
- `model`: string
- `metrics`: dict of metric_name → MetricValue
- `total_latency_ms`: int
- `peak_memory_mb`: float

### RegressionBaseline
Stored baseline from a previous run for regression comparison.
- `baseline_id`: string (e.g., git tag or commit SHA)
- `metrics`: dict of (dataset, mode, slot, metric) → MetricValue
- `created_at`: ISO-8601

### PromptVariant
A named prompt template variant for A/B testing.
- `name`: string
- `template`: string
- `dataset_results`: dict of dataset_name → DatasetResult

## 6. Dependencies

| Dependency | Type | Blueprint Ref | Notes |
|-----------|------|---------------|-------|
| Document parsing engine | Internal | C-05/06/07/08, TRL 9 | Must produce parse output consumable by evaluation pipeline |
| Gateway routing | Internal | C-12/13, TRL 7 | Required for multi-slot evaluation [FR-3] |
| Chunking strategy | Internal | C-32, TRL 7 | Required for document-to-span alignment with ground truth |
| PII stripping engine | Internal | Phase 3 | Required for PII recall measurement [FR-2] |
| CUAD dataset corpus | External research | [P-7] | Labeled contract QA corpus, 41 classes, ~500 contracts |
| MAUD dataset corpus | External research | [P-7] | M&A binary classification, 39 tasks, ~100 agreements |
| ContractNLI dataset corpus | External research | [P-7] | NLI over NDAs, 3 classes, ~600 examples |
| CI pipeline | Internal | §11 seed | Required for automated regression gating [FR-4] |

## 7. Assumptions

- The three research datasets (CUAD, MAUD, ContractNLI) are publicly available and can be distributed with or downloaded by the benchmark harness at evaluation time. Licensing of each dataset permits use in automated evaluation tools.
- Each dataset provides a documented evaluation protocol (train/test splits, metric definitions, scoring scripts) that can be reproduced programmatically.
- The document parsing engine (TRL 9) is stable enough that benchmark evaluation focuses on downstream accuracy rather than parser bugs.
- The reference hardware (8 GB RAM, 2-core CPU, no GPU) is available for benchmark runs. Cloud model calls are measured separately and excluded from hardware budget checks.
- The gateway supports the model slots required for evaluation (at minimum one SLM via Ollama and one cloud provider).
- Ground-truth annotations in CUAD and MAUD are span-based (character or token positions) and alignable to parsed clause output for F1 calculation.
- The hallucination measurement method uses a ROUGE-L lexical overlap placeholder (EXPERIMENTAL, `hallu_detect.py`). The method transitions to CG-DPO when that capability reaches TRL 7+ per AGENTS.md §Hallucination Detection — Transition Plan.

## 8. Risks

| Risk | Impact | Mitigation | Blueprint Ref |
|------|--------|------------|---------------|
| R-1: Comparison accuracy below floor | DealCheck/HireCheck unreliable | MAUD benchmark establishes early ceiling; threshold calibrated from baseline | [§9 R-1] |
| R-2: Hallucination rate too high | All modes produce unreliable output | Hallucination metric measured per mode; floor adjusted per product requirements | [§9 R-2] |
| R-3: Memory over budget on reference hardware | Product cannot run on target machines | Per-item memory profiling; regression gate catches drifts | [§9 R-3] |
| R-4: PII degradation after pipeline changes | Privacy posture weakened | PII recall benchmark in regression suite; floor at ≥0.95 | [§9 R-4] |
| R-7: SLM accuracy too low for production | Product requires cloud model for acceptable results | SLM-vs-cloud comparison built into harness; decision deferred to data, not opinion | [§9 R-7] |
| R-11: Multi-party mode degrades accuracy | DealCheck/HireCheck unreliable on multi-party documents | Experimental mode flags degradation without gating; data collected for future spec | [§9 R-11] |

## 9. Open Questions After Specification

**Decision**: New CLI subcommand `openreview benchmark` (Option A). The subcommand wraps the full benchmark harness, accepting dataset selection (`--datasets`), model slot selection (`--slots`), mode selection (`--modes`), output format (`--format json`), and baseline comparison (`--compare`). CI integration calls the subcommand directly.

Blueprint references: [§11 seed], [C-12], [C-13]

## 10. Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Privacy First | Pass | PII recall benchmark uses seeded documents, never real PII. Cloud evaluation routes through existing PII stripping. |
| II. Local-First, CLI-Only | Pass | Benchmark harness runs as a CLI invocation or CI job. No web server or daemon. |
| III. Hardware-Bounded | Pass | Per-item memory profiling. NLP model memory exempted per constitution. Budget verified on every run. |
| IV. Dependency Minimalism | Pass | No new runtime dependencies. Dataset corpora downloaded at evaluation time, not packaged. |
| V. Spec-Driven, YAGNI | Pass | This spec specifies the harness before implementation. Per-mode features gated by success criteria. |

## 11. Next Steps

1. Proceed to `/speckit.plan` for technical design
