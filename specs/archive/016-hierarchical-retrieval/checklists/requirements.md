# Requirements Validation Checklist: NX-2 Hierarchical Retrieval Pipeline

**Purpose**: Validate that the spec.md for NX-2 covers all functional requirements, success criteria, edge cases, and blueprint references.
**Created**: 2026-07-03
**Feature**: [specs/016-hierarchical-retrieval/spec.md](../spec.md)

## Structure

- [x] CHK001 Feature title matches [PR-2]/[T-3] naming — "Hierarchical Retrieval Pipeline — BM25 + Dense + LightRAG + RRF"
- [x] CHK002 Status line present (Draft Specification)
- [x] CHK003 Blueprint References section at top lists all relevant citations
- [x] CHK004 Executive Summary explains what the feature does and why it matters
- [x] CHK005 Comparison table vs existing capability (single-party review)

## User Scenarios & Testing

- [x] CHK006 At least 3 user scenarios with assigned priorities (P1/P2/P3)
- [x] CHK007 Each scenario has a priority, rationale, and independent test description
- [x] CHK008 Each scenario has acceptance scenarios in Given/When/Then format
- [x] CHK009 Edge cases section present with failure scenarios
- [x] CHK010 Scenario 1 is P1 — open-ended clause search (core value)

## Requirements

- [x] CHK011 Functional Requirements (FR-001+) cover all pipeline stages (ingestion, sparse, dense, hybrid, reranking, CLI)
- [x] CHK012 FR-001 defines hybrid retrieval pipeline with sparse/dense/hybrid methods
- [x] CHK013 FR-002 defines sparse retrieval via BM25 (SQLite FTS5)
- [x] CHK014 FR-003 defines dense retrieval via embedding similarity (Ollama)
- [x] CHK015 FR-004 defines RRF (Reciprocal Rank Fusion) with formula
- [x] CHK016 FR-005 defines reranker (LightRAG) with experimental/validation requirement (P-9)
- [x] CHK017 FR-006 defines ingestion pipeline (chunk → embed → index)
- [x] CHK018 FR-007 defines SQLite storage schema
- [x] CHK019 FR-008 defines CLI commands
- [x] CHK020 FR-009 defines validation benchmark integration

## Blueprint Citations

- [x] CHK021 Every requirement cites at least one blueprint reference
- [x] CHK022 P-9 cited for reranker validation requirement
- [x] CHK023 P-13 cited for hierarchical chunking
- [x] CHK024 T-8 cited for chunking strategy importance
- [x] CHK025 Speckit Seed (§11) cited for pipeline architecture
- [x] CHK026 All built dependencies cited (C-07, C-08, C-12, C-32)

## Constitution Compliance

- [x] CHK027 No forbidden dependencies (no FAISS, langchain, sentence-transformers)
- [x] CHK128 Principle I (Privacy First) — no PII in retrieval pipeline; chunking operates on stripped text per spec 007
- [x] CHK029 Principle II (Local-First) — BM25 works offline; dense requires local Ollama or falls back
- [x] CHK030 Principle III (Hardware-Bounded) — stream-and-discard architecture; memory budget cited
- [x] CHK031 Principle IV (Dependency Minimalism) — SQLite FTS5 (stdlib), no vector library; cosine loop in Python
- [x] CHK032 Principle V (Spec-Driven) — spec references spec 007 and spec 010 as dependencies

## Success Criteria

- [x] CHK033 At least 5 measurable success criteria defined
- [x] CHK034 Criteria are technology-agnostic
- [x] CHK035 Precision@5 ≥90% target included
- [x] CHK036 Memory budget (<100 MB) included
- [x] CHK037 Reranker validation criterion (must not degrade) included
- [x] CHK038 Performance targets (<1s BM25, <10s ingestion) included
- [x] CHK039 Default reranker state = disabled validated

## Edge Cases & Failure Handling

- [x] CHK040 No embedding model available
- [x] CHK041 Document not indexed
- [x] CHK042 Query returns no results
- [x] CHK043 Corrupt/missing index database
- [x] CHK044 Reranker validation failure
- [x] CHK045 Very large documents (>5,000 chunks)
- [x] CHK046 Interrupted ingestion

## Out of Scope

- [x] CHK047 Cross-document retrieval explicitly deferred
- [x] CHK048 Vector index acceleration explicitly out (no FAISS)
- [x] CHK049 RAG (Retrieval-Augmented Generation) explicitly deferred
- [x] CHK050 All scope deferrals are explicit, not implied

## Assumptions

- [x] CHK051 Assumptions section present with 9 documented items
- [x] CHK052 SQLite FTS5 sufficiency assumption stated
- [x] CHK053 Cosine similarity performance assumption stated
- [x] CHK054 Ollama dependency assumption stated
- [x] CHK055 Re-indexing assumption stated (user-initiated, not automatic)

## No [NEEDS CLARIFICATION] Markers

- [x] CHK056 No unresolved [NEEDS CLARIFICATION] markers remain
- [x] CHK057 All clarifications from the session are documented in the Clarifications section

## Risk Coverage

- [x] CHK058 Memory budget breach (R-3) addressed in risks and architecture
- [x] CHK059 SLM performance (R-7) addressed with BM25 fallback
- [x] CHK060 Reranker degradation (P-9) addressed with validation and opt-in default

## Notes

- All 60 checklist items pass.
- The spec.md is ready for the plan phase.
- Key design decisions (reranker disabled by default, SQLite FTS5 for BM25, cosine loop for dense) are documented with rationale and blueprint citations.
- No [NEEDS CLARIFICATION] markers — all design decisions have informed defaults documented in Assumptions.
