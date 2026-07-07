# Tasks: Game-Theoretic Negotiation Assistant

**Input**: Design documents from `/specs/026-game-theoretic-negotiation/`
**Branch**: `feat/026-game-theoretic-negotiation`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: TDD is mandatory per project constitution. Every task that adds logic requires a test task immediately before it.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story this task belongs to (FND = Foundational, US1/US2/US3)
- Exact file paths in every description
- Test tasks appear BEFORE implementation tasks (TDD)

## Traceability

| Task ID | FR Ref | Contract Ref | User Story |
|---------|--------|-------------|------------|
| T001 | — | — | FND |
| T002 | — | — | FND |
| T003 | — | — | FND |
| T004 | FR-001, FR-002, FR-003, FR-006 | data-model.md entities | FND |
| T005 | FR-001, FR-002, FR-003, FR-006 | — | FND |
| T006 | FR-001, FR-002, FR-004, FR-006 | payoff-matrix-contract.md | US1 |
| T007 | FR-002, FR-003 | research.md U1, U2, U3 | US1 |
| T008 | FR-004, FR-006 | equilibrium-strategy.md | US1 |
| T009 | FR-001, FR-002, FR-004, FR-006 | payoff-matrix-contract.md | US1 |
| T010 | FR-002, FR-003 | research.md U1, U2, U3 | US1 |
| T011 | FR-004, FR-006 | equilibrium-strategy.md | US1 |
| T012 | FR-005, SC-002 | equilibrium-strategy.md (JSON schema), report.py pattern | US1 |
| T013 | FR-001, FR-002 | negotiation-cmd.yaml | US1 |
| T014 | FR-001, FR-002, FR-004, FR-005 | negotiation-cmd.yaml | US1 |
| T015 | FR-005, FR-006, SC-003 | — | US2 |
| T016 | FR-005, SC-003 | — | US2 |
| T017 | FR-005, SC-003 | — | US2 |
| T018 | FR-007 | — | US3 |
| T019 | FR-007 | — | US3 |
| T020 | FR-007 | negotiation-cmd.yaml (--weights, --rationality, --depth) | US3 |
| T021 | SC-001, SC-004 | — | POL |
| T022 | SC-001 | — | POL |
| T023 | — | quickstart.md | POL |
| T024 | — | constitution.md | POL |

---

## Phase 1: Setup — Dependency & Module Scaffold

**Purpose**: Add runtime dependency, create directory structure, seed test fixtures.

- [X] T001 [P] [FND] Add nashpy dependency: `uv add "nashpy>=0.0.43"`. Verify MIT license compatibility per research.md U6. Confirm in `pyproject.toml`.
      → FR ref: none (infrastructure)
- [X] T002 [P] [FND] Create `src/openreview_cli/negotiation/` module directory with `__init__.py` stub (exports placeholder).
      → FR ref: none (infrastructure)
- [X] T003 [P] [FND] Create `tests/fixtures/negotiation/` directory with sample mock data: 3 test playbook YAML files (full, partial, impasse), sample ClauseAssessment list, sample PairedAssessment list.
      → FR ref: none (test infrastructure)

**Checkpoint**: Dependency installed, module stub exists, test fixtures ready.

---

## Phase 2: Foundational — Core Data Models (P1)

**Purpose**: Data models shared across ALL user stories. Must be complete before any story work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational Models

- [X] T004 [P] [FND] Write unit tests for ALL negotiation data models in `tests/unit/test_negotiation_models.py`. Cover:
  - `PayoffMatrix` — construction, validation (2-6 actions out of range), value bounds [0,1], square matrix shape
  - `EquilibriumStrategy` — strategy probability sum to 1.0 ±1e-6, confidence [0,1], is_amber when confidence < threshold
  - `NegotiationReport` — disclaimer text, schema_version, generated_at
  - `NegotiationSummary` — counts, impasse detection, deadlock_risk flag
  - `SolverType` enum values (nash, qre, level_k)
  - `PayoffSource` enum values (known, inferred_from_alignment, estimated, unknown)
  - Edge cases: empty actions (rejected), single action (rejected), 6+ actions (rejected)
  - Validation: ValueError on confidence >1.0 or <0.0, non-square payoff matrix
  - `@dataclass(slots=True)` present on all dataclasses per constitution III
      → FR ref: FR-001, FR-002, FR-003, FR-006 | Contract ref: data-model.md entities

### Implementation for Foundational Models

- [X] T005 [FND] Implement `src/openreview_cli/negotiation/models.py` with:
  - `SolverType(StrEnum)` — NASH, QRE, LEVEL_K
  - `PayoffSource(StrEnum)` — KNOWN, INFERRED_FROM_ALIGNMENT, ESTIMATED, UNKNOWN
  - `PayoffMatrix` — `@dataclass(slots=True)`, fields per data-model.md §"Entity: PayoffMatrix"
  - `EquilibriumStrategy` — `@dataclass(slots=True)`, fields per data-model.md §"Entity: EquilibriumStrategy"
  - `NegotiationSummary` — `@dataclass(slots=True)`, fields per data-model.md §"Entity: NegotiationSummary"
  - `NegotiationReport` — `@dataclass(slots=True)`, fields per data-model.md §"Entity: NegotiationReport"
  - Validation: raise `ValueError` on invalid confidence, non-square matrix, <2 actions
  - `is_amber` computed property: confidence < threshold OR source in (ESTIMATED, UNKNOWN)
      → FR ref: FR-001, FR-002, FR-003, FR-006 | Contract ref: data-model.md entities

**Checkpoint**: Foundation ready — models complete, tested, validated. User story work can now begin.

---

## Phase 3: User Story 1 — Analyze Contract & Receive Equilibrium Strategy (Priority: P1) 🎯 MVP

**Goal**: User runs `openreview negotiate contract.pdf` and receives clause-by-clause equilibrium strategy recommendations with suggested counteroffers.

**Independent Test**: Run `uv run openreview negotiate tests/fixtures/sample-nda.pdf` — output shows per-clause strategy table, all language is advisory, no error messages.

### Tests for User Story 1 (TDD — write first, verify fail)

- [X] T006 [P] [US1] Write unit tests for payoff matrix construction in `tests/unit/test_negotiation_payoffs.py`. Cover:
  - `build_payoff_matrix()` from single `ClauseAssessment` + optional `PairedAssessment`
  - Action mapping: preferred→action[0], acceptable→action[1], walkaway→action[2]
  - 3-component payoff formula with default weights (risk 0.33, financial 0.33, obligation 0.34)
  - Risk component: high confidence → high risk for preferred, low confidence → flat payoffs
  - Financial component: preferred=1.0, acceptable=0.5, walkaway=0.0
  - Obligation component: walkaway=1.0, preferred=0.7, acceptable=0.3
  - Symmetric vs asymmetric matrix based on PairedAssessment.divergence
  - All 4 PayoffSource types: known, inferred_from_alignment, estimated, unknown
  - Edge case: only user position known → `source="estimated"`, symmetric=True, noise ±0.1
  - Edge case: no PairedAssessment → `source="unknown"`, returns None
  - Edge case: single action → skips clause with warning
      → FR ref: FR-001, FR-002, FR-004, FR-006 | Contract ref: payoff-matrix-contract.md

- [X] T007 [P] [US1] Write unit tests for equilibrium solvers in `tests/unit/test_negotiation_solvers.py`. Cover:
  - `solve_nash()` — NashPy `support_enumeration()`, pure/mixed/multiple/no_equilibrium detection
  - `solve_qre()` — logit fixed-point iteration, λ default 1.0, convergence <1e-6 tol
  - `solve_level_k()` — iterative best-response, k=2 default, uniform level-0
  - All three solvers accept same A, B payoff matrices (numpy ndarray)
  - Nash: multiple equilibria → pick user-payoff-maximizing, set `equilibrium_type="multiple"`
  - QRE: λ→0 → near-uniform; λ→∞ → approximates Nash
  - Level-k: k=0 → uniform random; k=1 → best-respond to uniform
  - Edge case: no equilibrium found → `equilibrium_type="no_equilibrium"`
  - Edge case: Nash finds no equilibrium → fallback to QRE with λ=1.0, result marked Amber
  - Edge case: all probability on walkaway ≥0.8 → impasse
  - Mock NashPy at algorithm boundary for deterministic testing
      → FR ref: FR-002, FR-003 | Contract ref: research.md U1, U2, U3

- [X] T008 [P] [US1] Write unit tests for recommendation logic in `tests/unit/test_negotiation_recommend.py`. Cover:
  - `build_recommendation(strategy, payoff_matrix)` → produces `EquilibriumStrategy` with human-readable `suggested_counteroffer`
  - Amber annotation: confidence < confidence_threshold → is_amber=True; source=ESTIMATED → is_amber=True; confidence_threshold defaults to 0.7 and is configurable via `--confidence-threshold` CLI flag (see T014)
  - Assumption list: populated from PayoffMatrix.source and PayoffSource enum
  - Fallback position: next-best action after predicted_outcome
  - Language rules: no "sign this", no "reject this", uses "suggests", "indicates", "recommends considering"
  - Always includes disclaimer text
      → FR ref: FR-004, FR-006 | Contract ref: equilibrium-strategy.md

### Implementation for User Story 1

- [X] T009 [US1] Implement payoff matrix construction in `src/openreview_cli/negotiation/payoffs.py` (`build_payoff_matrix()` function). Per payoff-matrix-contract.md rules:
  - Map Position (preferred/acceptable/walkaway) to action indices
  - Compute 3-component linear payoff: `w_risk*risk + w_fin*financial + w_obl*obligation`
  - Use `ClauseAssessment.confidence` → risk component (higher confidence = steeper gradient)
  - Use divergence from `PairedAssessment` → symmetric vs asymmetric matrix
  - Set `PayoffMatrix.source` per contract rules
  - Return `(PayoffMatrix | None, list[str] | None)` — None + warning when <2 actions
      → FR ref: FR-001, FR-002, FR-004, FR-006 | Contract ref: payoff-matrix-contract.md

- [X] T010 [US1] Implement equilibrium solvers in `src/openreview_cli/negotiation/solvers.py`:
  - `solve_nash(A, B)` — wrap NashPy `Game(A,B).support_enumeration()`, handle multiple/no equilibria
  - `solve_qre(A, B, lam=1.0, max_iter=1000, tol=1e-6)` — logit fixed-point iteration per research.md U2
  - `solve_level_k(A, B, k=2)` — iterative best-response per research.md U3, cap at k=3
  - Each returns `(row_strategy: np.ndarray, col_strategy: np.ndarray, eq_type: str)`
  - `EquilibriumType` detection: pure/all strategies pure → "pure", mixed → "mixed", multiple found → "multiple", none found → "no_equilibrium"
  - QRE fallback: when `solve_nash` returns `eq_type="no_equilibrium"`, automatically call `solve_qre(lam=1.0)` and annotate result with `is_amber=True`
  - Impasse check: any action "walkaway" with prob ≥0.8
      → FR ref: FR-002, FR-003 | Contract ref: research.md U1, U2, U3

- [X] T011 [US1] Implement recommendation builder in `src/openreview_cli/negotiation/recommend.py`:
  - `build_recommendation(strategy, matrix, model, model_params)` → `EquilibriumStrategy`
  - Human-readable `suggested_counteroffer` from predicted outcome (e.g. "Propose preferred terms; counterparty likely to counter with acceptable")
  - `fallback_position` = next-best action for user
  - `confidence` = min(assessment confidence, payoff construction confidence, solver convergence quality)
  - `is_amber` = True if any: confidence < confidence_threshold (default 0.7, configurable via `--confidence-threshold`), counterparty source=ESTIMATED/UNKNOWN, multiple equilibria conflict, impasse detected
  - `assumptions` list from PayoffMatrix.source + any inference notes
  - Advisory language enforcement: never "sign this" or "reject this"
      → FR ref: FR-004, FR-006 | Contract ref: equilibrium-strategy.md

- [X] T012 [P] [US1] Implement report formatting in `src/openreview_cli/negotiation/report.py`:
  - `format_terminal(report: NegotiationReport)` — Rich `Table` per equilibrium-strategy.md contract (Clause ID, Recommended Counteroffer, Equilibrium Type, Confidence, Status with Amber indicator)
  - Include per-clause payoff summary row in terminal table: show user & counterparty payoffs (preferred/acceptable/walkaway) for each recommendation
  - `format_json(report: NegotiationReport)` — JSON serialization per contract schema, include `payoff_matrix` field with both parties' action values per clause
  - `format_memo(report: NegotiationReport)` — human-readable plaintext summary with payoff matrix section per clause
  - Reuse existing Rich formatting patterns from `src/openreview_cli/review/report.py`
  - Display disclaimer prominently at top: "EXPERIMENTAL and advisory only. Review with qualified legal counsel."
  - Verify terminal output renders payoff values in a readable row so user can trace reasoning from payoff structure to recommendation
      → FR ref: FR-005, **SC-002** | Contract ref: equilibrium-strategy.md (JSON schema), report.py pattern

- [X] T013 [US1] Implement public API in `src/openreview_cli/negotiation/__init__.py`:
  - `run_negotiation(doc_path, playbook, solver, **kwargs)` → `NegotiationReport`
  - Pipeline: parse doc → load playbook → extract ClauseAssessments → build PayoffMatrices → compute equilibria → build recommendations → aggregate NegotiationReport
  - Reuse existing `parse_document()` from `openreview_cli.parsing.stream`
  - Reuse existing `extract_clause()` and `match_category()` from `openreview_cli.review.extraction`
  - Reuse existing `load_playbook()` from `openreview_cli.review.playbook`
  - Export: `run_negotiation`, `NegotiationReport`, `EquilibriumStrategy`, `PayoffMatrix`
      → FR ref: FR-001, FR-002 | Contract ref: negotiation-cmd.yaml

- [X] T014 [US1] Wire `negotiate` CLI subcommand in `src/openreview_cli/app.py`:
  - Add `negotiate` command to Typer app per `negotiation-cmd.yaml` contract
  - Arguments: `doc_path: Path` (required)
  - Options: `--playbook`, `--playbook-path`, `--solver` (choices: nash, qre, level_k, default qre), `--rationality` (float, default 1.0), `--depth` (int, default 2), `--weights` (str, default "0.33,0.33,0.34"), `--confidence-threshold` (float, default 0.7), `--no-pii`, `--verbose`, `--output`, `--format` (choices: table, json, memo)
  - Handle errors: missing playbook, no positions defined, document not found
  - Follow existing Typer command patterns from `app.py`
      → FR ref: FR-001, FR-002, FR-004, FR-005 | Contract ref: negotiation-cmd.yaml

**Checkpoint**: US1 complete — `openreview negotiate contract.pdf` produces clause-by-clause strategy table with advisory language and Amber annotations. Tests pass.

---

## Phase 4: User Story 2 — Compare Strategy Against Bilateral Alignment (Priority: P2)

**Goal**: User sees where equilibrium game-theoretic analysis diverges from or complements existing bilateral comparison output.

**Independent Test**: Run both `openreview compare docA docB` and `openreview negotiate docA` on same document. US2 output highlights clauses where equilibrium suggests different approach.

### Tests for User Story 2

- [X] T015 [P] [US2] Write integration tests for cross-feature comparison in `tests/integration/test_negotiation_pipeline.py`. Cover:
  - `run_negotiation()` end-to-end with mocked ClauseAssessment + PairedAssessment fixtures
  - JSON output matches equilibrium-strategy contract schema
  - Terminal output includes clause-by-clause table with all required columns
  - Edge case: undefined playbook positions → graceful guidance, no crash
  - Edge case: asymmetric info (only user positions) → assumptions annotated
  - Edge case: all clauses at impasse → deadlock_risk=True, summary includes impasse_count
      → FR ref: FR-005, FR-006, SC-003 | Contract ref: —

### Implementation for User Story 2

- [X] T016 [**SC-003**] [US2] Extend `NegotiationReport` and `report.py` to include a per-clause "comparison with bilateral alignment" cross-reference section:
  - For each clause where PairedAssessment data is available, compute divergence between equilibrium recommendation and alignment-based recommendation
  - Display a cross-reference table per clause showing: equilibrium outcome, alignment verdict, divergence flag, and explanation of why equilibrium differs
  - Add `diverges_from_alignment: bool` field to EquilibriumStrategy
  - Highlight in terminal output where equilibrium suggests different approach with explicit text: "Equilibrium analysis diverges from bilateral alignment — see cross-reference below"
  - Include summary row per clause so user can identify at least one clause where game-theoretic output differs from bilateral comparison (SC-003)
  - The cross-reference section must be visually distinct (separator or sub-heading) and appear before the full strategy table
      → FR ref: FR-005, **SC-003** | Contract ref: —

- [X] T017 [US2] Enhance `recommend.py` to cross-reference equilibrium results with bilateral divergence data:
  - Where bilateral shows divergence AND equilibrium suggests concession: flag as "strategic convergence opportunity"
  - Where bilateral shows alignment AND equilibrium suggests different: flag as "alignment vs equilibrium tension"
  - Where bilateral shows divergence AND equilibrium says impasse: flag as "deadlock risk confirmed"
      → FR ref: FR-005, SC-003 | Contract ref: —

**Checkpoint**: US2 complete — output references bilateral alignment context when available, highlights divergence between analysis methods.

---

## Phase 5: User Story 3 — Explore "What-If" Scenarios (Priority: P3)

**Goal**: User adjusts position parameters (weights, rationality) and re-runs to see equilibrium shift.

**Independent Test**: Run with default weights, run with risk-focused weights (0.7,0.15,0.15), confirm JSON outputs differ.

### Tests for User Story 3

- [X] T018 [P] [US3] Write tests for what-if re-run in `tests/integration/test_negotiation_pipeline.py`. Cover:
  - Different `--weights` produce different strategy outputs (deterministic per param set)
  - Different `--rationality` values shift QRE output (λ=0.1 vs λ=10.0)
  - Different `--depth` values shift Level-k output (k=0 vs k=3)
  - Re-running with identical params produces identical output
      → FR ref: FR-007 | Contract ref: —

### Implementation for User Story 3

- [X] T019 [US3] Add weight-override support to `payoffs.py` `build_payoff_matrix()`:
  - Accept optional `weights` dict parameter (default: {"risk": 0.33, "financial": 0.33, "obligation": 0.34})
  - Validate weights sum to ≈1.0 (±1e-6)
  - Pass weights through to `PayoffMatrix.weights` field
      → FR ref: FR-007 | Contract ref: —

- [X] T020 [US3] Add parameter re-run support to CLI and `run_negotiation()`:
  - Wire `--weights`, `--rationality`, `--depth` CLI options to solver calls
  - Wire `--confidence-threshold` to Amber annotation logic
  - Document in quickstart.md scenario 4 (what-if exploration)
      → FR ref: FR-007 | Contract ref: negotiation-cmd.yaml (--weights, --rationality, --depth)

**Checkpoint**: US3 complete — user can adjust parameters and observe equilibrium shifts.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Performance validation, memory budget, edge case hardening, documentation.

- [X] T021 [P] [POL] Add memory budget validation test `pytest -m memory -k negotiation`. Assert peak RSS < 5 MB over baseline for 30-clause negotiation. Use project's `memory_tracker` fixture from `tests/conftest.py`.
      → FR ref: SC-001, SC-004 | Contract ref: constitution.md III (Hardware-Bounded)
- [X] T022 [P] [POL] Add performance benchmark test: assert 30-clause negotiation completes in <5s total (<100ms per Nash solver, <50ms per QRE). Use existing `pytest-benchmark` or timer fixture.
      → FR ref: SC-001 | Contract ref: plan.md performance goals
- [X] T023 [POL] Run all 5 quickstart.md validation scenarios and fix any failures:
  1. Basic negotiation analysis (FR-001, FR-002)
  2. Bounded rationality model selection (FR-003)
  3. Asymmetric information handling (FR-006)
  4. What-if exploration (FR-007)
  5. Edge cases: no positions, impasse, large contract (30+ clauses)
      → FR ref: — | Contract ref: quickstart.md
- [X] T024 [POL] Update project context documentation to reflect new negotiation module paths. Update `.specify/memory/reports/` with plain-English phase report for this feature.
      → FR ref: — | Contract ref: constitution.md development workflow

**Checkpoint**: All 24 tasks complete. Full test suite green (`uv run pytest tests/unit/test_negotiation_* tests/integration/test_negotiation_pipeline.py -v`). Memory <5 MB. Performance <5s for 30 clauses. Quickstart validation passes.

---

## Dependencies & Execution Order

### Phase Dependencies

| Phase | Depends On | Blocks |
|-------|-----------|--------|
| Phase 1: Setup | — | All phases |
| Phase 2: Foundational (models) | Phase 1 | All user stories |
| Phase 3: US1 (P1) | Phase 2 | — (can deliver independently) |
| Phase 4: US2 (P2) | Phase 2, Phase 3 | — (extends US1 output) |
| Phase 5: US3 (P3) | Phase 2, Phase 3 | — (extends US1 output) |
| Phase 6: Polish | All user stories | — (final validation) |

### User Story Dependencies

- **US1 (P1)**: No dependency on other user stories — after Phase 2, can deliver MVP.
- **US2 (P2)**: Depends on US1 for the recommendation mechanism + bilateral feature availability. Independently testable in isolation with mocked data.
- **US3 (P3)**: Depends on US1 for the core pipeline. Independently testable via weight/rationality parameter variation.

### Within Each Phase

- Tests written FIRST, verified to FAIL, then implementation added — per TDD mandate.
- Models before services (data shapes before logic).
- Services before CLI wiring (logic before user-facing command).
- Core implementation before integration tests.

### Parallel Opportunities

Setup tasks T001-T003 can run in parallel.
Foundational tests T004 and implementation T005 are sequential (TDD).
US1 test tasks T006-T008 run in parallel (different test files).
US1 implementation tasks T009-T013 are sequential (each depends on prior), except T012 (report) which runs parallel to T010-T011.
US2 tasks T015-T017 are sequential (test, then extend report, then enhance recommend).
US3 tasks T018-T020 are sequential.
Polish tasks T021-T022 run in parallel (separate concerns).

---

## Parallel Execution Example

```bash
# Setup (Phase 1) — parallel
Task: T001 — uv add nashpy
Task: T002 — mkdir -p src/openreview_cli/negotiation && create __init__.py stub
Task: T003 — mkdir -p tests/fixtures/negotiation && create sample files

# Foundational (Phase 2) — TDD
Task: T004 — Write test_negotiation_models.py (must FAIL)
Task: T005 — Implement models.py (tests now PASS)

# US1 tests — parallel
Task: T006 — Write test_negotiation_payoffs.py
Task: T007 — Write test_negotiation_solvers.py
Task: T008 — Write test_negotiation_recommend.py

# US1 implementation — sequential
Task: T009 — Implement payoffs.py
Task: T010 — Implement solvers.py
Task: T011 — Implement recommend.py
Task: T012 — Implement report.py
Task: T013 — Wire __init__.py API
Task: T014 — Wire app.py CLI
```

---

## Implementation Strategy

### MVP Delivery (US1 Only)

1. Phase 1: nashpy dep + module scaffold → commit
2. Phase 2: models.py + tests → commit
3. Phase 3: payoffs → solvers → recommend → report → API → CLI → commit
4. STOP. Validate: `uv run openreview negotiate tests/fixtures/sample-nda.pdf`
5. Full US1 test suite green → MVP ready.

### Incremental Delivery

1. Foundation → commit (T001-T005)
2. US1 → commit (T006-T014) → MVP!
3. US2 → commit (T015-T017)
4. US3 → commit (T018-T020)
5. Polish → commit (T021-T024)

Each story adds value without breaking previous stories.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to user story for traceability
- Each user story independently completable and testable
- Verify tests FAIL before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate independently
- All dataclasses use `@dataclass(slots=True)` per constitution III
- All payoff values normalized to [0, 1] per data-model.md validation rule 2
- No external API calls — all computation local per constitution II
- Advisory language only — never "sign this" or "reject this" per blueprint §6
- Avoid: vague tasks, same-file conflicts, cross-story dependencies

---

## Phase 7: Convergence — Close Intent Gaps

**Purpose**: Remediate gaps identified during converge assessment between implemented code and spec/plan/tasks intent. All findings are `partial` — code exists but does not fully satisfy requirements.

### US2 Bilateral Data Integration (High Severity)

- [X] T025 [US2] Add `PairedAssessment` parameter to `build_payoff_matrix()` in `src/openreview_cli/negotiation/payoffs.py`:
  - Accept optional `PairedAssessment` object with `divergence` and `divergence_type` fields
  - When `PairedAssessment` available: set `PayoffMatrix.source = PayoffSource.INFERRED_FROM_ALIGNMENT`
  - When `PairedAssessment` available: use divergence data to construct asymmetric counterparty payoff matrix instead of symmetric inversion
  - When `PairedAssessment` available: confidence should incorporate alignment confidence
  - Update `run_negotiation()` signature in `__init__.py` to accept optional `paired_assessments: dict[str, PairedAssessment]` parameter
  - Update all callers (CLI and tests) to pass bilateral data
  - Verify cross-reference display in `report.py::_render_cross_reference` now activates when `PayoffSource.INFERRED_FROM_ALIGNMENT`
  - Verify `recommend.py` divergence logic activates and produces meaningful cross-reference notes
      → FR ref: FR-002, FR-006 | Gap ref: F2 (HIGH)

- [X] T026 [US1] Wire playbook position extraction into CLI `negotiate` command in `src/openreview_cli/app.py`:
  - After loading playbook, use `extract_clause()` and `match_category()` from `openreview_cli.review.extraction` to map each clause to its playbook category and extract 3-position data (preferred/acceptable/walkaway)
  - Set `ClauseAssessment.position` from playbook data, not hardcoded `PREFERRED`
  - Set `ClauseAssessment.confidence` from playbook data where available (default 0.7 if unset)
  - Set `ClauseAssessment.playbook_category` from playbook mapping
  - Verify users can define per-clause positions through playbook YAML (FR-001)
      → FR ref: FR-001, T013 | Gap ref: F1 (HIGH)

### Amber Annotations (Medium Severity)

- [X] T027 [US1] Propagate fallback metadata in `src/openreview_cli/negotiation/solvers.py` and `recommend.py`:
  - `solve_nash()` to return additional flag `is_fallback: bool = True` when QRE fallback triggered
  - `build_recommendation()` to include "Fallback from Nash to QRE — no pure/mixed equilibrium" in Amber reasons when fallback occurred
      → FR ref: FR-002 | Gap ref: F3 (MEDIUM)

### Test Updates

- [X] T028 [P] [US2] Update payoff matrix tests in `tests/unit/test_negotiation_payoffs.py`:
  - Add test cases for `build_payoff_matrix()` with `PairedAssessment` parameter
  - Verify `PayoffSource.INFERRED_FROM_ALIGNMENT` is set when bilateral data provided
  - Verify asymmetric matrix construction from divergence data
      → FR ref: FR-002, FR-006 | Gap ref: F2 (HIGH)

- [X] T029 [P] [US1] Update CLI integration test for playbook-based position extraction:
  - Add test in `tests/integration/test_negotiation_pipeline.py` verifying positions are extracted from playbook fixtures
  - Verify different playbook fixtures produce different `ClauseAssessment.position` values
  - Verify partial playbook produces mixed defined/undefined positions per US1/AC2
      → FR ref: FR-001 | Gap ref: F1 (HIGH)
