# Data Model: Hierarchical Retrieval Pipeline

**Spec**: specs/016-hierarchical-retrieval/spec.md
**Research**: specs/016-hierarchical-retrieval/research.md

---

## Entities

### 1. Chunk

A single text fragment from a parsed contract, produced by the chunking pipeline (spec 007).

| Field | Type | Description | Validation |
|---|---|---|---|
| `chunk_id` | `str` | Unique identifier (UUID4) | Required, non-empty, unique across document |
| `document_id` | `str` | Document hash (SHA-256 of original bytes) | Required, 64-char hex string |
| `text` | `str` | Chunk text content | Required, ≥1 char, ≤8,192 tokens (~32,768 chars) |
| `clause_heading` | `str` | The heading of the clause this chunk belongs to | Required, non-empty |
| `clause_level` | `int` | Depth in clause hierarchy (0 = article, 1 = section, 2 = sub-section) | Required, ≥0, ≤10 |
| `parent_chunk_id` | `str or None` | Chunk ID of the parent clause chunk | Optional, must reference an existing chunk_id in the same document if set |
| `heading_chain` | `list[str]` | Ordered ancestor headings, root first | Required, at least [clause_heading], max depth 10 |
| `char_start` | `int` | Character offset (start) in the original document | Required, ≥0 |
| `char_end` | `int` | Character offset (end) in the original document | Required, >char_start |
| `created_at` | `str` | ISO 8601 timestamp | Auto-generated on insert |

**Relationships**:
- A Chunk may have one parent Chunk (via `parent_chunk_id`), forming a tree.
- A Chunk is part of one Document (identified by `document_id`).
- A Chunk may have zero or one Embedding (not zero or many — one vector per chunk).

**State transitions**: Chunk is created → Chunk is stored in SQLite → Chunk is indexed in FTS5 → (if dense mode) Chunk embedding is computed and stored.

---

### 2. Embedding

A vector representation of a chunk's text, stored as a binary float32 array.

| Field | Type | Description | Validation |
|---|---|---|---|
| `chunk_id` | `str` | FK → chunks.chunk_id | Required, must reference existing chunk |
| `embedding` | `bytes` | Float32 vector (row-major, little-endian) | Required, length = dimension × 4 bytes |
| `model_id` | `str` | Embedding model identifier (e.g., "nomic-embed-text") | Required, non-empty |
| `dimension` | `int` | Vector dimension (e.g., 1024) | Required, >0 |
| `chunk_norm` | `float` | Pre-computed L2 norm of the vector | Required, >0.0 (guaranteed for real embeddings) |

**Relationships**:
- 1:1 with Chunk (each chunk has at most one embedding).
- Embedding model dimension must match across all embeddings in the same document index.

**State transitions**: Chunk ingested → Embedding computed via Ollama → Embedding stored in SQLite → Embedding is retrievable for similarity search.

---

### 3. Index (RetrievalIndex)

A container representing one document's complete retrieval data.

| Component | Description |
|---|---|
| `chunks` table | All chunks for the document (see Chunk entity) |
| `chunk_fts` table | FTS5 virtual table indexing chunk text for BM25 |
| `chunk_embeddings` table | Embedding vectors (only if dense mode configured at ingest time) |
| `rerank_validation` table | Cached reranker validation results (FR-5) |
| `index_meta` table | Document hash, embedding model, chunk count, timestamps |

**States**:
- `empty`: No chunks ingested yet.
- `ingesting`: Ingestion in progress (incomplete marker present).
- `indexed`: All chunks stored, FTS5 built, embeddings computed.
- `stale`: Config changed (chunk size, embedding model) since last index.
- `corrupt`: Schema version mismatch or data integrity failure.

**Transitions**:
```
empty → ingesting → indexed
indexed → ingesting (on re-index)
ingesting → indexed → empty (on index-clear)
indexed → stale (on config change detection)
indexed → corrupt (on database corruption)
```

---

### 4. RetrievalResult

A single retrieved chunk with its relevance information, returned by a `retrieve()` call.

| Field | Type | Description |
|---|---|---|
| `chunk_id` | `str` | Unique identifier for the chunk |
| `text` | `str` | Chunk text content |
| `clause_heading` | `str` | The clause heading |
| `clause_level` | `int` | Depth in clause hierarchy |
| `hierarchy_chain` | `list[str]` | Ordered ancestor headings (root first) |
| `score` | `float` | Final relevance score (0.0–1.0) |
| `method` | `str` | Retrieval method: "sparse", "dense", "hybrid", or "hybrid+rerank" |
| `rank_sparse` | `int or None` | Rank in BM25 results (null if not in top-K) |
| `rank_dense` | `int or None` | Rank in dense results (null if not in top-K) |
| `rrf_score` | `float or None` | RRF fusion score (null if not hybrid mode) |
| `rerank_score` | `float or None` | Cross-encoder score (null if reranker not used) |

**Constraints**:
- `score` is always the final displayed score: for sparse mode = normalized BM25, for dense = cosine similarity, for hybrid = RRF score, for hybrid+rerank = reranker score.
- `method` is automatically set based on the pipeline configuration.

---

### 5. RetrievalQuery

Input parameters for a retrieval invocation.

| Field | Type | Default | Description |
|---|---|---|---|
| `query_text` | `str` | — | Natural-language query (required) |
| `method` | `str` | `"hybrid"` | Retrieval method: "sparse", "dense", or "hybrid" |
| `top_k` | `int` | 5 | Number of results (1–50) |
| `rerank` | `bool` | `False` | Enable cross-encoder reranker |
| `rerank_depth` | `int` | 20 | Number of hybrid results to rerank (≥top_k) |
| `force_rerank` | `bool` | `False` | Override reranker validation warning |

---

### 6. RerankValidation

Cached result of reranker benchmark comparison (FR-5).

| Field | Type | Description |
|---|---|---|
| `model_id` | `str` | Embedding model ID used during the benchmark |
| `document_type` | `str` | Document type (e.g., "nda", "msa") |
| `precision_at_5_with_reranker` | `float` | Precision@5 with reranker (0.0–1.0) |
| `precision_at_5_without_reranker` | `float` | Precision@5 without reranker (0.0–1.0) |
| `benchmark_timestamp` | `str` | ISO 8601 when benchmark was run |
| `reranker_degradation_pp` | `float` | Percentage-point degradation (negative = improvement) |

**Validation**: If `reranker_degradation_pp >= 0.0` for three consecutive runs, reranker is locked as disabled-by-default with warning.

---

## State Transition Diagram

```
┌──────────────┐     openreview ingest      ┌──────────────┐
│              │ ──────────────────────────→ │              │
│  PARSED DOC  │                             │  INGESTING   │
│  (spec 007)  │                             │              │
│              │ ←─── Ctrl+C / error ─────── │              │
└──────────────┘                             └──────┬───────┘
                                                     │
                                              ┌──────▼───────┐
                                              │              │
                                              │   INDEXED    │
                                              │              │
                                              └──────┬───────┘
                                                     │
                                        ┌────────────┼────────────┐
                                        │            │            │
                                        ▼            ▼            ▼
                                 ┌──────────┐ ┌──────────┐ ┌──────────┐
                                 │ RETRIEVE │ │ RE-INDEX │ │ CLEAR   │
                                 │ (query)  │ │ (config  │ │ (delete) │
                                 │          │ │  change) │ │          │
                                 └──────────┘ └──────────┘ └──────────┘
```

## Validation Rules Summary

1. **Document ID uniqueness**: Each document hash maps to exactly one SQLite database.
2. **Chunk ID uniqueness**: Chunk IDs are unique within a document.
3. **Embedding model consistency**: All embeddings in one index use the same model_id and dimension.
4. **Parent reference integrity**: `parent_chunk_id` must reference an existing chunk in the same document.
5. **Hierarchy depth limit**: Maximum 10 levels of clause nesting.
6. **Query constraints**: `query_text` must be non-empty, `top_k` must be 1–50, `rerank_depth` must be ≥ `top_k`.
7. **Score range**: All scores are normalized to 0.0–1.0 for display.
8. **Incomplete index detection**: If the `index_meta` table has `index_status = 'ingesting'`, retrieval is blocked.
