"""GenerateStage — wraps ``openreview_cli.gateway.Gateway.chat``."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from openreview_cli.pipeline.base import Stage
from openreview_cli.pipeline.errors import StageError

if TYPE_CHECKING:
    from openreview_cli.gateway.router import Gateway
    from openreview_cli.pipeline.base import PipelineContext


class GenerateStage(Stage):
    """Generate an AI response from retrieved context and playbook.

    Reads:
        ``ctx["retrieved"]`` — ``list[RetrievalResult]``.
        ``ctx["playbook"]`` — ``Playbook`` (optional).

    Writes:
        ``ctx["generated"]`` — generated text (``str``).

    Accepts a *slot* parameter to route to a specific gateway slot
    (default ``"extraction"``).
    """

    name = "generate"
    critical = False

    def __init__(
        self,
        gateway: Gateway | None = None,
        slot: str = "extraction",
        model: str | None = None,
    ) -> None:
        self._gateway = gateway
        self._slot = slot
        self._model = model

    async def run(self, ctx: PipelineContext) -> dict[str, Any]:
        if self._gateway is None:
            from openreview_cli.gateway.router import Gateway as Gw

            gateway: Gateway = Gw()
        else:
            gateway = self._gateway

        playbook = ctx.get("playbook")
        retrieved = ctx["retrieved"]

        # Build a simple messages list from retrieved context
        context_text = "\n\n".join(r.text for r in retrieved[:10])
        system_prompt = "You are a contract review assistant."
        if playbook is not None:
            system_prompt += (
                f"\nPlaybook: {getattr(playbook, 'id', 'unknown')} "
                f"({getattr(playbook, 'mode', 'unknown')})"
            )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Review the following clauses:\n\n{context_text}",
            },
        ]

        kwargs: dict[str, Any] = {}
        if self._model:
            kwargs["model"] = self._model

        try:

            def _chat() -> str:
                return gateway.chat(self._slot, messages, **kwargs)

            result = await asyncio.to_thread(_chat)
        except Exception as exc:
            raise StageError(f"GenerateStage failed: {exc}") from exc

        return {"generated": result}
