# Equilibrium Strategy Output Contract

**Contract ID**: equilibrium-strategy-v1
**Schema Version**: 1.0.0
**Purpose**: Define the structure of equilibrium strategy recommendations output by the negotiation assistant.

## Per-Clause Strategy

```python
@dataclass(slots=True)
class EquilibriumStrategy:
    clause_id: str
    model: str                        # "nash", "qre", "level_k"
    model_params: dict[str, float]    # {"lambda": 1.0} for QRE, {"k": 2} for level-k
    user_strategy: list[float]        # Mixed strategy probability vector
    counterparty_strategy: list[float]
    predicted_outcome: str            # e.g. "acceptable/acceptable"
    suggested_counteroffer: str       # Human-readable recommendation
    fallback_position: str            # If primary is untenable
    equilibrium_type: str             # "pure", "mixed", "multiple", "no_equilibrium"
    confidence: float                 # [0.0, 1.0]
    is_amber: bool                    # True if confidence < threshold
    assumptions: list[str]            # Assumptions made in this analysis
```

## Output Formats

### Terminal Table (Rich, default)

```
┌─────────────┬───────────────┬─────────────────┬──────────────┬──────────┐
│ Clause      │ Recommended   │ Equilibrium     │ Confidence   │ Status   │
│             │ Counteroffer  │ Type            │              │          │
├─────────────┼───────────────┼─────────────────┼──────────────┼──────────┤
│ 1.1         │ Acceptable    │ Pure Nash       │ 0.85         │ 🟢       │
│ 1.2         │ Preferred     │ Mixed           │ 0.62         │ 🟡 Amber │
│ 2.1         │ Walkaway      │ No Equilibrium  │ 0.45         │ 🟡 Amber │
└─────────────┴───────────────┴─────────────────┴──────────────┴──────────┘
```

### JSON

```json
{
  "schema_version": "1.0.0",
  "experimental": true,
  "generated_at": "2026-07-07T12:00:00Z",
  "document": {"filename": "contract.pdf", "clause_count": 5},
  "strategies": [
    {
      "clause_id": "1.1",
      "model": "qre",
      "model_params": {"lambda": 1.0},
      "user_strategy": [0.7, 0.3, 0.0],
      "counterparty_strategy": [0.2, 0.6, 0.2],
      "predicted_outcome": "preferred/acceptable",
      "suggested_counteroffer": "Propose preferred terms; counterparty likely to counter with acceptable",
      "fallback_position": "acceptable",
      "equilibrium_type": "mixed",
      "confidence": 0.85,
      "is_amber": false,
      "assumptions": ["Counterparty payoffs inferred from bilateral alignment data"]
    }
  ],
  "summary": {
    "total_clauses": 5,
    "equilibrium_distribution": {"pure": 2, "mixed": 2, "multiple": 0, "no_equilibrium": 1},
    "amber_count": 2,
    "avg_confidence": 0.72,
    "impasse_count": 1,
    "deadlock_risk": true
  }
}
```

## Amber Annotation Rules

Amber flag (`is_amber: true`) is set when ANY of:

1. **Confidence < threshold** (default 0.7)
   - Low assessment confidence → low strategic confidence
   - Uncertain equilibrium (divergent solver results across models) → low confidence

2. **Counterparty payoff source is uncertain**
   - `source == "estimated"` or `source == "unknown"`
   - Asymmetric information with no bilateral comparison data

3. **Multiple equilibria exist** with conflicting recommended actions
   - Solver found >1 equilibrium and they recommend different user actions

4. **Impasse detected**
   - All actions have high walkaway probability (≥0.8)
   - No agreement possible → deadlock risk

5. **Solver mismatch**
   - Different solver types (Nash vs QRE vs Level-k) produce contradictory recommendations
   - Flag as Amber with explanation of model disagreement

## Language Constraints

All output text must follow advisory language rules:

| Allowed | Forbidden |
|---------|-----------|
| "The model suggests considering..." | "Sign this clause" |
| "Equilibrium analysis indicates..." | "Reject this provision" |
| "Consider proposing acceptable terms" | "You must accept this" |
| "Based on available data, preferred terms..." | "This is the correct strategy" |

The disclaimer `EXPERIMENTAL and advisory only` must appear prominently (at top of terminal output, top-level field in JSON).
