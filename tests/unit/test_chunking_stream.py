from openreview_cli.chunking.models import ChunkConfig
from openreview_cli.parsing.models import Clause


def test_stream_chunks_empty() -> None:
    from openreview_cli.chunking.stream import stream_chunks

    config = ChunkConfig()
    chunks = list(stream_chunks([], config))
    assert len(chunks) == 0


def test_stream_chunks_single_clause() -> None:
    from openreview_cli.chunking.stream import stream_chunks

    clause = Clause(
        id="clause-1",
        title="Test",
        text="hello world",
        level=0,
        parent_id=None,
        source_page=None,
        source_paragraph=None,
        source_span=None,
    )
    config = ChunkConfig(chunk_size=512)
    chunks = list(stream_chunks([clause], config))
    assert len(chunks) == 1
    assert chunks[0].source_clause_id == "clause-1"


def test_stream_chunks_multiple_clauses() -> None:
    from openreview_cli.chunking.stream import stream_chunks

    clauses = [
        Clause(
            id=f"c-{i}",
            title=f"Section {i}",
            text="This is a test clause with some content for chunking." * 5,
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=None,
            source_span=None,
        )
        for i in range(3)
    ]
    config = ChunkConfig(chunk_size=20, chunk_overlap=0)
    chunks = list(stream_chunks(clauses, config))
    assert len(chunks) >= 3
    for c in chunks:
        assert c.source_clause_id in ("c-0", "c-1", "c-2")


def test_pii_placeholders_preserved() -> None:
    from openreview_cli.chunking.stream import stream_chunks

    clause = Clause(
        id="clause-1",
        title="NDA",
        text="[PARTY_1] and [PARTY_2] agree that [DATE_1] is the effective date.",
        level=0,
        parent_id=None,
        source_page=None,
        source_paragraph=None,
        source_span=None,
    )
    config = ChunkConfig(chunk_size=512)
    chunks = list(stream_chunks([clause], config))
    assert len(chunks) == 1
    assert "[PARTY_1]" in chunks[0].text
    assert "[PARTY_2]" in chunks[0].text
    assert "[DATE_1]" in chunks[0].text


def test_chunk_size_accuracy() -> None:
    """SC-007: 90% of chunks are within ±10% of target chunk size (512 tokens)."""
    from openreview_cli.chunking.stream import stream_chunks

    sentence = "The quick brown fox jumps over the lazy dog near the riverbank. " * 20
    clause = Clause(
        id="accuracy-clause",
        title="Long Article",
        text=sentence * 30,
        level=0,
        parent_id=None,
        source_page=None,
        source_paragraph=None,
        source_span=None,
    )
    config = ChunkConfig(chunk_size=512, chunk_overlap=0)
    chunks = list(stream_chunks([clause], config))

    assert len(chunks) > 1, "Should produce multiple chunks from oversized clause"

    target = 512
    lower = int(target * 0.9)
    upper = int(target * 1.1)
    within_range = sum(1 for c in chunks if lower <= c.token_count <= upper)
    ratio = within_range / len(chunks)
    assert ratio >= 0.9, (
        f"Only {within_range}/{len(chunks)} chunks ({ratio:.1%}) within "
        f"+/-10% of {target} tokens (range {lower}-{upper})"
    )


def test_hierarchy_preserved_in_stream() -> None:
    from openreview_cli.chunking.stream import stream_chunks

    clauses = [
        Clause(
            id="art-1",
            title="Article I",
            text="Article one content.",
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=None,
            source_span=None,
        ),
        Clause(
            id="sec-1.1",
            title="Section 1.1",
            text="Section one point one.",
            level=1,
            parent_id="art-1",
            source_page=None,
            source_paragraph=None,
            source_span=None,
        ),
    ]
    config = ChunkConfig(chunk_size=512, chunk_overlap=0)
    chunks = list(stream_chunks(clauses, config))
    assert len(chunks) == 2
    article_chunk = chunks[0]
    section_chunk = chunks[1]
    assert article_chunk.parent_chunk_id is None
    assert section_chunk.parent_chunk_id == "chunk-0"
    assert section_chunk.structural_location == "Article I/Section 1.1"
