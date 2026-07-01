# API Contract: Chunking Module

**Date**: 2026-07-01 | **Spec**: [spec.md](../spec.md)

## Internal API: `stream_chunks()`

```python
def stream_chunks(
    clauses: Iterator[Clause],
    config: ChunkConfig | None = None,
) -> Iterator[Chunk]:
    """Stream chunks from parsed clauses.
    
    Args:
        clauses: Iterator of Clause objects (from parsing.stream.stream_clauses)
        config: Optional ChunkConfig (defaults to 512 token chunks, 50 overlap)
    
    Yields:
        Chunk objects one at a time — never accumulated in memory.
    
    Raises:
        ValueError: If config.chunk_overlap >= config.chunk_size
    """
```

**Input contract**:
- `clauses` must yield `Clause` objects (from `openreview_cli.parsing.stream.stream_clauses`)
- `config` is optional; defaults match `ChunkConfig()`

**Output contract**:
- Each `Chunk` yields valid `Chunk` with all fields populated
- Chunks are yielded in document order (same order as input clauses)
- Sub-chunks from the same clause are yielded consecutively
- The iterator does `not` buffer — one chunk in memory at a time

## CLI Contract

```bash
openreview chunk <path> [--format text|json] [--summary]
```

| Argument | Description |
|----------|-------------|
| `<path>` | Path to parsed contract file |
| `--format` | Output format: `text` (default, human-readable), `json` (flat array) |
| `--summary` | One-line summary: "Chunked {n} clauses into {m} chunks in {t}s" |

**Exit codes**:
- `0`: Success
- `2`: Invalid configuration (overlap >= chunk size)
- `1`: Internal error
