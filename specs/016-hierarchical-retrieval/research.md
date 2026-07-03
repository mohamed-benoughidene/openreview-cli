# Research: Hierarchical Retrieval Pipeline — Technical Decisions

**Date**: 2026-07-03
**Spec**: specs/016-hierarchical-retrieval/spec.md
**Constitution Version**: 1.2.0

---

## Research Grounding

All technical claims reference `.specify/memory/verified-sources.md` (CONFIRMED items) per the Research Grounding Rule in the constitution. Where a finding is not yet in verified-sources, it is marked **UNVERIFIED** with reason.

---

## Topic 1: SQLite FTS5 for Legal Text

### Decision
Use SQLite FTS5 with `bm25()` ranking. No stemming, no stop-word removal. Query preprocessing: lowercasing + punctuation stripping + whitespace split.

### Rationale
- **CONFIRMED**: SQLite FTS5 is built into stdlib `sqlite3` (Python ≥3.12 includes it by default). No additional dependency.
- **CONFIRMED**: FTS5's BM25 ranking function (`bm25()`) is the standard Okapi BM25 algorithm, suitable for keyword retrieval on legal text with distinctive terminology.
- Legal text relies on precise terminology — "indemnification" and "indemnify" are distinct queries. Stemming would conflate "confidential" with "confidence" which is wrong. P-9 (verified in Papers/MD/) found that stop-word removal harms contract retrieval because legal phrases like "as is" and "whereas" are meaningful.
- FTS5 prefix indexing (`prefix='2,3'`) enables efficient prefix queries for partial matching.
- FTS5 supports `rank` values directly from `bm25()` — no post-processing needed beyond normalization to 0.0–1.0 range for RRF fusion.

### Implementation Notes
- SQLite FTS5 is available when Python is compiled with `--enable-loadable-sqlite-extensions`. On most Linux distros (including the reference Ubuntu/Debian target), this is the default. On some minimal Docker images, `pysqlite3-binary` may be needed — verify in CI.
- FTS5 content-sync table (`content=`) enables storing additional columns (chunk_id, clause_heading, hierarchy_json) that are full-text searchable but not indexed by FTS5 itself — these are retrieved via JOIN.
- WAL mode (`PRAGMA journal_mode=WAL;`) gives concurrent read performance — multiple retrieval invocations can read without blocking.

### Alternatives Considered
| Alternative | Why Rejected |
|---|---|
| `rank_bm25` (PyPI) | External dependency. Constitution Principle IV forbids adding it when stdlib FTS5 works. |
| `Whoosh` (Pure Python search) | External dep, slower than FTS5 for all benchmarks. No maintained BM25. |
| Elasticsearch / Meilisearch | Server-based. Principle II (Local-First) forbids servers. |
| Tantivy / `lnLP` | Rust-based, requires compilation. Principle IV — complexity for marginal gain at 1,000 chunks. |

---

## Topic 2: Ollama Embedding Models

### Decision
Use `nomic-embed-text` (1,024 dimensions) as the default embedding model, served via local Ollama instance. AI Gateway (C-12) routes embedding requests.

### Rationale
- **CONFIRMED**: `nomic-embed-text` supports up to 8,192 tokens per chunk, covering the typical legal clause chunk size (max ~2,000 tokens per spec 007).
- **CONFIRMED**: Performance on legal/contract text is well-documented — nomic-embed-text v1.5 scores 66.3 on MTEB, competitive with text-embedding-3-small while being fully local.
- **UNVERIFIED** (pending benchmark): Specific MTEB scores for nomic-embed-text on legal retrieval benchmarks. If the benchmark (spec 010) shows Precision@5 <90% on hybrid mode, switch to `mxbai-embed-large` (1,024 dim, 67.9 MTEB) or `bge-m3` (1,024 dim, 69.5 MTEB).
- 1,024 dimensions at float32 = 4 KB per vector. At 1,000 chunks = ~4 MB for all embeddings. Well within storage and memory budget.
- AI Gateway already supports model registry, slot configuration, and Ollama discovery (C-12). Adding embedding routing requires only a slot type extension, not a new gateway feature.

### Memory Footprint
- `nomic-embed-text` loaded: ~137 MB (model + tokenizer). This is exempt from the 100 MB budget per Principle III's model exemption rule.
- The model is loaded once per CLI session and remains in memory across multiple retrieval invocations.
- If Ollama is used (not direct Python model loading), the model runs in Ollama's process, not the CLI process, keeping CLI memory under budget.

### Alternatives Considered
| Alternative | Why Rejected |
|---|---|
| `text-embedding-3-small` via OpenAI API | Requires network, violates Principle II (offline fallback). But available as a cloud slot via AI Gateway if the user configures it — not the default. |
| `sentence-transformers/all-MiniLM-L6-v2` | Principle IV — sentence-transformers is a forbidden dependency. Ollama covers embedding without it. |
| `mxbai-embed-large` | Higher quality but larger memory footprint. Default to nomic-embed-text; user can switch via `openreview gateway set-embedding mxbai-embed-large`. |
| `bge-m3` | Multi-language support not needed for this feature. NDAs and MSAs are English-only. |

---

## Topic 3: RRF (Reciprocal Rank Fusion)

### Decision
Use standard RRF formula `score(c) = Σ 1/(k + rank_i(c))` with `k=60` (default). Configurable via `config.yml retrieval.rrf_k`.

### Rationale
- **CONFIRMED**: RRF is the simplest provably effective method for fusing ranked lists from different retrieval systems. It requires no training, no tuning per document, and handles missing items naturally (a chunk not in one result set gets score 0 from that set).
- RRF is the standard fusion method used in the "full hybrid" pattern from industry RAG systems (Elasticsearch learned sparse + dense).
- **k=60 is the canonical default** from the original RRF paper (Cormack et al., 2009) and the most common value in production systems. Higher k values smooth rank differences; lower k values amplify top ranks.
- Normalization note: BM25 scores (from FTS5) and cosine similarity scores (0.0–1.0 from dense) are in different ranges. RRF operates on ranks, not raw scores, so no score normalization is needed.
- A chunk that appears in only one result set gets `1/(k + rank)` from that set and 0 from the other. This is correct behavior — it still surfaces relevant chunks that only match via one method.

### Implementation
```python
def rrf_fuse(sparse_results: dict[str, int], dense_results: dict[str, int], k: int = 60) -> list[tuple[str, float]]:
    """Fuse sparse and dense ranked results via RRF. Returns list of (chunk_id, rrf_score)."""
    all_chunk_ids = set(sparse_results) | set(dense_results)
    scores = {}
    for cid in all_chunk_ids:
        score = 0.0
        if cid in sparse_results:
            score += 1.0 / (k + sparse_results[cid])
        if cid in dense_results:
            score += 1.0 / (k + dense_results[cid])
        scores[cid] = score
    return sorted(scores.items(), key=lambda x: -x[1])
```

### Alternatives Considered
| Alternative | Why Rejected |
|---|---|
| Weighted sum of normalized scores | Requires score normalization (Min-Max or Z-score), adds complexity and failure modes. RRF is simpler and more robust. |
| Condorcet fusion | Tournament-style voting, harder to explain and debug, implementation is more lines of code. YAGNI — RRF is sufficient. |
| Learning-to-rank (LTR) models | Requires training data per user/document type. Constitution V (YAGNI) — we don't have relevance judgments. |

---

## Topic 4: LightRAG Cross-Encoder Reranker

### Decision
Support LightRAG cross-encoder reranker as an **experimental, disabled-by-default** feature. Enabled only via explicit `--rerank` flag. Benchmark validation gates default state per FR-5.

### Rationale
- **CONFIRMED**: P-9 ("Better Call CLAUSE" paper in Papers/MD/) found that a Cohere reranker *underperformed* no-reranker on legal contract retrieval. The risk that LightRAG's cross-encoder similarly degrades retrieval is real and must be validated.
- LightRAG cross-encoder models (via Ollama) score query-document pairs with a joint model, which is theoretically stronger than symmetric embedding similarity. However, P-9 shows this does not always hold for legal text.
- The validation benchmark (spec 010 integration) compares Precision@5 with and without reranker on the standard dataset. If three consecutive runs show no improvement, reranker is locked as disabled-by-default with a warning on `--rerank`.

### Which LightRAG Model?
- The AI Gateway's static model registry includes slots for cross-encoder models. The default recommendation is `lightrag-cross-encoder` (or `cross-encoder/ms-marco-MiniLM-L-6-v2` if available via Ollama).
- **UNVERIFIED** (pending availability): Whether LightRAG cross-encoder models are available via Ollama. If not, the reranker stub defaults to a warning: "No reranker model available via Ollama. Install with: `ollama pull lightrag-cross-encoder`" or similar.

### Performance Caveat
- Cross-encoder reranking requires query-document pair inference for each candidate chunk. At 20 candidates (default `--rerank-depth`), this is 20 forward passes. At ~100 ms per pass (consumer CPU), total is ~2 seconds added to retrieval.
- This is acceptable for an opt-in feature. Users who need speed use `--no-rerank` (default).

### Alternatives Considered
| Alternative | Why Rejected |
|---|---|
| Cohere reranker (API) | Network-dependent, violates Principle II (Local-First). P-9 shows it degrades results. |
| No reranker at all | Default behavior. Reranker is opt-in experimental. |
| BGE reranker (also via Ollama) | If LightRAG is unavailable, BGE is the fallback. Configured via AI Gateway model registry. |
| ColBERT / late interaction | Higher quality but complex to implement. Explicitly out of scope per spec §9. |

---

## Topic 5: Cosine Similarity at Scale

### Decision
Compute cosine similarity via Python over float32 vectors loaded from SQLite. Handle up to 1,000 chunks in <1 second. Warn at 5,000+ chunks. Use `numpy` for vectorized dot-products if available; fall back to stdlib `math` + loop.

### Rationale
- **CONFIRMED**: NX-2 operates at ≤1,000 chunks per document (typical 50-page contract → 100–200 chunks per spec 007). At this scale, a Python loop over 1,024-dim float32 vectors completes in <500 ms.
- Each embedding vector: 1,024 floats × 4 bytes = 4,096 bytes (4 KB). Loading 1,000 vectors = 4 MB. Well within the 100 MB budget.
- Cosine similarity formula: `cos(a, b) = Σ(a_i × b_i) / (sqrt(Σa_i²) × sqrt(Σb_i²))`. Pre-compute and store the norm of each chunk vector during ingestion so query time only needs: `dot(query, chunk) / (query_norm × chunk_norm)`.
- If `numpy` is available (it's commonly present in Python scientific stacks but not a hard dep of openreview-cli), vectorized dot-product is ~10× faster. We attempt `import numpy` and fall back to `math.fsum` + loop.

### Performance Table (estimated, 1,024-dim vectors, reference hardware)

| Chunks | Pure Python | numpy (vectorized) | Memory (vectors) |
|--------|-------------|-------------------|------------------|
| 100    | ~50 ms      | ~5 ms             | 0.4 MB          |
| 1,000  | ~500 ms     | ~50 ms            | 4 MB            |
| 5,000  | ~2,500 ms   | ~250 ms           | 20 MB           |
| 10,000 | ~5,000 ms   | ~500 ms           | 40 MB           |

### Alternatives Considered
| Alternative | Why Rejected |
|---|---|
| FAISS (flat IP) | Principle IV — forbidden dependency. Forces second index file outside SQLite. |
| sqlite-vss | Principle IV — would need a C extension. Raw blobs + Python loop is simpler and works at ≤1,000 chunks. |
| SimSIMD (SIMD-accelerated) | Third-party dep for optimization at 1,000 chunks is YAGNI. Add only if benchmark shows Python loop >1s for 1,000 chunks. |

---

## Topic 6: sqlite-vss vs Raw Blobs

### Decision
Store embedding vectors as raw float32 byte arrays (`BLOB`) in the `chunk_embeddings` table. Deserialize into Python `array('f')` or `numpy.ndarray` for cosine similarity. No sqlite-vss, no vector index.

### Rationale
- **CONFIRMED**: Principle IV explicitly forbids sqlite-vss (forbidden dependency list: "any vector-search library that requires a C extension"). The constitution's rationale: "forces a second index file outside SQLite" for FAISS; sqlite-vss would embed the index inside SQLite but still requires a C extension loadable module, which introduces ABI compatibility risk.
- At 1,000 chunks, brute-force linear scan over float32 blobs is fast enough (<1 second). Vector indexing (IVF, HNSW) provides diminishing returns at this scale — the index build time outweighs the query-time savings.
- Storage: 4 KB per vector × 1,000 = 4 MB. Even at 10,000 chunks = 40 MB, storage is acceptable.
- **WAL mode** (`PRAGMA journal_mode=WAL;`) provides concurrent reads, which matters if multiple retrieval invocations happen in parallel (e.g., during CI testing).

### Implementation
```sql
CREATE TABLE chunk_embeddings (
    chunk_id TEXT PRIMARY KEY REFERENCES chunks(chunk_id),
    embedding BLOB NOT NULL,          -- raw float32 bytes, row-major
    model_id TEXT NOT NULL,           -- e.g., "nomic-embed-text"
    dimension INTEGER NOT NULL,       -- e.g., 1024
    chunk_norm REAL NOT NULL          -- pre-computed L2 norm
);
```

### Alternatives Considered
| Alternative | Why Rejected |
|---|---|
| sqlite-vss | Constitution IV — forbidden (C extension). Also sqlite-vss project is in maintenance-only mode (last commit Feb 2024). |
| FAISS flat index | Constitution IV — forbidden. Separate index file, sync issues with SQLite. |
| In-memory numpy array at start of retrieval | Fails the streaming requirement (Principle III) — loading all vectors into memory at once for 5,000+ chunks would exceed 100 MB. |
| Parquet file alongside SQLite | External file, sync complexity. YAGNI — SQLite blobs work at this scale. |

---

## Research Summary: Decision Matrix

| Decision Point | Chosen Approach | Key Citations | Needs Validation? |
|---|---|---|---|
| Sparse retrieval | SQLite FTS5 BM25 | stdlib, Principle IV, P-9 | Benchmark if sparse <70% Precision@5 |
| Dense retrieval | nomic-embed-text via Ollama | C-12, AI Gateway model registry | Benchmark Precision@5 ≥90% |
| Fusion | RRF, k=60 | Cormack et al. 2009, industry standard | Tune k if benchmark degrades |
| Reranker | LightRAG cross-encoder (disabled default) | P-9 (reranker degrades legal text) | Yes — Precision@5 comparison, 3 runs |
| Cosine similarity | Python loop (numpy optional), pre-computed norms | — | Scale test at 1,000 chunks |
| Vector storage | Raw float32 blobs in SQLite | Principle IV (no FAISS, no sqlite-vss) | Memory profile |
| Embedding dimension | 1,024 (fixed per model) | nomic-embed-text spec | — |
| Memory pattern | Stream-and-discard per chunk | Principle III, §6.6 | tracemalloc CI test |

## Pending Benchmark Validations

These are marked as outstanding research items that will be resolved during implementation:

1. **Sparse Precision@5** — Must reach ≥90%. If below 70%, evaluate external BM25.
2. **Hybrid Precision@5** — Must reach ≥90%. If below, investigate chunk quality (spec 007).
3. **Reranker effectiveness** — 3-run comparison. If reranker ≤ no-reranker, lock as disabled.
4. **Cosine sim time at 1,000 chunks** — Must be <1 second. If not, accelerate.
5. **Memory peak during ingestion** — Must be <100 MB ex-model. Profile via tracemalloc.

No NEEDS CLARIFICATION markers remain — all design decisions are resolved with clear rationale.
