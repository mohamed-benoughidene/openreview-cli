# Feature Specification: Chunking Strategy

**Feature Branch**: `feat/007-chunking-strategy`

**Created**: 2026-07-01

**Status**: Draft

**Input**: User description: "N-4 from product blueprint: Implement chunking strategy specification with RCTS (Recursive Character Text Splitting) and clause-boundary awareness. Research shows chunking strategy dominates retrieval quality (P-9, T-8). Must be specified before retrieval pipeline work."

## Clarifications

### Session 2026-07-01

- Q: Should chunking happen before or after PII stripping? → A: After PII stripping. PII placeholders must be preserved in chunks to maintain the privacy-first architecture. Chunking operates on stripped text.
- Q: What is the target chunk size for legal contracts? → A: 512 tokens (approximately 2,000 characters) with 50-token overlap. This balances context preservation with retrieval precision.
- Q: Should chunks respect clause boundaries or split mid-clause? → A: Clause boundaries first. If a clause exceeds the target chunk size, split at paragraph boundaries within the clause. Never split mid-sentence.
- Q: What happens when a single clause is larger than the target chunk size? → A: Split the clause at paragraph boundaries (blank-line-separated blocks) within the clause. If a paragraph exceeds chunk size, split at sentence boundaries. Preserve clause metadata (ID, title, level) in all sub-chunks.
- Q: Should chunking be configurable per document type? → A: Yes. NDA/employment contracts may need different chunk sizes than MSAs. Default to 512 tokens, allow override via config.yml.
- Q: How should chunks reference their source clauses? → A: Each chunk carries: source_clause_id, source_clause_title, source_clause_level, chunk_index_within_clause (0, 1, 2...), and character offset range within the clause text.
- Q: Should overlapping chunks be used? → A: Yes, 50-token overlap (approximately 200 characters) to preserve context across chunk boundaries. Overlap is applied within clauses, not across clause boundaries.
- Q: What is the memory budget for chunking? → A: Streaming — chunks are yielded one at a time, never accumulated. Peak memory for chunking logic itself: <10 MB (on top of the 100 MB parsing budget).
- Q: Should chunking support hierarchical retrieval (chunk → sub-chunk → paragraph)? → A: Yes. The chunking strategy produces a hierarchical chunk structure that mirrors the clause hierarchy via parent_chunk_id references. Each chunk carries metadata (structural location, document position) per PAKTON's approach (P-13).
- Q: What exactly is a "section summary" in hierarchical chunking? → A: Not a separate summary — hierarchical chunking preserves the clause hierarchy via parent_chunk_id references. Each chunk corresponds to a clause or sub-clause with metadata (structural location, document position). This aligns with PAKTON's approach: node-level, ancestor-aware, and descendant-aware chunks enriched with metadata (P-13).
- Q: What is the success metric for chunking quality? → A: Retrieval Precision@5 ≥90% on the benchmark dataset (vs 6.41% P@1 baseline from P-9). Measured after retrieval pipeline is built.
- Q: Does token counting precision matter (whitespace splitter ±5% vs. tiktoken)? → A: No — P-9 and P-13 use character-based chunking (500–1,000 chars), not token counting. Approximate tokenization is sufficient for retrieval-focused chunking.
- Q: Should chunk IDs be unique across documents or per-document? → A: Per-document (document-wide only). Chunks are ephemeral retrieval units, not persisted records.
- Q: How should tables and structured content within clauses be handled? → A: Flatten table rows into text and include them in the chunk. Skipping tables loses data; treating tables as atomic breaks the memory budget.
- Q: Is there a minimum chunk size threshold below which short clauses must be merged? → A: No — FR-015 grouping rule already merges consecutive short clauses from the same article when combined size is below the target. An explicit minimum adds complexity with no gain.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Chunk a Parsed Contract (Priority: P1)

A lawyer has parsed a 50-page NDA contract and wants to prepare it for retrieval-based review. The system chunks the parsed clauses into retrieval-ready units, preserving clause hierarchy and metadata. Each chunk references its source clause, so the lawyer can trace retrieval results back to the original document structure.

**Why this priority**: Chunking is the bridge between parsing and retrieval. Without chunking, the retrieval pipeline cannot operate. This is the foundation for all retrieval-based review modes.

**Independent Test**: Can be tested by running a chunk command on a parsed contract and verifying the output contains chunks with correct clause references, hierarchy, and metadata.

**Acceptance Scenarios**:

1. **Given** a parsed contract with hierarchical clauses, **When** the user chunks it, **Then** the system produces chunks that respect clause boundaries — no chunk spans multiple top-level clauses
2. **Given** a clause that exceeds the target chunk size (512 tokens), **When** chunked, **Then** the system splits the clause at paragraph boundaries within the clause, preserving clause metadata in all sub-chunks
3. **Given** a parsed contract, **When** chunked, **Then** each chunk carries: source_clause_id, source_clause_title, source_clause_level, chunk_index_within_clause, and character offset range
4. **Given** a parsed contract, **When** chunked, **Then** peak memory usage for chunking logic stays under 10 MB (streaming, no accumulation)

---

### User Story 2 - Clause-Boundary-Aware Chunking (Priority: P1)

A lawyer reviews a contract with nested clauses (Article → Section → Sub-section → Clause). The chunking system respects the hierarchy — chunks preserve the clause hierarchy via parent_chunk_id references. When the retrieval pipeline returns a chunk, the lawyer sees the full context (which article, which section, which sub-section).

**Why this priority**: Hierarchical chunking improves retrieval accuracy by 5× (P-13). Flat chunking loses legal context — a clause about "termination" is meaningless without knowing which article it belongs to.

**Independent Test**: Can be tested by chunking a contract with known hierarchy and verifying that chunks preserve the nesting structure (parent_chunk_id references).

**Acceptance Scenarios**:

1. **Given** a contract with nested clauses (Article I → Section 1.1 → Sub-section (a)), **When** chunked, **Then** the system produces hierarchical chunks with correct parent_chunk_id chain: Article-level chunks reference no parent, Section-level chunks reference Article chunk, Sub-section chunks reference Section chunk
2. **Given** a hierarchical chunk structure, **When** a retrieval query returns a sub-section chunk, **Then** the chunk carries parent_chunk_id references so the system can reconstruct the full context (Article I → Section 1.1 → Sub-section (a))
3. **Given** a contract with 10 top-level articles, **When** chunked, **Then** the system produces at least 10 top-level chunks (one per article), plus sub-chunks for detailed content

---

### User Story 3 - Configurable Chunk Size (Priority: P2)

A lawyer is reviewing different contract types — a short NDA and a long MSA. The NDA has simple clauses that fit in small chunks; the MSA has complex clauses that need larger chunks to preserve context. The lawyer configures chunk size per contract type via config.yml.

**Why this priority**: Different contract types have different granularity needs. A one-size-fits-all chunk size wastes retrieval precision (too small) or context (too large).

**Independent Test**: Can be tested by configuring different chunk sizes in config.yml and verifying the chunking output respects the configuration.

**Acceptance Scenarios**:

1. **Given** a config.yml with `chunk_size: 512` (tokens), **When** a contract is chunked, **Then** chunks are approximately 512 tokens (±10% tolerance)
2. **Given** a config.yml with `chunk_overlap: 50` (tokens), **When** a contract is chunked, **Then** consecutive chunks within the same clause overlap by approximately 50 tokens
3. **Given** a config.yml with per-mode chunk size overrides (e.g., `precheck.chunk_size: 256`), **When** the precheck mode chunks a contract, **Then** chunks are approximately 256 tokens

---

### User Story 4 - Chunking After PII Stripping (Priority: P1)

A lawyer has stripped PII from a contract (names replaced with [PARTY_1], [PARTY_2], etc.). The chunking system operates on the stripped text, preserving PII placeholders. When the retrieval pipeline returns a chunk, the lawyer sees the redacted text — no PII leakage.

**Why this priority**: The privacy-first architecture requires PII stripping before any external API call. Chunking must operate on stripped text to maintain this guarantee.

**Independent Test**: Can be tested by stripping PII from a contract, then chunking, and verifying that chunks contain PII placeholders (not raw PII).

**Acceptance Scenarios**:

1. **Given** a contract with PII stripped (placeholders like [PARTY_1], [DATE_1]), **When** chunked, **Then** chunks contain the placeholders, not raw PII
2. **Given** a PII-stripped contract, **When** chunked, **Then** chunk text length includes placeholder tokens (placeholders are treated as regular tokens)
3. **Given** a contract with PII mapping (encrypted), **When** chunked, **Then** the chunking process does not modify or expose the PII mapping

---

### User Story 5 - Chunk Command with Output Options (Priority: P3)

A lawyer wants to chunk a parsed contract and see the output in different formats — a human-readable summary for quick inspection, or a structured format (JSON) for piping into the retrieval pipeline.

**Why this priority**: Output flexibility is useful for debugging and integration but not blocking for the core chunking functionality.

**Independent Test**: Can be tested by running a chunk command with `--format json` and verifying valid JSON output with the expected chunk structure.

**Acceptance Scenarios**:

1. **Given** a parsed contract, **When** the user runs the chunk command (default format), **Then** the system displays a human-readable summary: "Chunked {n} clauses into {m} chunks (avg size: {s} tokens)"
2. **Given** a parsed contract, **When** the user runs the chunk command with `--format json`, **Then** the system outputs valid JSON as a flat array of chunk objects with clause references and hierarchy
3. **Given** a parsed contract, **When** the user runs the chunk command with `--summary`, **Then** the system displays a one-line summary: "Chunked {n} clauses into {m} chunks in {t}s"

---

### Edge Cases

- What happens when a contract has no detectable clause structure (flat text)? The system treats each paragraph as a clause (level 0) and chunks accordingly — each paragraph becomes one or more chunks.
- What happens when a single paragraph exceeds the target chunk size? The system splits the paragraph at sentence boundaries (period + space), preserving sentence integrity. If a sentence exceeds chunk size, split at word boundaries with a warning.
- What happens when a contract has very short clauses (e.g., 10 tokens each)? The system groups consecutive short clauses into a single chunk if their combined size is below the target chunk size. Grouping respects hierarchy — clauses from different articles are never grouped.
- What happens when chunking is interrupted mid-document (Ctrl+C)? The system exits cleanly, no partial output is written, no temporary files are left behind.
- What happens when a clause contains only whitespace or empty text? The system skips the clause — no chunk is produced for empty content.
- What happens when the overlap size exceeds the chunk size? The system validates the configuration and exits with an error: "Overlap size (X tokens) must be less than chunk size (Y tokens)."
- What happens when a clause contains a table (e.g., payment schedule)? The system flattens table rows into text and includes them in the chunk. No data is lost — tables become inline text within the clause.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST chunk parsed clauses into retrieval-ready units, respecting clause boundaries — no chunk spans multiple top-level clauses unless the clause is split due to size constraints
- **FR-002**: System MUST use Recursive Character Text Splitting (RCTS) as the base chunking algorithm, with clause-boundary awareness as the primary splitting criterion
- **FR-003**: System MUST split clauses at paragraph boundaries (blank-line-separated blocks) when a clause exceeds the target chunk size
- **FR-004**: System MUST split paragraphs at sentence boundaries (period + space) when a paragraph exceeds the target chunk size
- **FR-005**: System MUST preserve clause metadata in all sub-chunks — each chunk carries: source_clause_id, source_clause_title, source_clause_level, chunk_index_within_clause, and character offset range
- **FR-006**: System MUST support hierarchical chunking — chunks preserve the clause hierarchy via parent_chunk_id references. Each chunk corresponds to a clause or sub-clause, maintaining the document structure (Article → Section → Sub-section → Clause). Each chunk carries metadata including its structural location within the hierarchy
- **FR-007**: System MUST apply token-based chunk sizing (default: 512 tokens) with configurable overlap (default: 50 tokens). Tokenization uses a simple whitespace + punctuation splitter (no external tokenizer dependency)
- **FR-008**: System MUST operate on PII-stripped text — chunking occurs after PII stripping, and chunks contain PII placeholders (not raw PII)
- **FR-009**: System MUST stream chunks one at a time — chunks are yielded via an iterator, never accumulated in memory. Peak memory for chunking logic: <10 MB
- **FR-010**: System MUST provide a CLI command for chunking a parsed contract and outputting the chunk structure
- **FR-011**: System MUST support `--format` flag on the chunk command with values: `text` (default, human-readable summary), `json` (structured output as a flat array of chunk objects)
- **FR-012**: System MUST support `--summary` flag on the chunk command to display a one-line chunking result (clause count, chunk count, duration)
- **FR-013**: System MUST support configurable chunk size and overlap via config.yml — `chunk_size` (tokens), `chunk_overlap` (tokens), with per-mode overrides (e.g., `precheck.chunk_size`)
- **FR-014**: System MUST validate chunking configuration — overlap size must be less than chunk size. Invalid configuration exits with error code 2
- **FR-015**: System MUST group consecutive short clauses into a single chunk if their combined size is below the target chunk size. Grouping respects hierarchy — clauses from different articles are never grouped
- **FR-016**: System MUST skip clauses with empty or whitespace-only text — no chunk is produced for empty content
- **FR-017**: System MUST handle Ctrl+C (SIGINT) during chunking by exiting cleanly — no partial output, no temporary files left behind
- **FR-018**: System MUST display a progress indicator during chunking (e.g., "Chunking clause 12 of 47") so the user never sees a frozen screen
- **FR-019**: System MUST expose an internal `stream_chunks(clauses) -> Iterator[Chunk]` generator as the core chunking API. The CLI command wraps this generator — downstream pipeline stages call the generator directly
- **FR-020**: Chunking MUST use memory-efficient data classes (e.g., `@dataclass(slots=True)`) for Chunk objects to minimize per-chunk memory overhead
- **FR-021**: System MUST detect table-like patterns (3+ consecutive lines with aligned columns separated by 2+ spaces) and flatten table rows into text (e.g., "Row 1: col1=val1, col2=val2") so that tabular data is preserved in chunks rather than skipped. Detection is best-effort; if uncertain, treat as regular text.

### Key Entities

- **Chunk**: The fundamental unit of retrieval-ready content. Key attributes: id (unique within document, format "chunk-{n}" auto-incremented), text (chunk text content), token_count (number of tokens in chunk), source_clause_id (reference to source clause), source_clause_title (clause title or None), source_clause_level (clause hierarchy level), chunk_index_within_clause (0, 1, 2... for sub-chunks), char_offset_start (character offset within clause text), char_offset_end (character offset within clause text), parent_chunk_id (reference to parent chunk for hierarchical structure, None for top-level). Relationships: has zero or one parent chunk, has zero or more child chunks, belongs to exactly one source clause.
- **ChunkConfig**: Configuration for chunking behavior. Key attributes: chunk_size (target tokens per chunk, default 512), chunk_overlap (overlap tokens between consecutive chunks, default 50), group_short_clauses (boolean, default true), respect_clause_boundaries (boolean, default true). Relationships: none.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can chunk a 50-page parsed contract into retrieval-ready units in under 2 seconds on the reference hardware
- **SC-002**: Chunking respects clause boundaries — 100% of top-level chunks correspond to single top-level clauses (no cross-clause spanning)
- **SC-003**: Chunking preserves clause hierarchy — each chunk carries source_clause_id and parent_chunk_id references that reconstruct the full document structure
- **SC-004**: Chunking operates on PII-stripped text — 100% of chunks contain PII placeholders, not raw PII
- **SC-005**: Chunking memory usage stays under 10 MB (peak) for any document size — streaming, no accumulation
- **SC-006**: Retrieval Precision@5 >=90% on the benchmark dataset (measured after retrieval pipeline is built, using chunked contracts from this phase)
- **SC-007**: Chunk size accuracy — 90% of chunks are within ±10% of the target chunk size (512 tokens default)
- **SC-008**: All chunking tests (unit + integration) pass in CI, with integration tests exercising real parsed contracts from `tests/fixtures/`

## Assumptions

- Chunking operates on parsed clauses from Phase 2 (document parsing) and PII-stripped text from Phase 3. The chunking pipeline is: parse -> strip PII -> chunk -> retrieve -> generate
- The `stream_clauses(path) -> Iterator[Clause]` generator from Phase 2 is the input to chunking. The `stream_chunks(clauses) -> Iterator[Chunk]` generator is the output
- Tokenization uses a simple whitespace + punctuation splitter (no external tokenizer like tiktoken). This is sufficient for legal text and avoids adding dependencies. Token count is approximate (±5% vs. GPT tokenizer)
- Chunk size is measured in tokens, not characters. 512 tokens ≈ 2,000 characters for English legal text (average 4 characters per token including spaces)
- Hierarchical chunking produces a tree structure mirroring the document hierarchy: Article-level chunks -> Section-level chunks -> Sub-section chunks -> Clause chunks. Each level references its parent via parent_chunk_id. Each chunk carries metadata (structural location, document position) per PAKTON's approach (P-13)
- Overlap is applied within clauses, not across clause boundaries. Consecutive chunks within the same clause overlap by 50 tokens; chunks from different clauses do not overlap
- Short clause grouping: if consecutive clauses from the same article have combined size < target chunk size, they are grouped into a single chunk. This reduces fragmentation for contracts with many short clauses
- PII placeholders (e.g., [PARTY_1], [DATE_1]) are treated as regular tokens during chunking. Placeholder length is included in token count
- Chunking configuration (chunk_size, chunk_overlap) is stored in config.yml and can be overridden per mode (e.g., precheck.chunk_size). Default values are 512 tokens and 50 tokens overlap
- The chunking logic lives in `src/openreview_cli/chunking/` module. The CLI glue lives in `src/openreview_cli/app.py`
- Chunking is independent of the retrieval pipeline — it produces chunks, but does not perform retrieval. The retrieval pipeline consumes chunks
- TDD workflow: integration tests are written first (they FAIL because no chunking logic exists), then the chunking implementation makes them PASS. Unit tests cover individual functions (RCTS algorithm, clause-boundary splitting, hierarchy construction). All tests run in CI
- Research backing: P-9 shows chunking strategy dominates retrieval quality (RCTS outperforms naive approaches). T-8 shows hierarchical chunking improves accuracy 5×. This spec implements both findings
