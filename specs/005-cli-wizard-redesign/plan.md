# Implementation Plan: CLI Wizard UX Redesign

**Branch**: `feat/005-cli-wizard-redesign` | **Date**: 2026-06-27 | **Spec**: `specs/005-cli-wizard-redesign/spec.md`

**Input**: Feature specification from `specs/005-cli-wizard-redesign/spec.md`

## Summary

Replace `rich.prompt.Prompt.ask()` with `questionary` interactive prompts (arrow-key select, checkbox, autocomplete) across the gateway setup wizard and the new review wizard. Add summary-before-save to gateway setup, build a new `ReviewWizard` class for the `review` command, and add pre-flight gateway readiness checks.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**:
- `questionary>=2.1.1` (new — MIT, arrow-key prompts, checkbox, autocomplete, Ctrl+C safe)
- `rich>=15.0.0` (existing — summary tables, styling)
- `typer>=0.26.7` (existing — CLI framework)
- `pydantic>=2.13.4` (existing — slot config models)
- `prompt_toolkit>=2.0,<4.0` (transitive via questionary, BSD-3, SSH/PTY support)

**Storage**: YAML config (`config.yml`), JSON auth (`auth.json`, chmod 600 via `atomic_write`)

**Testing**: pytest (unit + integration). Existing patterns in `tests/unit/` and `tests/integration/`.

**Target Platform**: Linux, macOS, Windows Terminal, WSL, SSH with PTY

**Project Type**: CLI package (`openreview-cli`), single project, no server

**Performance Goals**: N/A — wizard responsiveness is bounded by prompt_toolkit rendering latency (sub-second)

**Constraints**:
- No web server or long-running daemon
- Must work over SSH with PTY
- Must degrade gracefully in non-interactive terminals (`TERM=dumb`, piped stdin)
- Peak memory <110 MB (questionary adds ~2 MB to install size)

**Scale/Scope**: Single user, local-only CLI

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Phase 0 | Phase 1 | Notes |
|-----------|---------|---------|-------|
| **1. Privacy First** | ✅ PASS | ✅ PASS | API key entry uses `questionary.password()` (masked input). Auth.json chmod 600 preserved. No contract text transmitted in wizard. |
| **2. Local-First, CLI-Only** | ✅ PASS | ✅ PASS | No web server, no daemon. questionary is prompt_toolkit-based — terminal UI only. |
| **3. Hardware-Bounded** | ✅ PASS | ✅ PASS | questionary ~0.5 MB + prompt_toolkit ~1.5 MB. Streaming parsers unchanged. |
| **4. Dependency Minimalism** | ✅ PASS | ✅ PASS | questionary not on forbidden list. MIT license compatible. Will `uv add questionary`. |
| **5. Spec-Driven, YAGNI** | ✅ PASS | ✅ PASS | Spec written, clarified (5 questions), approved. No speculative abstractions. |

**Gate result: ALL PASS — no violations.**

## Project Structure

### Documentation (this feature)

```text
specs/005-cli-wizard-redesign/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/
│   ├── review_wizard.md # Phase 1 output
│   └── gateway_wizard.md# Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── __init__.py
├── __main__.py
├── app.py              # + review command
├── cli/                # NEW — shared wizard utilities
│   ├── __init__.py
│   ├── utils.py        # _select(), _checkbox(), _autocomplete() wrappers
│   └── review.py       # ReviewWizard class
├── gateway/
│   └── wizard.py       # SetupWizard — refactored (questionary internals, public API unchanged)
└── ...

tests/
├── unit/
│   ├── test_review_wizard.py     # NEW
│   └── test_gateway_wizard.py    # existing (verify unchanged behavior)
├── integration/
│   ├── test_review_cli.py        # NEW
│   └── test_gateway_cli.py       # existing (verify unchanged behavior)
└── ...
```

**Structure Decision**: Single project (Option 1). New files created in `src/openreview_cli/cli/` for wizard utilities. No new directories needed outside the existing package structure.

## Complexity Tracking

No violations to justify. Section intentionally left empty.

## Implementation Order (Phase 2 — tasks.md)

1. `uv add questionary` → verify `uv sync` passes
2. Create `src/openreview_cli/cli/__init__.py` (empty)
3. Create `src/openreview_cli/cli/utils.py` — shared wrappers (`_select`, `_checkbox`, `_autocomplete`, `_confirm`, `_text`, `_password`) with consistent questionary styling
4. Refactor `gateway/wizard.py` — replace `Prompt.ask()` with questionary primitives, add summary-before-save confirmation, keep `SetupWizard.run()` signature unchanged
5. Create `src/openreview_cli/cli/review.py` — `ReviewWizard` class with 3-step flow, pre-flight check, conditional branching, Rich Table summary
6. Modify `src/openreview_cli/app.py` — add `review` Typer command with `--non-interactive`, `--mode`, `--jurisdiction`, `--output`, `--clauses` flags
7. Write tests: `tests/unit/test_review_wizard.py` (unit), `tests/integration/test_review_cli.py` (CLI flow)
8. Update `tests/integration/test_gateway_cli.py` — ensure existing tests pass post-refactor
9. Pre-commit sweep: `uv run pre-commit run --all-files`
10. Smoke test: `uv run pytest tests/ -k "wizard or review" -v`
