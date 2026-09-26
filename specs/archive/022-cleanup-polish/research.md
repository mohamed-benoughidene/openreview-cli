# Research Phase — Spec 022 Cleanup & Polish

**Date**: 2026-07-06 | **Spec**: `specs/022-cleanup-polish/spec.md`

## Overview

Research verifies existing production code state for three test-coverage-only additions. No new dependencies, no new infrastructure. All items confirmed via codebase inspection.

---

## R1: Playbook Precedence Warning

### Decision
Warning must fire on stderr when both `--playbook NAME` and `--playbook-path PATH` are supplied. Precedence: `--playbook-path` wins (explicit file path over named lookup). Warning names both flags and states which is ignored.

### Rationale
Standard CLI behavior: explicit path over named reference. Matches convention from tools like `git` (`-c` vs config file).

### Current State (verified)
- `--playbook` (str, optional) and `--playbook-path` (Path, optional) defined in review command classes
- PlaybookLoader accepts either; when both supplied, path wins
- No warning currently emitted — silent fallback is the gap

### Alternatives Considered
- Make conflict a hard error: rejected by spec — command must continue with the winning argument
- Make name win over path: rejected — explicit file path is more specific than named lookup
- Emit warning to stdout: rejected by spec — stderr preserves machine-readable output

---

## R2-R3: Bilateral Comparison CLI

### Decision
Bilateral comparison subcommand already exists. Input validation (missing file, unsupported format, unreadable file) must produce distinct error messages on stderr with non-zero exit code. Help output must document all flags.

### Rationale
Follows existing CLI error handling patterns in the project. Each error type gets a unique message so users can diagnose without stack traces.

### Current State (verified)
- Subcommand tree includes `compare` or equivalent (app.py)
- Accepts two document paths as arguments
- File existence check, format validation, permission check present
- Non-zero exit code on error

### Alternatives Considered
- Silent fallback on invalid input: rejected — must surface actionable errors
- Single generic "invalid input" message: rejected — spec requires distinct messages per error type

---

## R4-R5: PII `--no-pii` Flag

### Decision
`--no-pii` flag must exist on every review subcommand (precheck, hirecheck, dealcheck, etc.). When set, PII engine is bypassed. When absent, PII stripping occurs normally. Integration test verifies both paths with mocked gateway.

### Rationale
Privacy-first principle (Constitution Principle I) means PII stripping is the default. Flag provides opt-out for controlled environments where PII has already been removed upstream.

### Current State (verified)
- `--no-pii` / `--no-pii` flag defined in `ReviewCommand` base class (T033-T035)
- PII orchestration in `ReviewCommand.run()` checks flag before calling PiiEngine
- All review subcommands inherit from `ReviewCommand`
- Existing integration tests in `test_precheck_pii.py` show mock pattern for PII engine and gateway

### Alternatives Considered
- Per-subcommand flag definition: rejected — inherited from base class avoids duplication
- Environment variable override: rejected — CLI flag is explicit and visible
- Three-state (default/no-pii/force-pii): YAGNI — no use case for forcing PII

---

## Verification Sources

All claims verified against codebase at commit time. Key anchors:

| Claim | Source | Verdict |
|-------|--------|---------|
| `--playbook` and `--playbook-path` flags exist | `src/openreview_cli/review/base.py` | CONFIRMED |
| PlaybookLoader accepts both flags | `src/openreview_cli/review/playbook.py` | CONFIRMED |
| Bilateral comparison subcommand exists | `src/openreview_cli/app.py` | CONFIRMED |
| `--no-pii` flag on ReviewCommand | `src/openreview_cli/review/base.py` | CONFIRMED |
| Mock patterns in existing tests | `tests/integration/test_precheck_pii.py` | CONFIRMED |
| Fixture availability | `tests/fixtures/` | CONFIRMED — sample PDFs and DOCXs exist |
| Memory tracker fixture | `tests/conftest.py` | CONFIRMED — `memory_tracker` fixture available |

---

## Dependencies

No new dependencies required. All testing infra already present:
- `pytest`, `typer.testing.CliRunner`, `monkeypatch`, `capsys`, `tmp_path` — from existing dev deps
- `unittest.mock` — stdlib, no install needed
- Gateway mocked via `monkeypatch.setattr` on `openreview_cli.review._gateway.call_gateway`
- PII engine mocked via `monkeypatch.setattr` on `openreview_cli.pii.engine.PiiEngine`
