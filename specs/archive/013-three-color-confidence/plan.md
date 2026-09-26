# Implementation Plan: Three-Color Output with Confidence Scores

**Branch**: `013-three-color-confidence` | **Date**: 2026-07-03 | **Spec**: [`spec.md`](./spec.md)

**Input**: Feature specification from `specs/013-three-color-confidence/spec.md`

## Summary

Replace the current binary amber/ok output with a three-color (Green/Amber/Red) status system. Add a `--confidence-threshold` CLI flag (default 0.7) that controls the boundary between high-confidence (Green/Red) and low-confidence (Amber) assessments. Color is derived at output time as a stateless O(n) mapping from existing assessment fields — no pipeline re-run required.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: None new. Uses existing `dataclasses`, `enum.StrEnum`, `rich`, `typer`, `json` — all already installed.

**Storage**: N/A — color is derived at output time, not persisted.

**Testing**: pytest — unit tests for color assignment logic, integration tests for CLI flag, terminal rendering, and JSON output.

**Target Platform**: Linux/macOS/Windows (CLI tool)

**Project Type**: CLI tool (single-party review product mode)

**Performance Goals**: Stateless O(n) per clause — 1,000 clauses in <100 ms. No pipeline re-run on threshold change. No measurable memory allocation beyond existing assessment list.

**Constraints**: <100 MB peak memory, zero new runtime dependencies, backward compatibility with existing `is_amber` consumers (e.g., `app.py` lines checking `amber_count > 0`).

**Scale/Scope**: ~1,000 clauses max per review. Color logic is trivially parallelizable but the single-threaded O(n) scan is well within budget.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Justification |
|-----------|---------|---------------|
| **I. Privacy First** | Pass | No new PII exposure. Confidence scores are derived from already-processed assessment data. |
| **II. Local-First, CLI-Only** | Pass | No server, no daemon, no long-running process. Just a CLI flag + output formatting. |
| **III. Hardware-Bounded** | Pass | Color assignment is O(1) per clause, no new memory-heavy operations, no new imports at module level. |
| **IV. Dependency Minimalism** | Pass | Zero new runtime dependencies. Uses existing `rich`, `typer`, `dataclasses`, `enum.StrEnum`. |
| **V. Spec-Driven, YAGNI** | Pass | Building only what N-6/R-6/§6.4 require. No speculative abstractions — color enum replaces boolean directly, no factory, no plugin system. |

## Project Structure

### Documentation (this feature)

```text
specs/013-three-color-confidence/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output — four research questions
├── data-model.md        # Phase 1 output — entity definitions and color rules
├── quickstart.md        # Phase 1 output — validation scenarios
├── contracts/           # Phase 1 output — CLI interface contract
│   └── cli-interface.md
└── tasks.md             # Phase 2 output (/speckit.tasks command — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/openreview_cli/review/
├── models.py            # Add AssessmentColor enum, AmberReason enum
│                        # Modify ClauseAssessment: add color, effective_confidence, amber_reasons
│                        # Modify ReviewSummary: add green_count, red_count
│                        # Modify ReviewReport: add confidence_threshold
├── report.py            # Three-color terminal rendering + JSON output with color field
├── colors.py            # NEW — color assignment logic (pure function, testable)
├── __init__.py          # Export new types and assign_color function
├── base.py              # ReviewCommand: wire confidence_threshold through pipeline

src/openreview_cli/app.py  # Add --confidence-threshold flag to review subcommands

tests/unit/review/
├── test_colors.py       # NEW — unit tests for color assignment logic

tests/integration/
├── test_three_color_output.py  # NEW — CLI flag, terminal rendering, JSON schema
```

**Structure Decision**: Single-project layout (Option 1). No new package — `colors.py` is a single file in the existing `review/` package. Tests follow the existing `tests/unit/` and `tests/integration/` convention.

## Implementation Phases

### Phase 1 — Data Model (models.py)

Files: `src/openreview_cli/review/models.py`

1. Add `AssessmentColor(StrEnum)` — `green`, `amber`, `red`
2. Add `AmberReason(StrEnum)` — `low_confidence`, `qa_disagreement`, `qa_uncertain`, `error`, `grounding_failure`, `grounding_uncertain`
3. Modify `ClauseAssessment`:
   - Add `color: AssessmentColor | None = None` (set at output time, not in `__post_init__`)
   - Add `amber_reasons: list[AmberReason] | None = None`
   - Add `effective_confidence: float | None = None`
   - Add `is_amber` property: `return self.color == AssessmentColor.AMBER` (computed from color, not stored)
   - Keep existing `is_amber` field as backward-compat but deprecate it — the field will still be set in `__post_init__` for consumers that read it before color is assigned; the property takes precedence after color is set
4. Modify `ReviewSummary`:
   - Add `green_count: int = 0`
   - Add `red_count: int = 0`
   - Add `avg_effective_confidence: float = 0.0`
   - Preserve `amber_count` as stored field (backward compat)
5. Modify `ReviewReport`:
   - Add `confidence_threshold: float = 0.7`

### Phase 2 — Color Assignment Logic (colors.py + models.py)

Files: `src/openreview_cli/review/colors.py`, `src/openreview_cli/review/__init__.py`

1. Create `colors.py` with pure function `assign_colors(assessments, threshold=0.7)`:
   - Computes `effective_confidence = min(extraction_confidence, qa_confidence, grounding_confidence)` with missing stages defaulting to 1.0
   - Applies the rule set from spec FR-002 and the data-model.md color rules
   - Returns updated assessments with `color`, `effective_confidence`, `amber_reasons` set
   - Pure function: no side effects, no I/O, deterministic
2. Update `ReviewSummary` computation to include `green_count`, `red_count`, `avg_effective_confidence`
3. Export `assign_colors`, `AssessmentColor`, `AmberReason` from `review/__init__.py`

### Phase 3 — Terminal Rendering (report.py)

Files: `src/openreview_cli/review/report.py`

1. Replace binary `⚠ AMBER` / `OK` status with three-state color badge:
   - Green → `[green]● OK[/green]`
   - Amber → `[bold yellow]⚠ AMBER[/bold yellow]`
   - Red → `[bold red]● RED[/bold red]`
2. Add Amber reason detail in terminal output when `amber_reasons` is non-empty (e.g., an expandable detail row or secondary line)
3. Add `green_count` and `red_count` to summary section
4. Add `avg_effective_confidence` to summary section
5. Call `assign_colors()` before rendering if colors are not already set

### Phase 4 — JSON Output (report.py)

Files: `src/openreview_cli/review/report.py`

1. Add `"color"` field to each assessment in JSON output
2. Add `"amber_reasons"` field (list of strings)
3. Add `"effective_confidence"` field
4. Add `"confidence_threshold"` field to report root
5. Add `green_count`, `red_count`, `avg_effective_confidence` to summary
6. Keep `is_amber` boolean in JSON for backward compat (derived from color)

### Phase 5 — CLI Flag (app.py)

Files: `src/openreview_cli/app.py`, `src/openreview_cli/review/base.py`

1. Define `DEFAULT_CONFIDENCE_THRESHOLD = 0.7` shared constant
2. Add `--confidence-threshold` flag to every review-producing subcommand:
   - Type: `float`, range: `[0.0, 1.0]` with Typer callback validation
   - Default: `0.7`
   - Help text includes accuracy ceiling disclosure (FR-008)
3. Wire `confidence_threshold` through `ReviewCommand` to the report rendering step
4. Validate flag value: `0.0 <= value <= 1.0`, reject with clear error otherwise

### Phase 6 — Tests

Files: `tests/unit/review/test_colors.py`, `tests/integration/test_three_color_output.py`

1. Unit tests for `assign_colors()`:
   - Green: favorable/neutral + confidence >= threshold + no Amber triggers
   - Red: unfavorable + confidence >= threshold + no Amber triggers
   - Amber: low confidence, QA disagree, QA uncertain, error, grounding failure, grounding uncertain
   - Edge cases: empty list, threshold at boundary (0.5 exactly), all triggers simultaneously
   - Performance: 1,000 clauses in <100 ms
   - Determinism: identical output for identical input
2. Integration tests:
   - `--confidence-threshold` flag acceptance and rejection of invalid values
   - Different thresholds producing different color distributions
   - JSON output format with `color`, `amber_reasons`, `effective_confidence`, `confidence_threshold`
   - Terminal rendering with three-color badges
   - Empty assessment list
   - Backward compat: `is_amber` still accessible
   - Help text includes accuracy ceiling disclosure

## Complexity Tracking

None — all 5 constitution principles pass. No violations to justify.
