"""StripStage — wraps ``openreview_cli.pii.strip_pii_clauses``."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from openreview_cli.pipeline.base import Stage
from openreview_cli.pipeline.errors import StageError
from openreview_cli.pipeline.progress import ProgressEvent

if TYPE_CHECKING:
    from openreview_cli.pipeline.base import PipelineContext


class StripStage(Stage):
    """Strip PII from clauses.

    When ``no_pii=True`` the stage acts as a passthrough — it copies
    ``ctx["clauses"]`` into ``ctx["stripped_clauses"]`` without calling the
    PII engine.

    Reads:
        ``ctx["clauses"]`` — ``list[Clause]`` to strip.

    Writes:
        ``ctx["stripped_clauses"]`` — ``list[Clause]`` with PII removed.
    """

    name = "strip"
    critical = False

    def __init__(
        self,
        no_pii: bool = False,
        allow_partial: bool = False,
        emit_callback: Callable[[ProgressEvent], None] | None = None,
    ) -> None:
        self.no_pii = no_pii
        self.allow_partial = allow_partial
        self._emit_callback = emit_callback
        self._stage_index: int | None = None
        self._total_stages: int = 0

    async def run(self, ctx: PipelineContext) -> dict[str, Any]:
        clauses = ctx["clauses"]
        document = ctx.get("document")  # optional; may be None

        if self.no_pii:
            return {"stripped_clauses": list(clauses)}

        from openreview_cli.pii import strip_pii_clauses
        from openreview_cli.pii.models import PartialProcessingError

        try:
            # Map PII progress (desc, done, total) to pipeline ProgressEvent
            def _pii_cb(desc: str, done: int, total: int) -> None:
                if self._emit_callback is not None and self._stage_index is not None:
                    self._emit_callback(
                        ProgressEvent(
                            stage_index=self._stage_index,
                            total_stages=self._total_stages,
                            stage_name="strip",
                            status="running",
                            message=desc,
                        )
                    )

            # ponytail: synchronous call wrapped in thread pool
            stripped, _pii_result = await asyncio.to_thread(
                strip_pii_clauses,
                clauses,
                document,
                allow_partial=self.allow_partial,
                progress_callback=_pii_cb,
            )
        except PartialProcessingError as exc:
            from openreview_cli.pipeline.errors import CriticalStageError

            raise CriticalStageError(
                f"PII detection failed on {len(exc.failed_pages)} page(s); "
                "aborting before any external API call. Fix the document, "
                "or rerun with --allow-partial-pii or --no-pii."
            ) from exc
        except Exception as exc:
            raise StageError(f"StripStage failed: {exc}") from exc

        return {"stripped_clauses": stripped}
