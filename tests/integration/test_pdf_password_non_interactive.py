"""Non-interactive PDF password handling (the TUI must never prompt).

These tests pin real behaviour, not signatures:

* With ``allow_password_prompt=False`` (and ``sys.stdin`` claiming to be a TTY)
  an encrypted PDF must raise a ``password_protected`` ``ParseError`` and must
  never call ``getpass.getpass``.
* With the *default* (no flag) and ``sys.stdin.isatty()`` True the interactive
  prompt path is still reached and, given the correct password, parsing
  succeeds — proving the standalone CLI behaviour is preserved.
* The error surfaced on the non-interactive path carries an actionable
  ``action`` mentioning ``OPENREVIEW_PDF_PASSWORD`` and/or an unlocked copy.

The encrypted fixture is built in-test with pymupdf so the test does not
depend on generated fixture files.
"""

from __future__ import annotations

import asyncio
import getpass as _getpass
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from openreview_cli.parsing.models import ParseError
from openreview_cli.parsing.pdf_parser import PdfParser
from openreview_cli.parsing.stream import parse_document, stream_clauses

pytestmark = pytest.mark.integration

USER_PW = "user-correct-horse"
OWNER_PW = "owner-secret"


def _make_encrypted_pdf(path: Path) -> Path:
    """Write a single-page AES-256 encrypted PDF owned by OWNER_PW/USER_PW."""
    import pymupdf

    doc: Any = pymupdf.open()  # type: ignore[no-untyped-call]
    page = doc.new_page()
    page.insert_text((50, 50), "Confidential Agreement", fontname="helv", fontsize=12)
    doc.save(
        str(path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,  # type: ignore[attr-defined]
        owner_pw=OWNER_PW,
        user_pw=USER_PW,
    )
    doc.close()
    return path


@pytest.fixture
def encrypted_pdf(tmp_path: Path) -> Path:
    return _make_encrypted_pdf(tmp_path / "encrypted.pdf")


def _fake_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``sys.stdin.isatty()`` return True without a real terminal."""
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: True))


def _fail_if_getpass(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Patch getpass.getpass to fail loudly; return the call-recording list."""
    calls: list[str] = []

    def _boom(*_args: Any, **_kwargs: Any) -> str:
        calls.append("called")
        raise AssertionError("getpass.getpass must not be called on this path")

    monkeypatch.setattr(_getpass, "getpass", _boom)
    return calls


class TestNonInteractiveNoPrompt:
    """allow_password_prompt=False must raise, never prompt."""

    def test_pdf_parser_never_calls_getpass(
        self, encrypted_pdf: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENREVIEW_PDF_PASSWORD", raising=False)
        _fake_tty(monkeypatch)
        calls = _fail_if_getpass(monkeypatch)

        with pytest.raises(ParseError) as exc:
            list(PdfParser(encrypted_pdf).parse(allow_password_prompt=False))

        assert calls == [], "getpass was called despite allow_password_prompt=False"
        assert exc.value.category == "password_protected"
        assert exc.value.exit_code == 8
        assert exc.value.message == "This contract is password-protected."

    def test_action_is_actionable_for_a_tui_user(
        self, encrypted_pdf: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENREVIEW_PDF_PASSWORD", raising=False)
        _fake_tty(monkeypatch)
        _fail_if_getpass(monkeypatch)

        with pytest.raises(ParseError) as exc:
            list(PdfParser(encrypted_pdf).parse(allow_password_prompt=False))

        action = exc.value.action.lower()
        assert "openreview_pdf_password" in action or "unlocked" in action, (
            f"action is not actionable for a TUI user: {exc.value.action!r}"
        )

    def test_parse_document_raises_without_prompting(
        self, encrypted_pdf: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENREVIEW_PDF_PASSWORD", raising=False)
        _fake_tty(monkeypatch)
        calls = _fail_if_getpass(monkeypatch)

        with pytest.raises(ParseError) as exc:
            parse_document(encrypted_pdf, allow_password_prompt=False)

        assert calls == []
        assert exc.value.category == "password_protected"

    def test_stream_clauses_raises_without_prompting(
        self, encrypted_pdf: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENREVIEW_PDF_PASSWORD", raising=False)
        _fake_tty(monkeypatch)
        calls = _fail_if_getpass(monkeypatch)

        with pytest.raises(ParseError) as exc:
            list(stream_clauses(encrypted_pdf, allow_password_prompt=False))

        assert calls == []
        assert exc.value.category == "password_protected"


class TestInteractiveDefaultPreserved:
    """The default (no flag) still reaches the prompt and can succeed."""

    def test_pdf_parser_default_prompts_and_parses(
        self, encrypted_pdf: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENREVIEW_PDF_PASSWORD", raising=False)
        _fake_tty(monkeypatch)
        prompts: list[str] = []

        def _prompt(prompt: str = "") -> str:
            prompts.append(prompt)
            return USER_PW

        monkeypatch.setattr(_getpass, "getpass", _prompt)

        clauses = list(PdfParser(encrypted_pdf).parse())

        assert prompts == ["PDF password: "], "default call did not reach the prompt"
        assert isinstance(clauses, list)

    def test_parse_document_default_prompts_and_succeeds(
        self, encrypted_pdf: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENREVIEW_PDF_PASSWORD", raising=False)
        _fake_tty(monkeypatch)
        prompts: list[str] = []

        def _prompt(prompt: str = "") -> str:
            prompts.append(prompt)
            return USER_PW

        monkeypatch.setattr(_getpass, "getpass", _prompt)

        doc, clauses = parse_document(encrypted_pdf)

        assert prompts == ["PDF password: "]
        assert doc.clause_count >= 0
        assert isinstance(clauses, list)


class TestParseStagePipelineNonInteractive:
    """The real ParseStage -> parse_document chain never prompts when told not to."""

    def test_parse_stage_pipeline_never_prompts(
        self, encrypted_pdf: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from openreview_cli.pipeline.adapters.parse import ParseStage
        from openreview_cli.pipeline.errors import CriticalStageError
        from openreview_cli.pipeline.runner import Pipeline

        monkeypatch.delenv("OPENREVIEW_PDF_PASSWORD", raising=False)
        _fake_tty(monkeypatch)
        calls = _fail_if_getpass(monkeypatch)

        pipeline = Pipeline(stages=[ParseStage(allow_password_prompt=False)])
        with pytest.raises(CriticalStageError):
            asyncio.run(pipeline.run({"document_path": str(encrypted_pdf)}))

        assert calls == [], "ParseStage pipeline prompted despite allow_password_prompt=False"
