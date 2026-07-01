# Research: Chunking Strategy

**Phase**: 0 (Outline & Research) | **Date**: 2026-07-01 | **Source**: Context7 + P-9 + P-13

## RCTS Algorithm

**Decision**: Implement RCTS from scratch (not using LangChain)

**Rationale**: LangChain is a forbidden dependency per Constitution Principle IV. The Recursive Character Text Splitter algorithm is straightforward: try splitting on `["\n\n", "\n", " ", ""]` sequentially at character boundaries. No external library needed.

**Context7 Source**: LangChain docs confirm the algorithm uses these separators and parameters: `chunk_size` (characters), `chunk_overlap`, `add_start_index`. Our implementation adds clause-boundary awareness as the primary split criterion before falling back to RCTS.

## Hierarchical Chunking

**Decision**: Node-level chunks with parent_chunk_id references (no separate summary chunks)

**Rationale**: PAKTON (P-13) validates three chunk types: node-level (fine-grained), ancestor-aware (context from parents), descendant-aware (clauses with sub-clauses). Our approach uses parent_chunk_id references on each chunk to enable ancestor-aware reconstruction without duplicating text. This avoids the forbidden LangChain dependency while matching PAKTON's 5× Recall@1 improvement.

**Alternatives considered**:
- LangChain ParentDocumentRetriever (rejected: LangChain dependency)
- Section summaries approach (rejected: no research support for separate summary chunks)

## Token Counting

**Decision**: Simple whitespace + punctuation splitter (±5% tolerance)

**Rationale**: P-9 (LegalBench-RAG) and P-13 (PAKTON) both use character-based chunking (500-1000 chars), not token-based. Token precision is irrelevant for retrieval quality. No need for tiktoken dependency.

## Table Handling

**Decision**: Flatten table rows into text

**Rationale**: Tables are common in legal contracts (payment schedules, share tables). Flattening preserves the data; skipping loses information; treating as atomic breaks memory budget. Simple row-to-text conversion.

## Memory Strategy

**Decision**: Streaming generator — no accumulation

**Rationale**: Constitution Principle III mandates <100 MB peak. Chunking gets <10 MB of that. The `stream_chunks(clauses)` iterator yields chunks one at a time, never holding more than one chunk in memory.

## Configuration

**Decision**: Config.yml with per-mode overrides

**Rationale**: Different contract types (NDA, MSA, Employment) need different chunk sizes. Default 512 tokens, configurable per mode (e.g., `precheck.chunk_size: 256`). Uses existing config.yml infrastructure from Phase 1.

## Tokens vs Characters

**Decision**: Token-based chunking (default: 512 tokens) with approximate tokenizer

**Rationale**: The spec already specifies token-based sizing. While papers use character counts, token-based sizing is more intuitive for LLM context windows (which are token-limited). Our ±5% approximation is sufficient for retrieval — context window management at generation time is the retrieval pipeline's responsibility.
