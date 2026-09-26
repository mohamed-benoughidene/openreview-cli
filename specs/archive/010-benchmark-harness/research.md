# Research — Benchmark Harness (Phase 0)

Resolves every NEEDS CLARIFICATION from `plan.md` Technical Context.

---

## R1. Dataset Download Mechanism

**Question**: Should we use HuggingFace `datasets` library or raw HTTP+JSON/parquet download?

**Decision**: **Raw HTTP + JSON/parquet** from HuggingFace Hub URLs. No `datasets` library.

**Rationale**:
- CUAD and MAUD are available as raw JSON/parquet files on HuggingFace Hub (CC BY 4.0)
- `datasets` lib is ~2 MB install + pulls `pyarrow`, `dill`, `multiprocess`, `xxhash` — adds ~30 MB to `.venv`
- Raw download via `httpx` (existing dep) + stdlib `json` is ~30 lines of total code across all three datasets
- Per constitution Principle IV: a 30-line function is preferable to a new runtime dependency with transitive bloat
- The `datasets` lib's caching and sharding features are unnecessary at benchmark scale (500 contracts, ~150 MB total)

**Reference**: Verified Sources — CUAD and MAUD CC BY 4.0 licenses, available as downloadable artifacts.

**Alternatives considered**:
1. HuggingFace `datasets` — rejected (Principle IV violation, transitive bloat)
2. Check dataset into repo — rejected (git LFS, CI download overhead, license compliance complexity)
3. Submodule with git LFS — rejected (same issues as #2)

---

## R2. CUAD Ground-Truth Span Alignment

**Question**: What format are CUAD annotations in, and how do we align them with parsed clause output for F1 calculation?

**Decision**: **Character-offset spans** (start/end tokens in original text). CUAD annotations use token-level indices from the tokenizer but the underlying text is paragraph-based. We align via the parsed document's text offsets.

**Rationale**:
- CUAD's HuggingFace format provides `input_ids`, `token_type_ids`, and the original paragraph text per annotation
- The document parsing engine (PyMuPDF) extracts text with character-position metadata per page
- F1 is computed at the **token level** using the established CUAD evaluation protocol: tokenize both ground-truth and predicted spans with a standard tokenizer (NLTK `word_tokenize` or stdlib `re`), compute precision/recall/F1 per clause type, then macro-average across the 41 classes
- This matches the NeurIPS 2021 CUAD evaluation protocol exactly

**Technical approach**:
```
ground_tokens = tokenize(ground_truth_span)
pred_tokens = tokenize(predicted_span)
true_positives = len(ground_tokens & pred_tokens)
precision = true_positives / len(pred_tokens) if pred_tokens else 0
recall = true_positives / len(ground_tokens) if ground_tokens else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
```

**Alternatives considered**:
1. Character-level F1 — rejected (not compatible with CUAD protocol; character mismatches in whitespace/normalization inflate scores)
2. Sentence-level F1 — rejected (too coarse; clauses span partial sentences)
3. Exact-match accuracy — rejected (too strict for extractive QA)

---

## R3. Hallucination Measurement Method

**Question**: There is no parallel spec defining hallucination measurement (§6.3 reference). How do we implement FR-2 hallucination detection without it?

**Decision**: **Staged implementation** — Phase 1 uses a **lexical overlap heuristic** (ROUGE-L / BERTScore-free fallback) as a placeholder. Full semantic hallucination detection awaits the parallel spec.

**Rationale**:
- The spec (§6.3) promises a method defined in a "prior or parallel specification" that doesn't exist yet
- Blocking the benchmark on this is infeasible — FR-2 requires hallucination rate as a metric
- The minimal viable approach: compute ROUGE-L recall between generated claims and input text spans. If a claim has <0.40 ROUGE-L overlap with any clause, flag it as potentially hallucinated
- This is a ponytail:placeholder — imprecise but functional. A real semantic entailment check replaces it when the parallel spec lands
- Flagged in spec as §6.3 dependency; will be documented as **EXPERIMENTAL** in benchmark reports

**Implementation** (ponytail:placeholder):
```python
def lexical_overlap(claim: str, source_spans: list[str]) -> float:
    """ROUGE-L-inspired recall of claim unigrams in source text."""
    claim_tokens = set(tokenize(claim.lower()))
    if not claim_tokens:
        return 1.0
    source_tokens = set()
    for span in source_spans:
        source_tokens.update(tokenize(span.lower()))
    overlap = len(claim_tokens & source_tokens)
    return overlap / len(claim_tokens)
```

**Alternatives considered**:
1. Wait for parallel spec — rejected (blocks entire benchmark feature)
2. Use LLM-as-judge for hallucination detection — rejected (too expensive, circular dependency on gateway)
3. BERTScore via sentence-transformers — rejected (constitution-forbidden dep, Principle IV)

---

## R4. MAUD Task Count Discrepancy

**Question**: Spec says 39 tasks, research (academic papers) says 92 questions. Which is correct?

**Decision**: **92 questions** from the ABA's 2021 Public Target Deal Points Study, grouped into **39 deal-point categories**. The spec abbreviates to 39 for conceptual simplicity. The harness loads all 92 questions and groups reports by the 39 deal-point categories.

**Rationale**:
- The MAUD paper (EMNLP 2023) explicitly states "92 reading comprehension questions from the 2021 ABA Study"
- The ABA study defines 39 deal-point *categories* (e.g., "Knowledge Definition", "Material Adverse Effect"), each with 1-4 specific *questions*
- Both counts are correct at different granularity levels
- Metrics: per-question accuracy for the 92 items, per-category F1 for the 39 groups

**Implementation**:
```
MAUD_QUESTION_COUNT = 92     # Individual yes/no questions
MAUD_CATEGORY_COUNT = 39     # ABA Deal Point categories (for grouped reporting)
```

---

## R5. PII Benchmark Seeded Corpus Coverage

**Question**: Does the existing PII test fixtures corpus have sufficient coverage for PII recall benchmarking?

**Decision**: **Partially sufficient**. The existing `tests/fixtures/pii/` has seeded documents with ground-truth JSON used in the PII benchmark script (`scripts/benchmark_pii_stripping.py`). It covers 16 entity types across 54 documents (1,730 entities, 0 false positives on clean text). It is sufficient for the **initial** PII recall benchmark (FR-2). A dedicated benchmark corpus with measured recall/precision (T049) is deferred.

**Coverage gaps**:
- The existing corpus was designed for the PII stripping engine benchmark — it may not exercise every edge case (e.g., multi-page documents with PII on every page, mixed PII types in single sentence)
- No ground-truth annotations are yet published for recall/precision calculation — the benchmark script counts detections but doesn't compute recall
- The seeded corpus has `ground_truth.json` that needs to be integrated into the benchmark harness

**Action**: For the initial release, use the existing seeded corpus with ground-truth annotations. Document coverage limitations in the benchmark report. Expand coverage as T049/T050 are resolved.

---

## R6. CI Integration Point

**Question**: Where in `.github/workflows/ci.yml` does the benchmark run?

**Decision**: **New parallel CI job** called `benchmark`, running only on push to `main` (not on every PR).

**Rationale**:
- Full benchmark suite (<30 min all-local) is too heavy for per-PR CI — developers shouldn't wait 30 minutes for a lint fix
- CUAD dataset download (~150 MB) adds CI time
- PR CI runs the existing four jobs (lint, types, test, memory)
- On push to `main`, the `benchmark` job downloads datasets, runs evaluation, compares against stored baseline, and fails if any metric regresses >2pp F1
- Baselines stored as CI artifacts keyed by git commit SHA
- Can be triggered manually on PRs via `--benchmark` label (future enhancement)

**Implementation**:
```yaml
# In `.github/workflows/ci.yml` — new job:
benchmark:
  if: github.ref == 'refs/heads/main'
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v6
    - uses: astral-sh/setup-uv@v8.1.0
    - run: uv sync
    - run: uv run openreview benchmark --ci --compare HEAD~1
```

---

## Summary of Decisions

| # | Question | Decision | § Ref |
|---|----------|----------|-------|
| R1 | Dataset download mechanism | Raw HTTP+JSON/parquet (no `datasets` lib) | Principle IV |
| R2 | CUAD span alignment | Token-level F1 with stdlib word tokenization | FR-1, §6.4 |
| R3 | Hallucination measurement | Lexical overlap placeholder (ROUGE-L recall) | §6.3, FR-2 |
| R4 | MAUD task count | 92 questions / 39 deal-point categories | FR-1, verified sources |
| R5 | PII seeded corpus adequacy | Existing corpus sufficient for initial release | FR-2, T049 deferred |
| R6 | CI integration point | New parallel job on push to main only | FR-4 |
