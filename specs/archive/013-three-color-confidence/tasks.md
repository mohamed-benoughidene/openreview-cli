---
description: "Dependency-ordered task list for the Three-Color Output with Confidence Scores feature (N-6). Replaces binary amber/ok with Green/Amber/Red status, adds a user-configurable --confidence-threshold CLI flag, and shows amber reason breakdowns."
---

# Tasks: Three-Color Output with Confidence Scores (N-6)

**Input**: Design documents from `specs/013-three-color-confidence/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-interface.md, quickstart.md

**Tests**: TDD — tests MUST be written BEFORE the implementation they cover. Each test file starts as a failing test suite.

**Organization**: Tasks are grouped by user story. Each story is independently implementable and testable. US1 and US2 are P1 and form the MVP. US3 (P2) extends the display with amber reason breakdowns. US4 (P3) validates edge cases.

**Naming convention**: Existing review unit tests use flat naming (`tests/unit/test_review_models.py`, `tests/unit/test_review_report.py`). New test files follow the same flat pattern: `tests/unit/test_three_color_models.py`, `tests/unit/test_three_color_report.py`, `tests/unit/test_three_color_cli.py`. No `tests/unit/review/` subdirectory.

---

## Phase 1: Foundational — Data Models & Color Logic (Blocking Prerequisites)

**Purpose**: Core data model enums (`AssessmentColor`, `AmberReason`), the `assign_colors()` pure function, and updates to `ClauseAssessment`, `ReviewSummary`, and `ReviewReport`. ALL user stories depend on these modules being complete.

**⚠ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] **T001** Write unit tests for `AssessmentColor` and `AmberReason` enums in `tests/unit/test_three_color_models.py`:
  - `AssessmentColor` has values `green`, `amber`, `red` (StrEnum)
  - `AmberReason` has values `low_confidence`, `qa_disagreement`, `qa_uncertain`, `error`, `grounding_failure`, `grounding_uncertain` (StrEnum)
  - Enums are proper `StrEnum` subclasses (comparable to strings, JSON-serializable)
  - Match enum test patterns from existing `test_review_models.py` (`Position`, `QAVerdict`)
  - **FR reference**: FR-009
  - **File paths**: `tests/unit/test_three_color_models.py`
  - **Dependencies**: None
  - **Complexity**: S

- [ ] **T002** Implement `AssessmentColor(StrEnum)` and `AmberReason(StrEnum)` in `src/openreview_cli/review/colors.py`:
  - Define `class AssessmentColor(StrEnum):` with `green = "green"`, `amber = "amber"`, `red = "red"`
  - Define `class AmberReason(StrEnum):` with `low_confidence = "low_confidence"`, `qa_disagreement = "qa_disagreement"`, `qa_uncertain = "qa_uncertain"`, `error = "error"`, `grounding_failure = "grounding_failure"`, `grounding_uncertain = "grounding_uncertain"`
  - Match existing enum patterns in `models.py` (`Position`, `QAVerdict`)
  - **FR reference**: FR-009
  - **File paths**: `src/openreview_cli/review/colors.py` (NEW)
  - **Dependencies**: T001
  - **Complexity**: S

- [ ] **T003** Write unit tests for `assign_color()` function in `tests/unit/test_three_color_models.py`:
  - **Green**: favorable + confidence >= threshold + no Amber triggers → `AssessmentColor.green`
  - **Green**: neutral + confidence >= threshold + no Amber triggers → `AssessmentColor.green` (FR-011)
  - **Red**: unfavorable + confidence >= threshold + no Amber triggers → `AssessmentColor.red`
  - **Amber**: confidence < threshold (low_confidence trigger) → `AssessmentColor.amber`
  - **Amber**: QA disagree → `AssessmentColor.amber` with `qa_disagreement` reason
  - **Amber**: QA uncertain → `AssessmentColor.amber` with `qa_uncertain` reason
  - **Amber**: error present → `AssessmentColor.amber` with `error` reason
  - **Amber**: grounding ungrounded → `AssessmentColor.amber` with `grounding_failure` reason
  - **Amber**: grounding uncertain → `AssessmentColor.amber` with `grounding_uncertain` reason
  - **Amber**: uncertain position (no other trigger) → `AssessmentColor.amber` (ambiguous)
  - **Multiple triggers**: all applicable `AmberReason` values in `amber_reasons` list
  - **No grounding data**: grounding_verdict is None → grounding NOT a trigger (FR-004)
  - **Edge cases**: empty assessment list (returns empty list), threshold at boundary (`0.5` — must use `<` not `<=`), all triggers simultaneously (still single Amber status)
  - Performance: 1,000 assessments in <100 ms (SC-004)
  - Determinism: identical output for identical input (SC-005)
  - Pure function: no side effects, no I/O (FR-007)
  - **FR reference**: FR-001, FR-002, FR-004, FR-007, FR-011, FR-003
  - **File paths**: `tests/unit/test_three_color_models.py`
  - **Dependencies**: T002
  - **Complexity**: M

- [ ] **T004** Implement `assign_colors()` function in `src/openreview_cli/review/colors.py`:
  - Signature: `assign_colors(assessments: list[ClauseAssessment], threshold: float = 0.7) -> None`
  - Pure function: mutates assessments in-place (sets `color`, `effective_confidence`, `amber_reasons`)
  - No I/O, no side effects, no external calls — O(n) deterministic mapping
  - Call `_compute_effective_confidence()` per assessment (T006)
  - Apply color rules per data-model.md §Color Assignment Rules
  - Edge cases: empty list (no-op), assessments with already-set color (recompute)
  - Respect: grounding is only a trigger when `grounding_verdict is not None` (FR-004)
  - **FR reference**: FR-001, FR-002, FR-004, FR-007, FR-011, FR-003
  - **File paths**: `src/openreview_cli/review/colors.py` (NEW)
  - **Dependencies**: T003, T006 (effective_confidence), T002 (enums)
  - **Complexity**: M

- [ ] **T005** Write unit tests for `effective_confidence()` calculation in `tests/unit/test_three_color_models.py`:
  - `effective_confidence = min(confidence or 1.0, grounding_confidence or 1.0)`
  - Note: `qa_confidence` is not yet a field on `ClauseAssessment` — defaults to 1.0 (future spec)
  - Only extraction confidence available: `min(0.8, 1.0)` = 0.8
  - Both extraction and grounding confidence: `min(0.8, 0.6)` = 0.6
  - Both missing (None): `min(1.0, 1.0)` = 1.0
  - Extraction None, grounding 0.7: `min(1.0, 0.7)` = 0.7
  - Grounding None, extraction 0.5: `min(0.5, 1.0)` = 0.5
  - All stages at 1.0: effective confidence = 1.0
  - Zero confidence: `min(0.0, 1.0)` = 0.0
  - **FR reference**: FR-001
  - **File paths**: `tests/unit/test_three_color_models.py`
  - **Dependencies**: T002 (AmberReason enum for imports)
  - **Complexity**: S

- [ ] **T006** Implement `_compute_effective_confidence()` helper in `src/openreview_cli/review/colors.py`:
  - `def _compute_effective_confidence(assessment: ClauseAssessment) -> float`
  - `return min(assessment.confidence or 1.0, assessment.grounding_confidence or 1.0)`
  - Note: `qa_confidence` is omitted because it's not yet a field on `ClauseAssessment` (noted as `# ponytail: qa_confidence not yet a field — future spec`)
  - Used by `assign_colors()` (T004)
  - **FR reference**: FR-001
  - **File paths**: `src/openreview_cli/review/colors.py` (NEW)
  - **Dependencies**: T005, T002 (import ClauseAssessment type)
  - **Complexity**: S

- [ ] **T007** Extend existing unit tests for updated `ClauseAssessment` in `tests/unit/test_review_models.py`:
  - Test new fields: `color` defaults to `None`, `amber_reasons` defaults to `None`, `effective_confidence` defaults to `None`
  - Test `is_amber` property: returns `True` when `color == AssessmentColor.amber`, `False` for green/red
  - Test backward compat: existing consumers reading `ca.is_amber` before `assign_colors()` still work (falls back to stored `_is_amber`)
  - Test existing `ClauseAssessment` instances (without new fields) still construct via original constructor signature
  - Test serialization: `dataclasses.asdict()` includes new fields
  - Test `__post_init__` still sets `is_amber` for pre-color consumers (no regression)
  - **FR reference**: FR-009, FR-010
  - **File paths**: `tests/unit/test_review_models.py`
  - **Dependencies**: T002 (AssessmentColor enum)
  - **Complexity**: M

- [ ] **T008** Update `ClauseAssessment` dataclass in `src/openreview_cli/review/models.py`:
  - Add `color: AssessmentColor | None = None` field
  - Add `amber_reasons: list[AmberReason] | None = None` field
  - Add `effective_confidence: float | None = None` field
  - Rename stored `is_amber: bool = False` to `_is_amber: bool = False` (private)
  - Add `@property is_amber` that returns `(self.color == AssessmentColor.amber)` when color is set, falls back to `self._is_amber` when color is None
  - Import `AssessmentColor` and `AmberReason` from `openreview_cli.review.colors` using TYPE_CHECKING guard to avoid circular import
  - Bump `ReviewReport.schema_version` from `"1.0.0"` to `"1.1.0"` (additive fields only)
  - **FR reference**: FR-009, FR-010, FR-007
  - **File paths**: `src/openreview_cli/review/models.py`
  - **Dependencies**: T007, T002 (enum classes defined)
  - **Complexity**: M

- [ ] **T009** Extend existing unit tests for updated `ReviewSummary` in `tests/unit/test_review_models.py`:
  - Test `green_count` default (0)
  - Test `red_count` default (0)
  - Test `avg_effective_confidence` default (0.0)
  - Test `amber_count` preserved unchanged (backward compat)
  - Test `ReviewReport` can construct with new `confidence_threshold` field
  - Test `confidence_threshold` default (0.7)
  - Test `schema_version` is `"1.1.0"` after T008 bump
  - **FR reference**: FR-010, FR-007
  - **File paths**: `tests/unit/test_review_models.py`
  - **Dependencies**: T007 (ClauseAssessment tests done)
  - **Complexity**: S

- [ ] **T010** Update `ReviewSummary` and `ReviewReport` dataclasses in `src/openreview_cli/review/models.py`:
  - `ReviewSummary` additions:
    - `green_count: int = 0`
    - `red_count: int = 0`
    - `avg_effective_confidence: float = 0.0`
    - Keep `amber_count: int = 0` unchanged (backward compat)
  - `ReviewReport` addition:
    - `confidence_threshold: float = 0.7`
  - **FR reference**: FR-010, FR-007
  - **File paths**: `src/openreview_cli/review/models.py`
  - **Dependencies**: T009, T008 (ClauseAssessment updated)
  - **Complexity**: S

- [ ] **T011** Export new types and functions from `src/openreview_cli/review/__init__.py`:
  - Add to `__all__`: `"AssessmentColor"`, `"AmberReason"`, `"assign_colors"`
  - Add imports: `from openreview_cli.review.colors import AssessmentColor, AmberReason, assign_colors`
  - **FR reference**: FR-009
  - **File paths**: `src/openreview_cli/review/__init__.py`
  - **Dependencies**: T004, T002
  - **Complexity**: S

**Checkpoint**: Foundation ready — `uv run pytest tests/unit/test_three_color_models.py tests/unit/test_review_models.py -v` all pass. User story implementation can now begin.

---

## Phase 2: US1 + US3 — Three-Color Output with Amber Breakdown (P1 + P2) 🎯 MVP

**Goal**: Deliver the core three-color display in both terminal and JSON output. Amber reason breakdown (US3) is naturally bundled because reasons are displayed alongside the color in both output formats. The `assign_colors()` function is called before rendering to populate `color`, `amber_reasons`, and `effective_confidence`.

**Independent Test**: Run a review with known clause assessments and verify terminal shows Green/Amber/Red badges in the Status column with correct colors. JSON output includes `"color"`, `"amber_reasons"`, `"effective_confidence"`, and `"confidence_threshold"` fields.

- [ ] **T012** Write unit tests for three-color terminal rendering in `tests/unit/test_three_color_report.py`:
  - Green assessment → Status shows green badge (`● OK` or similar green indicator)
  - Amber assessment → Status shows amber badge (`⚠ AMBER` with yellow styling)
  - Red assessment → Status shows red badge (`● RED` with red styling)
  - Amber clause with reasons shows reason breakdown text (e.g., "Low confidence (0.45)")
  - Multiple amber reasons shown together ("Low confidence (0.45), QA disagreement")
  - Green/Red assessments have empty `amber_reasons` (not shown)
  - Summary section shows `Green: N`, `Amber: N`, `Red: N` (replacing `Amber flags: N` primary display)
  - Summary shows `Avg effective confidence: X.XX` and `Confidence threshold: X.X`
  - Backward compat: `Amber flags: N` still present in summary
  - Empty assessment list shows "No clauses to assess" without error
  - No grounding data present → no grounding triggers in amber reasons
  - **FR reference**: FR-005, FR-004, FR-010, FR-011
  - **File paths**: `tests/unit/test_three_color_report.py` (NEW)
  - **Dependencies**: T004, T008, T010 (models + colors exist)
  - **Complexity**: M

- [ ] **T013** Update `format_terminal()` in `src/openreview_cli/review/report.py`:
  - Import `assign_colors`, `AssessmentColor` from `openreview_cli.review.colors`
  - Call `assign_colors(report.assessments, report.confidence_threshold)` at the top of `format_terminal()`
  - Replace binary status rendering (line 71):
    ```python
    # OLD:
    status = "[bold red]⚠ AMBER[/bold red]" if ca.is_amber else "[dim]OK[/dim]"
    # NEW:
    if ca.color == AssessmentColor.green:
        status = "[green]● OK[/green]"
    elif ca.color == AssessmentColor.red:
        status = "[bold red]● RED[/bold red]"
    else:
        status = "[bold yellow]⚠ AMBER[/bold yellow]"
    ```
  - Update Summary section (lines 86-102):
    - Add `Green: {summary.green_count}` before `Amber:`
    - Add `Red: {summary.red_count}` after Amber
    - Add `Avg effective confidence: {summary.avg_effective_confidence:.2f}`
    - Add `Confidence threshold: {report.confidence_threshold}`
    - Keep `Amber flags: {summary.amber_count}` for backward compat
  - Add amber reason detail row when `ca.amber_reasons` is non-empty (secondary line per clause or detail section after table)
  - Ensure three-color computation does not add measurable latency (stateless O(n))
  - **FR reference**: FR-005, FR-004, FR-010, FR-001
  - **File paths**: `src/openreview_cli/review/report.py`
  - **Dependencies**: T012, T011 (exports), T010 (ReviewReport.confidence_threshold)
  - **Complexity**: M

- [ ] **T014** Write unit tests for three-color JSON output in `tests/unit/test_three_color_report.py`:
  - Each assessment has `"color"` field: `"green"`, `"amber"`, or `"red"`
  - Each assessment has `"amber_reasons"` field: list of strings (empty for Green/Red)
  - Each assessment has `"effective_confidence"` field: float or null
  - Each assessment has `"is_amber"` field: boolean (derived from color, backward compat)
  - Report root has `"confidence_threshold"`: 0.7 (default)
  - Summary has `"green_count"`, `"red_count"`, `"avg_effective_confidence"`
  - `"amber_count"` still present in summary (backward compat)
  - `"schema_version"` is `"1.1.0"`
  - JSON output is valid JSON (parses with `json.loads`)
  - `is_amber` is consistent with `color` (green → false, amber → true, red → false)
  - **FR reference**: FR-006, FR-009, FR-010
  - **File paths**: `tests/unit/test_three_color_report.py` (NEW)
  - **Dependencies**: T012 (report test infra), T004 (colors exist)
  - **Complexity**: M

- [ ] **T015** Update `format_json()` and `_report_to_dict()` in `src/openreview_cli/review/report.py`:
  - Import `assign_colors` from `openreview_cli.review.colors`
  - In `format_json()` (or `_report_to_dict()`), call `assign_colors()` before serialization
  - The new fields (`color`, `amber_reasons`, `effective_confidence`, `confidence_threshold`) are already included by `dataclasses.asdict()` after being populated by `assign_colors()`
  - `is_amber` is still written as a field (backward compat) — it's a stored field on the dataclass
  - `schema_version` is already `"1.1.0"` from T008
  - Verify: JSON output shape matches cli-interface.md schema
  - **FR reference**: FR-006, FR-009, FR-010
  - **File paths**: `src/openreview_cli/review/report.py`
  - **Dependencies**: T014, T013 (report formatting), T011 (exports)
  - **Complexity**: M

**Checkpoint**: MVP is shippable. Three-color terminal and JSON output work end-to-end. Amber reasons visible in both formats.

---

## Phase 3: US2 — Configurable Confidence Threshold (P1)

**Goal**: Users can pass `--confidence-threshold` on any review subcommand to control the boundary between high-confidence (Green/Red) and low-confidence (Amber) assessments. Invalid values are rejected with clear errors. Help text includes the accuracy ceiling disclosure.

**Independent Test**: Run the same review twice with `--confidence-threshold 0.9` and `--confidence-threshold 0.3`. The 0.9 run produces more Amber flags. Invalid values like `1.5` or `-0.1` are rejected.

- [ ] **T016** Write unit tests for `--confidence-threshold` CLI flag in `tests/unit/test_three_color_cli.py`:
  - Flag parses as float type
  - Default value is 0.7
  - Valid values: 0.0, 0.3, 0.5, 0.7, 0.9, 1.0 all accepted
  - Invalid values: -0.1, 1.5, "abc" rejected with error message
  - Validation callback: `0.0 <= value <= 1.0`
  - Help text contains accuracy ceiling disclosure substring
  - Help text mentions default of 0.7
  - Flag is optional (omitting it uses default)
  - Pattern matches existing Typer Option patterns in `app.py` (e.g., `--grounding-mode`)
  - **FR reference**: FR-003, FR-008, FR-012, FR-013
  - **File paths**: `tests/unit/test_three_color_cli.py` (NEW)
  - **Dependencies**: None (pure CLI parsing tests, can mock the review command)
  - **Complexity**: M

- [ ] **T017** Add `--confidence-threshold` flag to the `precheck review` subcommand in `src/openreview_cli/app.py`:
  - Define `DEFAULT_CONFIDENCE_THRESHOLD: float = 0.7` as a module-level constant in `app.py`
  - Add `_validate_threshold(value: float) -> float` callback:
    ```python
    def _validate_threshold(value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise typer.BadParameter(
                f"confidence-threshold must be between 0.0 and 1.0, got {value}"
            )
        return value
    ```
  - Add `confidence_threshold` parameter to `precheck review`:
    ```python
    confidence_threshold: float = typer.Option(
        DEFAULT_CONFIDENCE_THRESHOLD,
        "--confidence-threshold",
        help="Confidence threshold for Green/Amber/Red assignment (0.0-1.0). "
             "Clauses with effective confidence below this threshold are marked Amber. "
             "Note: The comparison accuracy of automated review is bounded by "
             "approximately 64% F1. Three-color output (Green/Amber/Red) is "
             "designed to mitigate this — set the threshold generously to push "
             "uncertain comparisons to Amber rather than risking false Green or Red.",
        min=0.0,
        max=1.0,
        callback=_validate_threshold,
    ),
    ```
  - Pass `confidence_threshold` to `run_review()` call
  - **FR reference**: FR-003, FR-008, FR-012, FR-013
  - **File paths**: `src/openreview_cli/app.py`
  - **Dependencies**: T016, T019 (threshold propagation)
  - **Complexity**: M

- [ ] **T018** Write integration tests for threshold propagation in `tests/integration/test_three_color_pipeline.py`:
  - Default threshold (0.7) produces expected color distribution
  - Custom threshold (0.9) produces MORE Amber flags than default
  - Custom threshold (0.3) produces FEWER Amber flags than default (SC-001)
  - Clause with confidence 0.85 and threshold 0.9 → Amber (confidence < threshold)
  - Clause with confidence 0.5 and threshold 0.5 → NOT Amber from threshold alone (`confidence < threshold` → `0.5 < 0.5` is False)
  - Empty assessment list: no error, graceful handling
  - Backward compat: `is_amber` accessible before and after `assign_colors()`
  - Benchmark: 1,000 assessments compute colors in <100 ms (SC-004)
  - Use monkeypatch or seeded data (no actual LLM calls)
  - **FR reference**: FR-003, FR-007, FR-012, FR-013, SC-001, SC-004
  - **File paths**: `tests/integration/test_three_color_pipeline.py` (NEW)
  - **Dependencies**: T017 (CLI flag), T013 (report rendering)
  - **Complexity**: M

- [ ] **T019** Wire `confidence_threshold` through the review pipeline in `src/openreview_cli/review/__init__.py`:
  - Add `confidence_threshold: float = 0.7` parameter to `run_review()` signature
  - Pass `confidence_threshold` to `_build_report()` — store it in `ReviewReport.confidence_threshold`
  - Update docstring with the new parameter
  - No need to modify extraction, QA, or grounding stages — threshold only affects output rendering
  - **FR reference**: FR-007, FR-013
  - **File paths**: `src/openreview_cli/review/__init__.py`
  - **Dependencies**: T010 (ReviewReport.confidence_threshold field), T017 (CLI flag exists)
  - **Complexity**: S

**Checkpoint**: MVP complete. Users can adjust threshold and see instant color recalculations. Invalid values rejected.

---

## Phase 4: US4 — Edge Cases & Validation (P3)

**Goal**: Boundary conditions are handled correctly: empty assessments, threshold values at extremes (0.0, 1.0), threshold at exact boundary (0.5), multiple amber triggers simultaneously. Pipeline integration completes with `ReviewReport` recording the threshold used.

**Independent Test**: Run with `--confidence-threshold 0.0` → no Amber from threshold alone, only error/QA-disagree. Run with `--confidence-threshold 1.0` → every non-perfect assessment is Amber.

- [ ] **T020** Write edge case tests extending `tests/unit/test_three_color_models.py`:
  - `--confidence-threshold 0.0`: no clause is Amber from threshold alone; only error/QA-disagree/grounding triggers Amber (FR-004)
  - `--confidence-threshold 1.0`: every clause with confidence < 1.0 is Amber; only perfect assessments (confidence=1.0, no triggers) pass
  - Threshold exactly 0.5 with confidence 0.5: NOT Amber from threshold (0.5 < 0.5 is False) — boundary correctness
  - Empty assessment list: `assign_colors()` returns gracefully with no error
  - Single-clause assessment list: works without special-casing
  - Assessment with ALL triggers simultaneously: status is Amber once (not triplicate), `amber_reasons` contains all 6 reasons
  - Assessment with no `grounding_verdict` (None): grounding is NOT a trigger (FR-004)
  - All Amber: all assessments show Amber, summary correctly shows `amber_count = N, green_count = 0, red_count = 0`
  - All Green: all favorable/neutral + confidence >= threshold → all Green, `amber_count = 0`
  - All Red: all unfavorable + confidence >= threshold → all Red, `amber_count = 0`
  - Mixture: 5 Green, 3 Amber, 2 Red → correct counts
  - Performance: 1,000 assessments in <100 ms (SC-004)
  - Determinism: same input → same output across multiple calls (SC-005)
  - **FR reference**: FR-001, FR-002, FR-004, FR-011, FR-003, SC-004, SC-005
  - **File paths**: `tests/unit/test_three_color_models.py`
  - **Dependencies**: T004 (assign_colors implemented)
  - **Complexity**: M

- [ ] **T021** Write integration test for `ReviewReport` confidence_threshold recording in `tests/integration/test_three_color_pipeline.py`:
  - `run_review()` with `confidence_threshold=0.7` → report has `confidence_threshold == 0.7`
  - `run_review()` with `confidence_threshold=0.3` → report has `confidence_threshold == 0.3`
  - Default (no argument) → report has `confidence_threshold == 0.7`
  - `schema_version` in report is `"1.1.0"` (minor bump, backward compat)
  - Two different thresholds on same input produce different color distributions with no pipeline re-run
  - **FR reference**: FR-007, FR-003, SC-001
  - **File paths**: `tests/integration/test_three_color_pipeline.py`
  - **Dependencies**: T019 (threshold wired), T018 (integration test infra)
  - **Complexity**: S

- [ ] **T022** Ensure `ReviewReport` construction records `confidence_threshold` in `src/openreview_cli/review/__init__.py`:
  - `_build_report()` already receives `confidence_threshold` from T019
  - Pass it to `ReviewReport(..., confidence_threshold=confidence_threshold)`
  - Update `_build_report()` to compute `green_count`, `red_count`, `avg_effective_confidence` in `ReviewSummary` — these are computed from assessments after color assignment
  - Note: `_build_report()` currently computes `amber_count` from `a.is_amber` — this still works because `is_amber` is a property that works before and after `assign_colors()`
  - The color counts in `ReviewSummary` are computed by `assign_colors()` before rendering, not in `_build_report()`. The fields default to 0 and get populated during rendering.
  - Alternatively: compute summary counts in `_build_report()` by calling `assign_colors()` there too. But that would break FR-001 (color at output time only). Better: keep summary counts as 0 defaults, compute during rendering alongside color.
  - **Resolution**: Keep `green_count`/`red_count`/`avg_effective_confidence` as 0 defaults. They are populated by `assign_colors()` or during rendering. The `amber_count` remains computed in `_build_report()` for backward compat.
  - **FR reference**: FR-007, FR-003
  - **File paths**: `src/openreview_cli/review/__init__.py`
  - **Dependencies**: T021, T019 (threshold wired), T010 (fields exist)
  - **Complexity**: S

**Checkpoint**: All edge cases handled. Pipeline fully integrated with threshold recording.

---

## Phase 5: Polish & Cross-Cutting

**Purpose**: Final integration, validation, and quality checks.

- [ ] **T023** Run full test suite:
  - `uv run pytest` — all unit and integration tests pass
  - New tests pass: `tests/unit/test_three_color_models.py`, `tests/unit/test_three_color_report.py`, `tests/unit/test_three_color_cli.py`
  - Extended tests pass: `tests/unit/test_review_models.py` (no regressions)
  - Integration tests pass: `tests/integration/test_three_color_pipeline.py`
  - Memory tests pass: `uv run pytest -m memory`
  - Fix any regressions in existing tests from model changes (`is_amber` property, new fields)
  - **FR reference**: All
  - **Dependencies**: T022 (all implementation done)
  - **Complexity**: M

- [ ] **T024** Run lint and format:
  - `uv run ruff check .` — zero new violations
  - `uv run ruff format --check .` — zero formatting diffs
  - Fix any lint/format issues in new or modified files
  - **FR reference**: All
  - **Dependencies**: T023
  - **Complexity**: S

- [ ] **T025** Run type check:
  - `uv run mypy src/ tests/` — zero new typing errors
  - No `# type: ignore` for three-color module code
  - `AssessmentColor` and `AmberReason` correctly typed as StrEnum subclasses
  - `assign_colors()` signature correctly typed
  - `confidence_threshold` typed as `float` everywhere
  - TYPE_CHECKING guards for cross-module imports (models.py → colors.py)
  - **FR reference**: All
  - **Dependencies**: T024
  - **Complexity**: S

- [ ] **T026** Run pre-commit:
  - `uv run pre-commit run --all-files` — all hooks pass
  - `ruff --fix` — no issues
  - `ruff-format` — no reformatting
  - `mypy` — clean
  - `pytest-fast` — fast tests pass (no slow/integration tests in fast suite)
  - stdlib hygiene — no issues
  - **FR reference**: All
  - **Dependencies**: T025
  - **Complexity**: S

- [ ] **T027** Quickstart validation scenarios from `specs/013-three-color-confidence/quickstart.md`:
  - Scenario 1 — Default threshold: terminal shows three-color badges with correct Green/Amber/Red
  - Scenario 2 — Custom threshold: `0.9` produces more Amber than `0.3`
  - Scenario 3 — JSON output: all new fields present
  - Scenario 4 — All Green edge case
  - Scenario 5 — Low confidence Amber edge case with reason
  - Scenario 6 — Backward compat: `is_amber` and `amber_count` still work
  - Scenario 7 — Help text: `--help` includes accuracy ceiling disclosure
  - Quick verification commands from quickstart.md all pass
  - **FR reference**: All, SC-001 through SC-007
  - **Dependencies**: T026 (pre-commit clean)
  - **Complexity**: M

---

## Phase 6: Documentation

- [ ] **T028** Update `AGENTS.md` deferred work table if any tasks are unblocked:
  - Check the deferred table in AGENTS.md (Phase 3 PII Stripping deferred tasks)
  - T033 (integration test for `--no-pii` flag) — blocked by review command existing (already exists as `precheck review`). The `--no-pii` flag is already on the `precheck review` command in `app.py`, so T033 test can be populated.
  - T035 (add `--no-pii` flag to review commands) — already done (line 443 of app.py)
  - **If T033 or T035 are now unblocked**, update the status and add a note referencing which task in this spec completed the unblocking
  - Otherwise, note that no Phase 3 deferred tasks were unblocked
  - **FR reference**: N/A (documentation)
  - **File paths**: `AGENTS.md` (or report the finding)
  - **Dependencies**: T027 (all scenarios validated)
  - **Complexity**: S

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Foundational) — BLOCKS all user stories
    ├── Phase 2 (US1+US3 — Three-Color Output) ← MVP
    │       └── Phase 3 (US2 — Configurable Threshold) ← MVP+
    │               └── Phase 4 (US4 — Edge Cases)
    └── Phase 5 (Polish) — depends on all phases
            └── Phase 6 (Documentation) — final
```

- **Phase 1** (Foundational): No dependencies — can start immediately. Blocking prerequisite for ALL phases.
- **Phase 2** (US1+US3): Depends on Phase 1 complete. Core three-color display.
- **Phase 3** (US2): Depends on Phase 2 (needs assign_colors to test threshold effect). Adds CLI flag.
- **Phase 4** (US4): Depends on Phase 3 (needs threshold wiring for edge case tests).
- **Phase 5** (Polish): Depends on all implementation phases (T022).
- **Phase 6** (Documentation): Depends on Polish complete.

### Within Each Phase

- Tests (marked TDD) MUST be written and FAIL before implementation
- Data models before services
- Core implementation before integration
- Phase complete before moving to next

### Parallel Opportunities

- **Phase 1 tasks**: T001 (enum tests), T003 (assign_color tests), T005 (eff_confidence tests), T007 (model extension tests), T009 (summary tests) — all test files can be drafted in parallel since they test different concerns. However, implementation (T002, T004, T006, T008, T010) must follow in dependency order.
- **T012 and T014** (terminal + JSON output tests): Can be written in parallel.
- **T013 and T015** (terminal + JSON implementation): Sequential (report.py same file).
- **T016 and T018** (CLI unit tests + integration tests): Can be written in parallel.
- **T020 and T021** (edge case unit tests + integration tests): Can be written in parallel.
- **T023–T027** (Polish): Sequential — each fix cycle depends on previous.

### Parallel Execution Example (Phase 1 — test files)

```bash
# Write all Phase 1 test files in parallel:
Task: "Write enum tests"                     # T001
Task: "Write assign_color tests"             # T003
Task: "Write effective_confidence tests"     # T005
Task: "Write ClauseAssessment extension tests"  # T007
Task: "Write ReviewSummary extension tests"  # T009
```

---

## Implementation Strategy

### MVP Scope (Phase 1 → Phase 2 → Phase 3)

The MVP delivers US1 + US2 + US3 (both P1 and P2), providing:
- Three-color terminal and JSON output (US1, P1)
- Configurable `--confidence-threshold` CLI flag (US2, P1)
- Amber reason breakdown in output (US3, P2)
- Default threshold of 0.7 with accuracy ceiling disclosure

**MVP ship**: Phase 3 (T019) complete. Both P1 features + P2 amber detail are working.

### Full Delivery (MVP + Polish)

1. Complete Phase 1: Foundational — Data Models & Color Logic
2. Complete Phase 2: US1+US3 — Three-Color Output → Ship MVP candidate
3. Complete Phase 3: US2 — Configurable Threshold → Ship MVP
4. Complete Phase 4: US4 — Edge Cases & Validation
5. Complete Phase 5: Polish — Quality gates
6. Complete Phase 6: Documentation

---

## Summary

| Item | Count |
|------|-------|
| **Total tasks** | 28 |
| Phase 1 (Foundational) | 11 |
| Phase 2 (US1+US3 — P1+P2 MVP) | 4 |
| Phase 3 (US2 — P1) | 4 |
| Phase 4 (US4 — P3) | 3 |
| Phase 5 (Polish) | 5 |
| Phase 6 (Documentation) | 1 |
| New source files | 1 (`colors.py`) |
| Modified source files | 4 (`models.py`, `report.py`, `__init__.py`, `app.py`) |
| New test files | 4 (`test_three_color_models.py`, `test_three_color_report.py`, `test_three_color_cli.py`, `test_three_color_pipeline.py`) |
| Extended test files | 1 (`test_review_models.py`) |

### MVP scope (Phase 1-3, 19 tasks)

The MVP includes three-color output, amber reason breakdown, and configurable threshold. This is shippable as a standalone feature — edge case validation (US4) is additive.

### File creation/modification order

1. `src/openreview_cli/review/colors.py` (NEW) + `tests/unit/test_three_color_models.py`
2. `src/openreview_cli/review/models.py` (MODIFY)
3. `src/openreview_cli/review/__init__.py` (MODIFY)
4. `tests/unit/test_review_models.py` (EXTEND)
5. `src/openreview_cli/review/report.py` (MODIFY) + `tests/unit/test_three_color_report.py`
6. `src/openreview_cli/app.py` (MODIFY) + `tests/unit/test_three_color_cli.py`
7. `tests/integration/test_three_color_pipeline.py` (NEW)
