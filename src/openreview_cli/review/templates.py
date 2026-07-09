"""MemoTemplate — Jinja2-based custom memo template rendering.

Provides a ``MemoTemplate`` class that wraps Jinja2 to render
``ReviewReport`` objects into Markdown strings.  A bundled default
template is used when no custom path is given — its output matches
``render_markdown()`` byte-for-byte.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from openreview_cli.review.memo.formats import (
    DISCLAIMER_TEXT,
    G_A_R_EMOJI,
    _citation_str,
    _truncate,
)
from openreview_cli.review.report import _confidence_bar

if TYPE_CHECKING:
    from pathlib import Path

    from openreview_cli.review.memo.models import MemoReport
    from openreview_cli.review.models import ReviewReport

logger = logging.getLogger(__name__)

_DEFAULT_TEMPLATE = "default_memo.md.j2"


def _build_memo(report: ReviewReport) -> MemoReport:
    """Convert a ReviewReport to a MemoReport using MemoExporter logic.

    This is a standalone version of MemoExporter._build_memo_report()
    to avoid coupling to the exporter class.  The ``review_date`` is
    sourced from ``report.generated_at`` for deterministic output.
    """
    from openreview_cli.review.memo.exporter import MemoExporter

    # ponytail: reuse MemoExporter's conversion logic instead of duplicating it
    exporter = MemoExporter(report=report, mode=report.mode or "precheck")
    memo = exporter._build_memo_report()
    # Use the report's generated_at for deterministic output
    memo.review_date = report.generated_at.isoformat()
    return memo


class MemoTemplate:
    """Jinja2-based template renderer for ReviewReport objects.

    Parameters
    ----------
    template_path : Path | None
        Path to a custom Jinja2 template file.  ``None`` loads the bundled
        default template (``default_memo.md.j2``) which produces the same
        output as ``render_markdown()``.
    """

    def __init__(self, template_path: Path | None = None) -> None:
        if template_path is None:
            self._env = None
            self._template_name = _DEFAULT_TEMPLATE
            return

        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")
        self._env = Environment(
            loader=FileSystemLoader(str(template_path.parent)),
            autoescape=select_autoescape(default=False),
        )
        self._template_name = template_path.name

        self._register_filters()

    def _register_filters(self) -> None:
        """Register custom Jinja2 filters that mirror Python helpers."""
        assert self._env is not None  # only called when custom template path set

        def _conf_bar(val: float) -> str:
            return _confidence_bar(val)

        def _cite_str(citation: Any) -> str:
            return _citation_str(citation)

        def _trunc(val: str, length: int = 10000) -> str:
            return _truncate(val, limit=length)

        self._env.filters["confidence_bar"] = _conf_bar
        self._env.filters["citation_str"] = _cite_str
        self._env.filters["trunc"] = _trunc
        self._env.filters["g_a_r_emoji"] = lambda c: G_A_R_EMOJI.get(c, "❓")

    def render(self, report: ReviewReport) -> str:
        """Render *report* through the loaded Jinja2 template.

        When the built-in default template is active, delegates to
        ``render_markdown()`` for byte-for-byte identical output with
        the existing ``MemoExporter``.  Custom templates are rendered
        via Jinja2 with ``report`` (``ReviewReport``), ``memo``
        (``MemoReport``), and ``DISCLAIMER_TEXT`` in context.

        Parameters
        ----------
        report : ReviewReport
            The review report to render.

        Returns
        -------
        str
            Rendered Markdown string.
        """
        memo = _build_memo(report)

        # ponytail: default template delegates to render_markdown for
        # guaranteed byte-for-byte identical output. Custom Jinja2
        # templates are rendered normally.
        if self._template_name == _DEFAULT_TEMPLATE:
            from openreview_cli.review.memo.formats import render_markdown

            return render_markdown(memo)

        assert self._env is not None  # custom template path always sets _env
        context: dict[str, Any] = {
            "report": report,
            "memo": memo,
            "DISCLAIMER_TEXT": DISCLAIMER_TEXT,
        }
        template = self._env.get_template(self._template_name)
        return template.render(**context)
