# Research: PII-to-Chunk Pipeline Bridge

**Date**: 2026-07-01

## Decisions

### 1. Implementation Strategy: Reuse detect_all_pages + per-clause replacement

**Decision**: Reuse the existing `PiiEngine.detect_all_pages()` for entity detection, then do text replacement per-clause instead of on the joined blob.

**Rationale**:
- `detect_all_pages()` already returns entities with offsets relative to each clause's text (adjusted via the overlap buffer at engine.py:155-157)
- The existing `strip_pii()` does: detect_all_pages → assign_placeholders → replace on joined text
- The bridge does: detect_all_pages → assign_placeholders → replace per-clause text
- This is the minimal code change — ~15 lines of new logic in engine.py

**Alternatives Considered**:
- Modify `detect_all_pages()` to return per-clause entity groups: More invasive, changes existing API surface
- Re-run detection per-clause from scratch: Duplicates work, potentially slower
- Offset-based mapping on joined text with clause boundary tracking: More complex, fragile

### 2. Error Handling: Partial results on per-clause failure

**Decision**: If PII detection fails on some clauses, return stripped clauses for successes with a warning (matching existing `strip_pii()` behavior).

**Rationale**: Consistency with the existing contract. The existing `strip_pii()` already tolerates `failed_pages` and returns partial results with warnings.

### 3. Audit Detail: Reuse existing document-level audit

**Decision**: No per-clause audit breakdown. The existing `build_audit()` produces entity counts, which are sufficient.

**Rationale**: No current consumer requires per-clause audit granularity. Adds complexity without benefit.

### 4. PiiResult.stripped_text: Joined stripped clauses

**Decision**: `PiiResult.stripped_text` contains the joined text of all stripped clauses (space-separated), matching the existing `strip_pii()` output format.

**Rationale**: Callers reading `PiiResult.stripped_text` get a consistent value regardless of whether they called `strip_pii()` or `strip_pii_clauses()`.
