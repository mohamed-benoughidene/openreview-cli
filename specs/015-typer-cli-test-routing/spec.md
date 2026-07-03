# Spec 015 — Typer CLI Test Routing Fix

**Status**: Implemented
**Date**: 2026-07-03
**Prerequisite**: Spec 014 (bilateral comparison CLI integration)

---

## Problem

The `precheck compare` subcommand was unreachable — both from Typer's `CliRunner`
in tests and from the production command line.

### Root Cause

`precheck_app.callback(invoke_without_command=True)` (line 366 of `app.py`) has
an optional positional argument `document_path`. When Click resolves the command
line, the positional argument consumes the first non-option token — including
subcommand names like `compare` or `review`. This is the behavior in Click 8.x
when `invoke_without_command=True` and the callback has positional parameters:
parameter parsing happens before subcommand resolution.

### Impact

Five integration tests were deferred in spec 014 (T050–T053, T055) with the
incorrect assumption that "production CLI works fine" and the issue was only
in `CliRunner`. In reality, `openreview precheck compare a.pdf b.pdf` never
worked from the shell either.

| Task | Flag | Status before 015 |
|------|------|-------------------|
| T050 | `--align-only` | Deferred (blocked) |
| T051 | `--format json --output` | Deferred (blocked) |
| T052 | `--confidence-threshold` | Deferred (blocked) |
| T053 | `--conservative` | Deferred (blocked) |
| T055 | `--verbose` | Deferred (blocked) |

## Fix

### 1. Production code: `app.py` callback signature

Change `document_path` from a positional `Argument` to a named `--document`
Option. This breaks Click's positional-arg-first resolution chain, allowing
subcommand names to be correctly identified.

```python
# Before (broken):
document_path: str = typer.Argument(None, ...)

# After (fixes routing):
document_path: str | None = typer.Option(None, "--document", "-d", ...)
```

Users now invoke: `openreview precheck --document file.pdf` instead of
`openreview precheck file.pdf`.

### 2. Latent bug: `_validate_threshold` crashes on `None`

The `compare` command's `--confidence-threshold` option defaults to `None`
and passes it through `_validate_threshold`, which did not guard against
`None`. This was masked because `compare` was previously unreachable.

Fix: accept `None` in the validator.

### 3. Test infrastructure

Subprocess-based tests in `test_bilateral_flags.py` matching the existing
`test_parse_command.py` pattern.

## Success Criteria

- [x] T050: `--align-only` produces experimental banner and doc info, exits 0
- [x] T051: `--format json --output <file>` writes valid JSON to disk, exits 0
- [x] T052: `--confidence-threshold 0.8` accepted; out-of-range rejected
- [x] T053: `--conservative` accepted; mutually exclusive with `--confidence-threshold`
- [x] T055: `--verbose` accepted and routed
- [x] All 7 new tests pass: `uv run pytest tests/integration/test_bilateral_flags.py -v`
- [x] Zero regression on 14 existing integration tests and 715 unit tests
- [x] T050–T053, T055 unblocked in spec 014 tasks

## Out of Scope

- Full pipeline accuracy validation (specs 014/010)
- Gateway mocking or network-dependent tests
- `review` subcommand routing (same pattern, confirmed fixed by the same change)
