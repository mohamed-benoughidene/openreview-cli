# Implementation Plan: Cleanup & Polish — Close Remaining Test Gaps

**Branch**: `feat/022-cleanup-polish` | **Date**: 2026-07-06 | **Spec**: `specs/022-cleanup-polish/spec.md`

**Input**: Feature specification from `/specs/022-cleanup-polish/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Close remaining test gaps across three already-shipped features: playbook versioning precedence warnings (R1), bilateral comparison CLI flag and error-handling tests (R2-R3), and PII `--no-pii` flag integration test and coverage across review commands (R4-R5). Excludes infrastructure-dependent blocked tasks (config-change detection, threshold re-strip, missing-model Presidio error, benchmark corpus validation). All production code already shipped — only test coverage is added.

Three scenarios:
1. **Playbook Precedence Warning** — test that `--playbook` + `--playbook-path` conflict emits warning on stderr, names both flags, states which won, continues execution
2. **Bilateral Comparison CLI** — test input validation (missing file, bad format, unreadable), flag parsing, help output, successful comparison
3. **PII `--no-pii` Flag** — integration test that flag exists on all review subcommands, bypasses PII engine, default behavior still strips PII

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**:
- Zero new dependencies. All testing uses existing project infrastructure:
  - `pytest` — test framework (dev dep, already configured)
  - `typer.testing.CliRunner` — CLI invocation tests (already used in existing tests)
  - `monkeypatch` — mock gateway and PII engine in integration tests
  - `capsys` / `capfd` — capture stderr for warning/error assertion
- Existing project modules:
  - `openreview_cli.app` — app, `cli_runner()` or `CliRunner()`
  - `openreview_cli.review.base` — ReviewCommand, PII orchestration
  - `openreview_cli.review.playbook` — PlaybookLoader, precedence logic
  - `openreview_cli.pii.engine` — PiiEngine (mock target)
  - `openreview_cli.review._gateway` — gateway call helper (mock target)
  - `tests.conftest` — shared fixtures (memory_tracker, fixtures_dir)

**Storage**: N/A — tests use temporary files (`tmp_path` fixture) and in-memory state. No database.

**Testing**:
- pytest with existing markers (`unit`, `integration`, `memory`, `slow`)
- `CliRunner` for CLI invocation tests
- `monkeypatch` / `unittest.mock` for gateway and PII engine mocking
- `capsys` / `capfd` for stderr output assertion
- `tmp_path` for temporary file creation
- Pre-commit hook `pytest-fast` runs unit tests; CI runs full suite

**Target Platform**: Linux, macOS, Windows (local CLI)

**Project Type**: Local CLI tool (Python package `openreview-cli`)

**Performance Goals**:
- All tests complete in < 5s total
- No new memory pressure — tests assert peak < 110 MB via existing memory_tracker fixture
- No external API calls in tests — gateway fully mocked

**Constraints**:
- Python 3.12 minimum
- `uv` package manager only
- No new dependencies
- No web server / no long-running process
- Mock all AI gateway and PII engine calls — no external dependencies in CI
- PII stripping may degrade extraction accuracy — tests validate behavior, not require new benchmarks
- Bilateral comparison accuracy ceiling (~64% F1 per research) — output uses Green/Amber/Red UX with Amber escape hatch
- `--no-pii` flag must be documented in help output for each review subcommand
- Warning on stderr (not stdout) for playbook conflict
- Non-zero exit code on bilateral comparison validation failure

**Scale/Scope**:
- ~5 new test files (3 unit, 2 integration)
- ~250 lines of test code total
- 0 lines of production code changes (all features already shipped)
- 0 new fixtures needed for existing tests
- 1-2 small fixture documents for bilateral comparison (if not already present)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Justification |
|-----------|---------|---------------|
| **I. Privacy First** | PASS | Tests never process real PII. Gateway mocked. No network calls. PII engine mock verifies bypass behavior only. |
| **II. Local-First, CLI-Only** | PASS | Tests are local only. No server, daemon, telemetry, or network path. All external APIs mocked. |
| **III. Hardware-Bounded** | PASS | Tests assert peak memory < 110 MB via existing `memory_tracker` fixture. No new document processing or NLP model loading in test paths. |
| **IV. Dependency Minimalism** | PASS | Zero new runtime or dev dependencies. Uses existing pytest, CliRunner, monkeypatch, capsys. No additions to `pyproject.toml`. |
| **V. Spec-Driven, YAGNI** | PASS | Pure test coverage for already-shipped production code. No speculative abstractions. No new features. Each test maps 1:1 to a spec requirement. |

**Result**: **PASS** — no violations. Complexity tracking section not required.

## Project Structure

### Documentation (this feature)

```text
specs/022-cleanup-polish/
├── spec.md              # Feature specification (input)
├── plan.md              # This file — implementation plan
├── research.md          # Phase 0 — research findings
├── data-model.md        # Phase 1 — data model and relationships
├── quickstart.md        # Phase 1 — validation guide
└── tasks.md             # Phase 2 — task breakdown (created by /speckit.tasks)
```

### Source Code (repository root)

```text
# No new source directories. All changes are test-file additions only.

src/openreview_cli/
├── app.py                        # Unchanged (already has bilateral comparison subcommand)
├── review/
│   ├── base.py                   # Unchanged (already has --no-pii flag)
│   ├── playbook.py               # Unchanged (already has precedence logic)
│   └── _gateway.py               # Mock target for integration tests

tests/
├── conftest.py                   # Unchanged (shared fixtures)
├── fixtures/                     # Existing test fixtures; optionally 1-2 small sample docs
├── unit/
│   ├── test_playbook_precedence.py   # NEW — playbook flag conflict warning (R1)
│   └── test_bilateral_comparison.py  # NEW — bilateral comparison CLI tests (R2-R3)
├── integration/
│   └── test_no_pii_flag.py           # NEW — --no-pii flag integration test (R4-R5)
└── README.md                    # Unchanged
```

**Structure Decision**: Follows existing `tests/unit/` and `tests/integration/` layout. No new source packages needed — all changes are test additions.

## Research Needs (resolved in research.md)

No NEEDS CLARIFICATION items. Spec is unambiguous. Research covers:
1. Verifying existing `--no-pii` flag wiring in `base.py` — confirm flag definition and PII orchestration path
2. Verifying existing playbook precedence logic in `playbook.py` — confirm which flag wins and where warning hook is needed
3. Verifying existing bilateral comparison subcommand in `app.py` — confirm flag names, validators, error messages
4. Confirming mocking patterns in existing integration tests (e.g., `test_precheck_pii.py` for gateway mock pattern)
5. Confirming test fixture availability for bilateral comparison sample documents
