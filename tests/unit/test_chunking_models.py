from openreview_cli.chunking.models import Chunk, ChunkConfig


def test_chunk_fields() -> None:
    chunk = Chunk(
        id="chunk-0",
        text="Test text",
        token_count=2,
        source_clause_id="clause-1",
        source_clause_title="Title",
        source_clause_level=0,
        chunk_index_within_clause=0,
        char_offset_start=0,
        char_offset_end=9,
        parent_chunk_id=None,
        structural_location="Article_I/Section_1",
    )
    assert chunk.id == "chunk-0"
    assert chunk.token_count == 2
    assert chunk.parent_chunk_id is None


def test_chunk_config_defaults() -> None:
    config = ChunkConfig()
    assert config.chunk_size == 512
    assert config.chunk_overlap == 50
    assert config.group_short_clauses is True
    assert config.respect_clause_boundaries is True


def test_chunk_config_custom() -> None:
    config = ChunkConfig(chunk_size=256, chunk_overlap=25)
    assert config.chunk_size == 256
    assert config.chunk_overlap == 25


def test_chunk_config_validation() -> None:
    import pytest

    with pytest.raises(ValueError):
        ChunkConfig(chunk_overlap=100, chunk_size=50)
