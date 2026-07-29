"""Unit tests for tui.domain.negotiation wrapper (T20A)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import openreview_cli.tui.domain.negotiation as _neg_mod


class TestNegotiationDomainWrapper:
    def teardown_method(self) -> None:
        """Reset module-level cancel flag between tests."""
        _neg_mod._tui_cancel_requested = False

    def test_cancel_requested_returns_none(self) -> None:
        result = _neg_mod.run_negotiation_via_tui("test.pdf", cancel_requested=True)
        assert result is None

    def test_module_flag_returns_none(self) -> None:
        _neg_mod._tui_cancel_requested = True
        try:
            result = _neg_mod.run_negotiation_via_tui("test.pdf")
            assert result is None
        finally:
            _neg_mod._tui_cancel_requested = False

    def test_success_returns_report(self, tmp_path: Path) -> None:
        """Patch full run pipeline; verify report passes through."""
        from openreview_cli.negotiation.models import NegotiationReport
        from openreview_cli.parsing.models import Clause, Document

        doc = tmp_path / "test.pdf"
        doc.write_text("dummy pdf content")

        with (
            patch("openreview_cli.parsing.stream.parse_document") as mock_parse,
            patch("openreview_cli.review.playbook.load_bundled") as mock_playbook,
            patch("openreview_cli.negotiation.run_negotiation") as mock_run,
        ):
            mock_doc = Document(
                source_path=Path("test.pdf"),
                format="pdf",
                page_count=1,
                clause_count=1,
                parse_duration_seconds=0.1,
                warnings=[],
            )
            mock_clause = Clause(
                id="c1",
                title="Clause 1",
                text="Some clause text.",
                level=1,
                parent_id=None,
                source_page=None,
                source_paragraph=1,
                source_span=None,
            )
            mock_parse.return_value = (mock_doc, [mock_clause])

            class MockPB:
                id = "bundled"
                categories: list = []

            mock_playbook.return_value = MockPB()

            mock_neg = NegotiationReport()
            mock_run.return_value = mock_neg

            result = _neg_mod.run_negotiation_via_tui(str(doc))

            assert result is not None
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["solver"] == "qre"
            assert call_kwargs["rationality"] == 1.0

    def test_cancel_flag_after_parse_returns_none(self, tmp_path: Path) -> None:
        """Module flag set after parse but before run_negotiation → None."""
        from openreview_cli.parsing.models import Clause, Document

        doc = tmp_path / "test.pdf"
        doc.write_text("dummy pdf content")

        with (
            patch("openreview_cli.parsing.stream.parse_document") as mock_parse,
            patch("openreview_cli.review.playbook.load_bundled"),
            patch("openreview_cli.negotiation.run_negotiation") as mock_run,
        ):
            mock_clause = Clause(
                id="c1",
                title="Clause 1",
                text="Some clause text.",
                level=1,
                parent_id=None,
                source_page=None,
                source_paragraph=1,
                source_span=None,
            )
            mock_parse.return_value = (
                Document(
                    source_path=Path("t.pdf"),
                    format="pdf",
                    page_count=1,
                    clause_count=1,
                    parse_duration_seconds=0.1,
                    warnings=[],
                ),
                [mock_clause],
            )

            # Set flag after assessments built
            _neg_mod._tui_cancel_requested = True
            try:
                result = _neg_mod.run_negotiation_via_tui(str(doc))
                assert result is None
                mock_run.assert_not_called()
            finally:
                _neg_mod._tui_cancel_requested = False

    def test_no_assessments_returns_none(self, tmp_path: Path) -> None:
        """Empty document → no assessments → None."""
        from openreview_cli.parsing.models import Document

        doc = tmp_path / "test.pdf"
        doc.write_text("dummy pdf content")

        with (
            patch("openreview_cli.parsing.stream.parse_document") as mock_parse,
            patch("openreview_cli.review.playbook.load_bundled"),
            patch("openreview_cli.negotiation.run_negotiation") as mock_run,
        ):
            mock_parse.return_value = (
                Document(
                    source_path=Path("t.pdf"),
                    format="pdf",
                    page_count=1,
                    clause_count=0,
                    parse_duration_seconds=0.1,
                    warnings=[],
                ),
                [],
            )
            result = _neg_mod.run_negotiation_via_tui(str(doc))
            assert result is None
            mock_run.assert_not_called()


def test_import_does_not_pull_litellm() -> None:
    """Importing tui.domain.negotiation must NOT pull litellm into sys.modules."""
    code = (
        "import openreview_cli.tui.domain.negotiation, sys; "
        "sys.exit(1 if 'litellm' in sys.modules else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
