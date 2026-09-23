"""StripStage — wraps ``openreview_cli.pii.strip_pii_clauses``."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openreview_cli.pipeline.base import Stage
from openreview_cli.pipeline.errors import StageError
from openreview_cli.pipeline.progress import ProgressEvent

if TYPE_CHECKING:
    from openreview_cli.pipeline.base import PipelineContext

logger = logging.getLogger(__name__)


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

        from openreview_cli.gateway.router import reset_pii_available

        if self.no_pii:
            reset_pii_available()
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
            stripped, pii_result = await asyncio.to_thread(
                strip_pii_clauses,
                clauses,
                document,
                allow_partial=self.allow_partial,
                progress_callback=_pii_cb,
            )

            from openreview_cli.gateway.router import mark_pii_available

            mark_pii_available()
            self._persist_pii(pii_result, ctx)
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

    def _persist_pii(self, pii_result: Any, ctx: PipelineContext) -> None:
        """Persist a PII result to the governance lifecycle (cache + audit trail).

        Mirrors the legacy ``ReviewCommand.run`` persistence but also writes the
        ``pii_audit_trail`` row that ``pii list`` reads for ``entity_count``.
        Persistence failures are non-fatal: PII stripping must not be blocked
        by governance write errors.
        """
        try:
            from openreview_cli.config.loader import load_config
            from openreview_cli.config.paths import get_config_dir, get_data_dir
            from openreview_cli.pii.config_hash import compute_config_hash
            from openreview_cli.pii.mapping import ensure_encryption_key
            from openreview_cli.pii.persist import persist_pii_result

            document_path = ctx.get("document_path")
            if not document_path:
                return

            doc_path = Path(document_path)
            if not doc_path.exists():
                return

            document_hash = hashlib.sha256(doc_path.read_bytes()).hexdigest()

            config_path = get_config_dir() / "config.yml"
            config = load_config(config_path)
            config_hash = compute_config_hash(config.get("privacy", {}))
            encryption_key = ensure_encryption_key(config, config_path)

            review_dir = get_data_dir() / "reviews" / document_hash[:12]
            db_path = get_data_dir() / "openreview.db"

            persist_pii_result(
                db_path,
                document_hash=document_hash,
                config_hash=config_hash,
                pii_result=pii_result,
                review_dir=review_dir,
                encryption_key=encryption_key,
                filename=doc_path.name,
            )
        except Exception as exc:
            logger.warning("PII persistence failed (non-fatal): %s", exc)
