"""Tests for D-10: redline-to-clause mapping."""

from openreview_cli.parsing.models import Clause


def _make_clause(
    id: str,
    text: str,
    span: tuple[int, int] | None = None,
    para: int = 0,
) -> Clause:
    return Clause(
        id=id,
        title=None,
        text=text,
        level=0,
        parent_id=None,
        source_page=None,
        source_paragraph=para,
        source_span=span,
        paragraph_count=1,
    )


class TestMapRedlinesToClauses:
    def test_empty_changes_empty_clauses(self) -> None:
        from openreview_cli.bilateral.comparison import map_redlines_to_clauses

        result = map_redlines_to_clauses([], [])
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_empty_changes_returns_all_empty(self) -> None:
        from openreview_cli.bilateral.comparison import map_redlines_to_clauses

        clauses = [
            _make_clause("c1", "First clause text here.", span=(0, 23)),
            _make_clause("c2", "Second clause here longer.", span=(24, 50)),
        ]
        result = map_redlines_to_clauses([], clauses)
        assert len(result) == 2
        assert result["c1"] == []
        assert result["c2"] == []

    def test_change_mapped_to_correct_clause_by_position(self) -> None:
        from openreview_cli.bilateral.comparison import map_redlines_to_clauses
        from openreview_cli.parsing.models import TrackedChange

        clauses = [
            _make_clause("c1", "Party A clause zero text", span=(0, 24)),
            _make_clause("c2", "Party B clause here another", span=(25, 52)),
        ]
        changes = [
            TrackedChange(author="Alice", change_type="ins", text="new stuff", position=10),
        ]
        result = map_redlines_to_clauses(changes, clauses)
        assert "c1" in result
        assert len(result["c1"]) == 1
        assert result["c1"][0].author == "Alice"
        assert result["c1"][0].change_type == "ins"
        assert result["c1"][0].text == "new stuff"

    def test_change_outside_all_spans_falls_to_last_clause(self) -> None:
        from openreview_cli.bilateral.comparison import map_redlines_to_clauses
        from openreview_cli.parsing.models import TrackedChange

        clauses = [
            _make_clause("c1", "First clause.", span=(0, 12)),
            _make_clause("c2", "Second.", span=(13, 20)),
        ]
        changes = [TrackedChange(author="Bob", change_type="del", text="old", position=999)]
        result = map_redlines_to_clauses(changes, clauses)
        assert len(result["c2"]) == 1
        assert result["c2"][0].author == "Bob"

    def test_no_source_span_falls_back_to_paragraph_index(self) -> None:
        from openreview_cli.bilateral.comparison import map_redlines_to_clauses
        from openreview_cli.parsing.models import TrackedChange

        clauses = [
            _make_clause("c1", "Paragraph zero text.", para=0),
            _make_clause("c2", "Paragraph one text.", para=1),
        ]
        changes = [TrackedChange(author="User", change_type="ins", text="addition", position=0)]
        result = map_redlines_to_clauses(changes, clauses)
        assert "c1" in result
