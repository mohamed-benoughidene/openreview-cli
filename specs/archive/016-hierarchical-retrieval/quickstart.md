# Quickstart: Hierarchical Retrieval Pipeline

**Spec**: specs/016-hierarchical-retrieval/spec.md

---

## Prerequisites

Before using the retrieval pipeline:

1. **Ollama running** with at least one embedding model:
   ```bash
   ollama pull nomic-embed-text       # default embedding model (137 MB)
   # or
   ollama pull mxbai-embed-large      # alternative (higher quality, ~270 MB)
   ```

2. **Ollama serving** (default: `http://localhost:11434`):
   ```bash
   ollama serve
   ```

3. **openreview-cli installed** with all deps:
   ```bash
   uv sync
   ```

4. **AI Gateway configured** with embedding model slot:
   ```bash
   openreview gateway set-embedding nomic-embed-text
   # Verify:
   openreview gateway status
   ```

5. **A parsed and chunked contract** (via spec 007 pipeline):
   ```bash
   openreview parse contract.pdf
   openreview chunk contract.ndax       # if chunking is separate
   ```
   Or simply:
   ```bash
   openreview ingest contract.pdf       # parse + chunk + index in one step
   ```

---

## Setup Commands

### Full pipeline (parse + chunk + embed + index)

```bash
# Option 1: One-shot (default: hybrid BM25 + dense)
openreview ingest contract.pdf

# Option 2: Sparse-only (fast, no model needed)
openreview ingest --method sparse contract.pdf

# Option 3: With specific embedding model
openreview ingest --method hybrid --model nomic-embed-text contract.pdf
```

### Verify indexing

```bash
# Check index status
openreview index-status contract.pdf

# Expected output:
# Document: contract.pdf
# Status:   Indexed (2026-07-03T14:30:00Z)
# Chunks:   47
# Method:   hybrid
# Model:    nomic-embed-text (1024d)
# DB size:  3.2 MB
```

---

## Validation Scenarios

### Scenario 1: Ingest a Test Document

```bash
# Using a test fixture
openreview ingest tests/fixtures/nda-short.pdf
```

**Expected outcome**:
```
✓ Indexed 12 chunks in 0.8s
  Method: hybrid (nomic-embed-text, 1024d)
```

**What to verify**:
- The index database file exists at `~/.local/share/openreview/indexes/{hash}.db`
- The database contains non-zero rows in `chunks`, `chunk_fts`, and `chunk_embeddings` tables
- No errors during embedding computation

**Test command**:
```bash
sqlite3 ~/.local/share/openreview/indexes/*.db "SELECT COUNT(*) FROM chunks;"
# → 12
sqlite3 ~/.local/share/openreview/indexes/*.db "SELECT COUNT(*) FROM chunk_embeddings;"
# → 12
```

---

### Scenario 2: Search for a Clause

```bash
# Search for confidentiality-related clauses
openreview retrieve "confidentiality obligations" nda-short.pdf

# Expected output (top 3 of 5):
# ┌──────┬────────────────────────────────────┬───────┬──────────┐
# │ Rank │ Clause Heading                     │ Score │ Method   │
# ├──────┼────────────────────────────────────┼───────┼──────────┤
# │ 1    │ Article 3 — Confidentiality        │ 0.94  │ hybrid   │
# │ 2    │ Section 3.1 — Definition           │ 0.87  │ hybrid   │
# │ 3    │ Section 3.2 — Exclusions           │ 0.72  │ hybrid   │
# └──────┴────────────────────────────────────┴───────┴──────────┘
```

**Expected outcome**:
- The confidentiality clause appears in position 1 or 2
- Hierarchy context is shown (Article → Section)
- Score is between 0.0 and 1.0
- Method column reads "hybrid"

**What to verify**:
- Hybrid retrieval combines BM25 and dense results
- RRF fusion produces different ranking than either method alone
- Hierarchy chain is correctly preserved

**Method comparison**:
```bash
openreview retrieve --method sparse "confidentiality" nda-short.pdf
openreview retrieve --method dense "confidentiality" nda-short.pdf
openreview retrieve --method hybrid "confidentiality" nda-short.pdf
```

All three return the same result format. Sparse and dense rankings should differ (rank correlation <1.0).

---

### Scenario 3: Verify Hybrid Retrieval (BM25 + Dense)

```bash
# Run a query that benefits from semantic matching
openreview retrieve "who is responsible for protecting secrets" nda-short.pdf

# Compare with sparse-only
openreview retrieve --method sparse "who is responsible for protecting secrets" nda-short.pdf
```

**Expected outcome**:
- Hybrid mode returns more semantically relevant results than sparse mode
- Sparse mode may miss clauses that don't contain the exact query words
- Dense mode catches clauses about "confidentiality obligations" even though the query uses different wording

**What to verify**:
- Hybrid mode Precision@5 ≥ sparse mode Precision@5 on the benchmark dataset
- BM25-only completes in <1 second (verified via timing output)

**Timing check**:
```bash
openreview retrieve --method sparse --format json "termination" nda-short.pdf | jq '.timing'
# Expected: bm25_ms < 1000
```

---

### Scenario 4: Test Reranker Validation Benchmark

```bash
# Run retrieval with and without reranker
openreview retrieve --method hybrid "limitation of liability" nda-short.pdf
openreview retrieve --method hybrid --rerank "limitation of liability" nda-short.pdf
```

**Expected outcome**:
- Default behavior (no `--rerank`): returns hybrid results without reranking
- With `--rerank`: reranker is applied to top-20 hybrid candidates
- If reranker degrades results, a warning is printed

**Validation benchmark** (requires benchmark dataset from spec 010):
```bash
openreview benchmark --retrieval
```

**Expected benchmark output**:
```
Retrieval Benchmark Results:
  Sparse Precision@5:  0.88
  Dense Precision@5:   0.91
  Hybrid Precision@5:  0.94
  Hybrid+Rerank P@5:   0.91   # ⚠ Degradation: -3pp vs hybrid
```

**What to verify**:
- Hybrid Precision@5 ≥ 90%
- Reranker Precision@5 ≥ no-reranker Precision@5 (or warning is displayed)
- Benchmark results are written to `rerank_validation` table in the index DB

---

## Offline Mode Validation

```bash
# Disconnect network, then:
openreview retrieve --method sparse "confidentiality" nda-short.pdf
# Should work with no network — BM25 only, no model needed
```

**Expected outcome**: BM25-only retrieval succeeds without network. Dense mode prints a fallback notice.

---

## Troubleshooting

| Symptom | Likely Cause | Solution |
|---|---|---|
| `Error: Embedding model not available` | Ollama not running or model not pulled | `ollama serve` and `ollama pull nomic-embed-text` |
| `Error: Document not indexed` | Haven't run `ingest` yet | `openreview ingest contract.pdf` |
| `No relevant clauses found` | Query too specific or chunks not well-formed | Try different query or `--method sparse` |
| `Slow retrieval (>3s)` | Large document (>1,000 chunks) | Fall back to `--method sparse` |
| `Warning: Reranker degrades results` | Reranker validation triggered (FR-5) | Use `--force-rerank` to override |
| `Index database version mismatch` | Schema changed | Re-run `openreview ingest` to rebuild |
