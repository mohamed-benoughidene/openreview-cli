"""ComparisonStage — wraps ``openreview_cli.bilateral.comparison.compare_pair``.

Reads aligned clause pairs from the shared context, delegates each pair
to the comparison agent, and writes ``paired_assessments`` back.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from openreview_cli.pipeline.base import Stage

if TYPE_CHECKING:
    from openreview_cli.bilateral.models import PairedAssessment
    from openreview_cli.pipeline.base import PipelineContext


class ComparisonStage(Stage):
    """Compare aligned clause pairs via the bilateral comparison agent.

    Reads
        ``ctx["aligned_pairs"]`` — ``list[dict]`` with keys:
        ``alignment``, ``party_a_assessment``, ``party_b_assessment``,
        ``playbook_category``.
        ``ctx.get("model")`` — model slot name (fallback to init value).
        ``ctx.get("comparison_model")`` — optional comparison model.

    Writes
        ``ctx["paired_assessments"]`` — ``list[PairedAssessment]``.
    """

    name = "comparison"
    critical = False

    def __init__(
        self,
        model: str,
        comparison_model: str | None = None,
    ) -> None:
        """Initialise the comparison stage.

        Parameters
        ----------
        model:
            AI Gateway model slot name for the comparison agent.
        comparison_model:
            Optional separate model for the comparison agent; falls back
            to *model* when ``None``.
        """
        self._model = model
        self._comparison_model = comparison_model

    async def run(self, ctx: PipelineContext) -> dict[str, Any] | None:
        from openreview_cli.bilateral.comparison import compare_pair

        aligned_pairs: list[dict[str, Any]] = ctx["aligned_pairs"]
        model: str = ctx.get("model", self._model)
        comparison_model: str | None = ctx.get("comparison_model", self._comparison_model)

        if not aligned_pairs:
            return {"paired_assessments": []}

        assessments: list[PairedAssessment] = []

        for item in aligned_pairs:
            try:
                paired = await asyncio.to_thread(
                    compare_pair,
                    alignment=item["alignment"],
                    party_a_assessment=item["party_a_assessment"],
                    party_b_assessment=item["party_b_assessment"],
                    playbook_category=item.get("playbook_category"),
                    model=model,
                    comparison_model=comparison_model,
                )
            except Exception as exc:
                paired = self._make_error_assessment(
                    pair_id=str(item.get("alignment", "")),
                    error=f"ComparisonStage failed: {exc}",
                )

            assessments.append(paired)

        return {"paired_assessments": assessments}

    def _make_error_assessment(self, pair_id: str, error: str) -> Any:
        """Build a minimal PairedAssessment-like object on error."""
        from openreview_cli.bilateral.models import DivergenceVerdict

        # Use a Mock-like fallback — the real PairedAssessment requires
        # alignment and assessment objects we don't have on failure.
        # Return a dict-shaped result that consumers can handle.
        class _FallbackAssessment:
            def __init__(self, pid: str, err: str) -> None:
                self.pair_id = pid
                self.divergence = DivergenceVerdict.uncertain
                self.error = err
                self.alignment = None
                self.party_a_assessment = None
                self.party_b_assessment = None
                self.primary_dimension = None
                self.rcbsf_details: dict[str, str] = {}
                self.alignment_quality = 0.0
                self.confidence = 0.0
                self.citations: list[str] = []
                self.rationale = ""
                self.color = None

        return _FallbackAssessment(pair_id, error)
