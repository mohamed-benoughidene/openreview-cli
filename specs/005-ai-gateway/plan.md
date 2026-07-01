# Implementation Plan: AI Gateway

**Branch**: `005-ai-gateway` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-ai-gateway/spec.md`

## Summary

Build the AI Gateway package — the model routing layer that connects the
contract review engine to any AI provider (cloud or local). The gateway wraps
LiteLLM's unified SDK behind a slot-based routing interface (`chat`, `embed`,
`rerank`), adds fallback chains with retry, logs costs to the existing SQLite
store, ships a curated model registry, and provides CLI subcommands + an
interactive setup wizard.

The existing codebase already has: Pydantic config models for all 5 gateway
slots (`config/loader.py`), auth.json management with env-var overlay
(`config/auth.py`), the `cost_logs` table and helper functions
(`storage/database.py`), and `platformdirs`-based path resolution
(`config/paths.py`). This plan builds **on top of** that foundation — no
existing code is rewritten.

## Technical Context

**Language/Version**: Python 3.12 (pinned in `.python-version` and `pyproject.toml`)

**Primary Dependencies**:
- `litellm` — unified SDK for completion, embedding, rerank across 100+ providers. **New dep — must be added via `uv add litellm`.**
- `httpx` — already installed, used for registry refresh HTTP call
- `pydantic` — already installed, used for config validation
- `typer` — already installed, CLI framework
- `rich` — already installed, styled output
- `PyYAML` — already installed, config serialization
- `sqlite3` — stdlib, cost store

**Storage**: SQLite (existing `openreview.db` with `cost_logs` table). Migration
003_gateway.sql renames the `review_id` column to `session_id` and adds a `slot`
column to `cost_logs`.

**Testing**: pytest (existing test suite). Unit tests mock `litellm.*` calls.
Integration tests mock HTTP at the `httpx` level.

**Target Platform**: Linux/macOS/Windows desktop, 8 GB RAM, no GPU, 2-core CPU

**Project Type**: CLI tool (local-first, no server)

**Performance Goals**: <50ms gateway overhead per call (excluding provider latency)

**Constraints**: <100 MB peak memory (excluding loaded NLP/inference models).
No network calls when all slots are Ollama. API keys never logged.

**Scale/Scope**: Single-user CLI. 5 model slots × 8 providers. ~15 source
files in `src/openreview_cli/gateway/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | **PASS** | API keys in auth.json (chmod 600) or env vars only. Keys redacted in all logs. PII stripped BEFORE gateway receives text. No data proxied through any server. |
| II. Local-First, CLI-Only | **PASS** | No web server. No daemon. Only outbound calls are to user's chosen provider (or localhost Ollama). Registry refresh is the only non-provider network call — permitted by Constitution Principle I. |
| III. Hardware-Bounded | **PASS** | Gateway is a thin wrapper — no models loaded in-process. LiteLLM SDK is ~5 MB installed. Processing stays well under 100 MB. |
| IV. Dependency Minimalism | **PASS** | One new runtime dep: `litellm`. It is specified in PR-1, approved by the spec, and replaces what would otherwise be 8 separate provider SDKs. None of the forbidden deps are introduced. |
| V. Spec-Driven, YAGNI | **PASS** | Every module maps to a spec requirement (FR-001 to FR-015). No speculative abstractions. |

## Project Structure

### Documentation (this feature)

```text
specs/005-ai-gateway/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── gateway-api.md   # Public API contract
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── gateway/                    # NEW — AI Gateway package
│   ├── __init__.py             # Public exports: Gateway, GatewayError
│   ├── models.py               # Pydantic models: SlotConfig, ProviderInfo, ModelEntry, CostRecord
│   ├── router.py               # Core Gateway class: chat(), embed(), rerank(), health_check()
│   ├── registry.py             # ModelRegistry: load, refresh, list_models, list_providers
│   ├── cost.py                 # CostTracker: log_call, get_session_cost, get_daily_cost
│   ├── wizard.py               # Interactive setup wizard: gateway_setup()
│   ├── redaction.py            # Key redaction utilities: redact_key(), RedactingFilter
│   └── models.json             # Static model registry (ships with package)
├── config/
│   ├── loader.py               # EXISTING — already has GatewayConfig, ModelSlot, etc.
│   ├── auth.py                 # EXISTING — already has load_auth, key_to_env, etc.
│   └── paths.py                # EXISTING — already has get_config_dir, etc.
├── storage/
│   ├── database.py             # EXISTING — already has log_cost, check_daily_limit, etc.
│   └── migrations/
│       ├── 001_initial.sql     # EXISTING — has cost_logs table
│       ├── 002_pii_tables.sql  # EXISTING
│       └── 003_gateway.sql     # NEW — adds slot + session_id columns to cost_logs
└── app.py                      # EXISTING — add gateway_app Typer subcommand group

tests/
├── unit/
│   ├── test_gateway_router.py      # Gateway.chat/embed/rerank with mocked litellm
│   ├── test_gateway_registry.py    # Registry load/refresh/list
│   ├── test_gateway_cost.py        # CostTracker log/query
│   ├── test_gateway_models.py      # Pydantic model validation
│   └── test_gateway_redaction.py   # Key redaction
└── integration/
    ├── test_gateway_wizard.py      # Interactive setup (mocked prompts)
    └── test_gateway_cli.py         # CLI subcommand invocations
```

**Structure Decision**: The gateway is a new subpackage under `src/openreview_cli/gateway/`.
It reuses existing infrastructure: `config/loader.py` (Pydantic models already exist),
`config/auth.py` (key management), `storage/database.py` (cost logging), and
`config/paths.py` (directory resolution). The gateway does NOT duplicate any of
these — it imports from them.

## Complexity Tracking

No violations. No complexity justifications needed.
