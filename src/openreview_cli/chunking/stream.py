from collections.abc import Iterator

from rich.progress import Progress

from openreview_cli.chunking.models import Chunk, ChunkConfig
from openreview_cli.chunking.splitter import (
    build_structural_location,
    group_short_clauses,
    reset_chunk_counter,
    split_clause,
)
from openreview_cli.parsing.models import Clause


def _iter_group_chunks(
    groups: list[list[Clause]],
    resolved: ChunkConfig,
    clauses_by_id: dict[str, Clause],
    progress: Progress | None,
) -> Iterator[Chunk]:
    """Yield the chunks for *groups*, advancing *progress* when it is given."""
    task = (
        progress.add_task("Chunking clauses...", total=sum(len(g) for g in groups))
        if progress is not None
        else None
    )

    def _advance() -> None:
        if progress is not None and task is not None:
            progress.update(task, advance=1)

    first_chunks: dict[str, str] = {}
    for group in groups:
        for clause in group:
            if not clause.text or not clause.text.strip():
                _advance()
                continue
            for chunk in split_clause(clause, resolved):
                if chunk.source_clause_id not in first_chunks:
                    first_chunks[chunk.source_clause_id] = chunk.id
                if chunk.chunk_index_within_clause > 0:
                    chunk.parent_chunk_id = first_chunks.get(chunk.source_clause_id)
                elif clause.parent_id:
                    chunk.parent_chunk_id = first_chunks.get(clause.parent_id)
                chunk.structural_location = build_structural_location(chunk, clause, clauses_by_id)
                yield chunk
            _advance()


def stream_chunks(
    clauses: list[Clause] | Iterator[Clause],
    config: ChunkConfig | None = None,
    *,
    show_progress: bool = True,
) -> Iterator[Chunk]:
    """Yield chunks for *clauses*.

    ``show_progress=False`` suppresses the Rich progress bar, so callers that
    own the terminal (the Textual TUI) are not written over. The yielded
    chunks are identical either way.
    """
    resolved = config or ChunkConfig()
    if resolved.chunk_overlap >= resolved.chunk_size:
        raise ValueError(
            f"Overlap size ({resolved.chunk_overlap} tokens) must be less than "
            f"chunk size ({resolved.chunk_size} tokens)"
        )

    clause_list = list(clauses)
    reset_chunk_counter()
    clauses_by_id = {c.id: c for c in clause_list}

    groups = group_short_clauses(clause_list, resolved)

    if not show_progress:
        yield from _iter_group_chunks(groups, resolved, clauses_by_id, None)
        return

    with Progress(transient=True) as progress:
        yield from _iter_group_chunks(groups, resolved, clauses_by_id, progress)


def format_chunks_text(chunks: list[Chunk]) -> str:
    lines: list[str] = []
    for i, chunk in enumerate(chunks):
        title = chunk.source_clause_title or "(no title)"
        lines.append(f"Chunk {i}: [{title}] ({chunk.token_count} tokens)")
        lines.append(chunk.text)
        lines.append("")
    return "\n".join(lines)


def format_chunks_json(chunks: list[Chunk]) -> str:
    import json

    def _serialize(c: Chunk) -> dict[str, object]:
        return {
            "id": c.id,
            "text": c.text,
            "token_count": c.token_count,
            "source_clause_id": c.source_clause_id,
            "source_clause_title": c.source_clause_title,
            "source_clause_level": c.source_clause_level,
            "chunk_index_within_clause": c.chunk_index_within_clause,
            "char_offset_start": c.char_offset_start,
            "char_offset_end": c.char_offset_end,
            "parent_chunk_id": c.parent_chunk_id,
            "structural_location": c.structural_location,
        }

    return json.dumps([_serialize(c) for c in chunks], indent=2, ensure_ascii=False)


def format_chunks_summary(clause_count: int, chunk_count: int, duration: float) -> str:
    return f"Chunked {clause_count} clauses into {chunk_count} chunks in {duration:.2f}s"
