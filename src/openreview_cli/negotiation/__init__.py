"""Game-theoretic negotiation assistant.

Computes clause-level equilibrium strategy recommendations using:
- Pure Nash equilibrium (hand-rolled NumPy support enumeration)
- Logit Quantal Response Equilibrium (bounded rationality)
- Level-k iterative best-response

All computation is local. No external API calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from openreview_cli.negotiation.models import (
    EquilibriumStrategy,
    NegotiationReport,
    NegotiationSummary,
    PayoffMatrix,
    PayoffSource,
    SolverType,
)
from openreview_cli.negotiation.report import format_json, format_memo, format_terminal

if TYPE_CHECKING:
    from openreview_cli.bilateral.models import PairedAssessment
    from openreview_cli.review.models import ClauseAssessment

__all__ = [
    "EquilibriumStrategy",
    "NegotiationReport",
    "NegotiationSummary",
    "PayoffMatrix",
    "PayoffSource",
    "SolverType",
    "format_json",
    "format_memo",
    "format_terminal",
    "run_negotiation",
]


def run_negotiation(
    assessments: list[ClauseAssessment],
    solver: str = "qre",
    *,
    weights: dict[str, float] | None = None,
    rationality: float = 1.0,
    depth: int = 2,
    confidence_threshold: float = 0.7,
    playbook_id: str = "unknown",
    paired_assessments: dict[str, PairedAssessment] | None = None,
) -> NegotiationReport:
    """Run the negotiation pipeline on a list of clause assessments.

    Builds payoff matrices from assessments, computes equilibrium
    strategies, and returns an aggregated report.

    Parameters
    ----------
    assessments : list[ClauseAssessment]
        Clause assessment objects from the review pipeline.
    solver : str
        Solver type: ``"nash"``, ``"qre"``, or ``"level_k"``.
    weights : dict or None
        Payoff component weights. Defaults to balanced weights.
    rationality : float
        Rationality parameter for QRE solver (λ). Default 1.0.
    depth : int
        Depth of reasoning for level-k solver (k). Default 2.
    confidence_threshold : float
        Threshold for Amber flagging. Default 0.7.
    paired_assessments : dict[str, PairedAssessment] or None
        Optional mapping of clause IDs to bilateral ``PairedAssessment``
        objects. When provided, payoff construction incorporates alignment
        and divergence signals.

    Returns
    -------
    NegotiationReport
        Aggregated report with per-clause equilibrium strategies.
    """
    from datetime import UTC, datetime

    from openreview_cli.negotiation.payoffs import build_payoff_matrix
    from openreview_cli.negotiation.recommend import build_recommendation
    from openreview_cli.negotiation.solvers import solve_level_k, solve_nash, solve_qre

    if not assessments:
        return NegotiationReport(
            strategies=[],
            payoff_matrices=[],
            summary=NegotiationSummary(),
            playbook_id=playbook_id,
            generated_at=datetime.now(UTC),
            confidence_threshold=confidence_threshold,
            schema_version="0.1.0",
        )

    strategies: list[EquilibriumStrategy] = []
    payoff_matrices: list[PayoffMatrix] = []

    for assessment in assessments:
        cid = getattr(assessment, "clause_id", "")
        pa = paired_assessments.get(cid) if paired_assessments else None
        matrix, _warnings = build_payoff_matrix(assessment, weights=weights, paired_assessment=pa)
        if matrix is None:
            continue

        payoff_matrices.append(matrix)
        a_mat = matrix.user_payoffs
        b_mat = matrix.counterparty_payoffs

        is_fallback: bool = False
        if solver == "nash":
            user_strat, cp_strat, eq_type, is_fallback = solve_nash(a_mat, b_mat)
            model_name = "nash"
            model_params: dict[str, float] = {}
        elif solver == "level_k":
            user_strat, cp_strat, eq_type = solve_level_k(a_mat, b_mat, k=depth)
            model_name = "level_k"
            model_params = {"k": float(depth)}
        else:
            user_strat, cp_strat, eq_type = solve_qre(a_mat, b_mat, lam=rationality)
            model_name = "qre"
            model_params = {"lambda": rationality}

        strategy = build_recommendation(
            user_strategy=user_strat,
            counterparty_strategy=cp_strat,
            matrix=matrix,
            eq_type=eq_type,
            model=model_name,
            model_params=model_params,
            confidence_threshold=confidence_threshold,
            is_fallback=is_fallback,
        )
        strategies.append(strategy)

    # Aggregate summary
    eq_dist: dict[str, int] = {}
    amber_count = 0
    impasse_count = 0
    total_conf = 0.0

    for s in strategies:
        eq_dist[s.equilibrium_type] = eq_dist.get(s.equilibrium_type, 0) + 1
        if s.is_amber:
            amber_count += 1
        if s.predicted_outcome and "walkaway" in s.predicted_outcome:
            impasse_count += 1
        total_conf += s.confidence

    avg_conf = total_conf / len(strategies) if strategies else 0.0

    summary = NegotiationSummary(
        total_clauses=len(strategies),
        equilibrium_distribution=eq_dist,
        amber_count=amber_count,
        avg_confidence=avg_conf,
        impasse_count=impasse_count,
        deadlock_risk=impasse_count > 0,
    )

    return NegotiationReport(
        strategies=strategies,
        payoff_matrices=payoff_matrices,
        summary=summary,
        playbook_id=playbook_id,
        generated_at=datetime.now(UTC),
        confidence_threshold=confidence_threshold,
        schema_version="0.1.0",
    )
