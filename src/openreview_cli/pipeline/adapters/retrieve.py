"""RetrieveStage — wraps ``openreview_cli.retrieval.RetrievalEngine``."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from openreview_cli.pipeline.base import Stage
from openreview_cli.pipeline.errors import StageError
from openreview_cli.retrieval.models import RetrievalQuery

if TYPE_CHECKING:
    from pathlib import Path

    from openreview_cli.gateway.router import Gateway
    from openreview_cli.pipeline.base import PipelineContext
    from openreview_cli.retrieval.engine import RetrievalEngine


class RetrieveStage(Stage):
    """Retrieve relevant passages for chunks or a query.

    Reads:
        ``ctx["chunks"]`` — ``list[Chunk]``.
        ``ctx["retrieval_query"]`` (optional) — custom query text.

    Writes:
        ``ctx["retrieved"]`` — ``list[RetrievalResult]``.

    If a ``RetrievalEngine`` is not provided via *engine*, the stage will
    attempt to create one using *db_path*.  When no engine configuration is
    available, the stage raises ``StageError``.
    """

    name = "retrieve"
    critical = False

    def __init__(
        self,
        engine: RetrievalEngine | None = None,
        db_path: str | Path | None = None,
        gateway: Gateway | None = None,
        top_k: int = 5,
    ) -> None:
        self._engine = engine
        self._db_path = db_path
        self._gateway = gateway
        self._top_k = top_k

    async def run(self, ctx: PipelineContext) -> dict[str, Any]:
        if self._engine is not None:
            engine = self._engine
        elif self._db_path is not None:
            from openreview_cli.retrieval.engine import RetrievalEngine

            engine = RetrievalEngine(self._db_path, self._gateway)
        else:
            raise StageError("RetrieveStage requires either an engine instance or a db_path")

        # Build a query from context or use a concatenation of chunk texts
        query_text: str | None = ctx.get("retrieval_query")
        if not query_text:
            chunks = ctx["chunks"]
            if chunks:
                # ponytail: simple concatenation rather than sophisticated query building
                query_text = " ".join(c.text for c in chunks[:5])

        if not query_text:
            raise StageError("No query text available for retrieval")

        query = RetrievalQuery(query_text=query_text, top_k=self._top_k)

        try:
            results = await asyncio.to_thread(engine.retrieve, query)
        except Exception as exc:
            raise StageError(f"RetrieveStage failed: {exc}") from exc

        return {"retrieved": results}
