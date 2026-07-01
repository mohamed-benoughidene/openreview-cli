from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PDF = FIXTURES / "pdf"


class TestErrorHandling:
    @pytest.mark.integration
    def test_corrupt_pdf(self) -> None:
        from openreview_cli.parsing.models import ParseError
        from openreview_cli.parsing.stream import stream_clauses

        with pytest.raises(ParseError) as exc:
            list(stream_clauses(PDF / "corrupt.pdf"))
        assert exc.value.category == "corrupt"
        assert "corrupt" in exc.value.message.lower()

    @pytest.mark.integration
    def test_password_protected_pdf(self) -> None:
        from openreview_cli.parsing.models import ParseError
        from openreview_cli.parsing.stream import stream_clauses

        with pytest.raises(ParseError) as exc:
            list(stream_clauses(PDF / "password_protected.pdf"))
        assert exc.value.category == "password_protected"

    @pytest.mark.integration
    def test_empty_file(self) -> None:
        from openreview_cli.parsing.models import ParseError
        from openreview_cli.parsing.stream import stream_clauses

        with pytest.raises(ParseError) as exc:
            list(stream_clauses(PDF / "empty.pdf"))
        assert exc.value.category == "empty"

    @pytest.mark.integration
    def test_unsupported_format(self) -> None:
        from openreview_cli.parsing.models import ParseError
        from openreview_cli.parsing.stream import stream_clauses

        with pytest.raises(ParseError) as exc:
            list(stream_clauses(FIXTURES / "test.txt"))
        assert exc.value.category == "unsupported_format"
        assert "supported" in exc.value.message.lower()

    @pytest.mark.integration
    def test_non_existent_path(self) -> None:
        from openreview_cli.parsing.models import ParseError
        from openreview_cli.parsing.stream import stream_clauses

        with pytest.raises(ParseError) as exc:
            list(stream_clauses(FIXTURES / "nonexistent.pdf"))
        assert exc.value.category == "file_not_found"

    @pytest.mark.integration
    def test_no_text_pdf(self) -> None:
        from openreview_cli.parsing.models import ParseError
        from openreview_cli.parsing.stream import stream_clauses

        with pytest.raises(ParseError) as exc:
            list(stream_clauses(PDF / "corrupt.pdf"))
        assert exc.value.category in ("corrupt", "no_text")

    @pytest.mark.integration
    def test_all_errors_exit_code_8(self) -> None:
        from openreview_cli.parsing.models import ParseError

        for cat in (
            "file_not_found",
            "unsupported_format",
            "corrupt",
            "password_protected",
            "empty",
            "no_text",
        ):
            err = ParseError(exit_code=8, category=cat, message=f"Error {cat}.", action="Fix it.")
            assert err.exit_code == 8
