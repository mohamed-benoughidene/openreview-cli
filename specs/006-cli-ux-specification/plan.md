# Implementation Plan: CLI UX System Design

**Branch**: `feat/006-cli-ux` | **Date**: 2026-06-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-cli-ux-specification/spec.md`

## Summary

Implement the UX layer for the openreview CLI: semantic design tokens, a Rich/questionary component library (11 interactive components), a multi-step wizard state machine, a unified verb-noun command structure, structured error/warning/success feedback, terminal compatibility detection, and a 4-tier implementation order. The UX layer wraps existing Typer CLI infrastructure with Rich output and questionary interactive prompts, producing legally-scoped, privacy-first output for non-developer users.

## Technical Context

**Language/Version**: Python 3.12 (pinned in `.python-version`, `pyproject.toml`)

**Primary Dependencies**:
- Rich v15.0.0 — already transitive via Typer; used for Console, Live, Table, Panel, Progress, Status, Text
- questionary v2.1.1 — NEW dependency (`uv add questionary`); used for interactive prompt components (select, checkbox, confirm, text, password)
- Typer v0.26.8 — already installed; used for command structure, shell completion, exit codes, echo/secho/style, Context object
- shellingham — already transitive via Typer; used for shell detection during completion install
- httpx — already installed; no new use in this feature
- Pydantic — already installed; may be used for config schema validation (deferred by spec §10 UNVERIFIED #3)

**Storage**: SQLite (existing `src/openreview_cli/storage/` layer) — no schema changes from this feature

**Testing**: pytest (existing suite under `tests/`), TDD mandated by constitution Principle V

**Target Platform**: Linux, macOS, Windows terminal; TTY and non-TTY (CI/piped) modes; 80+ column terminals

**Project Type**: CLI application (src layout: `src/openreview_cli/`)

**Performance Goals**: First render < 100ms (corrected from spec's 200ms claim per verified clig.dev guidance); warm startup < 300ms; wizard step transition < 50ms visual; progress bar updates at 10Hz max

**Constraints**:
- <100 MB peak memory budget (UI components are trivial; no document processing in this layer)
- No web server, daemon, or telemetry (constitution Principle II)
- PII redaction on all stderr/log output (constitution Principle I)
- Flesch-Kincaid grade level < 10 for all user-facing text
- No new dependencies beyond questionary v2.1.1 (spec §2.1 selects questionary over InquirerPy)
- `NO_COLOR` env var must suppress all color output (spec §7.3)
- Non-TTY mode must function without any interactive prompts (spec §3.3)

**Scale/Scope**: Single developer; ~11 component modules; ~5 new source files; ~5 test files; 4 implementation tiers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | PASS | No new network paths. Stderr/log output with `--verbose` has PII redaction mandated (FR-FB-005). Config values never contain raw contract text. |
| II. Local-First, CLI-Only | PASS | UX layer is purely local CLI output. No server, no daemon, no telemetry added. |
| III. Hardware-Bounded | PASS | Rich Console, questionary prompts, and Typer command parsing have negligible memory overhead (<5 MB combined). No document processing in this feature. |
| IV. Dependency Minimalism | PASS with justification | Adds questionary v2.1.1 (1 new dep). Justified: interactive wizard requires a prompt library; questionary selected over 4-year-stale InquirerPy v0.3.4. MIT license, AGPL-3.0 compatible. Rich and Typer already installed; no other additions. |
| V. Spec-Driven, YAGNI | PASS | This feature follows spec 006. No speculative components beyond the 11 defined in spec §2.1-2.11. Implementation order (§9) defers tier 4 (help/docs) until tiers 1-3 ship. |

| Constraint | Status | Justification |
|-----------|--------|---------------|
| Python >=3.12 | PASS | No version bump. |
| uv package manager | PASS | Will `uv add questionary`. |
| Distribution naming | PASS | No changes to openreview-cli, openreview, openreview_cli. |
| AGPL-3.0 + Commercial | PASS | questionary is MIT (compatible). Rich is MIT. Typer is MIT. |
| Hardware budget | PASS | UI components <5 MB; total well within 100 MB budget. |
| Forbidden deps | PASS | questionary not on forbidden list. No langchain, llama-index, FAISS, spaCy added. |
| Product modes | PASS | No mode changes; UX layer wraps existing commands. |

**Pre-Phase 0 Gate**: ALL PASS. Proceed to research.

## Project Structure

### Documentation (this feature)

```text
specs/006-cli-ux-specification/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── cli-ux-contract.md
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── __init__.py          # Exposes __version__
├── app.py               # Typer app (extended with output flags, wizard callback)
├── errors.py            # Exit code constants (extended: 8 codes from spec §5.3)
├── types.py             # NEW: type aliases (OutputFormat, WizardStep, ColorRole)
├── ui/                  # NEW: UX component package
│   ├── __init__.py      # Public exports
│   ├── console.py       # SGRenderer (Rich Console singleton, capability detection)
│   ├── colors.py        # Design tokens (semantic palette, Role → Hex mapping)
│   ├── components/      # 11 component modules
│   │   ├── panel.py         # Info/Warning/Error/Success panels
│   │   ├── table.py         # SGTable (auto-width, plain/table output)
│   │   ├── spinner.py       # Spinner wrapper (live + fallback)
│   │   ├── progress.py      # Progress wrapper (streaming, cancellation)
│   │   ├── prompt.py        # Select/checkbox/confirm/text/password (questionary)
│   │   ├── wizard.py        # Wizard state machine (Entry → Results)
│   │   ├── key_bindings.py  # Keyboard shortcut map (Ctrl-C, Escape, Tab, etc.)
│   │   ├── status_line.py   # Status display (LLM streaming, mode context)
│   │   ├── header.py        # Separator/breadcrumb headers
│   │   ├── markdown.py      # Minimal MD renderer (headers, bullets, bold)
│   │   └── validation.py    # Input validation (paths, config keys, ranges)
│   └── feedback.py      # Structured feedback format (3-part error, exit mapping)
└── config/              # Existing config package (extended)
    └── first_run.py     # NEW: first-run detection + auto-wizard trigger

tests/
├── unit/
│   ├── test_ui_console.py
│   ├── test_ui_colors.py
│   ├── test_ui_panel.py
│   ├── test_ui_table.py
│   ├── test_ui_spinner.py
│   ├── test_ui_progress.py
│   ├── test_ui_prompt.py
│   ├── test_ui_wizard.py
│   ├── test_ui_feedback.py
│   ├── test_ui_key_bindings.py
│   ├── test_ui_status_line.py
│   ├── test_ui_header.py
│   ├── test_ui_markdown.py
│   ├── test_ui_validation.py
│   └── test_first_run.py
└── integration/
    ├── test_cli_output.py
    ├── test_cli_wizard.py
    └── test_cli_config.py
```

**Structure Decision**: New `src/openreview_cli/ui/` package isolates all UX concerns. Components live under `ui/components/` (one module per component per spec §2). Tests mirror source structure. Follows existing repo convention of `src/` layout and parallel test directories.

## Complexity Tracking

> No violations to justify. Constitution check passes clean.
