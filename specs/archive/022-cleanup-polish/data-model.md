# Data Model — Spec 022 Cleanup & Polish

**Date**: 2026-07-06 | **Spec**: `specs/022-cleanup-polish/spec.md`

## Overview

This spec adds no new data structures, entities, or state transitions. All models are test-oriented: input configurations, expected output patterns, and mock return values. No changes to production data models.

---

## Test Input Models

### PlaybookArgumentConflict
Represents the condition where both `--playbook` and `--playbook-path` are supplied to a review command.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `playbook` | `str \| None` | Playbook name from `--playbook` flag | Must be non-None for conflict to exist |
| `playbook_path` | `Path \| None` | Playbook file path from `--playbook-path` flag | Must be non-None for conflict to exist |
| `expected_winner` | `str` | Which argument takes precedence (`"playbook_path"`) | Hard-coded: path wins over name |
| `expected_message_pattern` | `str` | Regex pattern the warning message must match | Contains both flag names and "ignored" |

### BilateralComparisonInput
Represents a bilateral comparison invocation with its arguments.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `doc1_path` | `Path` | First document path | Must exist, readable, supported format |
| `doc2_path` | `Path` | Second document path | Must exist, readable, supported format |
| `expected_exit_code` | `int` | Expected CLI exit code | 0 = success, non-zero = error |
| `expected_error_pattern` | `str \| None` | Regex for expected error in stderr | Present only for error cases |

### ComparisonErrorCase
Enumeration of error conditions for bilateral comparison input validation.

| Value | Description | Expected Exit Code | Expected Message Contains |
|-------|-------------|-------------------|-------------------------|
| `MISSING_FILE` | One or both paths don't exist | 1 | "not found" + path |
| `UNSUPPORTED_FORMAT` | File has unsupported extension | 1 | Format name (e.g. ".txt") |
| `UNREADABLE_FILE` | File exists but is not readable | 1 | "permission" or "unreadable" |
| `SAME_FILE` | Both paths point to same file | 1 | "same" or "identical" |

### NoPiiFlagState
Represents the state of the `--no-pii` flag and expected behavior.

| Field | Type | Description |
|-------|------|-------------|
| `flag_present` | `bool` | Whether `--no-pii` is passed on CLI |
| `pii_engine_called` | `bool` | Whether PiiEngine should be invoked |
| `gateway_receives_raw` | `bool` | Whether gateway receives raw (unstripped) text |
| `assessment_format` | `str` | "pii_stripped" or "raw" — affects test assertions |

---

## Mock Return Models

### MockGatewayResponse
Minimal mock return for the AI gateway in integration tests.

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | Simulated gateway response text |
| `model` | `str` | Simulated model name |
| `cached` | `bool` | Whether response was cached |

### MockPiiEngineResult
Minimal mock return for the PII engine when `--no-pii` is NOT set.

| Field | Type | Description |
|-------|------|-------------|
| `stripped_text` | `str` | Text with PII placeholders |
| `entities_found` | `int` | Count of entities detected |

---

## State Transitions

No state transitions apply. Each test scenario is a single CLI invocation with assertions on:
- Exit code (success vs error)
- stderr content (warning message, error message)
- Whether PII engine was called (mock call count)
- Whether gateway was called with stripped or raw text
- Help output contains expected flags

---

## Validation Rules (from spec requirements)

| Rule | Source | Test Verifies |
|------|--------|---------------|
| Playbook conflict warning on stderr | R1-AC1 | `capsys.readouterr().err` contains warning |
| Warning contains both flag names | R1-AC2 | `--playbook` and `--playbook-path` in warning text |
| Command continues after warning | R1-AC3 | Exit code 0, no crash |
| Missing file error contains "not found" + path | R2-AC1 | stderr contains path + "not found" |
| Unsupported format error names format | R2-AC2 | stderr contains format extension |
| Valid input produces comparison output | R2-AC3 | Exit code 0, stdout has output |
| Non-zero exit on validation failure | R2-AC4 | Exit code != 0 |
| Help output documents all flags | R3-AC1 | `--help` output contains all flags |
| `--no-pii` accepted on all review subcommands | R4-AC1 | Each subcommand accepts flag without error |
| PII engine not called when flag is set | R4-AC2 | Mock call count is 0 |
| PII engine called when flag is absent | R4-AC3 | Mock call count > 0 |
| Integration test passes with `--no-pii` | R5-AC1 | Test exits 0 |
| Integration test passes without `--no-pii` | R5-AC2 | Test exits 0, PII stripped |

---

## Relationship Diagram

```
CLI Invocation
  ├── [--playbook + --playbook-path] → PlaybookArgumentConflict → PrecedenceWarning (stderr)
  ├── [compare <doc1> <doc2>]         → BilateralComparisonInput
  │     ├── validation                → ComparisonErrorCase → ErrorMessage (stderr, exit != 0)
  │     └── success                   → ComparisonOutput (stdout, exit 0)
  └── [precheck --no-pii]             → NoPiiFlagState
        ├── flag set                  → PiiEngine skipped → Gateway called with raw text
        └── flag absent               → PiiEngine called → Gateway called with stripped text
```
