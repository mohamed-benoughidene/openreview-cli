# Implementation Plan: 011 — Single-Party Review (PAKTON 3-Agent Pipeline)

**Branch**: `feat/011-single-party-review` | **Date**: 2026-07-02 | **Spec**: specs/011-single-party-review/spec.md

**Input**: Feature specification from `specs/011-single-party-review/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Single-party review brings contract analysis to the CLI: a user uploads a contract and receives a structured, per-clause assessment scored against a 3-position playbook (favorable, neutral, unfavorable). Three pipeline stages — extraction, QA verification, and a no-op comparison placeholder — produce citation-grounded, uncertainty-aware output. Pilot scope: NDA review via `openreview precheck review`. Minimum 70% accuracy bar. Every claim cites its source clause. No default to "sign this" or "reject this" — uncertain assessments surface as Amber.

Technical approach: reuse existing `stream_clauses()` (C-08) for clause input, AI Gateway (C-12–C-18) for per-task model routing, pyyaml for bundled/custom playbook loading. The pipeline is streaming — one clause at a time — staying under the 100 MB memory budget. Extraction and QA agents are independently routable to different model slots (SLM-first per §6.1).

## Technical Context

**Language/Version**: Python 3.12 (pinned in `.python-version` and `pyproject.toml`)

**Primary Dependencies**:
- Typer (CLI framework — existing)
- Pydantic (data models — existing)
- httpx (async HTTP — existing)
- litellm (AI Gateway routing — existing)
- pyyaml (playbook loading — existing, listed in pyproject.toml)
- questionary (interactive prompts — existing)

**Storage**: None for this feature. Review reports are emitted to stdout or a JSON file. No persistent storage of assessments. The SQLite database from the storage layer is not used by this feature (deferred: clause-level caching is explicitly out of scope per spec §9).

**Testing**: pytest (existing), mypy strict. New unit tests for extraction/QA prompt templates, playbook loading, report formatting. Integration tests for the full `precheck review` CLI flow.

**Target Platform**: Linux/macOS/Windows (CLI tool, no platform-specific code)

**Project Type**: CLI tool — local-only, no server, no daemon.

**Performance Goals**:
- Per-clause processing: <5 seconds P95 (all-local SLMs)
- Peak memory: <100 MB (ex-NLP-model, per Principle III)
- 50-page NDA in under 30 seconds (all-local SLMs)
- Batch processing: sequential per-document, streaming per-clause

**Constraints**:
- <100 MB peak memory (hard floor 110 MB). NLP model memory exempt per constitution.
- Offline-capable: all-local model slots must produce identical output format.
- No PII reaches extraction/QA agents (PII stripping is upstream in the parser pipeline).
- No "sign this" / "reject this" language in any output. Uncertain → Amber.
- No web server, no daemon, no telemetry.

**Scale/Scope**: Single-document and batch review. Maximum practical batch: ~50 NDAs/day (no clause-level caching). Each document: 10–50 clauses typical.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Privacy First** | **Pass** | PII stripping is upstream (spec Assumption 8). `--no-pii` flag already exists. No raw contract text in logs. All-local mode fully supported — no network call unless cloud model slot configured. |
| **II. Local-First, CLI-Only** | **Pass** | This is a CLI subcommand (`openreview precheck review`). No web server, no daemon, no long-running process. Offline-capable with local SLMs per §6.1. |
| **III. Hardware-Bounded** | **Pass** | Streaming clause processing: clauses are processed one at a time, freeing extraction/QA results before the next. Async/concurrent across clauses. Only the summary report accumulates (bounded by clause count, typically <50). No in-memory accumulation of all clauses before processing. |
| **IV. Dependency Minimalism** | **Pass** | No new dependencies introduced. pyyaml is already listed in pyproject.toml. AI Gateway, stream_clauses(), and prompt registry are existing infrastructure reused via public APIs. No forbidden deps (langchain, FAISS, spaCy for PII, etc.). |
| **V. Spec-Driven, YAGNI** | **Pass** | Spec written before implementation (this plan). Comparison agent is a structural no-op — not speculative abstraction. Clause-level caching explicitly deferred. No interface with one implementation, no factory for one product. |

**Gate verdict**: ALL PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/011-single-party-review/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output — PAKTON patterns, matching approaches
├── data-model.md        # Phase 1 output — ClauseAssessment, Playbook, ReviewReport
├── quickstart.md        # Phase 1 output — validation scenarios
├── contracts/           # Phase 1 output — CLI contract
│   └── cli-contract.md  # Command schema, flags, output formats
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── __init__.py
├── __main__.py
├── app.py                    # Typer app — new "precheck review" subcommand
├── config/
├── parsing/
│   └── stream.py             # Existing — stream_clauses() as clause input
├── pii/
├── gateway/                  # Existing — AI Gateway, model routing
└── review/                   # NEW — single-party review package
    ├── __init__.py           # Public API: run_review(), ReviewResult
    ├── models.py             # ClauseAssessment, Playbook, ReviewReport dataclasses
    ├── playbook.py           # Playbook loader (YAML parsing, validation)
    ├── playbooks/            # Bundled YAML playbooks
    │   └── precheck-nda-v1.yaml
    ├── extraction.py         # Extraction agent — prompt building, model routing
    ├── qa.py                 # QA agent — verification prompt, disagreement logic
    ├── comparison.py         # Comparison agent — structural no-op (placeholder)
    ├── report.py             # Report formatting (terminal table + JSON output)
    ├── prompts.py            # Extraction and QA prompt templates
    ├── base.py               # ReviewCommand base class — PII orchestration, document hashing, caching
    └── _gateway.py           # Shared _call_gateway_chat helper — wraps Gateway.chat() for testability (monkeypatch target)

tests/
├── unit/
│   ├── test_review_models.py       # Data model unit tests
│   ├── test_playbook.py            # Playbook loading/validation tests
│   ├── test_extraction_agent.py    # Extraction prompt building, confidence parsing
│   ├── test_qa_agent.py            # QA verification prompt, disagreement logic
│   ├── test_comparison_agent.py    # No-op placeholder test
│   └── test_review_report.py       # Report formatting tests (terminal + JSON)
├── integration/
│   └── test_precheck_review.py     # End-to-end CLI flow
└── fixtures/
    └── playbooks/                  # Bundled NDA playbook for tests
        └── precheck-nda-v1.yaml
```

**Structure Decision**: New `src/openreview_cli/review/` package — following the existing package structure (parsing/, pii/, gateway/ are sibling packages). No modification to existing packages; reuse via public APIs only (per spec FR-6).

## Complexity Tracking

> No Constitution Check violations to justify. This section is empty.

## Extension Hooks

### Post-Execution: Check hooks.after_plan

`.specify/extensions.yml` exists with one hook under `hooks.after_plan`:

- **Optional Hook**: agent-context
  Command: `/speckit.agent-context.update`
  Description: Refresh agent context after planning
  Prompt: Execute speckit.agent-context.update?
  To execute: `/speckit.agent-context.update`

This hook is optional (`optional: true`). No mandatory post hooks.

---

## Research Phase Output

See `research.md` for Phase 0 findings (PAKTON architecture patterns, clause-to-playbook matching, SLM-first strategies, citation grounding, memory-efficient pipelines).

## Design Phase Output

See `data-model.md`, `contracts/cli-contract.md`, and `quickstart.md` for Phase 1 design artifacts.
