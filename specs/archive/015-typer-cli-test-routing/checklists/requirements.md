# Requirements Checklist — Spec 015

## Functional Requirements

- [x] FR-1: Subcommand routing fixed for `precheck compare` (and `review`)
- [x] FR-2: All 5 deferred tests (T050–T053, T055) are unblocked and passing
- [x] FR-3: Existing precheck callback retained (uses `--document`/`-d` flag instead of positional arg)
- [x] FR-4: Tests reuse existing fixture PDFs (no new fixtures needed)
- [x] FR-5: Flag-only tests paired with `--align-only` to avoid AI gateway dependency
- [x] FR-6: `_validate_threshold` accepts `None` without crashing

## Quality Requirements

- [x] QR-1: Each test has a clear docstring linking to its spec 014 task
- [x] QR-2: Tests timeout at 30s (matching `test_parse_command.py` pattern)
- [x] QR-3: Test file follows existing naming convention (`tests/integration/test_bilateral_*.py`)
- [x] QR-4: Spec 014 tasks.md updated to reflect unblocked status
- [x] QR-5: Zero regression — 14 existing integration tests + 715 unit tests all passing
- [x] QR-6: CLI backward compat — `openreview precheck --document file.pdf` works (new syntax)
