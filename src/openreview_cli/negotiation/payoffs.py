"""Payoff matrix construction from ClauseAssessment + playbook data."""

from __future__ import annotations

from typing import Any

from openreview_cli.negotiation.models import PayoffMatrix, PayoffSource


def _weighted_score(
    risk: float, financial: float, obligation: float, weights: dict[str, float]
) -> float:
    """Compute clamped linear weighted score from three components."""
    return max(
        0.0,
        min(
            1.0,
            weights["risk"] * risk
            + weights["financial"] * financial
            + weights["obligation"] * obligation,
        ),
    )


def _build_counterparty_payoffs(
    n: int,
    user_idx: int,
    confidence: float,
    weights: dict[str, float],
    paired_assessment: Any = None,
) -> tuple[list[list[float]], PayoffSource, bool]:
    """Build counterparty payoff matrix and determine source + symmetry.

    When ``paired_assessment`` is provided, uses bilateral alignment data
    for an asymmetric matrix. Otherwise, builds a symmetric estimate.
    """
    has_bilateral = paired_assessment is not None
    symmetric: bool = True

    if has_bilateral:
        divergence_str = str(getattr(paired_assessment, "divergence", "uncertain")).lower()
        pa_confidence = float(getattr(paired_assessment, "confidence", 0.5))
        alignment_quality = float(getattr(paired_assessment, "alignment_quality", 0.5))

        is_divergent = "divergent" in divergence_str

        if is_divergent:
            cp_idx = 2 - user_idx
            conf_factor = pa_confidence * alignment_quality * 1.0
        else:
            cp_idx = user_idx
            conf_factor = pa_confidence * alignment_quality * 0.6

        cp_risk_base = [0.0] * n
        for i in range(n):
            dist = abs(i - cp_idx) / max(n - 1, 1)
            cp_risk_base[i] = 1.0 - dist * conf_factor

        cp_financial_base = [0.0, 0.5, 1.0]
        cp_obligation_base = [1.0, 0.3, 0.7]

        cp_payoffs: list[list[float]] = [
            [
                _weighted_score(
                    cp_risk_base[i], cp_financial_base[i], cp_obligation_base[j], weights
                )
                for j in range(n)
            ]
            for i in range(n)
        ]
        source = PayoffSource.INFERRED_FROM_ALIGNMENT
        symmetric = not is_divergent
        return cp_payoffs, source, symmetric

    # Default symmetric path
    cp_idx = 2 - user_idx
    cp_risk_base = [0.0] * n
    for i in range(n):
        dist = abs(i - cp_idx) / max(n - 1, 1)
        cp_risk_base[i] = 1.0 - dist * confidence * 0.8

    cp_financial_base = [0.0, 0.5, 1.0]
    cp_obligation_base = [1.0, 0.3, 0.7]

    cp_payoffs = [
        [
            _weighted_score(cp_risk_base[i], cp_financial_base[i], cp_obligation_base[j], weights)
            for j in range(n)
        ]
        for i in range(n)
    ]
    return cp_payoffs, PayoffSource.ESTIMATED, True


def build_payoff_matrix(
    assessment: Any,
    weights: dict[str, float] | None = None,
    paired_assessment: Any = None,
) -> tuple[PayoffMatrix | None, str | None]:
    """Build a payoff matrix from a single clause assessment.

    Maps the user's position (preferred/acceptable/walkaway) to action
    indices and computes a 3-component linear payoff:
    ``w_risk * risk + w_fin * financial + w_obl * obligation``.

    Parameters
    ----------
    assessment :
        A clause assessment-like object with ``position``, ``confidence``,
        ``clause_id`` attributes.
    weights :
        Optional weight dict ``{"risk": w1, "financial": w2, "obligation": w3}``.
        Defaults to ``{"risk": 0.33, "financial": 0.33, "obligation": 0.34}``.
    paired_assessment :
        Optional bilateral ``PairedAssessment`` object with ``divergence``,
        ``divergence`` (DivergenceVerdict), and ``confidence`` fields.
        When provided, payoffs use bilateral alignment data.

    Returns
    -------
    tuple[PayoffMatrix | None, str | None]
        ``(matrix, warning)`` where *matrix* is ``None`` if the assessment
        has fewer than 2 actions, and *warning* describes the issue.
    """
    if weights is None:
        weights = {"risk": 0.33, "financial": 0.33, "obligation": 0.34}
    else:
        total = sum(weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to ~1.0, got {total:.6f}")

    actions = ["preferred", "acceptable", "walkaway"]
    n = len(actions)

    position = getattr(assessment, "position", "preferred")
    confidence = float(getattr(assessment, "confidence", 0.5))

    # Map position to action index
    pos_map = {"preferred": 0, "acceptable": 1, "walkaway": 2}
    user_idx = pos_map.get(str(position).lower(), 0)

    # Risk component: high confidence means steeper gradient
    # User payoff high on their preferred action, low on walkaway
    risk_base: list[float] = [0.0] * n
    for i in range(n):
        dist = abs(i - user_idx) / max(n - 1, 1)
        risk_base[i] = 1.0 - dist * confidence

    # Financial component: preferred=1.0, acceptable=0.5, walkaway=0.0
    financial_base = [1.0, 0.5, 0.0]

    # Obligation component: walkaway=1.0 (lowest obligation), preferred=0.7, acceptable=0.3
    # Lower obligation = higher payoff
    obligation_base = [0.7, 0.3, 1.0]

    # Build user payoff matrix
    user_payoffs: list[list[float]] = [
        [
            _weighted_score(risk_base[i], financial_base[i], obligation_base[j], weights)
            for j in range(n)
        ]
        for i in range(n)
    ]

    clause_id = getattr(assessment, "clause_id", "unknown")

    counterparty_payoffs, source, symmetric = _build_counterparty_payoffs(
        n=n,
        user_idx=user_idx,
        confidence=confidence,
        weights=weights,
        paired_assessment=paired_assessment,
    )

    matrix = PayoffMatrix(
        clause_id=clause_id,
        actions=actions,
        user_payoffs=user_payoffs,
        counterparty_payoffs=counterparty_payoffs,
        symmetric=symmetric,
        source=source,
        weights=weights,
    )

    return matrix, None
