"""Strategy recommendation and Amber annotation logic."""

from __future__ import annotations

import numpy as np

from openreview_cli.negotiation.models import (
    EquilibriumStrategy,
    PayoffMatrix,
    PayoffSource,
)


def build_recommendation(
    user_strategy: np.ndarray | list[float],
    counterparty_strategy: np.ndarray | list[float],
    matrix: PayoffMatrix,
    eq_type: str,
    model: str,
    model_params: dict[str, float] | None = None,
    confidence_threshold: float = 0.7,
    is_fallback: bool = False,
) -> EquilibriumStrategy:
    """Build a human-readable strategy recommendation from equilibrium output.

    Parameters
    ----------
    user_strategy : ndarray | list[float]
        User's equilibrium mixed strategy (probability vector).
    counterparty_strategy : ndarray | list[float]
        Counterparty's equilibrium mixed strategy.
    matrix : PayoffMatrix
        The payoff matrix for this clause.
    eq_type : str
        Equilibrium type: ``"pure"``, ``"mixed"``, ``"multiple"``,
        ``"no_equilibrium"``.
    model : str
        Solver model name.
    model_params : dict or None
        Parameters passed to the solver.
    confidence_threshold : float
        Threshold below which the recommendation is flagged Amber.

    Returns
    -------
    EquilibriumStrategy
        Human-readable recommendation with confidence and assumptions.
    """
    if model_params is None:
        model_params = {}

    # Accept both lists and ndarrays
    user_arr = np.asarray(user_strategy, dtype=float)
    cp_arr = np.asarray(counterparty_strategy, dtype=float)

    actions = matrix.actions

    predicted, fallback, suggested = _build_predicted_outcome_and_suggestion(
        actions, user_arr, cp_arr, eq_type
    )

    base_confidence = _compute_base_confidence(matrix, eq_type, user_arr)

    is_impasse, impasse_predicted, impasse_suggested = _determine_impasse(actions, user_arr, cp_arr)

    if is_impasse:
        predicted = impasse_predicted
        suggested = impasse_suggested

    # Amber logic
    is_amber = False
    amber_reasons: list[str] = []

    if base_confidence < confidence_threshold:
        is_amber = True
        amber_reasons.append("Low confidence")
    if matrix.source in (PayoffSource.ESTIMATED, PayoffSource.UNKNOWN):
        is_amber = True
        amber_reasons.append("Counterparty payoffs estimated")
    if eq_type == "no_equilibrium":
        is_amber = True
        amber_reasons.append("No equilibrium found")
    if is_impasse:
        is_amber = True
        amber_reasons.append("Impasse detected")
    if eq_type == "multiple":
        is_amber = True
        amber_reasons.append("Multiple equilibria — selecting highest user payoff")
    if is_fallback:
        is_amber = True
        amber_reasons.append("Fallback from Nash to QRE — no pure/mixed equilibrium")

    # Assumptions
    assumptions: list[str] = _build_assumptions(matrix, is_impasse, amber_reasons)
    if is_fallback:
        assumptions.append("Fallback from Nash to QRE — no pure/mixed equilibrium")

    # Cross-reference (US2): check if alignment data is available
    cross_ref_note = ""
    diverges = False
    if matrix.source == PayoffSource.INFERRED_FROM_ALIGNMENT:
        diverges = True
        if is_impasse:
            cross_ref_note = "Deadlock risk confirmed — equilibrium aligns with impasse"
        else:
            cross_ref_note = (
                "Equilibrium analysis diverges from bilateral alignment — "
                "consider game-theoretic approach"
            )

    return EquilibriumStrategy(
        clause_id=matrix.clause_id,
        model=model,
        model_params=model_params,
        user_strategy=user_arr.tolist(),
        counterparty_strategy=cp_arr.tolist(),
        predicted_outcome=predicted,
        suggested_counteroffer=suggested,
        fallback_position=fallback,
        equilibrium_type=eq_type,
        confidence=round(base_confidence, 4),
        is_amber=is_amber,
        assumptions=assumptions,
        diverges_from_alignment=diverges,
        cross_reference_note=cross_ref_note,
    )


def _build_predicted_outcome_and_suggestion(
    actions: list[str],
    user_arr: np.ndarray,
    cp_arr: np.ndarray,
    eq_type: str,
) -> tuple[str, str, str]:
    """Build predicted outcome, fallback, and suggested counteroffer."""
    n = len(actions)

    user_best = int(np.argmax(user_arr))
    cp_best = int(np.argmax(cp_arr))

    predicted = f"{actions[user_best]}/{actions[cp_best]}"

    # Fallback: next-best for user
    sorted_indices = np.argsort(user_arr)[::-1]
    fallback = actions[sorted_indices[1]] if n > 1 else actions[0]

    # Human-readable counteroffer
    if eq_type == "no_equilibrium":
        suggested = (
            f"Consider {actions[user_best]} terms; "
            f"counterparty may respond with {actions[cp_best]}. "
            "Analysis suggests no stable equilibrium — proceed with caution."
        )
    elif user_arr[user_best] > 0.8:
        suggested = (
            f"Consider proposing {actions[user_best]} terms; "
            f"counterparty likely to accept with {actions[cp_best]} adjustments."
        )
    else:
        suggested = (
            f"Consider {actions[user_best]} terms; "
            f"counterparty likely to counter with {actions[cp_best]}."
        )

    return predicted, fallback, suggested


def _determine_impasse(
    actions: list[str],
    user_arr: np.ndarray,
    cp_arr: np.ndarray,
) -> tuple[bool, str, str]:
    """Detect impasse when both parties favour walkaway."""
    walkaway_idx: int | None = None
    for i, a in enumerate(actions):
        if "walkaway" in a.lower():
            walkaway_idx = i
            break

    is_impasse = (
        walkaway_idx is not None and user_arr[walkaway_idx] >= 0.8 and cp_arr[walkaway_idx] >= 0.8
    )

    if is_impasse:
        predicted = "impasse (walkaway/walkaway)"
        suggested = (
            "Parties at impasse on this clause. "
            "Consider revisiting position or seeking compromise on related terms."
        )
        return True, predicted, suggested

    return False, "", ""


def _compute_base_confidence(
    matrix: PayoffMatrix,
    eq_type: str,
    user_strategy: np.ndarray,
) -> float:
    """Compute overall confidence from assessment, payoff source, solver quality."""
    # Solver confidence
    if eq_type == "no_equilibrium":
        solver_conf = 0.3
    elif eq_type == "pure":
        solver_conf = 0.9
    elif eq_type == "multiple":
        solver_conf = 0.6
    else:
        solver_conf = 0.75

    # Source confidence
    source = (
        matrix.source if isinstance(matrix.source, PayoffSource) else PayoffSource(matrix.source)
    )
    source_conf_map = {
        PayoffSource.KNOWN: 0.95,
        PayoffSource.INFERRED_FROM_ALIGNMENT: 0.7,
        PayoffSource.ESTIMATED: 0.5,
        PayoffSource.UNKNOWN: 0.3,
    }
    source_conf = source_conf_map.get(source, 0.5)

    return float(min(solver_conf, source_conf))


def _build_assumptions(
    matrix: PayoffMatrix,
    is_impasse: bool,
    amber_reasons: list[str],
) -> list[str]:
    """Build list of assumptions from matrix source and context."""
    assumptions: list[str] = []

    source = (
        matrix.source if isinstance(matrix.source, PayoffSource) else PayoffSource(matrix.source)
    )

    if source == PayoffSource.ESTIMATED:
        assumptions.append(
            "Counterparty payoffs estimated from user's position — actual "
            "counterparty incentives may differ."
        )
    elif source == PayoffSource.UNKNOWN:
        assumptions.append("Counterparty position unknown — analysis uses default assumptions.")
    elif source == PayoffSource.INFERRED_FROM_ALIGNMENT:
        assumptions.append("Counterparty payoffs inferred from bilateral alignment data.")

    if is_impasse:
        assumptions.append("Both parties heavily favour walkaway — impasse likely.")

    if matrix.symmetric:
        assumptions.append("Payoff matrix assumed symmetric (no divergence data available).")

    return assumptions
