from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from openreview_cli.parsing.models import ParseError

if TYPE_CHECKING:
    from collections.abc import Generator

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"


class TestPdfParserIntegration:
    def test_simple_contract_has_clauses(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        clauses = list(stream_clauses(FIXTURES / "simple_contract.pdf"))
        assert len(clauses) >= 3
        assert all(c.id.startswith("clause-") for c in clauses)

    def test_complex_numbering_detected(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        clauses = list(stream_clauses(FIXTURES / "complex_numbering.pdf"))
        assert len(clauses) >= 10

    def test_flat_document_all_level_zero(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        clauses = list(stream_clauses(FIXTURES / "flat_document.pdf"))
        assert all(c.level == 0 for c in clauses)

    def test_multi_column_reading_order(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        clauses = list(stream_clauses(FIXTURES / "multi_column.pdf"))
        texts = [c.text for c in clauses]
        joined = " ".join(texts)
        assert joined.index("Left") < joined.index("Right")

    def test_password_protected_raises_error(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        with pytest.raises(ParseError) as exc:
            list(stream_clauses(FIXTURES / "password_protected.pdf"))
        assert exc.value.category == "password_protected"

    def test_corrupt_pdf_raises_error(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        with pytest.raises(ParseError) as exc:
            list(stream_clauses(FIXTURES / "corrupt.pdf"))
        assert exc.value.category == "corrupt"

    def test_empty_pdf_raises_error(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        with pytest.raises(ParseError) as exc:
            list(stream_clauses(FIXTURES / "empty.pdf"))
        assert exc.value.category == "empty"

    def test_ctrl_c_cleanup(self) -> None:
        from openreview_cli.parsing.models import Clause
        from openreview_cli.parsing.stream import stream_clauses

        gen: Generator[Clause, Any, Any] = stream_clauses(FIXTURES / "simple_contract.pdf")  # type: ignore[assignment]
        try:
            next(gen)
            gen.throw(KeyboardInterrupt)
        except StopIteration:
            pass

    def test_non_existent_path_raises(self) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        with pytest.raises(ParseError) as exc:
            list(stream_clauses(FIXTURES / "nonexistent.pdf"))
        assert exc.value.category == "file_not_found"
