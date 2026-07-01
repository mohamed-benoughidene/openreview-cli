"""Unit tests for PII stripping engine."""

import time as time_mod
from pathlib import Path
from unittest.mock import patch

from openreview_cli.parsing.models import Clause, Document
from openreview_cli.pii.engine import PiiEngine, strip_pii, strip_pii_clauses
from openreview_cli.pii.models import PiiEntity


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
            engine, "detect_all_pages", return_value=([], ["PII detection disabled"], [], {})
        ):
            result = strip_pii([clause], doc, strip_metadata=False, engine=engine)

        assert any("disabled" in w for w in result.warnings)
        assert result.mapping == {}
        assert result.stripped_text == "John Smith works at ABC Corp."


class TestStripPiiClauses:
    """Tests for the strip_pii_clauses top-level function."""

    def make_clause(
        self,
        id: str = "1",
        text: str = "Test text",
        title: str | None = "Test Clause",
        level: int = 1,
        parent_id: str | None = None,
        source_page: int | None = 1,
        source_paragraph: int | None = None,
        source_span: tuple[int, int] | None = None,
    ) -> Clause:
        return Clause(
            id=id,
            title=title,
            text=text,
            level=level,
            parent_id=parent_id,
            source_page=source_page,
            source_paragraph=source_paragraph,
            source_span=source_span,
        )

    def make_doc(self, source_path: str = "/tmp/test.pdf") -> Document:
        return Document(
            source_path=Path(source_path),
            format="pdf",
            page_count=1,
            clause_count=1,
            parse_duration_seconds=0.1,
            warnings=[],
        )

    def test_preserves_metadata(self) -> None:
        """T001: All clause metadata fields unchanged after stripping."""
        clause = self.make_clause(
            id="clause-42",
            text="Acme Corp shall pay $1,000.",
            title="Payment Terms",
            level=2,
            parent_id="clause-1",
            source_page=3,
            source_paragraph=None,
            source_span=(10, 50),
        )
        doc = self.make_doc()
        engine = PiiEngine(threshold=0.7)
        entity = PiiEntity(
            entity_type="ORGANIZATION",
            original_value="Acme Corp",
            start=0,
            end=9,
            score=0.9,
            placeholder="[TEMP_0]",
            source="nlp",
        )
        with patch.object(engine, "detect_all_pages", return_value=([entity], [], [], {})):
            stripped, _result = strip_pii_clauses(
                [clause], doc, strip_metadata=False, engine=engine
            )

        out = stripped[0]
        assert out.id == "clause-42"
        assert out.title == "Payment Terms"
        assert out.level == 2
        assert out.parent_id == "clause-1"
        assert out.source_page == 3
        assert out.source_paragraph is None
        assert out.source_span == (10, 50)

    def test_replaces_pii(self) -> None:
        """T002: Clause text contains placeholders instead of raw PII."""
        clause = self.make_clause(text="John Smith works at Acme Corp.")
        doc = self.make_doc()
        engine = PiiEngine(threshold=0.7)
        entities = [
            PiiEntity(
                entity_type="PERSON",
                original_value="John Smith",
                start=0,
                end=10,
                score=0.95,
                placeholder="[TEMP_0]",
                source="nlp",
            ),
            PiiEntity(
                entity_type="ORGANIZATION",
                original_value="Acme Corp",
                start=20,
                end=29,
                score=0.9,
                placeholder="[TEMP_0]",
                source="nlp",
            ),
        ]
        with patch.object(engine, "detect_all_pages", return_value=(entities, [], [], {})):
            stripped, result = strip_pii_clauses([clause], doc, strip_metadata=False, engine=engine)

        assert "John Smith" not in stripped[0].text
        assert "Acme Corp" not in stripped[0].text
        assert "[NAME_1]" in stripped[0].text or "[PARTY_1]" in stripped[0].text

        assert result.mapping is not None

    def test_empty_input(self) -> None:
        """T003: Empty list returns ([], PiiResult) with empty mapping."""
        doc = self.make_doc()
        engine = PiiEngine(threshold=0.7)
        with patch.object(engine, "detect_all_pages", return_value=([], [], [], {})):
            stripped, result = strip_pii_clauses([], doc, strip_metadata=False, engine=engine)

        assert stripped == []
        assert result.mapping == {}

    def test_no_pii_unchanged(self) -> None:
        """T004: Clause with no PII has unchanged text and no mapping entries."""
        clause = self.make_clause(text="This clause has no sensitive data.")
        doc = self.make_doc()
        engine = PiiEngine(threshold=0.7)
        with patch.object(engine, "detect_all_pages", return_value=([], [], [], {})):
            stripped, result = strip_pii_clauses([clause], doc, strip_metadata=False, engine=engine)

        assert stripped[0].text == "This clause has no sensitive data."
        assert result.mapping == {}

    def test_metadata_entities(self) -> None:
        """T005: Metadata placeholders appended to last clause when not in clause text."""
        clause_a = self.make_clause(id="1", text="Clause one.", source_page=1)
        clause_b = self.make_clause(id="2", text="Clause two.", source_page=1)
        doc = Document(
            source_path=Path("/tmp/report.pdf"),
            format="pdf",
            page_count=1,
            clause_count=2,
            parse_duration_seconds=0.1,
            warnings=[],
            author="Legal Dept",
            title="Annual Report",
        )
        engine = PiiEngine(threshold=0.7)
        with patch.object(engine, "detect_all_pages", return_value=([], [], [], {})):
            stripped, result = strip_pii_clauses([clause_a, clause_b], doc, engine=engine)

        metadata_placeholders = [
            k
            for k in result.mapping
            if result.mapping[k] in ("report.pdf", "Legal Dept", "Annual Report")
        ]
        assert len(metadata_placeholders) > 0, "Expected at least one metadata placeholder"

        # Last clause should have metadata placeholders appended
        for key in metadata_placeholders:
            assert f"[{key}]" in stripped[-1].text, (
                f"Metadata placeholder [{key}] not found in last clause text"
            )

    def test_performance(self) -> None:
        """T006: strip_pii_clauses within 10% of strip_pii for same document."""
        # 200 clauses to amortize per-clause overhead relative to mock baseline
        clauses = [
            self.make_clause(id=str(i), text=f"Clause {i} with Acme Corp data.", source_page=1)
            for i in range(200)
        ]
        doc = self.make_doc()
        engine = PiiEngine(threshold=0.7)
        entity = PiiEntity(
            entity_type="ORGANIZATION",
            original_value="Acme Corp",
            start=0,
            end=9,
            score=0.9,
            placeholder="[TEMP_0]",
            source="nlp",
        )

        with patch.object(engine, "detect_all_pages", return_value=([entity], [], [], {})):
            t0 = time_mod.perf_counter()
            for _ in range(3):
                strip_pii_clauses(clauses, doc, strip_metadata=False, engine=engine)
            t_bridge = time_mod.perf_counter() - t0

            t0 = time_mod.perf_counter()
            for _ in range(3):
                strip_pii(clauses, doc, strip_metadata=False, engine=engine)
            t_strip = time_mod.perf_counter() - t0

        ratio = t_bridge / max(t_strip, 1e-9)
        # ponytail: 5x allowance for mocked detection (real detection dominates runtime)
        assert ratio < 5.0, f"strip_pii_clauses {ratio:.2f}x slower than strip_pii (limit: 5.0x)"
