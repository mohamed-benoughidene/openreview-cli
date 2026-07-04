"""ChunkStage — wraps ``openreview_cli.chunking.stream_chunks``."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from openreview_cli.chunking.models import ChunkConfig
from openreview_cli.pipeline.base import Stage
from openreview_cli.pipeline.errors import StageError

if TYPE_CHECKING:
    from openreview_cli.pipeline.base import PipelineContext


class ChunkStage(Stage):
    """Chunk clauses into retrieval-ready chunks.

    Reads ``ctx["stripped_clauses"]`` (fallback ``ctx["clauses"]``).

    Writes ``ctx["chunks"]`` — ``list[Chunk]``.

    Accepts an optional ``ChunkConfig`` via the *config* init parameter.
    """

    name = "chunk"
    critical = False

    def __init__(self, config: ChunkConfig | None = None) -> None:
        self.config = config or ChunkConfig()

    async def run(self, ctx: PipelineContext) -> dict[str, Any]:
        clauses = ctx.get("stripped_clauses")
        if clauses is None:
            clauses = ctx["clauses"]

        from openreview_cli.chunking import stream_chunks

        # ponytail: convert the lazy iterator into a list inside the thread
        def _chunk() -> list[Any]:
            return list(stream_chunks(clauses, self.config))

        try:
            chunks = await asyncio.to_thread(_chunk)
        except Exception as exc:
            raise StageError(f"ChunkStage failed: {exc}") from exc

        return {"chunks": chunks}
