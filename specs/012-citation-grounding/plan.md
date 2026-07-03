# Implementation Plan: Citation Grounding Discriminator (N-5)

**Branch**: `feat/citation-grounding` | **Date**: 2026-07-03 | **Spec**: `specs/012-citation-grounding/spec.md`

**Input**: Feature specification from `specs/012-citation-grounding/spec.md`

## Summary

Implement a post-hoc citation grounding discriminator for the single-party review pipeline. The discriminator validates that each assessment claim in a `ReviewReport` is actually supported by the source document clause it cites. It supports strict mode (ungrounded claims excluded) and lenient mode (ungrounded claims flagged). Uses the existing AI Gateway (litellm) for LLM-based grounding, adding zero new runtime dependencies. Structural CG metrics (CP/CR/CL) are computed deterministically without LLM calls. Integrates with the existing QA `citation_valid` flag and `HallucinationDetector` interface.

## Technical Context

**Language/Version**: Python 3.12 (pinned in `.python-version` and `pyproject.toml`)

**Primary Dependencies**: No new runtime deps. Uses existing: litellm (via AI Gateway), pydantic (models), stdlib logging, hashlib, json, pathlib, dataclasses.

**Storage**: Existing SQLite (no new tables — grounding data lives on `ClauseAssessment` fields and local file audit log).

**Testing**: pytest (unit + integration), ruff (lint), mypy --strict (types).

**Target Platform**: Linux/macOS CLI — local, no server.

**Project Type**: CLI application (Typer).

**Performance Goals**: 100 claims processed in <60s on reference machine (8 GB RAM, 2-core CPU, no GPU). Zero new deps loaded locally.

**Constraints**: <100 MB peak memory (ex-model). PII already stripped upstream. Privacy-first: no raw claim text in audit log (SHA-256 hashed).

**Scale/Scope**: Single-party review pipeline (spec 011). Post-hoc module, not a generation constraint.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | **Pass** | Claims may contain PII placeholders only — PII already stripped upstream. Audit log stores claim hashes, not raw text. |
| II. Local-First, CLI-Only | **Pass** | Post-hoc local module, no server, no daemon. Runs within a single CLI invocation. Gateway calls are direct user-to-provider, no first-party service. |
| III. Hardware-Bounded | **Pass** | LLM-based via Gateway — no local model loaded. Discriminator processing is pure Python + gateway calls. Memory overhead: prompt construction + response parsing only. Far under 100 MB. |
| IV. Dependency Minimalism | **Pass** | Zero new runtime dependencies. Uses existing litellm via Gateway, stdlib for hashing/JSON/paths. |
| V. Spec-Driven, YAGNI | **Pass** | Minimal viable discriminator: no speculative abstractions, no factory, no interface with one implementation (CGDPODetector is one of two, interfaces pre-existing). |

## Project Structure

### Documentation (this feature)

```text
specs/012-citation-grounding/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output — research findings
├── data-model.md        # Phase 1 output — data models
├── quickstart.md        # Phase 1 output — validation scenarios
├── contracts/           # Phase 1 output — CLI contracts
│   └── grounding-cli.md
└── tasks.md             # Phase 2 output (/speckit.tasks) — NOT created here
```

### Source Code (repository root)

```text
src/openreview_cli/
├── grounding/                      # NEW module
│   ├── __init__.py                 # Public API: run_grounding(), CGReport
│   ├── models.py                   # CitationProvenance, GroundingVerdict, CGReport, GroundingResult, CGMetrics, DiscriminationAuditEntry
│   ├── discriminator.py            # CitationGroundingDiscriminator — ground_claim(), ground_report()
│   ├── metrics.py                  # compute_cg_metrics() — deterministic CP/CR/CL
│   ├── audit.py                    # GroundingAuditLog — local file audit trail
│   └── prompts.py                  # Grounding prompt templates for gateway
├── review/
│   ├── models.py                   # MODIFY: add 3 optional fields to ClauseAssessment
│   ├── report.py                   # MODIFY: extend terminal table + JSON to show grounding info
│   └── __init__.py                 # MODIFY: wire grounding step into run_review() after QA
├── benchmark/
│   └── hallu_detect.py             # MODIFY: add CGDPODetector class implementing HallucinationDetector

tests/
├── unit/
│   ├── test_grounding_discriminator.py   # NEW — discriminator unit tests
│   ├── test_grounding_metrics.py         # NEW — CG metrics unit tests
│   ├── test_grounding_audit.py           # NEW — audit log unit tests
│   └── test_grounding_models.py          # NEW — data model unit tests
├── integration/
│   └── test_grounding_pipeline.py        # NEW — end-to-end grounding pipeline
└── fixtures/
    └── grounding/                       # NEW — seeded corpus for accuracy validation
        ├── claims.json                  # 1,000+ seeded claims with ground truth labels
        └── seed_doc.pdf                 # Source document for seeded corpus
```

**Structure Decision**: Single project (default). New `grounding/` module at same level as `review/` and `gateway/`. Modifications to existing files in `review/` and `benchmark/` for integration.

## Integration Points

```
run_review() pipeline (updated):
  parse → strip PII → match_category → extract → QA → GROUND → report
                                                    ↑
                                          CitationGroundingDiscriminator
                                          (skips claims where citation_valid=false)
```

- **Input**: `ReviewReport` (from spec 011) + `Document` (parsed source)
- **Skip logic**: Claims where QA already set `citation_valid=false` skip discriminator
- **Output**: `CGReport` merged back into `ReviewReport` via `merge_into()`
- **Reporting**: Terminal table gets grounding column; JSON output gets grounding fields

## Complexity Tracking

No constitution violations — all five principles pass. No complexity justification required.

## Key Design Decisions

1. **LLM-based via Gateway** — Reuses existing AI Gateway chat routing and cost tracking. Zero new deps. Multiple claims batched per prompt (5-10) to amortize latency.
2. **Augments QA `citation_valid`** — Discriminator runs after QA. Claims already flagged invalid by QA are skipped (no redundant LLM calls).
3. **New fields on ClauseAssessment** — Three optional fields (default None): `grounding_verdict`, `grounding_provenances`, `grounding_confidence`. Backwards-compatible.
4. **Structural CG metrics** — CP/CR/CL computed deterministically via string/index operations. No LLM calls needed for metrics.
5. **Mode-dependent multi-provenance** — Strict: multi-clause claims flagged uncertain (default ungrounded). Lenient: all matching provenances assigned with warning.
6. **HallucinationDetector interface** — `CGDPODetector` class in `benchmark/hallu_detect.py` implements the existing swappable interface. Benchmarks can use `--hallucination-method=cg-dpo`.
