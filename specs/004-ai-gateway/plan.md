# Implementation Plan: AI Gateway

**Branch**: `feat/004-ai-gateway` | **Date**: 2026-06-25 | **Spec**: [spec.md](../specs/004-ai-gateway/spec.md)

**Input**: Feature specification from `/specs/004-ai-gateway/spec.md`

## Summary

The AI Gateway is a model routing layer that connects the review engine to AI providers (cloud and local). It provides 5 task-specific slots (reasoning, extraction, embedding, reranking—optional, disabled by default—graph), fallback chains, cost tracking, interactive setup wizard, BYOK key management, and YAML config import. The gateway uses LiteLLM as the provider abstraction layer, Pydantic v2 for configuration validation, and follows the existing codebase patterns (lazy imports, dataclass models, dict-based config, atomic file writes).

## Technical Context

**Language/Version**: Python 3.12.3 (pinned in `.python-version` and `pyproject.toml`)

**Primary Dependencies**:
- `litellm` (provider abstraction — chat, embedding, reranking)
- `pydantic` + `pydantic-settings` (config validation, already permitted in constitution)
- `httpx` (HTTP client for provider API calls, already in deps)
- `rich` (interactive wizard UI, already in deps)
- `typer` (CLI framework, already in deps)
- `pyyaml` (YAML config loading, already in deps)

**Storage**:
- SQLite for cost records and session state (existing `storage/` module)
- YAML config files (`~/.config/openreview/config.yml`)
- JSON auth file (`~/.config/openreview/auth.json`, chmod 600)
- JSON model registry cache (`~/.cache/openreview/model_registry.json`)

**Testing**: pytest with markers (`unit`, `integration`, `slow`, `memory`)

**Target Platform**: Linux (8 GB RAM, 2-core CPU, no GPU reference machine)

**Project Type**: CLI tool (local-first, no server)

**Performance Goals**:
- Gateway routing overhead <50ms per request (SC-007)
- Fallback activation within 30 seconds including retries (SC-003)
- Interactive setup completion <5 minutes (SC-001)
- Non-interactive setup <30 seconds (SC-009)
- YAML import <10 seconds (SC-011)

**Constraints**:
- Peak memory <100 MB (NLP model exempt, constitution Principle III)
- Cold startup <1s, warm startup <0.3s (constitution)
- API keys never logged or sent to tool-operated servers (Principle I)
- Fully local configuration must work end-to-end (Principle I)
- No provider-specific imports in engine code (FR-017)

**Scale/Scope**: 
- 5 slots (reasoning, extraction, embedding, graph — required; reranking — optional, disabled by default)
- 8+ providers (OpenAI, Anthropic, Google, Ollama, OpenRouter, Cohere, HuggingFace, Custom)
- 300+ cloud models via registry
- ~10 local models for Ollama
- Per-call cost tracking aggregated per review session (UUID)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Privacy First** | PASS | API keys stored in `auth.json` with chmod 600 (FR-005). Env var overrides supported (FR-021). Keys never sent to tool-operated servers (FR-006). PII stripping (Phase 3) runs before gateway. Fully local config supported (FR-014). |
| **II. Local-First, CLI-Only** | PASS | No web server, no daemon, no telemetry. CLI-only interface. Direct calls from user machine to provider. Offline operation supported when all slots are local (FR-014). |
| **III. Hardware-Bounded** | PASS | LiteLLM is lightweight (no GPU required). Config loading is lazy. Cost tracking uses SQLite (not in-memory dicts). Hot-path types use `@dataclass(slots=True)`. Heavy imports (litellm, rich) are lazy. Peak memory budget maintained (gateway overhead is network-bound, not memory-bound). |
| **IV. Dependency Minimalism** | PASS | LiteLLM approved in constitution (not on forbidden list). Pydantic explicitly permitted. No new forbidden dependencies introduced. Stdlib used where possible (logging, json, pathlib, asyncio, dataclasses, sqlite3). |
| **V. Spec-Driven, YAGNI** | PASS | Spec written and reviewed before implementation. No speculative abstractions. Smallest change that works: LiteLLM handles provider abstraction (no custom provider classes). Response caching, multi-user, auto-selection explicitly out of scope. |

**Gate Result**: PASS — all principles satisfied.

## Project Structure

### Documentation (this feature)

```text
specs/004-ai-gateway/
├── plan.md              # This file (to be copied from .opencode/plans/)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── routing.md       # Routing function signatures
│   ├── config-schema.md # Gateway config YAML schema
│   └── cli-commands.md  # Gateway CLI subcommands
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── gateway/                    # New package
│   ├── __init__.py             # Re-exports: GatewayEngine, GatewayError
│   ├── models.py               # Dataclasses: SlotConfig, ModelAssignment, CostRecord, ReviewSession
│   ├── engine.py               # GatewayEngine: routing, retry, fallback, cost tracking
│   ├── providers.py            # Provider registry, model discovery, API key validation
│   ├── registry.py             # Model registry: fetch, cache, built-in fallback
│   ├── costs.py                # Cost tracking: SQLite storage, aggregation, limit enforcement
│   ├── wizard.py               # Interactive setup wizard (Rich UI)
│   └── errors.py               # GatewayError dataclass, exit codes
├── config/
│   └── loader.py               # Extended: gateway config validation (Pydantic models)
└── app.py                      # Extended: gateway_app Typer sub-app

tests/
├── unit/
│   ├── test_gateway_models.py
│   ├── test_gateway_engine.py
│   ├── test_gateway_providers.py
│   ├── test_gateway_registry.py
│   ├── test_gateway_costs.py
│   └── test_gateway_wizard.py
└── integration/
    ├── test_gateway_routing.py
    ├── test_gateway_fallback.py
    └── test_gateway_cli.py
```

**Structure Decision**: Follow existing pattern — flat package under `src/openreview_cli/gateway/` with single-concern modules. `__init__.py` re-exports public types. Dataclasses for runtime types, Pydantic for config validation only.

## Complexity Tracking

> No violations. All principles pass.
