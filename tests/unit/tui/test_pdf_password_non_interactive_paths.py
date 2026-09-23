"""TUI code paths must never reach the PDF password prompt.

Pins that the ``allow_password_prompt=False`` flag is threaded explicitly
(no global / env var / untyped context key) from the TUI entry points down to
the real parser call:

* ``run_review_via_tui`` forwards ``allow_password_prompt=False`` to
  ``run_review`` (and defaults it to False — the wrapper is TUI-only).
* ``run_negotiation_via_tui`` calls ``parse_document`` with
  ``allow_password_prompt=False``.
* ``ParseStage(allow_password_prompt=False)`` forwards the flag to the real
  ``parse_document``, so a TUI-constructed pipeline cannot prompt.
"""

from __future__ import annotations

import asyncio
import getpass as _getpass
import inspect
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _fail_if_getpass(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args: Any, **_kwargs: Any) -> str:
        raise AssertionError("getpass.getpass must not be called on the TUI path")

    monkeypatch.setattr(_getpass, "getpass", _boom)


class TestReviewWrapperForwardsFlag:
    def test_run_review_via_tui_forwards_false(self) -> None:
        from openreview_cli.tui.domain.review import run_review_via_tui

        with patch("openreview_cli.tui.domain.review.run_review") as mock_run:
            mock_run.return_value = []
            run_review_via_tui(paths=["test.pdf"], mode="precheck")

        assert mock_run.call_args.kwargs.get("allow_password_prompt") is False

    def test_run_review_via_tui_default_is_false(self) -> None:
        from openreview_cli.tui.domain.review import run_review_via_tui

        sig = inspect.signature(run_review_via_tui)
        assert sig.parameters["allow_password_prompt"].default is False


class TestNegotiationWrapperForwardsFlag:
    def test_negotiation_parse_document_passes_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import openreview_cli.tui.domain.negotiation as neg_mod

        doc = tmp_path / "test.pdf"
        doc.write_bytes(b"%PDF-1.4")

        _fail_if_getpass(monkeypatch)
        neg_mod._tui_cancel_requested = False
        try:
            with patch("openreview_cli.parsing.stream.parse_document") as mock_parse:
                mock_parse.return_value = (MagicMock(), [])
                neg_mod.run_negotiation_via_tui(str(doc))
        finally:
            neg_mod._tui_cancel_requested = False

        assert mock_parse.call_args.kwargs.get("allow_password_prompt") is False


class TestParseStageForwardsFlag:
    def test_parse_stage_forwards_false_to_parse_document(self) -> None:
        from openreview_cli.pipeline.adapters.parse import ParseStage

        with patch("openreview_cli.parsing.stream.parse_document") as mock_parse:
            mock_parse.return_value = (MagicMock(), [])
            stage = ParseStage(allow_password_prompt=False)
            asyncio.run(stage.run({"document_path": "/fake/encrypted.pdf"}))

        mock_parse.assert_called_once_with("/fake/encrypted.pdf", allow_password_prompt=False)

    def test_parse_stage_defaults_to_true(self) -> None:
        from openreview_cli.pipeline.adapters.parse import ParseStage

        assert ParseStage().allow_password_prompt is True
        sig = inspect.signature(ParseStage.__init__)
        assert sig.parameters["allow_password_prompt"].default is True
