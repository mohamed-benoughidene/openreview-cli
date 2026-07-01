import re
import warnings
from collections.abc import Iterator
from itertools import count

from openreview_cli.chunking.models import Chunk, ChunkConfig
from openreview_cli.chunking.tokenizer import count_tokens
from openreview_cli.parsing.models import Clause


def split_clause(clause: Clause, config: ChunkConfig) -> Iterator[Chunk]:
    raw_text = clause.text
    if not raw_text or not raw_text.strip():
        return
    text = flatten_tables(raw_text)

    token_count = count_tokens(text)
    if token_count <= config.chunk_size:
        yield _make_chunk(clause, text, 0, len(text), 0)
        return

    raw_chunks = _rcts_split(text, config.chunk_size)
    overlapped = _apply_overlap(text, raw_chunks, config.chunk_overlap)
    for i, (ctext, cstart, cend) in enumerate(overlapped):
        yield _make_chunk(clause, ctext, cstart, cend, i)


def group_short_clauses(clauses: list[Clause], config: ChunkConfig) -> list[list[Clause]]:
    if not config.group_short_clauses:
        return [[c] for c in clauses]

    grouped: list[list[Clause]] = []
    current_group: list[Clause] = []
    current_size = 0
    current_article: str | None = None

    for clause in clauses:
        article = _article_key(clause)
        clause_tokens = count_tokens(clause.text)

        if clause_tokens == 0:
            continue

        if clause_tokens >= config.chunk_size:
            if current_group:
                grouped.append(current_group)
                current_group = []
                current_size = 0
                current_article = None
            grouped.append([clause])
            continue

        if current_group and (
            article != current_article or current_size + clause_tokens > config.chunk_size
        ):
            grouped.append(current_group)
            current_group = []
            current_size = 0
            current_article = None

        current_group.append(clause)
        current_size += clause_tokens
        current_article = article

    if current_group:
        grouped.append(current_group)

    return grouped


def assign_parent_chunk_ids(chunks: list[Chunk], clauses_by_id: dict[str, Clause]) -> None:
    first_chunk_of_clause: dict[str, Chunk] = {}
    for chunk in chunks:
        if (
            chunk.source_clause_id not in first_chunk_of_clause
            or chunk.chunk_index_within_clause
            < first_chunk_of_clause[chunk.source_clause_id].chunk_index_within_clause
        ):
            first_chunk_of_clause[chunk.source_clause_id] = chunk

    for chunk in chunks:
        if chunk.chunk_index_within_clause > 0:
            chunk.parent_chunk_id = first_chunk_of_clause[chunk.source_clause_id].id
            continue
        clause = clauses_by_id.get(chunk.source_clause_id)
        if clause is None or clause.parent_id is None:
            chunk.parent_chunk_id = None
            continue
        parent_clause_id = clause.parent_id
        parent_chunk = first_chunk_of_clause.get(parent_clause_id)
        chunk.parent_chunk_id = parent_chunk.id if parent_chunk else None


def build_structural_location(
    chunk: Chunk, clause: Clause, clauses_by_id: dict[str, Clause]
) -> str:
    parts: list[str] = [clause.title or clause.id]
    current = clause
    visited: set[str] = set()
    while current.parent_id is not None and current.parent_id not in visited:
        visited.add(current.parent_id)
        parent = clauses_by_id.get(current.parent_id)
        if parent is None:
            break
        parts.insert(0, parent.title or parent.id)
        current = parent
    return "/".join(parts)


def _article_key(clause: Clause) -> str:
    if clause.parent_id is None:
        return clause.id
    return clause.parent_id


def _make_chunk(
    clause: Clause, text: str, char_start: int, char_end: int, chunk_index: int
) -> Chunk:
    return Chunk(
        id=f"chunk-{_chunk_counter()}",
        text=text,
        token_count=count_tokens(text),
        source_clause_id=clause.id,
        source_clause_title=clause.title,
        source_clause_level=clause.level,
        chunk_index_within_clause=chunk_index,
        char_offset_start=char_start,
        char_offset_end=char_end,
        parent_chunk_id=None,
        structural_location=None,
    )


class _ChunkIDCounter:
    def __init__(self) -> None:
        self._counter = count()

    def next(self) -> int:
        return next(self._counter)

    def reset(self) -> None:
        self._counter = count()


_chunk_ids = _ChunkIDCounter()
_chunk_counter = _chunk_ids.next


def flatten_tables(text: str) -> str:
    lines = text.split("\n")
    if len(lines) < 4:
        return text

    result: list[str] = []
    i = 0
    while i < len(lines):
        if _is_table_line(lines[i]) and _has_table_run(lines, i):
            table_start = i
            while i < len(lines) and _is_table_line(lines[i]):
                i += 1
            table_lines = lines[table_start:i]
            flattened = _flatten_table_lines(table_lines)
            result.append(flattened)
        else:
            result.append(lines[i])
            i += 1
    return "\n".join(result)


def _is_table_line(line: str) -> bool:
    parts = [p for p in line.split("  ") if p.strip()]
    return len(parts) >= 3


def _has_table_run(lines: list[str], start: int) -> bool:
    count = 0
    for j in range(start, min(start + 5, len(lines))):
        if _is_table_line(lines[j]):
            count += 1
        else:
            break
    return count >= 3


def _flatten_table_lines(lines: list[str]) -> str:
    rows: list[str] = []
    for idx, line in enumerate(lines):
        cols = [c.strip() for c in line.split("  ") if c.strip()]
        if cols:
            rows.append(
                f"Row {idx + 1}: " + ", ".join(f"col{i + 1}={v}" for i, v in enumerate(cols))
            )
    return " | ".join(rows)


def reset_chunk_counter() -> None:
    _chunk_ids.reset()


def _rcts_split(text: str, chunk_size: int) -> list[tuple[str, int, int]]:
    pieces = _split_by_separator(text, 0, len(text), chunk_size, ["\n\n", ". "])
    result: list[tuple[str, int, int]] = []
    for p_text, p_start, p_end in pieces:
        if count_tokens(p_text) <= chunk_size:
            result.append((p_text, p_start, p_end))
        else:
            result.extend(_split_by_words(text, p_start, p_end, chunk_size))
    return _merge_pieces(text, result, chunk_size)


def _split_by_separator(
    text: str, start: int, end: int, chunk_size: int, separators: list[str]
) -> list[tuple[str, int, int]]:
    if not separators:
        return [(text[start:end], start, end)]

    sep = separators[0]
    sep_len = len(sep)
    pieces: list[tuple[str, int, int]] = []
    seg_start = start

    while seg_start < end:
        sep_pos = text.find(sep, seg_start, end)
        if sep_pos == -1:
            pieces.append((text[seg_start:end], seg_start, end))
            break

        seg_text = text[seg_start:sep_pos]
        seg_tokens = count_tokens(seg_text)

        if seg_tokens > chunk_size and len(separators) > 1:
            pieces.extend(_split_by_separator(text, seg_start, sep_pos, chunk_size, separators[1:]))
        else:
            pieces.append((seg_text, seg_start, sep_pos))

        seg_start = sep_pos + sep_len

    return pieces


def _split_by_words(text: str, start: int, end: int, chunk_size: int) -> list[tuple[str, int, int]]:
    warnings.warn(
        f"Sentence exceeds chunk size ({chunk_size} tokens), splitting at word boundaries",
        stacklevel=2,
    )

    token_re = re.compile(r"\w+|[^\w\s]")
    tokens = list(token_re.finditer(text[start:end]))
    if not tokens:
        return [(text[start:end], start, end)]

    result: list[tuple[str, int, int]] = []
    chunk_token_start = 0
    while chunk_token_start < len(tokens):
        chunk_token_end = min(chunk_token_start + chunk_size, len(tokens))
        word_start = start + tokens[chunk_token_start].start()
        word_end = start + tokens[chunk_token_end - 1].end()
        chunk_text = text[word_start:word_end]
        if chunk_text.strip():
            result.append((chunk_text, word_start, word_end))
        chunk_token_start = chunk_token_end

    if not result:
        result.append((text[start:end], start, end))

    return result


def _apply_overlap(
    source_text: str,
    raw_chunks: list[tuple[str, int, int]],
    chunk_overlap: int,
) -> list[tuple[str, int, int]]:
    if chunk_overlap == 0 or len(raw_chunks) <= 1:
        return raw_chunks

    token_re = re.compile(r"\w+|[^\w\s]")
    tokens = list(token_re.finditer(source_text))
    if not tokens:
        return raw_chunks

    result: list[tuple[str, int, int]] = [raw_chunks[0]]
    for i in range(1, len(raw_chunks)):
        prev_end = raw_chunks[i - 1][2]
        prev_text = source_text[:prev_end]
        prev_token_list = list(token_re.finditer(prev_text))

        if len(prev_token_list) <= chunk_overlap:
            overlap_start = 0
        else:
            overlap_start = prev_token_list[-chunk_overlap].start()

        current_start = raw_chunks[i][1]
        overlap_text = source_text[overlap_start:current_start]
        if overlap_text.strip():
            chunk_text = overlap_text + raw_chunks[i][0]
            result.append((chunk_text, raw_chunks[i][1], raw_chunks[i][2]))
        else:
            result.append(raw_chunks[i])

    return result


def _merge_pieces(
    text: str,
    pieces: list[tuple[str, int, int]],
    chunk_size: int,
) -> list[tuple[str, int, int]]:
    if not pieces:
        return pieces

    merged: list[tuple[str, int, int]] = []
    current_pieces: list[tuple[str, int, int]] = []
    current_tokens = 0

    for p_text, p_start, p_end in pieces:
        p_tokens = count_tokens(p_text)
        if p_tokens == 0:
            continue

        if current_tokens + p_tokens <= chunk_size:
            current_pieces.append((p_text, p_start, p_end))
            current_tokens += p_tokens
        else:
            if current_pieces:
                merged.append(_join_pieces(current_pieces))
            current_pieces = [(p_text, p_start, p_end)]
            current_tokens = p_tokens

    if current_pieces:
        merged.append(_join_pieces(current_pieces))

    return merged


def _join_pieces(pieces: list[tuple[str, int, int]]) -> tuple[str, int, int]:
    first_start = pieces[0][1]
    last_end = pieces[-1][2]
    texts = [p[0] for p in pieces]
    joined = "\n\n".join(texts)
    return (joined, first_start, last_end)
