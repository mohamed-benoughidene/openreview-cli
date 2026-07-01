from dataclasses import dataclass


@dataclass(slots=True)
class Chunk:
    id: str
    text: str
    token_count: int
    source_clause_id: str
    source_clause_title: str | None
    source_clause_level: int
    chunk_index_within_clause: int
    char_offset_start: int
    char_offset_end: int
    parent_chunk_id: str | None
    structural_location: str | None

    def __post_init__(self) -> None:
        if self.token_count <= 0:
            raise ValueError(f"token_count must be > 0, got {self.token_count}")
        if self.char_offset_start >= self.char_offset_end:
            raise ValueError(
                f"char_offset_start ({self.char_offset_start}) must be < "
                f"char_offset_end ({self.char_offset_end})"
            )
        if self.chunk_index_within_clause < 0:
            raise ValueError(
                f"chunk_index_within_clause must be >= 0, got {self.chunk_index_within_clause}"
            )


@dataclass
class ChunkConfig:
    chunk_size: int = 512
    chunk_overlap: int = 50
    group_short_clauses: bool = True
    respect_clause_boundaries: bool = True

    def __post_init__(self) -> None:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be < chunk_size ({self.chunk_size})"
            )
        if self.chunk_size <= 0:
            raise ValueError(f"chunk_size must be > 0, got {self.chunk_size}")
        if self.chunk_overlap < 0:
            raise ValueError(f"chunk_overlap must be >= 0, got {self.chunk_overlap}")
