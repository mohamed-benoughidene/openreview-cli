"""ParseStage — wraps ``openreview_cli.parsing.stream.parse_document``."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from openreview_cli.pipeline.base import Stage
from openreview_cli.pipeline.errors import StageError

if TYPE_CHECKING:
    from openreview_cli.pipeline.base import PipelineContext


class ParseStage(Stage):
    """Parse a document from its file path.

    Reads:
        ``ctx["document_path"]`` — path to the PDF/DOCX file.

    Writes:
        ``ctx["document"]`` — ``Document`` metadata object.
        ``ctx["clauses"]`` — ``list[Clause]`` extracted from the document.
    """

    name = "parse"
    critical = True

    def __init__(self, *, allow_password_prompt: bool = True) -> None:
        self.allow_password_prompt = allow_password_prompt

    async def run(self, ctx: PipelineContext) -> dict[str, Any]:
        from openreview_cli.parsing.stream import parse_document

        path = ctx["document_path"]
        if not path:
            raise StageError("document_path is empty or None")

        try:
            document, clauses = await asyncio.to_thread(
                parse_document, path, allow_password_prompt=self.allow_password_prompt
            )
        except Exception as exc:
            raise StageError(f"ParseStage failed: {exc}") from exc

        return {
            "document": document,
            "clauses": clauses,
        }
