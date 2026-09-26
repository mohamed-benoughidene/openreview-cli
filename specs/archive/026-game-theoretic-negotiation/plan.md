# Implementation Plan: Game-Theoretic Negotiation Assistant

**Branch**: `feat/026-game-theoretic-negotiation` | **Date**: 2026-07-07 | **Spec**: specs/026-game-theoretic-negotiation/spec.md

**Input**: Feature specification from `/specs/026-game-theoretic-negotiation/spec.md`

## Summary

Add `src/openreview_cli/negotiation/` module implementing a lightweight game-theoretic negotiation assistant. Consumes existing single-party `ClauseAssessment` (position, confidence), bilateral `PairedAssessment` (divergence, RCBSF taxonomy), and 3-position playbook data to build clause-level payoff matrices. Computes equilibrium strategy via three models: pure Nash (NashPy), logit QRE (bounded rationality), and Level-k (iterated best-response). Outputs clause-by-clause strategy recommendations with Amber confidence annotations. No external API calls; all computation is local NumPy. Output format reuses existing review report infrastructure.

## Technical Context

**Language/Version**: Python 3.12 (project constraint)

**Primary Dependencies**:
- `numpy` — already a transitive dependency, used for all solver computation
- No new external dependencies. Nash solver uses hand-rolled NumPy support enumeration (≤6×6).

**Storage**: None for core computation. Optional caching of computed equilibria via existing SQLite storage layer (deferred to future).

**Testing**: pytest (existing project infra). Unit tests for payoff matrix construction, equilibrium solvers, bounded-rationality layers. Integration tests mock NashPy at the algorithm boundary.

**Target Platform**: Linux, macOS (project standard)

**Project Type**: CLI tool (existing Typer app)

**Performance Goals**:
- Per-clause equilibrium computation < 100 ms (NashPy support enumeration on ≤6×6 games)
- Per-clause QRE fixed-point iteration < 50 ms (≤1000 iterations)
- Total for 30-clause contract < 5 s
- Peak memory < 5 MB for full computation (no new large in-memory structures)

**Constraints**:
- Peak memory must stay under existing 100 MB budget (NLP model exempt)
- No external API calls — all computation local
- PII data from clause assessments must not appear in output (reuse existing stripping)
- All output must use descriptive/advisory language; never "sign this" or "reject this"
- Amber escape hatch required on all recommendations (per blueprint §6)

**Scale/Scope**: 2-party negotiation, clause-level (no cross-clause trade-offs). Up to 30 clauses per contract. 2-6 actions per game.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | **Pass** | No new external API calls. Existing PII pipeline applies to any clause text read. |
| II. Local-First, CLI-Only | **Pass** | All computation is local. No server, no daemon, no telemetry. NashPy + NumPy are pure computation. |
| III. Hardware-Bounded | **Pass** | Per-clause matrices ≤6×6. Total memory for 30 clauses < 1 MB. No full-document loads. |
| IV. Dependency Minimalism | **Pass** | Zero new deps. Nash solver is ~80 lines of NumPy (support enumeration for ≤6×6). QRE/Level-k each ~50 lines. |
| V. Spec-Driven, YAGNI | **Pass** | No speculative abstractions. No interface with one implementation. No deferred config knobs. |
| Forbidden Deps | **Pass** | No langchain, llama-index, FAISS, spaCy, sentence-transformers, Click, loguru, FastAPI/Flask. |

**Constitution Gate**: ✅ PASS — all principles satisfied.

## Project Structure

### Documentation (this feature)

```text
specs/026-game-theoretic-negotiation/
├── plan.md              # This file
├── research.md          # Phase 0 - resolved unknowns
├── data-model.md        # Phase 1 - data model design
├── quickstart.md        # Phase 1 - validation guide
├── contracts/           # Phase 1 - interface contracts
│   ├── negotiation-cmd.yaml      # CLI command schema
│   ├── payoff-matrix-contract.md # Payoff matrix data contract
│   └── equilibrium-strategy.md   # Equilibrium strategy output contract
└── tasks.md             # Phase 2 (speckit.tasks output)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── negotiation/                        # NEW module
│   ├── __init__.py                     # Public API: run_negotiation, NegotiationReport
│   ├── models.py                       # NegotiationData, PayoffMatrix, EquilibriumStrategy, NegotiationReport
│   ├── payoffs.py                      # Build payoff matrices from ClauseAssessment + bilateral data
│   ├── solvers.py                      # Nash (NashPy), QRE, Level-k equilibrium solvers
│   ├── recommend.py                    # Strategy recommendation + Amber annotation logic
│   └── report.py                       # Report formatting (terminal + JSON)

tests/
├── unit/
│   ├── test_negotiation_models.py      # Model validation, edge cases
│   ├── test_negotiation_payoffs.py     # Payoff matrix construction
│   ├── test_negotiation_solvers.py     # Nash/QRE/Level-k correctness
│   └── test_negotiation_recommend.py   # Recommendation + Amber logic
├── integration/
│   └── test_negotiation_pipeline.py    # End-to-end with mocked existing modules
└── fixtures/
    └── negotiation/                    # Test data: sample assessments, payoffs
```

**Structure Decision**: New `negotiation/` module under existing `src/openreview_cli/` package. Follows the same pattern as `review/` and `bilateral/`. One main pipeline function (`run_negotiation`) with clear sub-modules for each concern. Tests mirror project convention.

## Complexity Tracking

No constitution violations — all principles satisfied. No complexity justification needed.

| Complexity | Why Needed | Simpler Alternative Rejected Because |
|------------|------------|--------------------------------------|
| Three solver implementations (Nash, QRE, Level-k) | FR-003 requires bounded rationality. Users need to see how different models converge/diverge. | Single Nash solver would violate FR-003. Users need model comparison for confidence calibration. |
| Separate payoffs.py module | Payoff construction from ClauseAssessment + bilateral data is non-trivial (~80 lines) and independently testable. | Inlining into __init__.py would violate single-responsibility and make testing harder. |
| Amber annotation in recommend.py | FR-006 requires assumption labeling + blueprint §6 mandates Amber escape hatch for all output. | Output without confidence flags would violate spec. Amber logic is cross-cutting but remains in one module. |

## Phase 0: Research Complete

See `research.md` for full resolution of all unknowns:
- U1: NashPy API — `nash.Game(A, B)` + `support_enumeration()` / `lemke_howson_enumeration()`
- U2: QRE — logit QRE fixed-point iteration in NumPy (~30 lines)
- U3: Level-k — iterative best-response, cap at k=3 (~25 lines)
- U4: Payoff function — 3-component linear: risk + financial + obligation, default equal weights
- U5: Existing model reuse — `ClauseAssessment.position` maps to actions, `PairedAssessment.divergence` guides symmetry
- U6: License — NashPy MIT, compatible with AGPL-3.0

## Phase 1: Design Complete

See `data-model.md`, `contracts/`, and `quickstart.md` for design outputs.

**Key design decisions**:
- No new external API calls — all solvers are local NumPy/NashPy
- Three solver modes: pure Nash, logit QRE (default λ=1.0), Level-k (default k=2)
- Fallback chain: Nash solver first; if no pure/mixed equilibrium found → QRE (λ=1.0) → Amber confidence flag.
- Payoff matrices built from existing playbook positions (preferred/acceptable/walkaway)
- Output uses existing report format patterns (Rich tables + JSON)
- All recommendations annotated with confidence level; Amber flag if confidence < confidence_threshold (default 0.7, configurable via `--confidence-threshold` CLI flag)

## Agent Context Update

Plan reference in `AGENTS.md` updated to point to this file.
