# Phase 1 — Foundation

**Date:** 2026-06-23
**Commit:** `018c4ba` (reports folder) | `742a8dc` (Phase 1 foundation)
**Audience:** non-technical stakeholder

## What this phase was

We turned a single `Hello world` file into a properly installed,
properly tested, properly checked Python package. The house is still
empty — no product features shipped — but the foundation is in place.

## What changed in plain English

- The project now lives in a real Python package at `src/openreview_cli/`.
  The old `main.py` Hello-world is gone.
- `uv run openreview --version` works. So does `python -m openreview_cli`.
  A `uv tool install .` from a fresh checkout now installs a working
  `openreview` command.
- A test suite exists. It runs four tests and proves the package
  stays under 110 MB of RAM.
- A linter, a type checker, and a code formatter are now configured.
  They run automatically before every commit and on every push to GitHub.
- GitHub Actions (the CI pipeline) now runs four checks in parallel:
  lint, type-check, tests, memory budget. Green CI is required to merge.
- `AGENTS.md` (the developer-only instruction file) was updated to
  reflect the new state.

## What was verified

- ruff (linter) — clean
- ruff format — 9 files formatted correctly
- mypy (type checker, strict) — no issues
- pytest — 4 of 4 tests pass
- memory budget test — passes (peak under 110 MB)
- `openreview --version` — prints `openreview 0.1.0`

## What's next

Phase 2 — the first product mode, end-to-end. Most likely `precheck`
(NDA review). This is the phase that pulls in the big dependencies
(`litellm`, `PyMuPDF`, `presidio-*`, `docling`, `python-docx`,
`sqlite-vss`, `PyYAML`, `ijson`) one at a time, each justified by
the feature that needs it.

## Questions for the stakeholder

- (placeholder — write here when you have a question or a decision
  for me to track)
