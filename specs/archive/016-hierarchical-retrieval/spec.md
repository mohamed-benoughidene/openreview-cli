# NX-2: Hierarchical Retrieval Pipeline — BM25 + Dense + LightRAG + RRF Hybrid Retrieval

**Feature ID**: 016-hierarchical-retrieval
**Status**: Draft Specification
**Created**: 2026-07-03
**Phase**: NEXT (4–12 weeks)
**Blueprint References**: [PR-2], [T-3], [P-9], [P-13], [T-8], §4 (C-07, C-08, C-12, C-32), §6.2, §6.6, §8 (R-2), §9 (R-3, R-7), §11 (Speckit Seed)

---

## 1. Executive Summary

A lawyer reviewing a 50-page contract needs to find relevant clauses — the termination clause, the indemnification clause, the data-processing clause — without reading the entire document. Single-party review (spec 011) operates on pre-selected clauses from a playbook, but it does not answer open-ended queries: *"Find all clauses related to data breach notification"* or *"Show me every limitation of liability provision."*

NX-2 builds a **hierarchical retrieval pipeline** that turns a parsed and chunked contract into a searchable knowledge base. The user poses a natural-language query, and the system returns the most relevant clause chunks, ranked by relevance. The pipeline uses **hybrid retrieval** — combining sparse keyword matching (BM25) with dense semantic embeddings and cross-encoder reranking (LightRAG) — fused via **Reciprocal Rank Fusion (RRF)**.

The key design constraint is **validation over novelty**: P-9 and T-8 show that chunking strategy dominates retrieval quality, and that a Cohere reranker *underperformed* no-reranker on legal contract retrieval. NX-2 must validate that LightRAG's cross-encoder reranker does not degrade retrieval quality relative to the BM25 + Dense fusion alone. If the reranker degrades results, it is disabled by default and retained as an opt-in experimental mode.

Retrieval quality is measured as **Precision@5 ≥90%** on the benchmark dataset, matching the success criterion established in spec 007 (SC-006).

### 1.1 What Hierarchical Retrieval Gives the User That Single-Party Review Does Not

| Capability | Single-Party Review (spec 011) | Hierarchical Retrieval (NX-2) |
|---|---|---|
| Open-ended queries | ❌ Not available — playbook-driven only | ✅ Ask any question, get relevant clauses |
| Hybrid search | ❌ Not available | ✅ BM25 keyword + Dense semantic + reranking |
| Clause hierarchy preserved | ❌ Not available | ✅ Results show full context (Article → Section → Clause) |
| Cross-clause discovery | ❌ Not available | ✅ Finds clauses the playbook didn't pre-select |
| Query-time flexibility | ❌ Fixed playbook per mode | ✅ Any query, any time, re-run on same document |
| No-inference retrieval | ❌ Not available | ✅ BM25-only mode works with no model loaded |

Blueprint references: §11 (Speckit Seed — retrieval pipeline), [PR-2], [T-3]

---

## 2. User Scenarios

### Scenario 1: Open-Ended Clause Search (Priority: P1)

A legal professional has parsed and chunked an NDA. Instead of running a pre-defined playbook, they want to ask a specific question:

```
openreview retrieve "limitation of liability for data breach" contract.ndax
```

The system returns the top 5 relevant clause chunks, each showing:
- The chunk text (with surrounding clause context indicated via parent hierarchy)
- The clause heading and structural location (e.g., "Article 7 — Limitation of Liability → Section 7.3")
- The relevance score (0.0–1.0) and which retrieval method contributed most
- A three-color confidence indicator per result (Green = high relevance, Amber = moderate, Red = low)

**Why this priority**: Open-ended retrieval is the foundation query mode. Without it, the retrieval pipeline has no user-facing purpose.

**Independent Test**: Can be tested by indexing a known contract, running a query with known expected results, and verifying that the expected clause appears in the top 5 results.

**Acceptance Scenarios**:

1. **Given** a parsed and chunked contract, **When** the user runs `openreview retrieve "<query>" <file>`, **Then** the system returns the top 5 most relevant clause chunks ranked by relevance
2. **Given** a retrieval result, **When** displayed, **Then** each result shows clause heading, structural location, relevance score, and hierarchy context (parent clause chain)
3. **Given** a query that matches a specific clause (e.g., "confidentiality term" on an NDA), **When** retrieved, **Then** the matching clause appears in position 1–5

Blueprint references: [P-13] (hierarchical chunking — chunk metadata includes structural location), §11 (Speckit Seed — retrieval)

---

### Scenario 2: Hybrid Retrieval Mode Switching (Priority: P1)

A user wants to understand how different retrieval modes perform on their document:

```
openreview retrieve --method hybrid "termination for convenience" contract.ndax
openreview retrieve --method sparse "termination for convenience" contract.ndax
openreview retrieve --method dense "termination for convenience" contract.ndax
```

The hybrid mode (default) combines BM25 + Dense via RRF. The sparse mode uses BM25 only (fastest, no model required). The dense mode uses embeddings only (best semantic matching). Each mode returns the same result format, so the user can compare.

**Why this priority**: Different queries benefit from different retrieval methods. Keyword-specific queries (e.g., "indemnification") work well with BM25. Semantic queries (e.g., "who pays if data is leaked") need dense retrieval. Hybrid gives the best of both.

**Independent Test**: Can be tested by running the same query in all three modes and verifying that results differ in ranking but share the same output format.

**Acceptance Scenarios**:

1. **Given** a parsed contract, **When** the user runs `--method sparse`, **Then** retrieval uses BM25 only and returns results within 1 second (no model loaded)
2. **Given** a parsed contract, **When** the user runs `--method dense`, **Then** retrieval uses embedding similarity only
3. **Given** a parsed contract, **When** the user runs `--method hybrid` (default), **Then** retrieval fuses BM25 + Dense via RRF

Blueprint references: §11 (Speckit Seed — hybrid BM25 + Dense → RRF fusion), §9 R-7 (SLM performance on consumer hardware — sparse mode exists for low-resource scenarios)

---

### Scenario 3: Retrieval with Reranker Validation (Priority: P1)

Per the P-9 finding that Cohere's reranker underperformed no-reranker on legal contract retrieval, NX-2 must validate that LightRAG's cross-encoder reranker does not degrade quality.

```
openreview retrieve --method hybrid --rerank "limitation of liability" contract.ndax
openreview retrieve --method hybrid --no-rerank "limitation of liability" contract.ndax
```

The user can compare results with and without reranking. The system logs the quality difference internally for the benchmark harness. The default for the reranker is determined by the benchmark: if Precision@5 without reranker ≥ Precision@5 with reranker, the reranker is disabled by default.

**Why this priority**: P-9 warns that rerankers can actively harm retrieval on legal text. Before shipping reranking as a default, we must validate it doesn't degrade results.

**Independent Test**: Can be tested by running the retrieval benchmark (spec 010) once with reranker and once without, comparing Precision@5 on the standard dataset.

**Acceptance Scenarios**:

1. **Given** the benchmark dataset, **When** retrieval runs without reranker, **Then** Precision@5 is recorded
2. **Given** the benchmark dataset, **When** retrieval runs with reranker, **Then** Precision@5 is recorded
3. **Given** both Precision@5 scores, **When** compared, **Then** if reranker degrades Precision@5, it is disabled by default and available only via explicit `--rerank` flag

Blueprint references: [P-9] (reranker underperforms no-reranker on legal text), [T-8] (chunking strategy dominates retrieval quality), §6.2 (Cohere reranker finding)

---

### Scenario 4: Retrieval with Hierarchy Context (Priority: P2)

A user retrieves a chunk from a deeply nested clause. The result shows not just the chunk text, but the full hierarchical context:

```
Article 3 — Confidentiality Obligations
  Section 3.1 — Definition of Confidential Information
    Sub-section (a) — Written Information
       → [RETRIEVED CHUNK]: "Confidential Information includes all written materials..."
```

This context lets the user understand where in the document the clause lives without opening the original document.

**Why this priority**: Hierarchical context dramatically improves result interpretability (P-13 shows 5× improvement in retrieval accuracy with hierarchical chunking). Without it, a standalone clause chunk is meaningless.

**Independent Test**: Can be tested by indexing a contract with known multi-level hierarchy and verifying that retrieval results include the full ancestor chain.

**Acceptance Scenarios**:

1. **Given** a contract with Article → Section → Sub-section hierarchy, **When** a sub-section-level chunk is retrieved, **Then** the result shows Article heading, Section heading, and Sub-section heading as parent context
2. **Given** a retrieval result with hierarchy, **When** displayed, **Then** parent chunks are shown in a tree-like indentation format

Blueprint references: [P-13] (hierarchical chunking, parent_chunk_id references), §8 R-2 (chunking strategy with clause-boundary awareness — built in spec 007)

---

### Scenario 5: Retrieval via Streaming (Priority: P2)

The user wants to search across a large contract without loading it entirely into memory. The retrieval pipeline streams chunks from SQLite, processes each through BM25 and/or embedding similarity, and returns results without ever holding the full chunk collection in memory.

**Why this priority**: The hardware budget (<100 MB peak, excluding models) forbids loading the full chunk set into memory. Streaming is not optional — it's a constitutional requirement.

**Independent Test**: Can be tested by indexing a 500-chunk contract and verifying peak memory stays under the 100 MB budget (excluding model memory per the PII model exemption).

**Acceptance Scenarios**:

1. **Given** a contract with 500+ chunks stored in SQLite, **When** retrieval runs, **Then** peak processing memory stays under 100 MB (excluding model memory)
2. **Given** a retrieval query, **When** BM25 processes chunks, **Then** chunks are read from SQLite one batch at a time, never the full set

Blueprint references: §6.6 (stream-and-discard, no full-corpus in memory), §9 R-3 (memory budget breach — pipeline must stream), §11 (Speckit Seed — stream-and-discard)

---

### Scenario 6: Offline / All-Local Retrieval (Priority: P2)

A user on a plane or in a secure facility has no internet connection. They run retrieval using only local models (BM25 via SQLite FTS5, dense embeddings via local Ollama instance). The system works entirely offline. If no local embedding model is available, the system falls back to BM25-only with a notice.

**Why this priority**: Principle II requires offline operability. The tool must work when no network path exists.

**Independent Test**: Can be tested by disconnecting the network, running retrieval with all model slots set to local, and verifying end-to-end output.

**Acceptance Scenarios**:

1. **Given** no network connection, **When** the user runs retrieval with all-local model slots, **Then** retrieval completes successfully using BM25 + local embeddings
2. **Given** no local embedding model available, **When** the user runs retrieval with `--method dense`, **Then** the system falls back to BM25 with a notice: "Local embedding model not available; falling back to BM25-only. Install a local embedding model via `openreview gateway install nomic-embed-text`"

Blueprint references: Principle II (Local-First, CLI-Only — offline operation), [C-12] (AI Gateway — model routing for local/cloud slots)

---

## 3. Functional Requirements

### FR-1: Hybrid Retrieval Pipeline

The system MUST implement a hybrid retrieval pipeline that combines sparse (BM25) and dense (embedding) retrieval via Reciprocal Rank Fusion (RRF).

- The pipeline SHALL accept a natural-language query string and a document reference (parsed and chunked contract) as input.
- The pipeline SHALL support three retrieval methods: `sparse` (BM25 only), `dense` (embedding similarity only), and `hybrid` (BM25 + Dense fused via RRF).
- `hybrid` SHALL be the default method.
- The pipeline SHALL return a ranked list of chunks, each with: chunk ID, chunk text, clause heading, hierarchical parent chain, relevance score (0.0–1.0), contributing method(s), and the RRF fusion score if hybrid.
- The pipeline SHALL be stateless per query — each invocation re-runs retrieval from scratch against the stored chunks.
- The pipeline SHALL support configurable result count (default: 5, configurable via `--top-k`).

Blueprint references: §11 (Speckit Seed — BM25 + Dense → RRF fusion), [P-9] (hybrid retrieval methodology)

### FR-2: Sparse Retrieval via BM25 (SQLite FTS5)

The sparse retrieval component SHALL use BM25 ranking via SQLite's built-in FTS5 full-text search engine.

- Chunk text SHALL be indexed in a SQLite FTS5 virtual table at chunk-ingestion time.
- The FTS5 index SHALL store: chunk ID, chunk text, clause heading, and hierarchical metadata.
- BM25 ranking SHALL use SQLite FTS5's built-in `bm25()` ranking function with default weights.
- The FTS5 index SHALL be stored in the same SQLite database as chunk metadata — no separate index file.
- Query preprocessing SHALL be minimal: lowercasing, stripping punctuation, and splitting on whitespace. No stemming or stop-word removal — legal text relies on precise terminology [P-9].
- BM25 retrieval SHALL complete in under 1 second for documents with up to 1,000 chunks on the reference hardware.
- No additional dependencies beyond `sqlite3` (stdlib) SHALL be required for BM25 retrieval.

Blueprint references: §11 (Speckit Seed — BM25 via SQLite FTS5, not FAISS), Principle IV (Dependency Minimalism — stdlib `sqlite3` preferred), §9 R-7 (SLM performance — BM25 is the fast path)

### FR-3: Dense Retrieval via Embedding Similarity

The dense retrieval component SHALL use embedding vectors and cosine similarity to find semantically relevant chunks.

- Chunk embeddings SHALL be generated at chunk-ingestion time using a local embedding model (served via Ollama, per the AI Gateway — C-12).
- The default embedding model SHALL be `nomic-embed-text` (1,024 dimensions, local-only, ~137 MB loaded) — per AI Gateway's static model registry.
- Embedding vectors SHALL be stored in the SQLite database alongside chunk data. Storage format SHALL be binary blob (raw float32 bytes per vector).
- Cosine similarity SHALL be computed via a simple Python loop over stored vectors — no vector-search index library (no sqlite-vss, no FAISS, per Principle IV).
- The system SHALL support an alternative embedding model configured via the AI Gateway model registry. The user SHALL be able to switch embedding models via `openreview gateway set-embedding <model>`.
- Dense retrieval SHALL only be available when a local embedding model is configured and available. If no embedding model is available, the system SHALL fall back to BM25-only with a user-facing notice.
- Embedding computation at ingestion time SHALL NOT block the CLI — a progress indicator SHALL show "Embedding chunk 12 of 47" while the user waits.

Blueprint references: [C-12] (AI Gateway — model routing), §11 (Speckit Seed — dense via Ollama), Principle IV (no FAISS, no sqlite-vss — use SQLite, simple cosine loop)

### FR-4: Reciprocal Rank Fusion (RRF)

The hybrid retrieval mode SHALL combine BM25 and dense results via Reciprocal Rank Fusion (RRF).

- The RRF formula SHALL be: `score(chunk) = 1/(k + rank_sparse(chunk)) + 1/(k + rank_dense(chunk))` where `k` is a constant (default: 60).
- Chunks that appear in only one result set SHALL receive a score contribution only from that set.
- The final ranking SHALL be by descending RRF score, capped at the configured `--top-k` count.
- The `k` constant SHALL be configurable via config.yml (`retrieval.rrf_k`, default 60).
- Each result SHALL expose per-method ranks and the fused score for debugging transparency.

Blueprint references: §11 (Speckit Seed — RRF fusion)

### FR-5: Reranker (LightRAG Cross-Encoder) — Experimental, Requires Validation

The system SHALL support an optional reranking step using a LightRAG cross-encoder model.

- Reranking SHALL operate on the top-N results from the hybrid retrieval pipeline (N default: 20, configurable via `--rerank-depth`).
- The default reranker model SHALL be LightRAG's cross-encoder (via Ollama, per the AI Gateway).
- Reranking SHALL be disabled by default — the user SHALL explicitly enable it via `--rerank`.
- **The reranker SHALL be validated against the no-reranker baseline.** If benchmark Precision@5 with reranker ≤ Precision@5 without reranker for three consecutive benchmark runs, the system SHALL:
  1. Disable reranking by default (already the starting state)
  2. Print a warning when `--rerank` is used: "⚠ Reranker validation: benchmark shows reranker does not improve retrieval quality for this document type."
- The reranker validation result SHALL be cached per embedding-model version and document type in the SQLite database.
- The user SHALL always be able to override the validation and use the reranker via `--rerank --force-rerank`.

Blueprint references: [P-9] (reranker underperforms no-reranker), §6.2 (Cohere reranker finding — validate, not assume help), §9 R-1 (accuracy caveats)

### FR-6: Ingestion Pipeline — Chunk + Embed + Index

The system SHALL provide an ingestion pipeline that transforms a parsed contract (clauses with chunk metadata) into a retrievable index.

- Ingestion SHALL accept the output of the chunking pipeline (spec 007) — a stream of Chunk objects with clause references and hierarchy metadata.
- Ingestion SHALL:
  1. Write chunk data (ID, text, clause heading, hierarchy chain, char offsets) to SQLite
  2. Create/update the FTS5 index for each chunk
  3. Compute and store the embedding vector for each chunk (if dense mode is configured)
- Ingestion SHALL stream — each chunk is written individually, never accumulated.
- Ingestion SHALL be idempotent: re-ingesting the same document SHALL replace the existing index, not duplicate it.
- A progress indicator SHALL show "Indexing chunk 12 of 47" during ingestion.
- Ingestion SHALL complete in under 10 seconds for a 50-page contract (with 100–200 chunks) on the reference hardware.

Blueprint references: spec 007 (FR-001–FR-021 — chunking output as input), §6.6 (stream-and-discard)

### FR-7: SQLite Storage for Chunks, Vectors, and Index

All retrieval data SHALL be stored in a single SQLite database per document.

- The database SHALL contain:
  - `chunks` table: chunk ID (text, unique), document ID, chunk text, clause heading, clause level, parent chunk ID, hierarchy chain (JSON array), character offsets
  - `chunk_fts` virtual table: FTS5 index over chunk text
  - `chunk_embeddings` table: chunk ID, embedding vector (blob), embedding model ID, embedding dimension
  - `rerank_validation` table: embedding model ID, document type, Precision@5 with reranker, Precision@5 without reranker, benchmark timestamp
- The database file SHALL be stored in the application data directory (per platformdirs), keyed by document hash.
- The database SHALL be created with WAL mode for performance.
- No external database server, index service, or vector database SHALL be required — SQLite is the only storage engine.

Blueprint references: §11 (Speckit Seed — SQLite for chunks + vectors), Principle IV (no FAISS, no sqlite-vss), [C-07] (clause boundary detection — stored clauses feed chunking)

### FR-8: CLI Commands

The system SHALL provide CLI commands for retrieval and ingestion:

- `openreview ingest <file>` — Parse, chunk, and index a document for retrieval. Output: "Indexed {n} chunks in {t}s".
- `openreview retrieve "<query>" [<file>]` — Retrieve relevant chunks. If `<file>` is omitted, use the most recently indexed document.
- `openreview retrieve --method sparse|dense|hybrid` — Select retrieval method.
- `openreview retrieve --top-k <n>` — Number of results (default: 5).
- `openreview retrieve --rerank` — Enable reranker (experimental, disabled by default).
- `openreview retrieve --rerank-depth <n>` — Number of results to rerank (default: 20).
- `openreview retrieve --force-rerank` — Enable reranker even if validation says it degrades quality.
- `openreview retrieve --no-header` — Omit headings from output (JSON mode).
- `openreview retrieve --format json` — Output results as structured JSON.
- `openreview index-status [<file>]` — Show indexing status: chunk count, embedding model used, index timestamp, rerank validation status.
- `openreview index-clear [<file>]` — Remove indexed data for a document.

Blueprint references: §11 (Speckit Seed — CLI commands map to pipeline stages)

### FR-9: Validation Benchmark Integration

The retrieval pipeline SHALL integrate with the benchmark harness (spec 010) for automated quality validation.

- The benchmark SHALL run retrieval queries from the standard dataset against indexed contracts.
- The benchmark SHALL record Precision@5 for each retrieval method (sparse, dense, hybrid, hybrid+reranker).
- The benchmark SHALL compare reranker Precision@5 against no-reranker baseline per FR-5.
- Benchmark results SHALL be writable to the rerank_validation table in the retrieval database.
- The benchmark SHALL be runnable via: `openreview benchmark --retrieval` (already defined in spec 010).

Blueprint references: spec 010 (Benchmark Harness), §11 (Speckit Seed — benchmark validates quality)

### Processing Model

The retrieval pipeline SHALL process documents in distinct phases, each releasing memory before the next starts:

1. **Check phase**: Load document hash → check if indexed and up-to-date. If config changed (chunk size, embedding model), re-index.
2. **Ingestion phase** (if needed): Stream parsed clauses → chunk (spec 007) → write chunks + FTS5 index → compute embeddings → store vectors. Each chunk is processed and released individually.
3. **Query phase**: Load query → tokenize for BM25 → run FTS5 search → load embeddings and compute similarity → fuse via RRF → optionally rerank → return top-K results. Only top-K chunks and their embedding vectors are held in memory simultaneously.

Blueprint references: §6.6 (stream-and-discard), §9 R-3 (memory budget breach)

---

## 4. Success Criteria

| Criterion | Target | Verifiable By |
|---|---|---|
| Retrieval Precision@5 across all method modes | ≥90% on the benchmark dataset | Benchmark run (spec 010) — [P-9], [T-8] |
| Reranker does not degrade Precision@5 | Reranker Precision@5 ≥ no-reranker Precision@5 for hybrid mode | Comparison benchmark run — [P-9], §6.2 |
| BM25-only retrieval time for 1,000 chunks | <1 second P95 on reference hardware | Timed run — §9 R-7 |
| Full ingestion (parse + chunk + embed) for 50-page contract | <10 seconds on reference hardware | Timed run |
| Peak processing memory (ex-model) during retrieval | <100 MB (per the hard budget, §III) | `test_memory` profile — §9 R-3 |
| Peak processing memory (ex-model) during ingestion | <100 MB (chunks streamed, not accumulated) | `test_memory` profile — §6.6 |
| SQLite database size for 1,000 chunks (BM25 only, no embeddings) | <10 MB | Measure after ingestion |
| SQLite database size for 1,000 chunks (with embeddings at 1,024 dim) | <20 MB (16 MB for vectors + metadata overhead) | Measure after ingestion |
| Default reranker state | Disabled (opt-in via `--rerank`) | Acceptance test — FR-5 |
| Offline mode (BM25-only) works | Full end-to-end without network | Integration test — Principle II |
| Chunk hierarchy preserved in results | ≥95% of results include correct parent chain | Acceptance test with known hierarchy — [P-13] |
| RRF fusion produces different ranking than individual methods | Rank correlation (sparse vs hybrid) <1.0 | Benchmark correlation analysis |
| All retrieval methods return same output schema | Sparse, dense, hybrid, and hybrid+reranker return identical result format | Schema validation test |

All success criteria are technology-agnostic by design.

Blueprint references: [P-9] (chunking strategy dominates retrieval quality), [T-8] (chunking strategy research), [P-13] (hierarchical chunking), §6.6 (stream-and-discard), §9 R-3 (memory budget), §9 R-7 (SLM performance)

---

## 5. Key Entities

### RetrievalResult
A single retrieved chunk with relevance information.

| Field | Type | Description |
|---|---|---|
| chunk_id | string | Unique identifier for the chunk |
| text | string | The chunk text content |
| clause_heading | string | The clause heading (e.g., "Section 3.1 — Definition") |
| clause_level | int | Depth in the clause hierarchy (0 = top-level article) |
| hierarchy_chain | string[] | Ordered list of ancestor headings (e.g., ["Article 3 — Confidentiality", "Section 3.1 — Definition"]) |
| parent_chunk_id | string or null | Reference to parent chunk in hierarchy |
| score | float | Final relevance score (0.0–1.0) |
| method | string | Which retrieval method(s) contributed: "sparse", "dense", "hybrid", or "hybrid+rerank" |
| rank_sparse | int or null | Rank position in BM25 results (null if not in top-K) |
| rank_dense | int or null | Rank position in dense results (null if not in top-K) |
| rrf_score | float or null | The RRF fusion score (null if not hybrid mode) |
| rerank_score | float or null | The reranker score (null if reranker not used) |

### RetrievalQuery
The input parameters for a retrieval invocation.

| Field | Type | Description |
|---|---|---|
| query_text | string | Natural-language query |
| method | string | "sparse", "dense", or "hybrid" (default) |
| top_k | int | Number of results to return (default: 5) |
| rerank | bool | Whether to enable reranker (default: false) |
| rerank_depth | int | Number of hybrid results to rerank (default: 20) |
| force_rerank | bool | Override validation and use reranker (default: false) |

### RetrievalIndex
The on-disk representation of a document's retrievable chunks.

| Table | Contents | Notes |
|---|---|---|
| chunks | Chunk ID, text, clause heading, hierarchy, offsets | One row per chunk |
| chunk_fts | FTS5 full-text index over chunk text | Virtual table, BM25 ranking |
| chunk_embeddings | Chunk ID, embedding blob, model ID, dimension | One row per chunk (only if embeddings exist) |
| rerank_validation | Model ID, doc type, Precision@5 scores | Validation cache per FR-5 |

Blueprint references: §11 (Speckit Seed — entities mirror the pipeline stages)

---

## 6. Dependencies

| Dependency | Type | Built In | Notes |
|---|---|---|---|
| Clause boundary detection (C-07) | Runtime | ✅ Phase 2 | Input — parsed clauses with hierarchy |
| stream_clauses() (C-08) | Runtime | ✅ Phase 2 | Input — streaming clause iterator |
| AI Gateway (C-12) | Runtime | ✅ Phase 4 | Model routing for embedding and reranker |
| RCTS chunking strategy (C-32) | Runtime | ✅ spec 007 | Produces chunks with hierarchy metadata |
| SQLite3 (stdlib) | Runtime | ✅ stdlib | BM25 via FTS5, chunk/vector storage |
| Embedding model (via Ollama) | Runtime | ✅ Configurable | Dense retrieval — default: nomic-embed-text |
| LightRAG cross-encoder (via Ollama) | Runtime | ✅ Configurable | Reranker — disabled by default |
| Benchmark harness (spec 010) | Test | ✅ spec 010 | Precision@5 validation |

Blueprint references: §4 (all built dependencies), §11 (Speckit Seed — storage: SQLite)

---

## 7. Assumptions

1. **SQLite FTS5 BM25 is sufficient for sparse retrieval**: SQLite's built-in FTS5 with `bm25()` ranking provides adequate keyword retrieval for legal contract text. No external BM25 library (e.g., `rank_bm25`) is needed. Legal text has distinctive terminology that FTS5 handles well. If benchmark Precision@5 for sparse mode falls below 70%, an external BM25 implementation may be evaluated.

2. **Cosine similarity over SQLite-stored vectors is fast enough for 1,000 chunks**: Computing cosine similarity by loading embedding vectors from SQLite and iterating in Python is acceptable for the expected chunk count (≤1,000 chunks per document). If documents routinely exceed 5,000 chunks, a vector index approach may be needed — but this is deferred until the scale is demonstrated.

3. **Embedding model runs locally via Ollama**: The AI Gateway routes embedding requests to a local Ollama instance. The user must have Ollama installed and running (or use a cloud embedding provider configured via the gateway). This is consistent with the existing gateway architecture (C-12).

4. **Document re-indexing is user-initiated**: The system does not auto-detect config changes (chunk size, embedding model) and re-index automatically. The user runs `openreview ingest` explicitly. Automatic re-indexing on config change is a deferred enhancement.

5. **Reranker validation is per-model and per-document-type**: The reranker validation cache (FR-5) stores validation results keyed by (embedding model ID, document type). If the user changes the embedding model or switches document types (NDA vs MSA), the cache is invalidated and a new benchmark run is needed.

6. **Vectors are stored as binary blobs, not in a vector index**: Per Principle IV (no FAISS, no sqlite-vss), embedding vectors are stored as raw float32 byte arrays in SQLite. Cosine similarity is computed by deserializing and iterating. This is not a high-performance vector search — it is a correctness-first approach for the expected scale.

7. **Chunks are indexed per-document, not cross-document**: Each document gets its own SQLite database. No cross-document retrieval is supported in NX-2. Cross-document retrieval is a future enhancement.

8. **Ingestion happens once per document version**: If the user edits the document and re-parses it, the old index is replaced. There is no incremental update or merge. The system compares document hashes to detect changes and invalidate the index.

9. **The embedding dimension is fixed per model**: All embedding vectors for a document use the same model with the same dimension. If the user switches embedding models, the document must be re-ingested. The database stores the model ID and dimension per embedding to detect mismatches.

Blueprint references: §11 (Speckit Seed), Principle IV (Dependency Minimalism), §6.6 (stream-and-discard)

---

## 8. Edge Cases / Failure Handling

### No Embedding Model Available
If dense retrieval or hybrid mode is requested but no embedding model is configured or available (Ollama not running, gateway slot empty), the system SHALL fall back to BM25-only with a notice: "Embedding model not available; falling back to BM25-only. Configure via `openreview gateway set-embedding <model>`."

### Document Not Indexed
If the user runs `openreview retrieve` on a document that has not been indexed, the system SHALL exit with: "Document not indexed. Run `openreview ingest <file>` first." Exit code 2.

### Query Returns No Results
If the query does not match any chunk (all scores below a minimum threshold), the system SHALL return an empty result set with a notice: "No relevant clauses found for this query. Try a different query or use `--method sparse` for broader matching."

### Corrupt or Missing Index Database
If the index database is missing, corrupt, or from an incompatible schema version, the system SHALL prompt the user: "Index database is missing or corrupt. Re-run `openreview ingest <file>` to rebuild." Exit code 3.

### Reranker Validation Fails
If the reranker benchmark (FR-5) shows that reranker degrades Precision@3 (not just @5) and the degradation is ≥5 percentage points, the system SHALL print a warning on every `--rerank` use: "⚠ Reranker benchmark shows {n}pp degradation. Results may be worse than without reranker." The user can suppress with `--quiet`.

### Very Large Documents (>5,000 chunks)
For documents exceeding 5,000 chunks, the system SHALL print a performance notice: "Large document ({n} chunks). BM25-only recommended for best performance. Embedding similarity may take several seconds." The system SHALL NOT refuse to process the document but SHALL warn the user.

### Interrupted Ingestion
If ingestion is interrupted (Ctrl+C, power loss), the system SHALL leave the partial index in place with a marker indicating incomplete status. The next `openreview ingest` invocation SHALL detect the incomplete marker and re-index from scratch. No partial index SHALL be used for retrieval.

### Embedding Dimension Mismatch
If the current embedding model produces vectors of a different dimension than those in the existing index, the system SHALL re-ingest automatically with a notice: "Embedding model changed; re-indexing document."

Blueprint references: §9 R-3 (memory budget breach), §9 R-7 (SLM performance warning for large documents)

---

## 9. Out of Scope (Explicit)

The following are explicitly deferred to later phases or separate features:

- **Cross-document retrieval**: NX-2 indexes and retrieves within a single document. Searching across multiple documents simultaneously is a future enhancement.
- **Vector index acceleration**: FAISS, sqlite-vss, and other vector-search libraries are out of scope per Principle IV. Cosine similarity over SQLite-stored vectors is the initial approach.
- **Query expansion / reformulation**: The system does not rewrite or expand user queries. The query is used as-is for BM25 and embedding.
- **Document ranking / contract-level scoring**: NX-2 retrieves clause chunks, not entire documents. Document-level ranking (e.g., "which of these 10 contracts is most relevant to my query") is deferred.
- **RAG (Retrieval-Augmented Generation)**: NX-2 provides retrieval only. Feeding retrieved chunks into an LLM for answer generation is a downstream feature (spec 011's single-party review is the first consumer of retrieval output).
- **Persistent embedding cache across documents**: Embeddings are stored per-document database. Cross-document embedding reuse is deferred until cross-document retrieval lands.
- **Streaming embedding computation**: Embeddings are computed synchronously at ingestion time with a progress indicator. Streaming embedding generation (compute on-the-fly during retrieval) is deferred.
- **HyDE (Hypothetical Document Embeddings)**: Query-side embedding augmentation is out of scope for NX-2.
- **ColBERT / late interaction models**: NX-2 uses bi-encoder embeddings + cross-encoder reranker. Late-interaction models like ColBERT are not evaluated.
- **Multi-modal retrieval (tables, images)**: Retrieval operates on chunk text only. Tables flattened to text (per spec 007) are included; images and other non-text content are not retrievable.
- **Automated re-indexing on config change**: The user must explicitly re-ingest after changing chunk size, overlap, or embedding model. Auto-detection of config drift is deferred.

Blueprint references: §8 (R-2 — chunking strategy explicit), §11 (Speckit Seed — narrow scope), Principle IV (no FAISS, no sqlite-vss)

---

## 10. Research Limitations and Risks

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| R-3: Memory budget breach during ingestion | HIGH | MEDIUM | Stream-and-discard architecture per chunk; tracemalloc profiler in CI |
| R-7: SLM embedding on consumer hardware is slow | MEDIUM | HIGH | BM25 fallback; progress indicator; embedding is non-blocking with status display |
| Reranker degrades retrieval quality (P-9) | MEDIUM | HIGH | Disabled by default; validation benchmark per FR-5; user override with warning |
| Cosine similarity over SQLite vectors is too slow for 5,000+ chunks | MEDIUM | LOW | Warn at 5,000 chunks; defer vector index until scale is demonstrated |
| FTS5 BM25 insufficient for legal terminology | LOW | LOW | Benchmark Precision@5 target ≥90%; if sparse mode falls below 70%, evaluate external BM25 |
| Embedding model changes require full re-ingest | LOW | HIGH | Notice to user; ingestion is idempotent and fast (<10s typical) |

Blueprint references: §9 (R-3, R-7), [P-9] (reranker degradation)

---

## 11. Relationship to Existing Specifications

| Spec | Relationship |
|---|---|
| **007** (Chunking Strategy) | NX-2 consumes chunk output (FR-001–FR-021 from spec 007). Chunk metadata, hierarchy, and parent_chunk_id are the foundation for retrieval. |
| **010** (Benchmark Harness) | NX-2's retrieval quality is validated via the benchmark harness. New retrieval-specific benchmark queries are added to the dataset. |
| **011** (Single-Party Review) | NX-2 provides the retrieval layer that single-party review can optionally use for clause discovery beyond the playbook. |
| **004** (AI Gateway) | NX-2 uses the gateway for embedding model routing (dense retrieval) and cross-encoder routing (reranker). No new gateway capabilities needed. |
| **009** (Prompt Management) | NX-2 has no prompt dependencies — retrieval is purely algorithmic. If retrieval is later used for RAG (out of scope), prompts would be needed then. |

---

## Clarifications

### Session 2026-07-03

The following clarifications were applied to the spec above:

- **Q1: Reranker default state** — Disabled by default, opt-in via `--rerank`. This aligns with the P-9 finding that rerankers can actively harm retrieval on legal text. (Applied to FR-5.)
- **Q2: Embedding storage format** — Binary blob (raw float32) in SQLite. No vector index library. Cosine similarity computed in Python. (Applied to FR-3, §7 Assumptions.)
- **Q3: Cross-document retrieval scope** — Explicitly out of scope. NX-2 is single-document only. (Applied to §9 Out of Scope.)
