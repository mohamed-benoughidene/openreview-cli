# Implementation Plan: LicenseCheck, LeaseCheck, PrivacyCheck

**Branch**: `feat/027-product-modes-license-lease-privacy` | **Date**: 2026-07-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/027-product-modes-license-lease-privacy/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add three new product modes (LicenseCheck, LeaseCheck, PrivacyCheck) to the openreview CLI. Each mode reuses the existing single-party review pipeline (3-agent PAKTON design, 3-position playbook, three-color confidence output, memo export) with a domain-specific playbook YAML and extraction prompt template. No pipeline changes required. Follows the established pattern from PreCheck, DealCheck, HireCheck [S-011] [S-021].

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: No new runtime dependencies. Reuses existing stack: httpx, pydantic, rich, typer, PyMuPDF, python-docx, presidio-analyzer, presidio-anonymizer, cryptography, litellm, questionary, platformdirs, pyyaml.

**Storage**: SQLite (existing database layer) — no new tables required. Playbooks stored as YAML files in `src/openreview_cli/review/playbooks/`.

**Testing**: pytest (existing suite). Unit tests for playbook schema validation. Integration tests per mode with fixture documents. Accuracy benchmark per mode using existing benchmark harness [S-010].

**Target Platform**: Linux, macOS, Windows (CLI)

**Project Type**: CLI tool (single-party contract review modes)

**Performance Goals**: `<110 MB peak memory` (existing budget, no new memory pressure from playbook-only changes). Parse + assess within existing pipeline timing.

**Constraints**: Same constraints as spec 011 single-party review pipeline. No per-mode model routing overrides [S-011]. No multi-party comparison [S-014]. SLM-first/task-level model routing [S-006].

**Scale/Scope**: Three new CLI subcommands, three playbook YAML files, three extraction prompt templates. No new source files beyond playbooks and prompt templates.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | **Pass** | No new PII-related code. All three modes reuse existing PII stripping engine [S-003] [S-004]. |
| II. Local-First, CLI-Only | **Pass** | No server, no daemon, no telemetry. Existing CLI-only architecture unchanged. |
| III. Hardware-Bounded | **Pass** | No new memory pressure. Playbook-only changes add negligible runtime overhead. |
| IV. Dependency Minimalism | **Pass** | Zero new dependencies. Reuses existing deps for YAML parsing (pyyaml) and prompt management. |
| V. Spec-Driven, YAGNI | **Pass** | Spec 027 defined before implementation. No speculative abstractions — follows established single-mode pattern exactly. No per-mode model overrides or multi-party review. |

## Project Structure

### Documentation (this feature)

```text
specs/027-product-modes-license-lease-privacy/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
├── tasks.md             # Phase 2 output (/speckit.tasks command)
└── spec.md              # Feature specification
```

### Source Code (repository root)

```text
# Existing structure — no new directories required.
# New files are playbook YAMLs and prompt template registrations:
src/openreview_cli/
├── review/
│   ├── playbooks/
│   │   ├── precheck-nda-v1.yaml       # existing
│   │   ├── saas-license-v1.yaml       # new (LicenseCheck)
│   │   ├── commercial-lease-v1.yaml   # new (LeaseCheck)
│   │   └── dpa-v1.yaml                # new (PrivacyCheck)
│   └── prompts.py                     # append extraction prompts for each mode
└── app.py                             # append three CLI subcommands

tests/
├── unit/
│   └── test_playbook_schema.py        # create with new playbook validation tests
├── integration/
│   └── test_{license,lease,privacy}check.py  # new E2E tests
└── fixtures/
    ├── saas-license-agreement.pdf     # new
    ├── commercial-lease.pdf           # new
    └── dpa.pdf                        # new
```

**Structure Decision**: Follows existing single-mode pattern exactly. No new directories, no new abstractions. Each mode is a playbook YAML file + prompt template entry + CLI subcommand wiring. This is the minimal change set validated by PreCheck/DealCheck/HireCheck [S-011].

## Dependencies

| What | Spec Ref | Status |
|------|----------|--------|
| Single-party review pipeline | [S-011] | Complete, production-ready |
| Three-color confidence | [S-013] | Complete |
| Memo export | [S-021] | Complete |
| Prompt management / registry | [S-009] | Complete |
| Playbook versioning / management | [S-017] [S-024] | Complete |
| Playbook schema (3-position, 3-question) | [S-011] | Established pattern |

## Architecture Implications

| Implication | Source | Impact |
|------------|--------|--------|
| Comparison accuracy ceiling is low; Amber thresholds generous, confidence scores mandatory | [S-013] | All three modes use same thresholds as PreCheck. No mode-specific threshold tuning. |
| Multi-party comparison is experimental; default all modes to single-party | [S-014] | All three modes default to single-party review. No multi-party scope in this spec. |
| SLM-first/task-level model routing; no per-mode model overrides | [S-011] [S-006] | All three modes use same model slot config as existing modes. |
| Versioned prompts; each mode gets its own prompt template under prompt registry | [S-009] | Each mode registered as a named template in the prompt registry. |
| Citation grounding required on every claim | [S-012] | All three modes reuse existing citation grounding. No changes. |

## Risks

1. **Accuracy ceiling (~60-64% F1)** — Mitigation: document in help text and memo output that Amber assessments are expected. [S-013]
2. **Domain vocabulary gap** — LLM may misinterpret domain terms (e.g., "CAM charges", "data controller"). Mitigation: prompt templates inject domain vocabulary and few-shot examples.
3. **Playbook question coverage** — Three questions may miss high-risk clauses in some domains. Mitigation: documented as v1 starting point; playbook versioning [S-024] enables updates without code changes.
