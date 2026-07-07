"""Data models for the game-theoretic negotiation assistant."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from enum import StrEnum


class SolverType(StrEnum):
    """Supported equilibrium solver types."""

    NASH = "nash"
    QRE = "qre"
    LEVEL_K = "level_k"


class PayoffSource(StrEnum):
    """How counterparty payoffs were determined."""

    KNOWN = "known"
    INFERRED_FROM_ALIGNMENT = "inferred_from_alignment"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


@dataclasses.dataclass(slots=True, frozen=True)
class PayoffMatrix:
    """Clause-level payoff matrix for both players.

    Represents the clause-level game as payoff matrices for both players.
    Actions map to indices in the n x n matrix.
    """

    clause_id: str
    actions: list[str]
    user_payoffs: list[list[float]]
    counterparty_payoffs: list[list[float]]
    symmetric: bool
    source: PayoffSource | str
    weights: dict[str, float]

    def __post_init__(self) -> None:
        n_actions = len(self.actions)
        if not (2 <= n_actions <= 6):
            raise ValueError(f"actions must have 2-6 entries, got {n_actions}")

        if len(self.user_payoffs) != n_actions:
            raise ValueError(
                f"user_payoffs rows ({len(self.user_payoffs)}) must match actions ({n_actions})"
            )
        if len(self.counterparty_payoffs) != n_actions:
            raise ValueError(
                f"counterparty_payoffs rows ({len(self.counterparty_payoffs)}) "
                f"must match actions ({n_actions})"
            )

        for row in self.user_payoffs:
            if len(row) != n_actions:
                raise ValueError("user_payoffs must be square")
            for val in row:
                if not 0.0 <= val <= 1.0:
                    raise ValueError(f"payoff value {val} outside [0, 1]")

        for row in self.counterparty_payoffs:
            if len(row) != n_actions:
                raise ValueError("counterparty_payoffs must be square")
            for val in row:
                if not 0.0 <= val <= 1.0:
                    raise ValueError(f"counterparty payoff value {val} outside [0, 1]")


@dataclasses.dataclass(slots=True, frozen=True)
class EquilibriumStrategy:
    """Output of equilibrium computation for one clause.

    Includes the equilibrium result, predicted outcome, confidence
    annotation, and any assumptions made during computation.
    """

    clause_id: str
    model: str
    model_params: dict[str, float]
    user_strategy: list[float]
    counterparty_strategy: list[float]
    predicted_outcome: str
    suggested_counteroffer: str
    fallback_position: str
    equilibrium_type: str
    confidence: float
    is_amber: bool
    assumptions: list[str]
    diverges_from_alignment: bool = False
    cross_reference_note: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        # Verify strategy probabilities sum to ~1.0
        for label, vec in [
            ("user_strategy", self.user_strategy),
            ("counterparty_strategy", self.counterparty_strategy),
        ]:
            total = sum(vec)
            if abs(total - 1.0) > 1e-6:
                raise ValueError(f"{label} probabilities sum to {total}, expected 1.0")


@dataclasses.dataclass(slots=True, frozen=True)
class NegotiationSummary:
    """Aggregate statistics across all clauses in a negotiation run."""

    total_clauses: int = 0
    equilibrium_distribution: dict[str, int] = dataclasses.field(default_factory=dict)
    amber_count: int = 0
    avg_confidence: float = 0.0
    impasse_count: int = 0
    deadlock_risk: bool = False


@dataclasses.dataclass(slots=True)
class NegotiationReport:
    """Top-level output of a negotiation run.

    Aggregates all clause-level equilibrium strategies, payoff matrices,
    and summary statistics. Not frozen because ``generated_at`` is set
    dynamically.
    """

    experimental: bool = True
    disclaimer: str = (
        "EXPERIMENTAL and advisory only. This analysis uses game-theoretic "
        "models with bounded-rationality approximations. It is not a substitute "
        "for professional legal or negotiation advice. Review with qualified "
        "legal counsel before acting on any recommendation."
    )
    strategies: list[EquilibriumStrategy] = dataclasses.field(default_factory=list)
    payoff_matrices: list[PayoffMatrix] = dataclasses.field(default_factory=list)
    summary: NegotiationSummary = dataclasses.field(default_factory=NegotiationSummary)
    playbook_id: str = ""
    generated_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(UTC))
    confidence_threshold: float = 0.7
    schema_version: str = "0.1.0"
