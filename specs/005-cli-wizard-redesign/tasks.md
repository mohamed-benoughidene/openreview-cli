---
description: "Tasks for CLI wizard UX redesign — arrow-key navigation, review wizard, non-interactive guard"
---

# Tasks: CLI Wizard UX Redesign

**Input**: Design documents from `specs/005-cli-wizard-redesign/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Test tasks are included per the project TDD convention (AGENTS.md). Write tests FIRST, verify they fail, then implement.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths

---

## Phase 1: Setup

**Purpose**: Project initialization — add questionary dependency

- [ ] T001 Add `questionary` dependency — run `uv add questionary`, verify `uv sync` passes

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure that ALL user stories depend on

**⚠️**: No user story work can begin until this phase is complete

- [ ] T002 [P] Create `src/openreview_cli/cli/utils.py` — shared wrappers: `_select()`, `_checkbox()`, `_autocomplete()`, `_confirm()`, `_text()`, `_password()` around questionary primitives with consistent styling
- [ ] T003 [P] Create `ReviewConfiguration` dataclass, `ReviewMode` enum, `OutputFormat` enum in `src/openreview_cli/cli/review.py`
- [ ] T004 Add `_is_interactive()` terminal detection (pip, `TERM=dumb`, `sys.stdin.isatty()`) in `src/openreview_cli/cli/utils.py`

**Checkpoint**: Foundation ready — user story implementation can begin

---

## Phase 3: User Story 1 — Gateway Wizard Refactor (Priority: P1) 🎯 MVP

**Goal**: Refactor `SetupWizard` to use questionary arrow-key navigation, summary-before-save, inline validation, and Ctrl+C graceful exit. Public API unchanged.

**Independent Test**: `uv run pytest tests/ -k gateway -v` — all existing + new tests pass

### Tests for User Story 1 ⚠️

- [ ] T005 [P] [US1] Write unit tests for refactored `SetupWizard` arrow-key navigation and model selection in `tests/unit/test_gateway_wizard.py`
- [ ] T006 [P] [US1] Write integration tests for summary-before-save flow in `tests/integration/test_gateway_cli.py`

### Implementation for User Story 1

- [ ] T007 [US1] Replace `Prompt.ask()` provider/ model selection with `questionary.select()` / `autocomplete()` in `src/openreview_cli/gateway/wizard.py`
- [ ] T008 [US1] Add summary-before-save Rich Table confirmation in `src/openreview_cli/gateway/wizard.py`
- [ ] T009 [US1] Add Ctrl+C graceful exit (questionary returns None) + back navigation via choice option in `src/openreview_cli/gateway/wizard.py`
- [ ] T010 [US1] Refactor API key entry to `questionary.password()` with inline validation in `src/openreview_cli/gateway/wizard.py`
- [ ] T011 [US1] Verify all gateway tests pass — `uv run pytest tests/ -k gateway -v`

**Checkpoint**: US1 complete — gateway setup has arrow-key navigation and summary-before-save

---

## Phase 4: User Story 2 — Review Wizard + Review Command (Priority: P2)

**Goal**: Create `ReviewWizard` class (3-step flow + pre-flight check) and register `openreview review <file>` in `app.py`

**Independent Test**: `uv run pytest tests/ -k "review or gateway" -v`

### Tests for User Story 2 ⚠️

- [ ] T012 [P] [US2] Write unit tests for `ReviewWizard` in `tests/unit/test_review_wizard.py`
- [ ] T013 [P] [US2] Write integration tests for review CLI flow in `tests/integration/test_review_cli.py`

### Implementation for User Story 2

- [ ] T014 [US2] Implement `ReviewWizard.__init__()` with file validation and config in `src/openreview_cli/cli/review.py`
- [ ] T015 [US2] Implement pre-flight gateway readiness check (≥1 chat + ≥1 embed configured) in `src/openreview_cli/cli/review.py`
- [ ] T016 [US2] Implement mode/jurisdiction/output-format selection steps with conditional branching in `src/openreview_cli/cli/review.py`
- [ ] T017 [US2] Implement clause multi-select step (conditional: clause-by-clause mode only) in `src/openreview_cli/cli/review.py`
- [ ] T018 [US2] Implement Rich Table summary + confirmation before returning `ReviewConfiguration` in `src/openreview_cli/cli/review.py`
- [ ] T019 [US2] Add `review` Typer command with flags (`--non-interactive`, `--mode`, `--jurisdiction`, `--output`, `--clauses`) in `src/openreview_cli/app.py`
- [ ] T020 [US2] Verify review tests pass — `uv run pytest tests/ -k "review or gateway" -v`

**Checkpoint**: US2 complete — review command works in interactive mode

---

## Phase 5: User Story 3 — Non-Interactive Mode (Priority: P3)

**Goal**: Detection and graceful fallback when running in non-interactive terminals (`TERM=dumb`, piped stdin), plus instruction hints on all prompts

**Independent Test**: `uv run pytest tests/ -k "non-interactive" -v`

### Tests for User Story 3 ⚠️

- [ ] T021 [P] [US3] Write integration tests for non-interactive terminal fallback in `tests/integration/test_review_cli.py`

### Implementation for User Story 3

- [ ] T022 [US3] Add non-interactive terminal guard + flag-based fallback in `src/openreview_cli/gateway/wizard.py`
- [ ] T023 [US3] Add instruction hints (FR-08) to all wizard prompts in `src/openreview_cli/cli/utils.py`
- [ ] T024 [US3] Verify non-interactive scenarios pass — `uv run pytest tests/ -k "non-interactive" -v`

**Checkpoint**: US3 complete — all scenarios from quickstart.md should pass

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verification, pre-commit, memory budget, constitution compliance

- [ ] T025 [P] Pre-commit sweep — `uv run pre-commit run --all-files`
- [ ] T026 [P] Memory budget check — `uv run pytest -m memory`
- [ ] T027 Verify all 8 quickstart validation scenarios from `specs/005-cli-wizard-redesign/quickstart.md`
- [ ] T028 Cross-check constitution compliance: Privacy (masked input, auth.json), Local-First (no server), Dep-Minimalism (no forbidden deps), YAGNI (no speculative abstractions)

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup ─ T001)
  └→ Phase 2 (Foundational ─ T002-T004) — blocks all stories
       ├→ Phase 3 (US1 ─ T005-T011) 🎯 MVP
       ├→ Phase 4 (US2 ─ T012-T020) — shares utils.py from Phase 2
       └→ Phase 5 (US3 ─ T021-T024) — depends on both wizard codebases existing
            └→ Phase 6 (Polish ─ T025-T028)
```

### User Story Dependencies

| Story | Blocks | Blocked by |
|-------|--------|------------|
| US1 (P1) | — | Phase 2 (utils.py) |
| US2 (P2) | — | Phase 2 (utils.py, types) — independent of US1 |
| US3 (P3) | — | Phase 2 + US1 wizard + US2 wizard |

### Within Each User Story

- Tests (T005-T006, T012-T013, T021) written FIRST, verified failing
- Implementation tasks follow
- Story complete before moving to next

### Parallel Opportunities

| Batch | Tasks | Rationale |
|-------|-------|-----------|
| Phase 2 setup | T002, T003 | Different files, no deps |
| US1 tests | T005, T006 | Different files, no deps |
| US2 tests | T012, T013 | Different files, no deps |
| Polish | T025, T026 | Independent checks |

---

## Parallel Example: User Story 1

```bash
# Write tests (parallel):
# Task: T005 — Write unit tests for SetupWizard
# Task: T006 — Write integration tests for SetupWizard

# Implement (sequential within file):
# Task: T007 — Refactor provider/model selection
# Task: T008 — Add summary-before-save
# Task: T009 — Ctrl+C + back navigation
# Task: T010 — Password entry with validation

# Verify:
uv run pytest tests/ -k gateway -v
```

## Parallel Example: User Story 2

```bash
# Write tests (parallel):
# Task: T012 — Write unit tests for ReviewWizard
# Task: T013 — Write integration tests for review CLI

# Implement (sequential within file):
# Task: T014 — ReviewWizard.__init__
# Task: T015 — Pre-flight check
# Task: T016 — Mode/jurisdiction/format steps
# Task: T017 — Clause multi-select
# Task: T018 — Summary + confirmation
# Task: T019 — app.py review command

# Verify:
uv run pytest tests/ -k "review or gateway" -v
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup (T001)
2. Phase 2: Foundational (T002-T004)
3. Phase 3: US1 — Gateway wizard refactor (T005-T011)
4. **Stop and validate**: Gateway setup works with arrow keys
5. Deploy/demo if ready

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. US1 → Arrow-key gateway setup → deploy/demo (MVP!)
3. US2 → Review wizard + command → deploy/demo
4. US3 → Non-interactive mode → deploy/demo
5. Polish → Final verification

### Parallel Strategy

With multiple developers:
- Dev A: Phase 2 (T002-T004) then US1 (T005-T011)
- Dev B: US2 (T012-T020) once Phase 2 is done
- Dev C: US3 (T021-T024) once both wizards exist

---

## Notes

- `[P]` tasks = different files, no dependencies — can run in parallel
- `[Story]` label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Write tests first, verify they fail, then implement
- `cli/__init__.py` already created (Phase 1 plan output)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
