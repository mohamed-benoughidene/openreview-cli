# Data Model: Game-Theoretic Negotiation Assistant

**Feature**: 026-game-theoretic-negotiation
**Date**: 2026-07-07
**Status**: Final

## Overview

Four new entities support the negotiation pipeline. All are `@dataclass` models in `src/openreview_cli/negotiation/models.py`. They consume existing entities from `review.models` and `bilateral.models` — no changes to those modules.

## Entity Relationship

```
ClauseAssessment (existing) ──→ PayoffMatrix ──→ EquilibriumStrategy
         │                             │                   │
         │                             │                   ▼
         └── position          Playbook (existing)   NegotiationReport
         └── confidence              │
         └── clause_text             └── categories
         └── playbook_category

PairedAssessment (existing)
         │
         ├── divergence
         ├── primary_dimension
         └── confidence
```

## Entity: PayoffMatrix

**Purpose**: Represents the clause-level game as payoff matrices for both players.

**File**: `negotiation/models.py`

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `clause_id` | `str` | Reference to the clause being analyzed | Must match `ClauseAssessment.clause_id` |
| `actions` | `list[str]` | Named actions (e.g. ["preferred", "acceptable", "walkaway"]) | 2-6 entries |
| `user_payoffs` | `list[list[float]]` | User's payoff matrix, shape (n_actions × n_actions) | All values in [0, 1] |
| `counterparty_payoffs` | `list[list[float]]` | Counterparty's payoff matrix, same shape | All values in [0, 1] |
| `symmetric` | `bool` | Whether matrices are identical (derived from divergence) | — |
| `source` | `str` | How counterparty payoffs were determined: `"known"`, `"inferred_from_alignment"`, `"estimated"`, `"unknown"` | — |
| `weights` | `dict[str, float]` | Payoff component weights used: `{"risk": w1, "financial": w2, "obligation": w3}` | Must sum to ≈1.0 |

**Construction rules**:
- Actions = distinct positions found across both parties' assessments for this clause.
- If only user's position is known, counterparty actions = same set (symmetric action space).
- User payoff for (action_i, action_j) = w_risk·risk_i + w_fin·fin_i + w_obl·obl_j
  - Higher payoff when user's action aligns with their own position preference AND counterparty concedes.
- Counterparty payoff estimated from divergence data (aligned → symmetric, divergent → asymmetric with noise).
- `source` field documents confidence in counterparty payoff estimates per FR-006.

## Entity: EquilibriumStrategy

**Purpose**: Output of a single equilibrium computation for one clause.

**File**: `negotiation/models.py`

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `clause_id` | `str` | Reference to clause | Must match `PayoffMatrix.clause_id` |
| `model` | `str` | Solver used: `"nash"`, `"qre"`, `"level_k"` | — |
| `model_params` | `dict[str, float]` | Parameters: `{"lambda": 1.0}` for QRE, `{"k": 2}` for level-k, `{}` for Nash | — |
| `user_strategy` | `list[float]` | User's equilibrium mixed strategy (probability vector) | Sums to 1.0, each ≥ 0 |
| `counterparty_strategy` | `list[float]` | Counterparty's equilibrium mixed strategy | Sums to 1.0, each ≥ 0 |
| `predicted_outcome` | `str` | Most likely action pair (e.g. `"acceptable/acceptable"`) | — |
| `suggested_counteroffer` | `str` | Recommended user action (human-readable) | — |
| `fallback_position` | `str` | Next-best position if primary is untenable | — |
| `equilibrium_type` | `str` | `"pure"`, `"mixed"`, `"multiple"`, `"no_equilibrium"` | — |
| `confidence` | `float` | Overall confidence 0.0-1.0 | [0, 1] |
| `is_amber` | `bool` | True if confidence < threshold (default 0.7) | — |
| `assumptions` | `list[str]` | Assumptions made (e.g. "Counterparty payoff estimated from alignment data") | — |

**Computation rules**:
- Nash: use NashPy `support_enumeration()`, take first equilibrium. If multiple, mark `equilibrium_type = "multiple"` and pick the one maximizing user payoff.
- QRE: fixed-point iteration. λ default 1.0. If λ > 5.0, warn that result ≈ Nash.
- Level-k: k default 2. If k = 0, output uniform random (trivial).
- `confidence` = minimum of: assessment confidence, payoff construction confidence, solver convergence quality.
- `is_amber` set when confidence < 0.7 or when counterparty `source` is `"estimated"` or `"unknown"`.

## Entity: NegotiationReport

**Purpose**: Top-level output of a negotiation run, aggregating all clauses.

**File**: `negotiation/models.py`

| Field | Type | Description |
|-------|------|-------------|
| `experimental` | `bool` | Always True |
| `disclaimer` | `str` | Accuracy caveat + legal disclaimer (advisory language only) |
| `document` | `DocMeta` | Document metadata (from review pipeline) |
| `strategies` | `list[EquilibriumStrategy]` | Per-clause equilibrium strategies |
| `payoff_matrices` | `list[PayoffMatrix]` | Per-clause payoff matrices (reference for transparency) |
| `summary` | `NegotiationSummary` | Aggregate statistics |
| `playbook_id` | `str` | Playbook used |
| `generated_at` | `datetime` | Timestamp |
| `confidence_threshold` | `float` | Amber threshold for this run |
| `schema_version` | `str` | Output schema version |

## Entity: NegotiationSummary

**File**: `negotiation/models.py`

| Field | Type | Description |
|-------|------|-------------|
| `total_clauses` | `int` | Number of clauses analyzed |
| `equilibrium_distribution` | `dict[str, int]` | Count of pure/mixed/multiple/no_equilibrium |
| `amber_count` | `int` | Clauses requiring Amber flag |
| `avg_confidence` | `float` | Average confidence across all strategies |
| `impasse_count` | `int` | Clauses where no agreement is possible (all walkaway) |
| `deadlock_risk` | `bool` | True if any clause at impasse |

## Enum: SolverType

**File**: `negotiation/models.py`

```python
class SolverType(StrEnum):
    NASH = "nash"        # Pure Nash equilibrium via NashPy
    QRE = "qre"          # Logit Quantal Response Equilibrium (NumPy)
    LEVEL_K = "level_k"  # Iterative best-response hierarchy (NumPy)
```

## Enum: PayoffSource

**File**: `negotiation/models.py`

```python
class PayoffSource(StrEnum):
    KNOWN = "known"                     # Both parties' positions explicitly defined
    INFERRED_FROM_ALIGNMENT = "inferred_from_alignment"  # From bilateral divergence
    ESTIMATED = "estimated"             # From clause text + playbook defaults
    UNKNOWN = "unknown"                 # No data available
```

## State Transitions

Not applicable — each negotiation run is stateless. Payoff matrices are constructed fresh from assessments and playbook data. Solver outputs are deterministic given the same inputs. No state machine, no session persistence.

## Validation Rules

1. `PayoffMatrix.actions` must have 2-6 entries. Games where either party has <2 positions are degenerate — skip with a warning.
2. `PayoffMatrix.user_payoffs` and `PayoffMatrix.counterparty_payoffs` must be square matrices of dimension len(actions).
3. `EquilibriumStrategy.user_strategy` must sum to 1.0 within 1e-6 tolerance.
4. If any action is "walkaway" with probability ≥ 0.8, mark clause as impasse.
5. Confidence > 1.0 or < 0.0 raises ValueError.
