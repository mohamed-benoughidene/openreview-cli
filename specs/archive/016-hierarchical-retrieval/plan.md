# Implementation Plan: Hierarchical Retrieval Pipeline — BM25 + Dense + LightRAG + RRF Hybrid Retrieval

**Branch**: `feat/016-hierarchical-retrieval` | **Date**: 2026-07-03 | **Spec**: specs/016-hierarchical-retrieval/spec.md

**Input**: Feature specification from `/specs/016-hierarchical-retrieval/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Build a hierarchical retrieval pipeline that turns parsed/chunked contracts into a searchable knowledge base. Users pose natural-language queries and get relevant clause chunks ranked by relevance via hybrid retrieval — BM25 (SQLite FTS5) + dense embeddings (Ollama via AI Gateway) fused via Reciprocal Rank Fusion (RRF). Optional LightRAG cross-encoder reranker (disabled by default, requires validation per P-9 finding). Precision@5 ≥90%. Memory ≤100 MB (ex-model). No FAISS, no sqlite-vss, no vector index library — raw float32 blobs in SQLite with Python cosine similarity loop.

## Technical Context

**Language/Version**: Python ≥3.12 (per constitution constraint — MAJOR amendment required to bump)

**Primary Dependencies**:
- Runtime: `sqlite3` (stdlib — FTS5 BM25), `httpx` (AI Gateway calls to Ollama), `numpy` (dot-product for cosine similarity), `pydantic` (config), `rich` (progress/CLI display), `typer` (CLI commands)
- Embedding: Ollama via AI Gateway (C-12) — default model `nomic-embed-text` (1024 dimensions, ~137 MB loaded)
- Reranker: LightRAG cross-encoder via Ollama (C-12) — disabled by default, requires benchmark validation
- No new dependencies added — building on `uv add numpy` only (if not already present; `numpy` is needed for vectorized cosine similarity vs raw Python loop, per Principle IV's permission of dependencies that ship with the feature)

**Storage**: SQLite — single `.db` file per document. Tables: `chunks`, `chunk_fts` (FTS5 virtual table), `chunk_embeddings`, `rerank_validation`. WAL mode. Stored in `platformdirs` user data directory, keyed by document hash.

**Testing**: pytest — unit tests per module (test_retrieval_engine.py, test_ingest.py, test_rrf.py), integration tests for CLI commands (test_retrieve_command.py, test_ingest_command.py), memory profiler test (pytest -m memory). Benchmark via spec 010 harness.

**Target Platform**: Linux (reference: 8 GB RAM, 2-core CPU, no GPU). macOS and Windows secondary (Ollama must be available).

**Project Type**: CLI tool extension — no server, no daemon, no web service.

**Performance Goals**:
- BM25-only retrieval for 1,000 chunks: <1 second P95
- Full ingestion (parse + chunk + embed) for 50-page contract: <10 seconds
- Hybrid retrieval (BM25 + dense) for 1,000 chunks: <3 seconds
- Cosine similarity computation for 1,000 chunks × 1,024 dims: <1 second

**Constraints**:
- Peak processing memory <100 MB (ex-model, per Principle III)
- Model memory exemption: embedding model (~137 MB) is exempt from the 100 MB budget
- Offline-capable: BM25-only mode works with no network, no model loaded
- No FAISS, no sqlite-vss, no sentence-transformers, no langchain, no llama-index (per Principle IV)
- Forbidden dependencies list applies (Principle IV)

**Scale/Scope**: Single-document retrieval only. ≤1,000 chunks per document (typical). Warning at 5,000+ chunks. Cross-document retrieval is explicitly deferred.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Privacy First** | ✅ Pass | Retrieval operates on local-only data. Embedding requests go to local Ollama only (no cloud path for retrieval — FR-6 mandates local-only embedding). No PII stripping needed at retrieval time because data was already stripped at parse time (Phase 3). |
| **II. Local-First, CLI-Only** | ✅ Pass | All retrieval modes operate locally. BM25 via SQLite FTS5 (stdlib). Dense via local Ollama. Reranker via local Ollama. No server, no daemon, no telemetry. Offline mode (BM25-only) works with no network. |
| **III. Hardware-Bounded** | ✅ Pass | Stream-and-discard architecture per chunk during ingestion (FR-6). Cosine similarity loop loads one embedding vector at a time (FR-3, Assumption 2). Top-K only held in memory during query (Processing Model §3). Under 100 MB ex-model target. Model exemption for embedding model (~137 MB loaded for nomic-embed-text). |
| **IV. Dependency Minimalism** | ✅ Pass | BM25 uses stdlib `sqlite3` FTS5 — no external BM25 library. Vectors stored as raw float32 blobs — no FAISS, no sqlite-vss, no vector index. Cosine similarity via stdlib `math`/`numpy` (numpy added only if vectorized perf is measurably better). LightRAG cross-encoder via existing AI Gateway (C-12) — no new dep. Guiding rule from spec: "if numpy is already in the dep tree, use it; if not, stdlib `math` is sufficient for 1,000 chunks." |
| **V. Spec-Driven, YAGNI** | ✅ Pass | Full spec written (516 lines) before implementation. All design decisions cited to spec, constitution, or research papers. Reranker disabled by default until validated. No speculative abstractions — no interface with one implementation, no factory. RRF fusion is the single fusion method. |

**Phase 1 re-check result**: ✅ All principles still pass after detailed design. No violations introduced.

## Project Structure

### Documentation (this feature)

```text
specs/016-hierarchical-retrieval/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── cli.md           # CLI command schemas
│   ├── api.md           # Python API contracts
│   └── database.md      # SQLite schema
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── __init__.py
├── __main__.py
├── app.py                    # → `ingest`, `retrieve`, `index-status`, `index-clear` commands
├── errors.py                 # → ExitCode enum additions (INDEX_MISSING, INDEX_CORRUPT)
├── config/config.py          # → retrieval.* config keys
├── gateway/                  # C-12 — embedding model routing already exists
├── retrieval/                # NEW: retrieval pipeline package
│   ├── __init__.py           # Public exports: RetrievalEngine, RetrievalResult, ingest_document, retrieve
│   ├── engine.py             # RetrievalEngine — orchestrates hybrid retrieval + RRF fusion
│   ├── ingest.py             # ingest_document() — chunk → SQLite → FTS5 → embed → store
│   ├── bm25.py               # BM25 via SQLite FTS5 — query builder, rank extractor
│   ├── dense.py              # Dense retrieval — embedding fetch + cosine similarity
│   ├── rrf.py                # Reciprocal Rank Fusion — fuse sparse + dense ranks
│   ├── rerank.py             # LightRAG cross-encoder reranker wrapper (via AI Gateway)
│   ├── storage.py            # SQLite storage layer — schema creation, CRUD, WAL mode
│   └── models.py             # RetrievalResult, RetrievalQuery, RetrievalIndex dataclasses
tests/
├── unit/
│   ├── test_retrieval_engine.py   # Unit tests for RetrievalEngine
│   ├── test_retrieval_ingest.py   # Unit tests for ingest_document
│   ├── test_retrieval_bm25.py     # Unit tests for BM25 query/rank
│   ├── test_retrieval_dense.py    # Unit tests for dense similarity
│   ├── test_retrieval_rrf.py      # Unit tests for RRF fusion
│   ├── test_retrieval_rerank.py   # Unit tests for reranker wrapper
│   ├── test_retrieval_storage.py  # Unit tests for storage layer
│   └── test_retrieval_models.py   # Unit tests for dataclasses
├── integration/
│   ├── test_ingest_command.py     # Integration test for `openreview ingest`
│   ├── test_retrieve_command.py   # Integration test for `openreview retrieve`
│   ├── test_index_status.py       # Integration test for `openreview index-status`
│   └── test_retrieval_memory.py   # Memory profiler test (pytest -m memory)
└── fixtures/
    └── retrieval/                 # Test data: small contracts, expected results
```

**Structure Decision**: Single project (DEFAULT), adding `retrieval/` package under `src/openreview_cli/`. Matches existing package structure (parsing/, pii/, gateway/, review/). Tests follow existing pattern: unit/ per module, integration/ per command, fixtures/ for test data.

## Complexity Tracking

No constitution violations. All principles pass. No complexity justification needed.
