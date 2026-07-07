# Quickstart: Game-Theoretic Negotiation Assistant

**Feature**: 026-game-theoretic-negotiation
**Date**: 2026-07-07
**Status**: Validation guide

## Prerequisites

- Python 3.12, uv installed
- Project deps installed: `uv sync`
- Extra dep: `uv add nashpy>=0.0.43`
- A contract document (.pdf or .docx) for testing
- (Optional) A playbook YAML file with 3-position definitions

## Setup

```bash
# From repo root
uv sync
uv add "nashpy>=0.0.43"
```

## Validation Scenarios

### Scenario 1: Basic Negotiation Analysis (FR-001, FR-002)

**Goal**: Verify the assistant produces clause-by-clause equilibrium strategy recommendations from position data.

**Command**:
```bash
uv run openreview negotiate tests/fixtures/sample-nda.pdf
```

**Expected outcomes**:
- Output shows a table with one row per clause
- Each row has: clause ID, recommended counteroffer, equilibrium type, confidence, status
- No error messages or stack traces
- Disclaimer appears at top of output
- All language is advisory (no "sign this" or "reject this")

**Failure conditions**:
- Command exits with non-zero code
- No strategy recommendations produced
- All clauses marked as Amber with "unknown" source (indicates payoff construction failure)

### Scenario 2: Bounded Rationality Model Selection (FR-003)

**Goal**: Verify three solver modes produce different — but reasonable — outputs.

**Commands**:
```bash
uv run openreview negotiate sample.pdf --solver nash
uv run openreview negotiate sample.pdf --solver qre --rationality 1.0
uv run openreview negotiate sample.pdf --solver level_k --depth 2
```

**Expected outcomes**:
- All three commands complete successfully
- Outputs differ in predicted outcomes or confidence levels (bounded rationality diverges from pure Nash)
- QRE with λ=1.0 shows more mixed strategies than pure Nash
- Level-k with k=2 shows intermediate behavior
- Pure Nash may have "no equilibrium" cases where QRE/Level-k produce mixed strategies

**Failure conditions**:
- Any solver crashes with NumPy/NashPy error
- All three solvers produce identical output (indicates bounded rationality layer not working)
- Solver takes >5 seconds for 10-clause contract

### Scenario 3: Asymmetric Information Handling (FR-006)

**Goal**: Verify the assistant clearly labels assumptions when counterparty positions are unknown.

**Setup**: Use a playbook with only user's positions defined. No bilateral comparison data available.

**Command**:
```bash
uv run openreview negotiate sample.pdf --playbook-path tests/fixtures/partial-playbook.yaml
```

**Expected outcomes**:
- All recommendations include "assumptions" annotations
- Counterparty payoff source is "estimated" or "unknown"
- All clauses marked Amber (due to uncertainty)
- Output text explicitly states which values were assumed
- User guidance: "Define counterparty positions or run bilateral comparison for more accurate analysis"

### Scenario 4: What-If Exploration (FR-007)

**Goal**: Verify adjusting position parameters changes equilibrium recommendations.

**Commands**:
```bash
# Run with default weights (balanced)
uv run openreview negotiate sample.pdf --format json --output default.json

# Run with heavy risk focus
uv run openreview negotiate sample.pdf --weights 0.7,0.15,0.15 --format json --output risk-focused.json

# Compare
diff default.json risk-focused.json
```

**Expected outcomes**:
- Different weight profiles produce different predicted outcomes for at least some clauses
- JSON output is parseable and matches the `equilibrium-strategy.md` schema
- Re-running with same parameters produces identical output (deterministic)

### Scenario 5: Edge Cases

#### No playbook positions defined
```bash
uv run openreview negotiate sample.pdf --playbook-path empty.yaml
```
**Expected**: Graceful guidance output: "No positions defined. Please define positions in a playbook first."

#### Impasse (all walkaway)
**Setup**: Playbook where all user positions for a clause are "walkaway"
```bash
uv run openreview negotiate sample.pdf --playbook-path impasse-playbook.yaml
```
**Expected**: Clause flagged as "impasse" with deadlock risk warning. Suggested fallback strategy.

#### Large contract (30+ clauses)
```bash
uv run openreview negotiate large-contract.pdf
```
**Expected**: Completes in <5 seconds. All 30+ clauses analyzed. Memory usage <5 MB over baseline.

## Running Tests

```bash
# Unit tests
uv run pytest tests/unit/test_negotiation_models.py -v
uv run pytest tests/unit/test_negotiation_payoffs.py -v
uv run pytest tests/unit/test_negotiation_solvers.py -v
uv run pytest tests/unit/test_negotiation_recommend.py -v

# Integration tests
uv run pytest tests/integration/test_negotiation_pipeline.py -v

# All negotiation tests
uv run pytest tests/unit/test_negotiation_* tests/integration/test_negotiation_pipeline.py -v

# Memory profile (must stay under 100 MB)
uv run pytest -m memory -k negotiation -v
```

## File Reference

| File | Purpose |
|------|---------|
| `specs/026-game-theoretic-negotiation/plan.md` | Implementation plan |
| `specs/026-game-theoretic-negotiation/data-model.md` | Data model definitions |
| `specs/026-game-theoretic-negotiation/contracts/negotiation-cmd.yaml` | CLI command schema |
| `specs/026-game-theoretic-negotiation/contracts/payoff-matrix-contract.md` | Payoff matrix contract |
| `specs/026-game-theoretic-negotiation/contracts/equilibrium-strategy.md` | Strategy output contract |
