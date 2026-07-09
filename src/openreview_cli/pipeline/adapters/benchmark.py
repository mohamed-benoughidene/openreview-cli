"""BenchmarkStage — per-item processing stage for benchmark evaluation.

Reads ``text`` and ``category`` from the shared context, produces a
``prediction`` dict that mirrors the output of ``_mock_pipeline``.
This stage replaces the ``PipelineFn`` callback when the benchmark runner
is configured with a pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openreview_cli.pipeline.base import Stage

if TYPE_CHECKING:
    from openreview_cli.pipeline.base import PipelineContext


class BenchmarkStage(Stage):
    """Process a single benchmark item.

    Reads
        ``ctx["text"]`` — document text for the item.
        ``ctx.get("category", "unknown")`` — playbook category.

    Writes
        ``ctx["prediction"]`` — dict with keys ``match``, ``start``, ``end``,
        ``label`` (matching the ``_mock_pipeline`` contract).
    """

    name = "benchmark"
    critical = False

    async def run(self, ctx: PipelineContext) -> dict[str, Any] | None:
        text: str = ctx["text"]

        # ponytail: static prediction — real model pipeline wired later
        prediction: dict[str, Any] = {
            "match": False,
            "start": 0,
            "end": len(text) if text else 0,
            "label": "unknown",
        }

        return {"prediction": prediction}
