# Implementation Plan: Playbook Management

**Branch**: `feat/playbook-management` | **Date**: 2026-07-06 | **Spec**: `specs/024-playbook-management/spec.md`

**Input**: Feature specification from `/specs/024-playbook-management/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command.

## Summary

Add 5 CLI commands to the existing `playbook` group — `export`, `diff`, `set-current`, `delete` (soft), `history` — plus T055/T056 precedence warning convergence. All operate on the existing SQLite playbook store (single new migration 007). No new dependencies.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `typer` (CLI framework, already in), `pyyaml` (YAML serde, already in), `rich` (terminal tables, already in), `sqlite3` (stdlib)

**Storage**: SQLite via `src/openreview_cli/storage/database.py`. Migration 007 adds `playbook_meta` table (`current_version`, `deleted_at` columns).

**Testing**: pytest (existing unit/integration layout). New files under `tests/unit/test_playbook_export.py`, `tests/unit/test_playbook_diff.py`, etc. TDD: tests before implementation.

**Target Platform**: Linux/macOS CLI. No platform-specific code.

**Project Type**: CLI tool (local-only, no server)

**Performance Goals**: N/A — playbook metadata is tiny (<100 rows, <1KB per row). No measurable impact on memory or latency.

**Constraints**: Append-only invariant — no hard-delete, no version overwrite. Peak memory <100 MB (floor: 110 MB; existing constitutional floor, playbook operations use negligible memory).

**Scale/Scope**: 5 new CLI subcommands + 1 schema migration + precedence warning convergence. ~350-500 lines total new production code.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | N/A | Playbook management operates on local metadata (playbook names, versions, YAML content). No PII involvement. |
| II. Local-First, CLI-Only | Pass | New commands are CLI-only, no server, no daemon, no telemetry. All data stays in local SQLite. |
| III. Hardware-Bounded | Pass | Playbook metadata is tiny (<100 rows, <1KB each). No streaming, no large allocations. No memory budget impact. |
| IV. Dependency Minimalism | Pass | Zero new dependencies. Uses PyYAML (already in), Rich (already in), sqlite3 (stdlib). |
| V. Spec-Driven, YAGNI | Pass | Spec exists, reviewed. Minimal surface — 5 commands, no speculative abstraction. No interface/one-impl patterns. |

**Result: PASS** — no violations. No complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/024-playbook-management/
├── spec.md               # Feature specification
├── checklists/
│   └── requirements.md   # Spec quality checklist
├── plan.md               # This file
├── research.md           # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
│   ├── cli-commands.md
│   └── storage-api.md
└── tasks.md              # Phase 2 output (next command)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── app.py                 # New subcommands in playbook group (~lines 420-610)
├── review/
│   └── playbook.py        # DiffResult dataclass + diff computation (business logic)
├── storage/
│   ├── database.py        # New storage functions (export data fetch, set-current, delete, history)
│   └── migrations/
│       └── 007_playbook_meta.sql  # Add playbook_meta table

tests/
├── unit/
│   ├── test_playbook_export.py     # Export command tests
│   ├── test_playbook_diff.py       # Diff command tests
│   ├── test_playbook_set_current.py # Set-current tests
│   ├── test_playbook_delete.py     # Soft-delete tests
│   ├── test_playbook_history.py    # History command tests
│   └── test_playbook_precedence.py # T055/T056 convergence tests
└── integration/
    ├── test_playbook_export.py     # Round-trip integration tests
    ├── test_playbook_diff.py       # Full-stack diff integration tests
    └── test_playbook_management.py # Delete/set-current/history integration
```

**Structure Decision**: Follows existing single-project layout. New storage functions added to `database.py`. Diff computation and `DiffResult` dataclass live in `review/playbook.py` (business logic layer). New unit tests follow `test_<module>_<feature>.py` pattern. Integration tests follow `test_<command>_<feature>.py` pattern.

## Complexity Tracking

*No constitution violations to justify.*
