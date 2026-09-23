"""Unit tests for the clause-graph TUI domain wrapper.

No Textual app is started here: ``graph_summary_via_tui`` is exercised directly
against the real ``nda_with_pii.pdf`` fixture and against the real failure
paths (missing path, directory, unsupported format, encrypted PDF, clause-free
DOCX), so the numbers the screen shows are pinned to what the parser measures.
"""

from __future__ import annotations

import dataclasses
import time
from pathlib import Path
from typing import Any

import pytest
from docx import Document

from openreview_cli.graph.metrics import GraphMetrics
from openreview_cli.parsing.models import ParseError, ParseErrorCategory
from openreview_cli.tui.domain.graph import GraphSummary, graph_summary_via_tui

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
REAL_PDF = FIXTURES / "nda_with_pii.pdf"


def test_real_fixture_reports_its_measured_numbers() -> None:
    """The real NDA fixture parses to five flat clauses and a 98/100 score."""
    summary = graph_summary_via_tui(REAL_PDF)

    assert summary.filename == "nda_with_pii.pdf"
    assert summary.node_count == 5
    assert summary.edge_count == 0
    assert summary.parent_child_edge_count == 0
    assert summary.metrics.max_depth == 1
    assert summary.metrics.density == 0.0
    assert summary.metrics.orphan_ratio == 0.0
    assert summary.metrics.broken_ref_count == 0
    assert summary.metrics.definition_coverage == 1.0
    assert summary.score == 98


def test_missing_path_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        graph_summary_via_tui(tmp_path / "gone.pdf")


def test_directory_named_pdf_raises_oserror_not_parse_error(tmp_path: Path) -> None:
    directory = tmp_path / "contract.pdf"
    directory.mkdir()

    with pytest.raises(OSError) as excinfo:
        graph_summary_via_tui(directory)

    assert isinstance(excinfo.value, IsADirectoryError)
    assert not isinstance(excinfo.value, ParseError)


def test_unsupported_format_raises_parse_error(tmp_path: Path) -> None:
    text = tmp_path / "notes.txt"
    text.write_text("Article 1. Confidential information.", encoding="utf-8")

    with pytest.raises(ParseError) as excinfo:
        graph_summary_via_tui(text)

    assert excinfo.value.category == ParseErrorCategory.unsupported_format


def test_password_protected_pdf_raises_without_prompting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An encrypted PDF is refused up front, without reaching ``getpass``."""
    import pymupdf

    pdf_path = tmp_path / "locked.pdf"
    doc: Any = pymupdf.open()  # type: ignore[no-untyped-call]
    page = doc.new_page()
    page.insert_text((72, 72), "Article 1. Confidential information.")
    doc.save(
        str(pdf_path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,  # type: ignore[attr-defined]
        owner_pw="owner-secret",
        user_pw="user-secret",
    )
    doc.close()

    def _fail_prompt(*_args: Any, **_kwargs: Any) -> str:
        pytest.fail("graph_summary_via_tui prompted for a PDF password")

    monkeypatch.setattr("getpass.getpass", _fail_prompt)

    start = time.monotonic()
    with pytest.raises(ParseError) as excinfo:
        graph_summary_via_tui(pdf_path)
    elapsed = time.monotonic() - start

    assert excinfo.value.category == ParseErrorCategory.password_protected
    assert elapsed < 5.0


def test_encrypted_pdf_with_configured_password_returns_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A correct ``OPENREVIEW_PDF_PASSWORD`` opens the PDF instead of refusing it.

    The removed pymupdf guard rejected every ``needs_pass`` document outright,
    ignoring the password the rest of the app honours. Delegating to
    ``parse_document(..., allow_password_prompt=False)`` restores that: the
    parser authenticates with the env password and the summary is returned, all
    without reaching ``getpass``.
    """
    import pymupdf

    pdf_path = tmp_path / "locked.pdf"
    doc: Any = pymupdf.open()  # type: ignore[no-untyped-call]
    page = doc.new_page()
    page.insert_text((72, 72), "Article 1. Confidential information.")
    doc.save(
        str(pdf_path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,  # type: ignore[attr-defined]
        owner_pw="owner-secret",
        user_pw="user-secret",
    )
    doc.close()

    def _fail_prompt(*_args: Any, **_kwargs: Any) -> str:
        pytest.fail("graph_summary_via_tui prompted for a PDF password")

    monkeypatch.setattr("getpass.getpass", _fail_prompt)
    monkeypatch.setenv("OPENREVIEW_PDF_PASSWORD", "user-secret")

    summary = graph_summary_via_tui(pdf_path)

    assert isinstance(summary, GraphSummary)
    assert summary.filename == "locked.pdf"
    assert summary.node_count == 1


def test_docx_without_clauses_returns_empty_summary(tmp_path: Path) -> None:
    docx_path = tmp_path / "blank.docx"
    Document().save(str(docx_path))

    summary = graph_summary_via_tui(docx_path)

    assert isinstance(summary, GraphSummary)
    assert summary.node_count == 0
    assert summary.edge_count == 0
    assert summary.parent_child_edge_count == 0
    assert summary.score == 100


def test_metric_row_mapping_covers_every_metric_field() -> None:
    """The screen's row mapping can never drift from the real ``GraphMetrics``."""
    from openreview_cli.tui.screens.graph import _METRIC_ROWS

    real_fields = {field.name for field in dataclasses.fields(GraphMetrics)}
    assert set(_METRIC_ROWS) == real_fields
