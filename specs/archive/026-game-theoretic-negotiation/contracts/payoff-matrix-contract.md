# Payoff Matrix Data Contract

**Contract ID**: payoff-matrix-v1
**Schema Version**: 1.0.0
**Purpose**: Define the structure and construction rules for clause-level payoff matrices used in equilibrium computation.

## Data Structure

A payoff matrix represents the negotiation game for a single clause. It is a 2-player normal-form game where:
- **Players**: User (row), Counterparty (column)
- **Actions**: Distinct positions (preferred, acceptable, walkaway) that each party can propose
- **Payoffs**: Utility values in [0, 1] computed from clause assessment data

```python
@dataclass(slots=True)
class PayoffMatrix:
    clause_id: str
    actions: list[str]                 # e.g. ["preferred", "acceptable", "walkaway"]
    user_payoffs: list[list[float]]    # shape (n, n), row = user action, col = counterparty action
    counterparty_payoffs: list[list[float]]  # shape (n, n), same ordering
    symmetric: bool                    # True if user == counterparty matrices
    source: PayoffSource               # How counterparty payoffs were determined
    weights: dict[str, float]          # {"risk": w1, "financial": w2, "obligation": w3}
```

## Construction Rules

### Action Mapping

Each position from the playbook becomes an action:

| Position | Action Label | Meaning |
|----------|-------------|---------|
| PREFERRED | "preferred" | Party proposes their ideal terms |
| ACCEPTABLE | "acceptable" | Party can accept these terms |
| WALKAWAY | "walkaway" | Party walks rather than accepts |

If a party has multiple "acceptable" positions, each becomes a separate action.

### Payoff Computation

Payoff = w_risk * risk_component + w_financial * financial_component + w_obligation * obligation_component

Default weights: {risk: 0.33, financial: 0.33, obligation: 0.34}

#### Risk Component
- Derived from `ClauseAssessment.confidence`
- Higher confidence → higher risk component for preferred action (party knows what they want)
- Lower confidence → flatter payoffs across actions (party is uncertain)
- Range: [0.3, 1.0] — never zero, ensures game has structure

#### Financial Component
- Estimated from clause text and position
- PREFERRED = 1.0 (best economic outcome)
- ACCEPTABLE = 0.5 (neutral)
- WALKAWAY = 0.0 (worst — deal dies)
- When only user's position is known, counterparty's financial component is estimated from `PairedAssessment.divergence`:
  - `aligned`: symmetric (same financial impact for both)
  - `divergent`: asymmetric (opposite financial preference)

#### Obligation Component
- Measures how strongly a party is committed to their position
- Derived from position type:
  - WALKAWAY = 1.0 (non-negotiable)
  - PREFERRED = 0.7 (strong desire)
  - ACCEPTABLE = 0.3 (flexible)
- Counterparty obligation estimated from divergence + alignment quality

### Counterparty Payoff Estimation

| Source | Condition | Behavior |
|--------|-----------|----------|
| `known` | Both parties explicitly defined positions | Use both sets directly, symmetric=False |
| `inferred_from_alignment` | Bilateral comparison exists | Derive from divergence: aligned → near-symmetric, divergent → asymmetric |
| `estimated` | Only user's position known | Mirror user payoffs with noise (±0.1), symmetric=True assumed |
| `unknown` | No data available | Return None — clause cannot be analyzed |

### Validation Rules

1. `user_payoffs` and `counterparty_payoffs` must be square (n × n where n = len(actions))
2. All payoff values must be in [0, 1]
3. If any action probability sum is required, must be 1.0 ± 1e-6
4. At least 2 actions required (1-action game is degenerate)
5. Maximum 6 actions (beyond this, support enumeration is exponential)
