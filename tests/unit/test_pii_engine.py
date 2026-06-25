"""Unit tests for PII stripping engine."""

from pathlib import Path
from unittest.mock import patch

from openreview_cli.parsing.models import Clause, Document
from openreview_cli.pii.engine import PiiEngine, strip_pii


class TestStripPii:
    """Tests for the strip_pii top-level function."""

    def test_strip_skipped_when_disabled(self) -> None:
        """When PII stripping is disabled, no entities are detected and a warning is emitted."""
        clause = Clause(
            id="1",
            title=None,
            text="John Smith works at ABC Corp.",
            level=1,
            parent_id=None,
            source_page=1,
            source_paragraph=None,
            source_span=None,
        )
        doc = Document(
            source_path=Path("/tmp/test.pdf"),
            format="pdf",
            page_count=1,
            clause_count=1,
            parse_duration_seconds=0.1,
            warnings=[],
        )

        engine = PiiEngine(threshold=0.7)
        with patch.object(
            engine, "detect_all_pages", return_value=([], ["PII detection disabled"])
        ):
            result = strip_pii([clause], doc, strip_metadata=False, engine=engine)

        assert any("disabled" in w for w in result.warnings)
        assert result.mapping == {}
        assert result.stripped_text == "John Smith works at ABC Corp."
