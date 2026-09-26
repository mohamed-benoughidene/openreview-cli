# Research: Game-Theoretic Negotiation Assistant

**Feature**: 026-game-theoretic-negotiation
**Date**: 2026-07-07
**Status**: Resolved

## Unknowns Identified from Spec

| # | Unknown | Resolution Method | Status |
|---|---------|-------------------|--------|
| U1 | NashPy API surface (Game creation, equilibrium algorithms) | Web fetch official docs | RESOLVED |
| U2 | QRE (Quantal Response Equilibrium) formula and implementation | Web fetch academic sources | RESOLVED |
| U3 | Level-k bounded rationality formulas | Web fetch academic sources | RESOLVED |
| U4 | Payoff function design linking clause assessments to game payoffs | Design decision (see below) | RESOLVED |
| U5 | How to consume bilateral PairedAssessment + single-party ClauseAssessment | Code review of existing models | RESOLVED |
| U6 | NashPy dependency license compatibility (MIT vs AGPL-3.0) | Web fetch PyPI/ license | RESOLVED |

---

## U1: Nash Equilibrium — Hand-Rolled Support Enumeration

**Decision**: Implement support enumeration directly in NumPy. No external game-theory library.

**Rationale**:
- Support enumeration is a straightforward algorithm: enumerate equal-sized support pairs, solve linear system with `np.linalg.solve`, verify best-response conditions.
- ~80 lines of NumPy replaces a full dependency (nashpy).
- Only needed for ≤6×6 clause-level games. The O(2^(n²)) enumeration over supports is fine at this size.
- Zero new dependencies = faster install, no license review, no version drift.

**Implementation**:
```python
import numpy as np
from itertools import combinations

def support_enumeration(A, B):
    m, n = A.shape
    for r in range(1, min(m, n, 6) + 1):
        for I in combinations(range(m), r):
            for J in combinations(range(n), r):
                eq = _solve_support(A, B, I, J)
                if eq: yield eq
```

Where `_solve_support` solves the linear system `A[I,J] @ y_J = v` with `sum(y_J) = 1` and checks best-response conditions for all rows/columns. See `solvers.py` for full implementation.

---

## U2: QRE (Quantal Response Equilibrium)

**Decision**: Implement logit QRE as a fixed-point iteration using NumPy. No new dependency.

**Rationale**:
- Logit QRE is the standard bounded-rationality model in behavioral game theory (McKelvey & Palfrey, 1995).
- Formula: P_i(a_i) = exp(λ · EU_i(a_i, σ_{-i})) / Σ_{a'_i} exp(λ · EU_i(a'_i, σ_{-i}))
  - λ ≥ 0 is the rationality parameter. λ → ∞ recovers Nash; λ → 0 is uniform random.
- Fixed-point iteration: start with uniform mixed strategies, compute expected utilities, update choice probabilities via logit, repeat until convergence (||σ_new - σ_old|| < ε).
- Pure NumPy implementation is ~30 lines, no new deps needed.
- Computational cost: O(iterations × n_actions²) per clause — negligible at clause level (max 6 actions).

**Implementation approach**:
```python
import numpy as np

def logit_qre(A: np.ndarray, B: np.ndarray, lam: float = 1.0,
               max_iter: int = 1000, tol: float = 1e-6):
    """Compute logit QRE for a 2-player game.

    A, B = payoff matrices (n x m). lam = rationality parameter.
    Returns (row_strategy, col_strategy) as probability vectors.
    """
    n, m = A.shape
    row_strat = np.ones(n) / n
    col_strat = np.ones(m) / m

    for _ in range(max_iter):
        # Expected utilities
        eu_row = A @ col_strat
        eu_col = B.T @ row_strat

        new_row = np.exp(lam * eu_row)
        new_row = new_row / new_row.sum()

        new_col = np.exp(lam * eu_col)
        new_col = new_col / new_col.sum()

        if (np.linalg.norm(new_row - row_strat) < tol and
            np.linalg.norm(new_col - col_strat) < tol):
            break

        row_strat, col_strat = new_row, new_col

    return row_strat, col_strat
```

**Alternatives considered**:
- `quantecon` library — has QRE implementation but adds 4+ MB dependency.
- `PyCE` library — unmaintained, Python 3.8 only.
- Scipy `fsolve` — overkill for 2-player games, adds scipy as dep.

---

## U3: Level-k Bounded Rationality

**Decision**: Implement iterative level-k with uniform level-0 default. Cap at k=3. Pure NumPy, no new deps.

**Rationale**:
- Level-0: uniform random over actions (standard assumption).
- Level-1: best-respond to level-0's uniform distribution.
- Level-2: best-respond to level-1's mixed strategy.
- Level-k: best-respond to level-(k-1).
- Cap at k=3 per behavioral economics literature (most real players are level-1 or level-2; level-3+ is indistinguishable from Nash).
- Implementation: ~25 lines of NumPy.

**Implementation approach**:
```python
def level_k(A: np.ndarray, B: np.ndarray, k: int = 2):
    """Compute level-k strategies for 2-player game.

    Level-0 = uniform. Level-1 best-responds to level-0, etc.
    Returns (row_strategy, col_strategy) as probability vectors.
    """
    n, m = A.shape
    row_strat = np.ones(n) / n
    col_strat = np.ones(m) / m

    for _ in range(k):
        # Row player best-responds to current col strategy
        eu_row = A @ col_strat
        row_strat = np.zeros(n)
        row_strat[eu_row.argmax()] = 1.0

        # Column player best-responds to current row strategy
        eu_col = B.T @ row_strat
        col_strat = np.zeros(m)
        col_strat[eu_col.argmax()] = 1.0

    return row_strat, col_strat
```

**Alternatives considered**: Cognitive Hierarchy Model (CHM) — more accurate but requires computing all lower-level distributions; level-k is simpler and matches literature for 2-player games.

---

## U4: Payoff Function Design

**Decision**: Three-component linear payoff: payoff = w₁·risk + w₂·financial + w₃·obligation. Weights default to equal (1/3 each), user-configurable.

**Rationale**:
- Each player has 3 positions per clause: preferred, acceptable, walkaway (from playbook/ClauseAssessment.position).
- Each position maps to a different "action" (term proposal) in the negotiation game.
- Payoff for each (user_action, counterparty_action) pair is computed from:
  1. **Risk score**: derived from assessment confidence and playbook category. Higher risk = higher urgency to secure favorable terms.
  2. **Financial impact**: derived from the clause text and position. Estimated monetary/economic impact of each outcome.
  3. **Obligation weight**: from the clause's position relative to walkaway. Closer to walkaway = higher weight.

- Each component normalized to [0, 1].
- Default weights equal (1/3 each). User can override per run.
- Payoff matrix size: n_actions × n_actions where n_actions = number of distinct positions across both parties (typically 3: preferred/acceptable/walkaway).

**Under asymmetric information** (only user's position known):
- Counterparty payoffs estimated using alignment data from bilateral comparison.
- `DivergenceVerdict.divergent` → payoff asymmetry (lower alignment → more divergent payoffs).
- `DivergenceVerdict.aligned` → payoff symmetry (same terms valued similarly by both).
- All estimates marked with confidence flag in output.

**Alternatives considered**:
- Log-utility (CARA/CRRA) — overkill, no empirical basis for contract negotiation.
- Single-dimension payoff (risk only) — loses financial and obligation distinction.
- Machine-learned payoff — violates hardware budget, no training data.

---

## U5: Consuming Existing Models

**Decision**: Reuse `ClauseAssessment.position` (preferred/acceptable/walkaway), `PairedAssessment.divergence` and `PairedAssessment.rcbsf_details` from bilateral. No new extraction work.

**Key integration points**:
- `ClauseAssessment.position` → maps to a player action (action = the term the party proposes).
- `ClauseAssessment.confidence` → weights payoff certainty. Low confidence → wider variance in equilibrium estimates.
- `PairedAssessment.divergence` → determines whether payoff matrices are symmetric or asymmetric.
- `PairedAssessment.rcbsf_details` → qualitative context for negotiation recommendations.
- `Playbook` categories → define the universe of clauses to analyze.

---

## U6: License Compatibility

**Decision**: No new dependencies = no license review needed. NumPy (BSD-3-Clause) is already a transitive dep.

---

## Summary of Dependency Changes

| Package | Version | License | Reason | Action |
|---------|---------|---------|--------|--------|
| numpy | >=1.26 | BSD-3 | Already a transitive dep | No action needed |

Zero new dependencies. Nash solver uses hand-rolled NumPy support enumeration. QRE and Level-k are pure NumPy implementations within the project module.
