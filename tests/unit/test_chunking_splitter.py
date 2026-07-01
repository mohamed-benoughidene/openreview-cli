from openreview_cli.chunking.models import Chunk, ChunkConfig
from openreview_cli.parsing.models import Clause


def test_split_clause_small() -> None:
    from openreview_cli.chunking.splitter import split_clause

    clause = Clause(
        id="clause-1",
        title="Short Clause",
        text="hello world",
        level=0,
        parent_id=None,
        source_page=None,
        source_paragraph=None,
        source_span=None,
    )
    config = ChunkConfig()
    chunks = list(split_clause(clause, config))
    assert len(chunks) == 1
    assert chunks[0].source_clause_id == "clause-1"
    assert chunks[0].token_count == 2


def test_split_clause_multi_paragraph() -> None:
    from openreview_cli.chunking.splitter import split_clause

    clause = Clause(
        id="clause-1",
        title="Long Clause",
        text="First paragraph with some content.\n\nSecond paragraph that is longer.\n\nThird paragraph here.",
        level=0,
        parent_id=None,
        source_page=None,
        source_paragraph=None,
        source_span=None,
    )
    config = ChunkConfig(chunk_size=5, chunk_overlap=0)
    chunks = list(split_clause(clause, config))
    assert len(chunks) > 1
    for c in chunks:
        assert c.source_clause_id == "clause-1"


def test_group_short_clauses_same_article() -> None:
    from openreview_cli.chunking.splitter import group_short_clauses

    clauses = [
        Clause(
            id=f"c-{i}",
            title=f"Section {i}",
            text="hello world",
            level=0,
            parent_id="article-1",
            source_page=None,
            source_paragraph=None,
            source_span=None,
        )
        for i in range(2)
    ]
    clauses.append(
        Clause(
            id="c-2",
            title="Section 2",
            text="a" * 500,
            level=0,
            parent_id="article-2",
            source_page=None,
            source_paragraph=None,
            source_span=None,
        )
    )
    config = ChunkConfig(chunk_size=50, chunk_overlap=0)
    groups = group_short_clauses(clauses, config)
    assert len(groups) == 2  # first two merged (same article), third stays alone
    assert len(groups[0]) == 2
    assert len(groups[1]) == 1


def test_assign_parent_ids_level0() -> None:
    from openreview_cli.chunking.splitter import assign_parent_chunk_ids

    chunks = [
        Chunk(
            id="chunk-0",
            text="Article I",
            token_count=2,
            source_clause_id="art-1",
            source_clause_title="Article I",
            source_clause_level=0,
            chunk_index_within_clause=0,
            char_offset_start=0,
            char_offset_end=9,
            parent_chunk_id=None,
            structural_location=None,
        ),
    ]
    clauses_by_id = {
        "art-1": Clause(
            id="art-1",
            title="Article I",
            text="Article I",
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=None,
            source_span=None,
        ),
    }
    assign_parent_chunk_ids(chunks, clauses_by_id)
    assert chunks[0].parent_chunk_id is None


def test_assign_parent_ids_child_refers_to_parent() -> None:
    from openreview_cli.chunking.splitter import assign_parent_chunk_ids

    chunks = [
        Chunk(
            id="chunk-0",
            text="Article I",
            token_count=2,
            source_clause_id="art-1",
            source_clause_title="Article I",
            source_clause_level=0,
            chunk_index_within_clause=0,
            char_offset_start=0,
            char_offset_end=9,
            parent_chunk_id=None,
            structural_location=None,
        ),
        Chunk(
            id="chunk-1",
            text="Section 1.1",
            token_count=2,
            source_clause_id="sec-1.1",
            source_clause_title="Section 1.1",
            source_clause_level=1,
            chunk_index_within_clause=0,
            char_offset_start=0,
            char_offset_end=10,
            parent_chunk_id=None,
            structural_location=None,
        ),
    ]
    clauses_by_id = {
        "art-1": Clause(
            id="art-1",
            title="Article I",
            text="Article I",
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=None,
            source_span=None,
        ),
        "sec-1.1": Clause(
            id="sec-1.1",
            title="Section 1.1",
            text="Section 1.1",
            level=1,
            parent_id="art-1",
            source_page=None,
            source_paragraph=None,
            source_span=None,
        ),
    }
    assign_parent_chunk_ids(chunks, clauses_by_id)
    assert chunks[0].parent_chunk_id is None
    assert chunks[1].parent_chunk_id == "chunk-0"


def test_build_structural_location() -> None:
    from openreview_cli.chunking.splitter import build_structural_location

    clause = Clause(
        id="sec-1.1",
        title="Section 1.1",
        text="Section 1.1",
        level=1,
        parent_id="art-1",
        source_page=None,
        source_paragraph=None,
        source_span=None,
    )
    clauses_by_id = {
        "art-1": Clause(
            id="art-1",
            title="Article I",
            text="Article I",
            level=0,
            parent_id=None,
            source_page=None,
            source_paragraph=None,
            source_span=None,
        ),
        "sec-1.1": clause,
    }
    chunk = Chunk(
        id="chunk-0",
        text="Section 1.1",
        token_count=2,
        source_clause_id="sec-1.1",
        source_clause_title="Section 1.1",
        source_clause_level=1,
        chunk_index_within_clause=0,
        char_offset_start=0,
        char_offset_end=10,
        parent_chunk_id=None,
        structural_location=None,
    )
    loc = build_structural_location(chunk, clause, clauses_by_id)
    assert loc == "Article I/Section 1.1"


def test_flatten_tables() -> None:
    from openreview_cli.chunking.splitter import flatten_tables

    table_text = "\n".join(
        [
            "Name          Age  City",
            "John          30   New York",
            "Jane          25   London",
            "Bob           35   Paris",
            "Some regular text after.",
        ]
    )
    result = flatten_tables(table_text)
    assert "Row 1" in result
    assert "Row 2" in result
    assert "Row 3" in result
    assert "col1=John" in result


def test_table_inside_clause() -> None:
    from openreview_cli.chunking.splitter import split_clause

    clause = Clause(
        id="clause-1",
        title="Payment Schedule",
        text="Amounts due:\nItem          Price  Qty\nWidget A      10.00  5\nWidget B      20.00  3\nWidget C      15.00  2\nTotal due: 155.00",
        level=0,
        parent_id=None,
        source_page=None,
        source_paragraph=None,
        source_span=None,
    )
    config = ChunkConfig(chunk_size=512, chunk_overlap=0)
    chunks = list(split_clause(clause, config))
    assert len(chunks) == 1
    assert "Row 1" in chunks[0].text


def test_flat_text_no_structure() -> None:
    from openreview_cli.chunking.splitter import split_clause

    clause = Clause(
        id="clause-1",
        title="Flat Text",
        text="This is a flat text with no structure at all. It just goes on and on without any paragraphs or headings.",
        level=0,
        parent_id=None,
        source_page=None,
        source_paragraph=None,
        source_span=None,
    )
    config = ChunkConfig(chunk_size=512, chunk_overlap=0)
    chunks = list(split_clause(clause, config))
    assert len(chunks) == 1


def test_oversized_paragraph() -> None:
    from openreview_cli.chunking.splitter import split_clause

    clause = Clause(
        id="clause-1",
        title="Long Paragraph",
        text="word " * 1000,
        level=0,
        parent_id=None,
        source_page=None,
        source_paragraph=None,
        source_span=None,
    )
    config = ChunkConfig(chunk_size=50, chunk_overlap=0)
    chunks = list(split_clause(clause, config))
    assert len(chunks) > 1
    for c in chunks:
        assert c.token_count <= 60  # allow slight variance
