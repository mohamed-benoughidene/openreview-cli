# Feature Specification: Three-Color Output with Confidence Scores

**Feature Branch**: `013-three-color-confidence`

**Created**: 2026-07-03

**Status**: Draft

**Input**: Blueprint §11 seed — "Three-color output with confidence scores. User-configurable `--confidence-threshold` flag."

**Blueprints**: N-6 (§7, line 425), §6.4 (lines 334–344), R-6 (§8, line 464), Q-8 (§10, lines 613–627), CON-1, R-1, R-11, P-4

---

## User Scenarios & Testing

### User Story 1 — Legal professional reads a Green/Amber/Red review at a glance (Priority: P1)

A legal professional runs a single-party review on an NDA. Instead of scanning every clause detail, they see the output color-coded: Green (safe — proceed), Amber (uncertain — check manually), Red (problematic — needs attention). They immediately know which clauses are safe and which need human review, without reading through every assessment.

**Why this priority**: The three-color signal is the primary mitigation for the comparison accuracy ceiling (§6.4, CON-1). Without it, the user cannot distinguish high-confidence from uncertain assessments at a glance. This is the core value of the feature.

**Independent Test**: Can be fully tested by running a review with known clause assessments and verifying the terminal output shows the correct color for each clause (Green/Amber/Red) in the Status column.

**Acceptance Scenarios**:

1. **Given** a review with 10 clause assessments, 5 of which are favorable + high confidence, 3 uncertain + low confidence, and 2 unfavorable + high confidence, **When** the report is rendered in the terminal, **Then** the Status column shows Green, Amber, Red respectively with distinct visual styling.
2. **Given** a review where all clauses are favorable with confidence ≥ threshold, **When** the report is rendered, **Then** all clauses show Green status.
3. **Given** a review where all clauses are uncertain or have confidence < threshold, **When** the report is rendered, **Then** all clauses show Amber status with the `⚠ AMBER` indicator.

---

### User Story 2 — Legal professional adjusts confidence threshold (Priority: P1)

A legal professional wants fewer Amber flags because they trust the model, so they run with `--confidence-threshold 0.3`. Conversely, a risk-averse professional wants more Amber flags and runs with `--confidence-threshold 0.8`. In both cases, the output is recalculated without re-running extraction, QA, or grounding. The user sees the effect immediately.

**Why this priority**: User-configurable threshold is listed as a hard requirement in the blueprint seed (§11). It directly addresses the "set Amber threshold generously" mandate from §6.4 and R-6, and it is the mechanism through which users adapt the tool to their risk tolerance.

**Independent Test**: Can be fully tested by running the same review twice with different `--confidence-threshold` values and verifying the color distributions differ.

**Acceptance Scenarios**:

1. **Given** a review with 10 clause assessments, **When** the user runs with `--confidence-threshold 0.9`, **Then** the number of Amber flags is greater than or equal to the number at the default threshold (0.7).
2. **Given** the same review, **When** the user runs with `--confidence-threshold 0.3`, **Then** the number of Amber flags is less than or equal to the number at the default threshold (0.7).
3. **Given** a review run with `--confidence-threshold 0.9`, **When** the output is rendered, **Then** a clause with confidence 0.85 must be Amber (confidence < threshold).

---

### User Story 3 — Legal professional inspects why a clause is Amber (Priority: P2)

A senior attorney sees a clause marked Amber and wants to understand why before deciding whether to override. They inspect the assessment details and can see: which stage triggered the Amber flag (low extraction confidence, QA disagreement, grounding failure), the individual confidence scores from each stage, and the specific reason (e.g., "QA agent disagreed: position should be unfavorable").

**Why this priority**: Transparency drives trust. Without it, users cannot distinguish a "barely Amber" clause (confidence 0.49, near the boundary) from a "deeply Amber" one (confidence 0.1 with QA disagreement and grounding failure). P2 because the core three-color output (P1) is functional without it, but professional users will not trust an opaque Amber flag.

**Independent Test**: Can be fully tested by running a review where a clause is deliberately made Amber (low confidence, QA disagree, or error) and verifying the breakdown is visible.

**Acceptance Scenarios**:

1. **Given** a clause assessment where extraction confidence = 0.4 and QA disagrees, **When** the user inspects the breakdown, **Then** they see both the low extraction confidence and QA disagreement as separate triggers.
2. **Given** a clause assessment that is Amber due to grounding failure (grounding_verdict = UNGROUNDED), **When** the user inspects the breakdown, **Then** they see the grounding failure listed as the trigger.
3. **Given** a clause assessment that is Amber solely because confidence is below the user-configured threshold, **When** the user inspects the breakdown, **Then** they see "Below confidence threshold (0.49 < 0.5)" as the reason.

---

### User Story 4 — Developer validates threshold behavior across edge cases (Priority: P3)

A developer tests the three-color system by passing extreme `--confidence-threshold` values (0.0 and 1.0) and reviewing assessment lists that are empty, all Amber, or single-clause. The system handles all boundary conditions gracefully without crashing or producing ambiguous output.

**Why this priority**: Threshold boundary behavior is critical for correctness but does not deliver user-facing value until the first three stories are implemented.

**Independent Test**: Can be fully tested by running the system with edge-case threshold values and verifying correct color assignment.

**Acceptance Scenarios**:

1. **Given** a review with `--confidence-threshold 0.0`, **When** the report is rendered, **Then** no clause is Amber due to confidence threshold (all pass), and only QA disagreement/error/grounding failure triggers Amber.
2. **Given** the same review with `--confidence-threshold 1.0`, **When** the report is rendered, **Then** every clause with confidence < 1.0 is Amber, and only perfect assessments are Green/Red.
3. **Given** an empty assessment list, **When** the report is rendered, **Then** the output shows "No clauses to assess" without error.
4. **Given** `--confidence-threshold 0.5`, **When** a clause has confidence exactly 0.5, **Then** it is NOT Amber from the threshold alone (confidence >= threshold; `confidence < 0.5` is the trigger, so 0.5 passes).

---

### Edge Cases

- **Threshold at exact boundary (0.5)**: A clause with confidence exactly 0.500 must be treated as passing (Green/Red if no other trigger), not Amber. The rule is `confidence < threshold`, not `confidence <= threshold`.
- **Threshold values outside [0.0, 1.0]**: The CLI must reject values outside the valid range with a clear error message.
- **Clause with all Amber triggers**: A clause where confidence is low, QA disagrees, and grounding fails must show Amber once (not triplicate the indicator). All contributing reasons are visible in the breakdown (US3), but the status is a single Amber.
- **No grounding data present**: When grounding is not available (e.g., discriminator not run), grounding failure must not trigger Amber. Only defined Amber triggers apply.
- **Mixed QA outcomes across multiple QA passes**: If QA disagrees on one round but subsequent passes agree, the final verdict determines Amber — not intermediate states.
- **Performance with many clauses**: The three-color computation must not add measurable latency — it is a stateless deterministic mapping that runs in O(n) with no external calls.
- **CLI flag precedence**: `--confidence-threshold` applies at the command level that generates review output (e.g., `precheck`, `hirecheck`), not globally. Each command that produces a `ReviewReport` MUST accept the flag.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST assign each `ClauseAssessment` a three-color status (Green/Amber/Red) computed from the combined position, confidence, QA verdict, grounding verdict, and user-configured threshold. The color is a derived property — it is not stored but computed at output time. The computation is O(n) and introduces no external calls. [N-6][§6.4]

- **FR-002**: Color assignment rules:
  - **Green**: Position is favorable or neutral AND confidence >= threshold AND no Amber trigger is active.
  - **Red**: Position is unfavorable AND confidence >= threshold AND no Amber trigger is active.
  - **Amber** (everything else): Position is uncertain, OR confidence < threshold, OR QA verdict is disagree or uncertain, OR error is present, OR grounding verdict is ungrounded or uncertain.
  - These rules supersede the current hardcoded `is_amber` logic in `ClauseAssessment.__post_init__` (which unconditionally uses 0.5 as threshold). The threshold becomes configurable, and the color enum replaces the boolean flag. [§6.4][CON-1][R-11]

- **FR-003**: System MUST expose a `--confidence-threshold` CLI flag on every review-producing subcommand (`precheck`, `hirecheck`, etc.). The flag accepts a float in [0.0, 1.0], defaulting to 0.7. Values outside the range MUST be rejected with a clear error message. [N-6][R-6]

- **FR-004**: Amber triggers are defined as: extraction confidence < threshold; QA verdict is `disagree` or `uncertain`; assessment has a non-None error; grounding verdict is `ungrounded` or `uncertain`. Each trigger is evaluated independently — any single trigger makes the assessment Amber. Grounding is only a trigger when grounding data exists (grounding_verdict is not None). [§6.4][R-11]

- **FR-005**: The three-color status MUST be rendered in terminal output via a dedicated color indicator (distinct from the position color) in the Status column. The existing `⚠ AMBER` / `OK` representation MUST be replaced with a three-state indicator: Green badge, Amber badge with warning symbol, Red badge. [Q-8]

- **FR-006**: JSON output MUST include a `"color"` field on each `ClauseAssessment` with one of `"green"`, `"amber"`, `"red"`. The existing `is_amber` boolean field in JSON output MUST be deprecated in favor of the three-state field. [Q-8]

- **FR-007**: The color computation MUST be a pure stateless mapping from existing assessment fields — it MUST NOT require re-running extraction, QA, or grounding. Changing `--confidence-threshold` must produce output instantaneously (sub-second for any reasonable number of clauses). [§6.4]

- **FR-008**: User-facing help text for `--confidence-threshold` MUST include a disclosure of the comparison accuracy ceiling: "Note: The comparison accuracy of automated review is bounded by approximately 64% F1. Three-color output (Green/Amber/Red) is designed to mitigate this — set the threshold generously to push uncertain comparisons to Amber rather than risking false Green or Red." [CON-1][R-1]

- **FR-009**: The `AssessmentColor` enum (Green/Amber/Red) MUST be a first-class entity in the review data model, replacing the boolean `is_amber` flag as the primary color signal. The `is_amber` flag MAY be retained as a derived convenience property (`is_amber == (color == AssessmentColor.AMBER)`) for backwards compatibility with existing consumers of `ReviewSummary.amber_count`. [N-6][§6.4]

- **FR-010**: The ReviewSummary MUST include a three-color breakdown count (green_count, amber_count, red_count) in addition to the existing position breakdown. The existing `amber_count` is preserved as a derived property from `amber_count`. [Q-8]

- **FR-011**: Neutral position with confidence ≥ threshold maps to Green. Neutral position with confidence < threshold maps to Amber. This is a three-color system (not four-color): neutral with high confidence is treated as "safe to proceed" (Green). [§6.4]

- **FR-012**: Default confidence threshold is 0.7. Users may override via `--confidence-threshold` flag. The 0.7 default implements the "set Amber threshold generously" mandate from §6.4 and the accuracy ceiling mitigation from R-6. [§6.4][R-6]

- **FR-013**: The `--confidence-threshold` flag is per-command (e.g., `openreview precheck --confidence-threshold 0.8`). Each review subcommand accepts the flag independently with a shared default of 0.7. Mode-specific defaults are a future option. [§6.4]

### Key Entities

- **AssessmentColor**: An enumeration with three values — `GREEN`, `AMBER`, `RED`. Represents the final color-assigned verdict for a single clause assessment. Derived deterministically from position, confidence, QA verdict, error, grounding verdict, and the user-configured threshold. Replaces the boolean `is_amber` as the primary color signal. A convenience property `is_amber` MAY be retained on `ClauseAssessment` for backwards compatibility, defined as `is_amber == (color == AMBER)`.

- **ConfidenceThreshold**: A single float value in [0.0, 1.0] that controls the boundary between high-confidence (Green/Red) and low-confidence (Amber) assessments. Default is 0.7. Provided per-command via `--confidence-threshold` CLI flag. The threshold affects color assignment only — it does not change extraction, QA, or grounding behavior. [§6.4][R-6]

### Integration Points

- **Input**: The three-color computation consumes existing `ClauseAssessment` fields (position, confidence, qa_verdict, error, grounding_verdict) plus the user-provided `--confidence-threshold`. All inputs are already available after the review pipeline (extraction → QA → grounding) completes.

- **Output**: The three-color status appears in:
  - **Terminal table** (Rich): Status column shows a colored badge (Green/Amber/Red) replacing the current `⚠ AMBER` / `OK` binary. Position column retains its existing per-position coloring (favorable=green, neutral=yellow, unfavorable=red, uncertain=bold red).
  - **JSON output**: Each assessment gains a `"color"` field. The existing `is_amber` field may be retained as a derived boolean for backwards compatibility.

- **Relationship to existing `is_amber`**: The current `is_amber` boolean is set in `ClauseAssessment.__post_init__` with a hardcoded 0.5 threshold. Spec 013 replaces this with a configurable threshold and a three-state color enum. Implementation must either:
  - (A) Modify `__post_init__` to accept a threshold parameter, or
  - (B) Make color a computed property at output time (not stored on the instance).

  Resolution (B) is recommended: it ensures threshold changes can be applied without re-serializing assessments, and it keeps the assessment data model clean. The spec does not mandate HOW — only WHAT the color output must be.

- **CLI integration**: Every review-producing subcommand (currently `precheck` in app.py) must accept `--confidence-threshold`. The flag is applied when rendering output, not during the pipeline run (no re-run needed).

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: A user can pass `--confidence-threshold 0.7` and `--confidence-threshold 0.3` on the same review and observe different color distributions in the output, with 0.7 producing more Amber flags than 0.3. The output for both invocations is produced in under 1 second for a 100-clause review (no pipeline re-run). [N-6][§6.4]

- **SC-002**: Every clause assessment in terminal output shows one of three distinct color badges (Green/Amber/Red) in the Status column. JSON output includes a `"color"` field on every assessment. Zero assessments fail to render a color. [Q-8]

- **SC-003**: User-facing help text for `--confidence-threshold` includes the accuracy ceiling disclosure (§6.4, CON-1) and a recommendation to set the threshold generously. Verified by grepping the help text. [CON-1][R-1]

- **SC-004**: Given a list of 1,000 clause assessments with known positions and confidences, the color assignment function returns correct colors for all 1,000 in under 100 ms. Verified with a unit test. [§6.4]

- **SC-005**: The color computation is stateless and produces identical output for identical input, regardless of invocation order, system state, or number of calls. Verified by running the same computation twice and comparing results. [§6.4]

- **SC-006**: A review with all assessments marked Amber (due to low confidence, QA disagreement, and errors) renders without visual conflicts — each Amber badge is distinct and readable, no color clashes. [Q-8]

- **SC-007**: When `--confidence-threshold` is not specified, the system uses the default threshold and produces consistent output. When an invalid value (e.g., `1.5` or `-0.1`) is passed, the CLI exits with a clear error message and non-zero exit code. [N-6]

---

## Assumptions

- **Neutral positions map to Green**: When a neutral position has confidence ≥ threshold and no Amber triggers are active, the assessment is Green (low-risk). This matches the three-color model from §6.4 and CON-1, where Green means "safe to proceed" and neutral with high confidence is safe. [FR-011][§6.4]

- **Color is derived at output time, not stored**: The three-color status is computed when rendering terminal/JSON output, not stored on the `ClauseAssessment` dataclass. This allows threshold changes without re-processing assessments and keeps the data model clean. The `AssessmentColor` enum may appear transiently during rendering but is not persisted.

- **Default confidence threshold is 0.7**: Per §6.4 guidance to "set Amber threshold generously" and R-6 accuracy ceiling mitigation. Users may override via `--confidence-threshold` on any review subcommand. [FR-012][§6.4][R-6]

- **Single-party review only (v1)**: The three-color output integrates with the single-party review pipeline (spec 011). Multi-party review (future) and other product modes will add `--confidence-threshold` when they are specified.

- **`is_amber` backwards compatibility**: The existing `is_amber` boolean and `amber_count` in `ReviewSummary` are preserved as derived properties for consumers that depend on them (e.g., `app.py` line 501 which checks `amber_count > 0`). This avoids breaking changes to existing CLI behavior or integrations.

- **Existing QA and grounding pipelines unchanged**: The three-color computation reads from existing fields but does not modify extraction, QA, or grounding logic. The `threshold` parameter in `ReviewCommand` (currently used for PII) remains separate from the `--confidence-threshold` for review colors — they are independent configuration knobs.

- **Hardware budget not impacted**: The color computation is a deterministic O(n) mapping with no external calls, no new dependencies, and no memory allocation proportional to document size beyond the existing assessment list. It stays well within the 100 MB peak memory budget.

- **CLI scope**: `--confidence-threshold` is per-command (e.g., `openreview precheck --confidence-threshold 0.7`), not global. Each review-producing mode accepts the flag independently with a shared default of 0.7. Mode-specific defaults are a future option. [FR-013][§6.4]

---

## Resolved Clarifications

The following [NEEDS CLARIFICATION] items were resolved via `/speckit.clarify`:

1. **FR-011 — Neutral color mapping**: Neutral + high confidence → Green (three-color, not four-color). [§6.4]
2. **FR-012 — Default threshold**: 0.7 (generous, per §6.4 "set Amber threshold generously"). [§6.4][R-6]
3. **FR-013 — Flag scope**: Per-command with shared 0.7 default. [§6.4]

All three clarifications are reflected in the functional requirements and assumptions above. The spec is ready for planning.
