# Feature Specification: Game-Theoretic Negotiation Assistant

**Feature Branch**: `feat/026-game-theoretic-negotiation`

**Created**: 2026-07-07

**Status**: Draft

**Input**: User description: Lightweight game-theoretic negotiation assistant — compute equilibrium strategy and counteroffers from clause-level payoff matrices using bounded-rationality game theory, powered by existing bilateral comparison and three-position playbook capabilities.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Analyze Contract and Receive Equilibrium Strategy (Priority: P1)

A negotiator who has prepared their positions using the existing playbook system wants to see what strategy a rational game-theoretic analysis would recommend. They run the negotiation assistant on a contract where they have already defined their reservation price, target price, and walkaway terms for each clause. The assistant considers both parties' incentives and returns a recommended strategy with suggested counteroffers.

**Why this priority**: This is the core value proposition — transforming static positions into actionable, game-informed negotiation strategy. Without this, the feature provides no user value.

**Independent Test**: Can be fully tested by running the assistant on a contract with predefined positions and verifying that:
- The output includes a strategy recommendation
- The recommendation references both parties' incentives
- Each clause has a suggested counteroffer or negotiation approach
- All output is understandable to a non-technical user

**Acceptance Scenarios**:

1. **Given** a contract document with clause-level positions defined in the playbook, **When** the user runs the negotiation assistant, **Then** the system produces a strategy report showing clause-by-clause equilibrium recommendations.

2. **Given** a contract where the user has defined only a subset of clauses in their playbook, **When** the assistant runs, **Then** it produces recommendations for the defined clauses and clearly marks undefined ones as requiring input.

3. **Given** a contract with symmetric information (both parties' positions are known), **When** the assistant runs, **Then** the recommendations account for both parties' incentives and show the equilibrium outcome.

---

### User Story 2 - Compare Game-Theoretic Strategy Against Bilateral Alignment (Priority: P2)

A negotiator has already run the bilateral comparison feature to see how their positions align with the counterparty's draft. They now want to see how a game-theoretic strategy differs from the alignment-based view — for example, where the bilateral comparison shows divergence, the game-theoretic analysis might suggest the optimal concession path.

**Why this priority**: This connects the new feature to existing capabilities, showing the user when game-theoretic analysis adds value beyond what bilateral comparison already provides.

**Independent Test**: Can be tested by running both features on the same contract and comparing outputs. The game-theoretic output must explicitly differ from or complement the bilateral comparison report in a meaningful way.

**Acceptance Scenarios**:

1. **Given** a contract that has been analyzed with bilateral comparison, **When** the user requests a game-theoretic strategy, **Then** the output highlights where equilibrium reasoning suggests a different approach than pure alignment analysis.

2. **Given** a clause where both parties have compatible positions (bilateral alignment is high), **When** the game-theoretic assistant analyzes it, **Then** it recommends a straightforward agreement path for that clause.

---

### User Story 3 - Explore "What-If" Scenarios by Adjusting Positions (Priority: P3)

An experienced negotiator wants to explore how changes to their position affect the recommended strategy. They adjust their reservation price or walkaway terms for specific clauses and re-run the analysis to see how the equilibrium shifts.

**Why this priority**: This adds strategic depth for power users and demonstrates the value of the game-theoretic model beyond a single static analysis.

**Independent Test**: Can be tested by running the assistant, modifying one position parameter, re-running, and confirming the output changes in a predictable and explainable way.

**Acceptance Scenarios**:

1. **Given** a completed analysis with strategy recommendations, **When** the user tightens their reservation price on a key clause, **Then** the re-run analysis shows different equilibrium recommendations that reflect the more constrained position.

2. **Given** a completed analysis, **When** the user adjusts their walkaway terms and re-runs, **Then** the system highlights which clauses are now at risk of deadlock vs. resolvable through negotiation.

---

### Edge Cases

- What happens when the user has not defined any positions in the playbook? The assistant must ask for position input or gracefully decline with guidance on how to proceed.
- How does the system handle a clause where only the user's position is known (asymmetric information)? The assistant should clearly label assumptions made about the counterparty's incentives.
- How should the assistant behave when equilibrium analysis suggests no agreement is possible (all clauses at impasse)? The output should indicate deadlock risk and suggest fallback strategies.
- Requests involving more than two parties are declined with a clear guidance message. Multi-party negotiation is out of scope for this feature.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: User MUST be able to define clause-level positions including their reservation price, target price, and walkaway terms through the existing playbook system.
  - *Traceability*: Derived from the three-position playbook capability (reservation/target/walkaway per clause).
- **FR-002**: System MUST compute clause-by-clause equilibrium strategy recommendations based on both parties' defined positions. When the equilibrium computation yields no pure or mixed Nash equilibrium for a clause, the system MUST fall back to a bounded-rationality approximate equilibrium model with default parameters and report the result with an Amber confidence flag.
  - *Traceability*: Derived from the game-theoretic negotiation assistant concept in the feature blueprint.
- **FR-003**: System MUST account for bounded rationality — real negotiators do not always play perfectly — in its equilibrium calculations.
  - *Traceability*: Derived from the game-theoretic revision research indicating pure Nash equilibrium is insufficient for real-world negotiation.
- **FR-004**: System MUST generate suggested counteroffers for each clause, with the reasoning tied to the equilibrium analysis.
  - *Traceability*: Derived from the negotiation assistant requirement for actionable output.
- **FR-005**: System MUST present strategy recommendations in a format compatible with the existing review and report infrastructure.
  - *Traceability*: Derived from the bilateral comparison capability (existing report format) and the three-position playbook capability (existing position definitions).
- **FR-006**: System MUST explicitly label any assumptions made about the counterparty's positions when information is incomplete.
  - *Traceability*: Derived from the negotiation assistant requirement for transparency in strategic advice.
- **FR-007**: System MUST allow the user to adjust their position parameters and re-run the analysis to observe how the equilibrium shifts.
  - *Traceability*: Derived from the "what-if" exploration use case in the feature blueprint.

*No [NEEDS CLARIFICATION] markers — all requirements have reasonable defaults given the existing capabilities.*

### Key Entities *(include if feature involves data)*

- **Clause Payoff Matrix**: A representation of each clause showing the possible outcomes (agreement terms) and the value each party assigns to each outcome. Key attributes: clause identifier, list of possible terms, user's valuation per term, counterparty's estimated valuation per term.
- **Equilibrium Strategy**: The recommended negotiation approach for each clause, including the predicted outcome under rational play, the range of acceptable terms, and the suggested next offer. Key attributes: clause identifier, equilibrium type, predicted outcome, confidence level, fallback position.
- **Position Profile**: A user's defined stance on a clause, encompassing their reservation price (minimum acceptable), target price (ideal outcome), and walkaway terms (deal-breakers). This entity is inherited from the three-position playbook capability.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: User receives a complete strategy recommendation report within a single interactive session for a standard contract (up to 30 clauses). The report requires no manual adjustment or re-running to be actionable.
- **SC-002**: Strategy recommendations explicitly reference a payoff matrix that shows both the user's and the counterparty's incentives for each clause, making the reasoning transparent to the user.
- **SC-003**: The game-theoretic output differs from and adds value beyond the existing bilateral comparison output — users can identify at least one clause per contract where equilibrium analysis suggests a different (and better) approach than pure alignment analysis.
- **SC-004**: Bounded-rationality adjustments produce noticeably different recommendations than pure rational equilibrium in at least 20% of test cases with asymmetric or constrained positions, preventing the unrealistic "perfect play" assumption.
- **[Post-launch research metric] SC-005**: A user with no game-theory background can understand and act on the recommended strategy — measured by a post-launch user research study where participants successfully identify their suggested counteroffer and the reasoning behind it. This is a post-launch metric, not a build-time success criterion.

## Assumptions

- **Scope boundary**: This feature focuses on two-party negotiation only. Multi-party negotiation (three or more parties with interdependent payoffs) is out of scope.
- **Scope boundary**: The game-theoretic analysis operates at the clause level. Cross-clause strategic trade-offs (trading concession in one clause for gain in another) are out of scope for this version.
- **Dependency on existing capabilities**: This feature depends on the bilateral comparison capability (clause-level alignment/divergence detection) and the three-position playbook capability (reservation/target/walkaway terms). Both must be available for the feature to function.
- **Information assumptions**: The system assumes the user can provide at minimum their own positions. Counterparty positions may be inferred from the contract draft and the user's input, but the system will mark such inferences as assumptions.
- **User expertise**: The feature is designed for contract negotiators who are familiar with defining positions in the playbook system. No game-theory knowledge is required to use the assistant.
- **Hardware constraint compliance**: All computation must complete within the project's existing hardware budget (8 GB RAM, 2-core CPU, no GPU). No external API calls are required for the core equilibrium computation.
- **PII compliance**: Any negotiation positions or pricing data extracted from contract text must pass through the existing PII-stripping pipeline before being used in reports or logs.

## Traceability (Blueprint Citations)

Since the feature blueprint documents are internal and gitignored, the following plain-English descriptions map each requirement to its source:

| Requirement | Blueprint Source |
|---|---|
| FR-001 (position definitions) | Derived from the three-position playbook capability (reservation/target/walkaway per clause) |
| FR-002 (equilibrium computation) | Derived from the game-theoretic negotiation assistant concept — replacing the original Stackelberg approach with a lightweight bounded-rationality model |
| FR-003 (bounded rationality) | Derived from the game-theoretic revision research indicating pure Nash equilibrium is insufficient |
| FR-004 (actionable counteroffers) | Derived from the negotiation assistant requirement for output users can act on |
| FR-005 (report integration) | Derived from the bilateral comparison capability and three-position playbook capability for consistent output |
| FR-006 (assumption labeling) | Derived from transparency requirements in the negotiation assistant concept |
| FR-007 (what-if scenarios) | Derived from the "what-if" exploration use case in the feature blueprint |

Additional sources: The original L-3 feature description ("Game-theoretic negotiation assistant — Stackelberg game model, counterparty behavior prediction. Advanced negotiation mode.") provided the overall direction, which has been repositioned per user direction to drop the Stackelberg/A100 model in favor of a lightweight, hardware-feasible approach.
