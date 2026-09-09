import sys
from pathlib import Path

import pytest

from openreview_cli.parsing.models import ParseError

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pdf"

PASSWORD_PDF = FIXTURES / "password_protected.pdf"


class TestPdfPasswordIntegration:
    @pytest.mark.integration
    def test_correct_password_parses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        monkeypatch.setenv("OPENREVIEW_PDF_PASSWORD", "test123")
        # The fixture is a single "Hello World" page with no clause headings, so it
        # may yield zero or more clauses. The essential guarantee is that no
        # password_protected ParseError is raised.
        clauses = list(stream_clauses(PASSWORD_PDF))
        assert isinstance(clauses, list)

    @pytest.mark.integration
    def test_wrong_password_raises_parse_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        monkeypatch.setenv("OPENREVIEW_PDF_PASSWORD", "wrongpass")
        with pytest.raises(ParseError) as exc:
            list(stream_clauses(PASSWORD_PDF))
        assert exc.value.category == "password_protected"
        assert exc.value.exit_code == 8

    @pytest.mark.integration
    def test_no_password_non_tty_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from openreview_cli.parsing.stream import stream_clauses

        monkeypatch.delenv("OPENREVIEW_PDF_PASSWORD", raising=False)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        with pytest.raises(ParseError) as exc:
            list(stream_clauses(PASSWORD_PDF))
        assert exc.value.category == "password_protected"
        assert exc.value.exit_code == 8
