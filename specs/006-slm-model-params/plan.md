# Implementation Plan: SLM Model Params Extension

**Branch**: `006-slm-model-params` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-slm-model-params/spec.md`

## Summary

Extend the gateway's `ModelParams` handling to support provider-specific pass-through parameters for SLM optimization. The gateway already has a partial implementation (router.py lines 98-100 read `extra_params` from config). This plan formalises that behaviour by adding protected-key stripping, debug/warning logging, health check visibility, and a documentation field on `ModelEntry`. No new dependencies required.

## Technical Context

**Language/Version**: Python 3.12.3 (pinned in `.python-version`)

**Primary Dependencies**: Pydantic 2.13.4 (models), LiteLLM 1.90.1 (routing), stdlib `logging` (debug/warning output)

**Storage**: N/A — no schema changes; `extra_params` lives in config.yml (YAML), not SQLite

**Testing**: pytest (unit tests in `tests/unit/test_gateway_models.py` and `tests/unit/test_gateway_router.py`)

**Target Platform**: Local CLI, Linux/macOS/Windows, 8 GB RAM reference machine

**Project Type**: CLI (Python package `openreview-cli`)

**Performance Goals**: Zero additional latency — `extra_params` merge is dict.update(), O(n) where n is number of extra keys (typically 1-5)

**Constraints**: <100 MB peak memory (unchanged — no new allocations beyond a small dict)

**Scale/Scope**: 3 files modified, 1 file unchanged, ~60 lines of new code, ~80 lines of new tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | PASS | No new network calls. `extra_params` values stay in config.yml (local). Keys logged at DEBUG level, not values. |
| II. Local-First, CLI-Only | PASS | No server, no daemon. Config-only change. |
| III. Hardware-Bounded | PASS | Dict merge adds negligible memory. No new imports. |
| IV. Dependency Minimalism | PASS | Zero new dependencies. Uses existing Pydantic, stdlib logging. |
| V. Spec-Driven, YAGNI | PASS | Specified in spec.md. Addresses blueprint R-4 and C-5. Minimal change — no speculative abstractions. |

## Project Structure

### Documentation (this feature)

```text
specs/006-slm-model-params/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI contract)
│   └── cli-contract.md
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/openreview_cli/gateway/
├── models.py            # MODIFY — add extra_params field to ModelEntry
├── router.py            # MODIFY — add protected-key stripping, logging, health check extra_params
├── models.json          # MODIFY — add extra_params examples for Ollama models
└── (other files)        # UNCHANGED

tests/unit/
├── test_gateway_models.py  # MODIFY — add extra_params tests for ModelEntry
└── test_gateway_router.py  # MODIFY — add protected-key, logging, health check tests
```

**Structure Decision**: Single project, src layout. All changes are within the existing `src/openreview_cli/gateway/` package and `tests/unit/` directory. No new modules, no new directories.

## Complexity Tracking

No violations. No complexity justification needed.
