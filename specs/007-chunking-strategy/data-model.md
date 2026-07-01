# Data Model: Chunking

**Date**: 2026-07-01 | **Spec**: [spec.md](./spec.md)

## Chunk

The fundamental unit of retrieval-ready content.

```python
@dataclass(slots=True)
class Chunk:
    id: str                    # "chunk-{n}" auto-incremented, unique within document
    text: str                  # Chunk text content
    token_count: int           # Number of tokens (approximate, ±5%)
    source_clause_id: str      # Reference to source clause (e.g., "clause-3")
    source_clause_title: str | None  # Clause title/heading
    source_clause_level: int   # Clause hierarchy level (0 = top-level)
    chunk_index_within_clause: int    # 0, 1, 2... for sub-chunks
    char_offset_start: int     # Character offset within clause text
    char_offset_end: int       # Character offset within clause text
    parent_chunk_id: str | None       # Parent chunk reference for hierarchy
    structural_location: str | None   # e.g., "Article_II/Section_2.1/Subsection_(a)"
```

**Validation rules**:
- `id` must be unique within a single document
- `token_count` must be > 0
- `char_offset_start < char_offset_end`
- `chunk_index_within_clause` starts at 0 for the first chunk from a clause
- `parent_chunk_id` is `None` for top-level chunks
- `structural_location` is constructed from clause hierarchy + parent chunks

## ChunkConfig

Configuration for chunking behavior.

```python
@dataclass
class ChunkConfig:
    chunk_size: int = 512                    # Target tokens per chunk
    chunk_overlap: int = 50                  # Overlap tokens between consecutive chunks
    group_short_clauses: bool = True         # Merge consecutive short clauses
    respect_clause_boundaries: bool = True   # Don't split across top-level clauses
```

**Validation rules**:
- `chunk_overlap < chunk_size` (FR-014)
- `chunk_size > 0`
- `chunk_overlap >= 0`

## Relationships

```
Document (parsing.models)
  └── has many → Clause (parsing.models)
                   └── chunked into → Chunk (chunking.models)
                                       └── has parent → Chunk (optional)
```

## State Transitions

```
Clause → [RCTS splitter] → Chunk (with sub-chunks as needed)
                             └── All chunks yielded at once (no persistent state)
```

Chunks are ephemeral — generated on demand, consumed by retrieval pipeline, not persisted in this phase.
