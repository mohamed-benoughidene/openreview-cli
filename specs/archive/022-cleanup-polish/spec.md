# Cleanup and Polish — Close Remaining Test Gaps

**Feature ID**: 022-cleanup-polish
**Status**: Draft Specification
**Created**: 2026-07-06

## Overview

Close remaining test gaps across three already-shipped features: playbook versioning precedence warnings, bilateral comparison CLI flag and error-handling tests, and PII no-pii flag integration test and coverage across review commands. Excludes infrastructure-dependent blocked tasks (config-change detection, threshold re-strip, missing-model Presidio error, benchmark corpus validation).

---

## User Scenarios and Testing

### Scenario 1: Playbook Versioning Precedence Warning

A user runs a review command with both `--playbook` (by name) and `--playbook-path` (by file path) provided simultaneously. The system detects the conflict and issues a clear warning message explaining which argument takes precedence and that the other is ignored. The user sees the warning and understands which playbook was selected.

**Testing considerations**:
- Warning fires when both flags are present
- Warning message names both arguments and states which won
- No crash or silent fallback — command proceeds with the winning argument
- Warning appears on stderr, not stdout (preserving machine-readable output)

### Scenario 2: Bilateral Comparison CLI Flag and Error Handling

A user invokes the bilateral comparison feature (comparing two documents side by side). The system validates input, provides clear error messages for missing files, invalid formats, and permission issues. On success, comparison output is produced.

**Testing considerations**:
- Valid comparison command with correct arguments succeeds
- Missing file path produces a user-friendly error
- Invalid document format produces a user-friendly error
- Unreadable file produces a user-friendly error
- Correct CLI flags are accepted and parsed
- Help output documents the comparison subcommand

### Scenario 3: PII No-PII Flag Integration

A user runs a review command and passes the `--no-pii` flag, indicating PII stripping should be skipped. The system respects the flag across all review subcommands (precheck, etc.). PII detection is bypassed; text is sent to the AI gateway without stripping.

**Testing considerations**:
- `--no-pii` flag accepted on all review subcommands
- PII engine not invoked when flag is set
- Document text reaches AI gateway without PII processing
- Default behavior (no flag) still strips PII
- Flag is documented in help output for each subcommand

---

## Functional Requirements

### R1: Playbook Precedence Warning

The system must issue a warning message to stderr when both `--playbook` and `--playbook-path` flags are provided to a single command invocation. The warning must state which flag takes precedence and that the other is ignored.

**Acceptance criteria**:
- Warning appears on stderr
- Warning text contains both flag names
- Command execution continues without error after the warning

### R2: Bilateral Comparison Input Validation

The bilateral comparison subcommand must validate all input paths before proceeding. For each invalid input (missing file, unreadable file, unsupported format), the system must produce a distinct, user-friendly error message on stderr and exit with a non-zero code.

**Acceptance criteria**:
- Missing file path produces error containing the path and "not found"
- Unsupported format produces error naming the format
- Valid input produces comparison output
- Non-zero exit code on any validation failure

### R3: Bilateral Comparison CLI Flag Coverage

The bilateral comparison CLI subcommand must support all flags documented in its help output. All flag combinations that produce valid output must be tested. The help text must contain the `compare` (or equivalent) subcommand name.

**Acceptance criteria**:
- Help output documents all comparison flags
- Each flag accepted and parsed correctly
- No silent flag collisions

### R4: PII No-PII Flag Across Review Commands

Every review subcommand (precheck review, precheck compare) must accept a `--no-pii` flag. Future review subcommands inherit this flag from the `ReviewCommand` base class. When the flag is present, PII detection and stripping must be skipped for the entire document. When absent, PII stripping must occur as normal.

**Acceptance criteria**:
- `--no-pii` accepted on every review subcommand
- With `--no-pii`: PII engine not called; text bypasses PII processing
- Without `--no-pii`: PII engine called; text is stripped before gateway
- Help output for each review subcommand lists the flag

### R5: PII No-PII Integration Test

An integration test must verify the `--no-pii` flag end-to-end: invoke a review command with the flag, confirm PII was not stripped, and confirm text reached the AI gateway intact. A second test must confirm the default (no flag) still strips PII.

**Acceptance criteria**:
- Integration test passes with `--no-pii` flag
- Integration test passes without `--no-pii` flag (PII stripped)
- Tests run in CI without external network or API calls (mocked gateway)

---

## Success Criteria

1. All warning messages and error outputs are clearly worded and actionable for the user.
2. Every testable error path in the bilateral comparison subcommand produces a distinct exit code and message.
3. The `--no-pii` flag is consistently available across all review subcommands.
4. Integration tests for all three feature areas pass in CI without external dependencies.
5. No regressions in existing test suite (full pre-commit suite passes).
6. Peak memory stays under 110 MB for all new test scenarios.

---

## Key Entities

| Entity | Description |
|--------|-------------|
| Playbook argument conflict | The condition where both `--playbook` and `--playbook-path` are supplied |
| Precedence warning | The user-facing warning message emitted on stderr |
| Bilateral comparison input | One or two document paths to compare |
| Validation error | Structured error for missing file, bad format, permissions |
| No-PII flag state | Boolean state indicating whether PII stripping is disabled |
| Review command | Any product-mode subcommand (precheck, etc.) that processes a document |

---

## Assumptions

1. The bilateral comparison subcommand already exists in `app.py` (per spec 014).
2. The `--no-pii` flag is already defined in the review base command class (per phase 3 deferred tasks T033-T035).
3. Playbook precedence logic (name wins over path or vice versa) is already implemented in the playbook loader — only the warning message is missing.
4. All three features have their production code already shipped; only test coverage is being added.
5. CI infrastructure (GitHub Actions, pytest, pre-commit) is already configured and working.
6. Tests use mocking for the AI gateway and PII engine to avoid external dependencies and model downloads.
7. The `--no-pii` flag integration test (T066) is currently a skeleton and needs to be populated.

---

## Dependencies

1. Spec 017 (playbook versioning) — defines the `--playbook` and `--playbook-path` flags.
2. Spec 014 (bilateral comparison) — defines the comparison subcommand and its flags.
3. Phase 3 PII stripping deferred tasks (T033-T035) — defines the `--no-pii` flag.
4. Test fixtures directory (`tests/fixtures/`) — must contain sample documents for bilateral comparison tests.

---

## Scope Boundaries

### In scope
- Warning message for playbook flag conflict
- Input validation tests for bilateral comparison
- CLI flag parsing tests for bilateral comparison
- Integration test for `--no-pii` flag across review commands
- Test fixtures needed for bilateral comparison tests

### Explicitly excluded (remain deferred)
- Config-change detection (threshold hash compare)
- Threshold-change re-strip
- Missing-model Presidio error integration test (requires monkeypatching spacy.load)
- Benchmark corpus validation (T049, T050)
- Any implementation changes to production code
- New features beyond test coverage
