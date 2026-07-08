# Implementation Plan: IndemnityCheck, ConsultCheck, WorkCheck, LOICheck, SubCheck, SettlementCheck

**Branch**: `feat/028-product-modes-batch-1` | **Date**: 2026-07-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/028-product-modes-batch-1/spec.md`

## Summary

Add six new product modes to the openreview CLI for solo/small-business contract types. Each mode reuses the existing single-party review pipeline (3-agent PAKTON design, 3-position playbook, three-color confidence output, memo export) with a domain-specific playbook YAML and extraction prompt template. No pipeline changes required. Follows the established pattern from the four wired modes (PreCheck, LicenseCheck, LeaseCheck, PrivacyCheck). As part of scope expansion B, this batch also wires DealCheck and HireCheck (pre-existing spec/code gap — mentioned in data-model.md as existing values but not wired in `app.py`).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: No new runtime dependencies. Reuses existing stack: httpx, pydantic, rich, typer, PyMuPDF, python-docx, presidio-analyzer, presidio-anonymizer, cryptography, litellm, questionary, platformdirs, pyyaml.

**Storage**: SQLite (existing database layer) — no new tables required. Playbooks stored as YAML files in `src/openreview_cli/review/playbooks/`.

**Testing**: pytest (existing suite). Unit tests for playbook schema validation. Integration tests per mode with fixture documents. Accuracy benchmark per mode using existing benchmark harness.

**Target Platform**: Linux, macOS, Windows (CLI)

**Project Type**: CLI tool (single-party contract review modes)

**Performance Goals**: <100 MB peak memory budget (110 MB hard floor, per constitution). No new memory pressure from playbook-only changes. Parse + assess within existing pipeline timing.

**Constraints**: Same constraints as established single-party review pipeline. No per-mode model routing overrides (task-level routing only). No multi-party comparison. SLM-first/task-level model routing.

**Scale/Scope**: Six new CLI subcommands, six playbook YAML files, six extraction prompt templates, six integration test files, six fixture documents, updated unit tests.

## Pre-existing Spec/Code Gap: DealCheck & HireCheck

The data-model.md lists `dealcheck` and `hirecheck` as "existing values" alongside `precheck`, `licensecheck`, `leasecheck`, and `privacycheck`. In the actual codebase, **only four modes are wired** in `app.py` (`precheck`, `licensecheck`, `leasecheck`, `privacycheck`). `DealCheck` and `HireCheck` have playbook YAMLs and `MODE_VOCABULARY` entries but lack CLI subcommand wiring. This batch wires both to close the gap, as part of user-approved scope expansion B.

## Playbook Registration Note

New playbook YAML files must be registered in the `BUNDLED_PLAYBOOKS` dict in `src/openreview_cli/review/playbook.py` in addition to being placed in the `playbooks/` directory. Without this registration, `load_playbook()` will not find them by name.

## CLI Wiring Note

New subcommands use the `_register_product_mode` helper in `src/openreview_cli/app.py`, not the standalone Typer sub-app pattern used by `precheck`. The helper standardises flag parsing (--no-pii, --playbook, --format, --output, --memo-format, --output-dir, --verbose, --confidence-threshold/-ct) and mode routing.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | **Pass** | Per spec FR8, all six modes reuse existing PII stripping engine identically. No new PII-related code. PII is stripped before any external API call across all modes. |
| II. Local-First, CLI-Only | **Pass** | No server, no daemon, no telemetry. Six new subcommands on existing CLI-only architecture. No background processes. |
| III. Hardware-Bounded | **Pass** | Playbook-only changes and prompt template additions add negligible runtime memory overhead. Estimated <1 MB additional per mode. No new parsers, no new in-memory collections. |
| IV. Dependency Minimalism | **Pass** | Zero new runtime dependencies. Reuses existing deps for YAML parsing (pyyaml) and prompt management. Each mode is a YAML file + entry in an existing dict. |
| V. Spec-Driven, YAGNI | **Pass** | Spec 028 defined before implementation. No speculative abstractions — follows established single-mode pattern exactly. No per-mode model overrides, no multi-party review, no custom output templates. Each mode is the minimal change set: playbook + prompt + CLI wiring. |

**Constitution Gate Verdict**: PASS — all five principles satisfied.

## Project Structure

### Documentation (this feature)

```
specs/028-product-modes-batch-1/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 design
├── quickstart.md        # Phase 1 validation scenarios
├── contracts/           # Phase 1 CLI contracts (6 files)
│   ├── INDEMNITYCHECK.md
│   ├── CONSULTCHECK.md
│   ├── WORKCHECK.md
│   ├── LOICHECK.md
│   ├── SUBCHECK.md
│   └── SETTLEMENTCHECK.md
├── tasks.md             # Phase 2 output (speckit.tasks)
└── spec.md              # Feature specification
```

### Source Code (repository root)

No new source directories. Changes to these existing files:

```
src/openreview_cli/
├── review/
│   ├── playbooks/
│   │   ├── precheck-nda-v1.yaml           # existing
│   │   ├── saas-license-v1.yaml           # existing
│   │   ├── commercial-lease-v1.yaml       # existing
│   │   ├── dpa-v1.yaml                    # existing
│   │   ├── indemnification-v1.yaml        # new
│   │   ├── consulting-agreement-v1.yaml   # new
│   │   ├── work-for-hire-v1.yaml          # new
│   │   ├── letter-of-intent-v1.yaml       # new
│   │   ├── subcontractor-agreement-v1.yaml # new
│   │   └── settlement-agreement-v1.yaml   # new
│   └── prompts.py                         # append 6 mode entries to MODE_VOCABULARY
└── app.py                                 # append 6 CLI subcommands

tests/
├── unit/
│   └── test_playbook_schema.py            # add 6 playbook validation tests
├── integration/
│   ├── test_indemnitycheck.py             # new
│   ├── test_consultcheck.py               # new
│   ├── test_workcheck.py                  # new
│   ├── test_loicheck.py                   # new
│   ├── test_subcheck.py                   # new
│   └── test_settlementcheck.py            # new
└── fixtures/
    ├── indemnification-agreement.pdf      # new
    ├── consulting-agreement.pdf           # new
    ├── independent-contractor-agreement.pdf # new
    ├── letter-of-intent.pdf               # new
    ├── subcontractor-agreement.pdf        # new
    └── settlement-agreement.pdf           # new
```

**Structure Decision**: Follows existing single-mode pattern. No new directories, no new abstractions. Each mode = playbook YAML file + prompt template entry + CLI subcommand wiring. This is the minimal change set validated by all six prior modes.

## Implementation Order

Each mode is independent. Implementation proceeds sequentially for testability. Integration tests for each mode run independently.

### Mode 1: IndemnityCheck

**Files to create/modify:**

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/indemnification-v1.yaml` | Create | 4-category playbook (indemnity scope, liability cap, survival period, defense obligations) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"indemnitycheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/app.py` | Modify | Add `indemnitycheck` CLI subcommand |
| `tests/fixtures/indemnification-agreement.pdf` | Create | Test document (minimal, valid, well-formed PDF) |
| `tests/unit/test_playbook_schema.py` | Modify | Add `indemnification-v1` schema validation test |
| `tests/integration/test_indemnitycheck.py` | Create | E2E flow: parse → assess → output.json with correct mode field |

**Playbook categories**: Indemnity scope, Liability cap, Survival period, Defense obligations

**Prompt vocabulary**: indemnify, hold harmless, defense, liability cap, survival, third-party claim, broad form, limited form, mutual, sole

**CLI wiring** (via `_register_product_mode` — generates a `typer.Command` with all standard flags: `--no-pii`, `--playbook`, `--format`, `--output`, `--memo-format`, `--output-dir`, `--verbose`, `--confidence-threshold`/`-ct`):
```python
_register_product_mode(
    app,
    name="indemnitycheck",
    help_text="Review an indemnification agreement with IndemnityCheck.",
    path_help="Path to an indemnification agreement (PDF or DOCX).",
)
```

### Mode 2: ConsultCheck

**Files to create/modify:**

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/consulting-agreement-v1.yaml` | Create | 5-category playbook (SOW, payment, IP, confidentiality, termination) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"consultcheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/app.py` | Modify | Add `consultcheck` CLI subcommand |
| `tests/fixtures/consulting-agreement.pdf` | Create | Test document |
| `tests/unit/test_playbook_schema.py` | Modify | Add consulting-agreement-v1 schema validation test |
| `tests/integration/test_consultcheck.py` | Create | E2E flow |

**Playbook categories**: SOW specificity, Payment terms, IP ownership, Confidentiality, Termination rights

**Prompt vocabulary**: statement of work, deliverable, scope creep, IP assignment, work product, non-solicit, change order

### Mode 3: WorkCheck

**Files to create/modify:**

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/work-for-hire-v1.yaml` | Create | 5-category playbook (classification, IP, payment, non-compete, termination) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"workcheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/app.py` | Modify | Add `workcheck` CLI subcommand |
| `tests/fixtures/independent-contractor-agreement.pdf` | Create | Test document |
| `tests/unit/test_playbook_schema.py` | Modify | Add work-for-hire-v1 schema validation test |
| `tests/integration/test_workcheck.py` | Create | E2E flow |

**Playbook categories**: Worker classification, IP ownership, Payment terms, Non-compete restrictions, Termination

**Prompt vocabulary**: work for hire, independent contractor, classification, commissioned work, assignment, non-compete, IRS factors

### Mode 4: LOICheck

**Files to create/modify:**

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/letter-of-intent-v1.yaml` | Create | 5-category playbook (binding provisions, exclusivity, breakup fees, due diligence, expiration) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"loicheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/app.py` | Modify | Add `loicheck` CLI subcommand |
| `tests/fixtures/letter-of-intent.pdf` | Create | Test document |
| `tests/unit/test_playbook_schema.py` | Modify | Add letter-of-intent-v1 schema validation test |
| `tests/integration/test_loicheck.py` | Create | E2E flow |

**Playbook categories**: Binding provisions, Exclusivity/no-shop, Breakup fees, Due diligence access, Expiration

**Prompt vocabulary**: non-binding, exclusivity, no-shop, breakup fee, due diligence, confidentiality, binding provisions

### Mode 5: SubCheck

**Files to create/modify:**

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/subcontractor-agreement-v1.yaml` | Create | 5-category playbook (flow-through, payment, indemnity, change-order, termination) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"subcheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/app.py` | Modify | Add `subcheck` CLI subcommand |
| `tests/fixtures/subcontractor-agreement.pdf` | Create | Test document |
| `tests/unit/test_playbook_schema.py` | Modify | Add subcontractor-agreement-v1 schema validation test |
| `tests/integration/test_subcheck.py` | Create | E2E flow |

**Playbook categories**: Flow-through clauses, Payment terms (pay-if-paid vs. pay-when-paid), Broad-form indemnity, Change-order process, Termination rights

**Prompt vocabulary**: flow-through, pay-if-paid, pay-when-paid, broad form indemnity, no-damages-for-delay, change order, prime contract

### Mode 6: SettlementCheck

**Files to create/modify:**

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/settlement-agreement-v1.yaml` | Create | 5-category playbook (release scope, payment, confidentiality, unknown claims, breach) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"settlementcheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/app.py` | Modify | Add `settlementcheck` CLI subcommand |
| `tests/fixtures/settlement-agreement.pdf` | Create | Test document |
| `tests/unit/test_playbook_schema.py` | Modify | Add settlement-agreement-v1 schema validation test |
| `tests/integration/test_settlementcheck.py` | Create | E2E flow |

**Playbook categories**: Release scope (general vs. specific), Payment terms and timing, Confidentiality/non-disparagement, Waiver of unknown claims, Breach consequences

**Prompt vocabulary**: general release, specific release, non-disparagement, non-admission, waiver, unknown claims, confidentiality, Civil Code 1542

## Dependencies

| What | Spec Ref | Status |
|------|----------|--------|
| Single-party review pipeline | Established pattern | Complete, production-ready |
| Three-color confidence | Established pattern | Complete |
| Memo export | Established pattern | Complete |
| Prompt management / registry | Established pattern | Complete |
| Playbook versioning / management | Established pattern | Complete |
| Playbook schema (3-position, 3-5 questions) | Established pattern | Complete |

## Architecture Implications

| Implication | Source | Impact |
|------------|--------|--------|
| Comparison accuracy ceiling is low; Amber thresholds generous, confidence scores mandatory | Established pattern | All six modes use same thresholds as existing modes. No mode-specific threshold tuning. |
| Multi-party comparison is experimental; default all modes to single-party | Established pattern | All six modes default to single-party review. No multi-party scope in this spec. |
| Task-level model routing; no per-mode model overrides | Established pattern | All six modes use same model slot config as existing modes. |
| Versioned prompts; each mode gets its own prompt template under prompt registry | Established pattern | Each mode registered as a named template in MODE_VOCABULARY. |
| Citation grounding required on every claim | Established pattern | All six modes reuse existing citation grounding. No changes. |
| Playbook-only changes; no pipeline modifications needed | FR4 | Each mode adds <1 KB to MODE_VOCABULARY dict, one YAML file, one CLI function. |

## Risks

1. **Accuracy ceiling (~60-64% F1)** — Mitigation: document in help text and memo output that Amber assessments are expected. Default uncertain matches to Amber as established.
2. **Domain vocabulary gap** — LLM may misinterpret domain-specific terms (e.g., "broad form" vs. "limited form", "pay-if-paid" vs. "pay-when-paid"). Mitigation: prompt templates inject domain vocabulary and few-shot examples. Default uncertain matches to Amber.
3. **Settlement agreement complexity** — Wide variation in settlement agreement structures. Mitigation: target most common small-business settlement scenarios first. Complex settlements out of scope for v1.
4. **LOI binding provision ambiguity** — Whether a provision is binding depends on jurisdiction-specific case law. Mitigation: the playbook flags commonly binding provisions and notes jurisdiction dependence in the assessment.
5. **22-mode sustainability** — Each mode adds maintenance surface. Mitigation: simpler playbook format (3-5 categories) for small-business modes reduces maintenance burden compared to enterprise modes (7-9 categories).

## Test Plan

### Unit Tests

| Test | File | What it validates |
|------|------|-------------------|
| Playbook schema validation (×6) | `test_playbook_schema.py` | Each playbook YAML passes `load_playbook()` without error |
| Prompt vocabulary keys (×6) | Existing prompt tests | Each mode key exists in `MODE_VOCABULARY` with non-empty domain/vocabulary |

### Integration Tests

| Test | File | What it validates |
|------|------|-------------------|
| IndemnityCheck E2E | `test_indemnitycheck.py` | Parse → assess → JSON output with `"mode": "indemnitycheck"` |
| ConsultCheck E2E | `test_consultcheck.py` | Parse → assess → JSON output with `"mode": "consultcheck"` |
| WorkCheck E2E | `test_workcheck.py` | Parse → assess → JSON output with `"mode": "workcheck"` |
| LOICheck E2E | `test_loicheck.py` | Parse → assess → JSON output with `"mode": "loicheck"` |
| SubCheck E2E | `test_subcheck.py` | Parse → assess → JSON output with `"mode": "subcheck"` |
| SettlementCheck E2E | `test_settlementcheck.py` | Parse → assess → JSON output with `"mode": "settlementcheck"` |

### Fixture Documents

Six fixture PDFs, each:
- Well-formed, valid PDF (no scanned images)
- 1-3 pages covering the mode's contract type
- Contains at least one clause matching each playbook category
- English language
- Small-business-relevant factual scenario

### Verification Checklist

- [ ] `uv run openreview --help` lists all 6 new subcommands
- [ ] Each subcommand `--help` shows mode-specific help text
- [ ] Each mode produces valid JSON via `--format json`
- [ ] JSON `mode` field matches invoked subcommand
- [ ] Each playbook passes schema validation (`load_playbook()`)
- [ ] Memo export produces file > 1 KB with mode name prefix
- [ ] PII stripping produces identical placeholders across modes (given identical PII content)
- [ ] Playbook override produces different assessments
- [ ] `--no-pii` flag preserves raw text
- [ ] All tests pass in CI environment
