# Implementation Plan: AI Gateway v2 Redesign

**Branch**: `033-ai-gateway-v2` | **Date**: 2026-07-13 | **Spec**: `/specs/033-ai-gateway-v2/spec.md`

**Input**: Feature specification from `/specs/033-ai-gateway-v2/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Redesign AI Gateway to support both human (TUI per spec 032) and agent (CLI) use cases. Fix 3 gaps from first integration test: grounding slot schema missing from Pydantic model, JSON-stdin setup (replaces TTY-only wizard), cost tracking FK constraint bug. Add OS keyring integration for API keys, short-name model resolution, model discovery (`models available` command), and v2 provider-first config format with migration from v1. Hard break on config format — gateway reads v2 only; migration command provided.

3 phases: **Phase A** (bug fixes, non-breaking), **Phase B** (additive features, non-breaking), **Phase C** (config migration, breaking on schema).

## Technical Context

**Language/Version**: Python 3.12 (per `.python-version` and `pyproject.toml`)

**Primary Dependencies**: litellm (existing SDK routing), keyring (new, optional, for OS-level credential storage), pydantic (existing, for config schema validation), typer (existing, CLI framework), rich (existing, terminal output), questionary (existing, deprecated for CLI flow — kept for TUI compat per spec 032), platformdirs (existing, config paths), pyyaml (existing, v1 config reading), sqlite3 (stdlib, database), httpx (existing, HTTP client)

**Storage**: SQLite via `openreview.db` with existing `cost_logs` table (extended with nullable `session_id`). Keyring (optional, via `keyring` library — macOS Keychain, Windows Credential Manager, Linux Secret Service). File fallback: `~/.config/openreview/auth.json` (chmod 600) for API keys when keyring unavailable. `~/.config/openreview/config.yml` (v2 format, provider-first). `~/.config/openreview/config.yml.bak` (v1 auto-backup on migration).

**Testing**: pytest (existing). ruff + mypy for lint/types. New unit tests: `test_gateway_resolver.py`, `test_gateway_keyring.py`, `test_gateway_v2_config.py`, `test_gateway_migrate.py`, `test_gateway_apply.py`. Extended tests: `test_gateway_router.py`, `test_gateway_cost.py`. New integration test: `test_e2e_gateway_v2.py`.

**Target Platform**: Linux/macOS/Windows desktop, 8 GB RAM, no GPU, 2-core CPU (per constitution Principle III)

**Project Type**: CLI tool (local-first, no server — per constitution Principle II). Gateway is a routing/wrapper layer calling LiteLLM SDK. No daemon, no web server.

**Performance Goals**:
- <50ms gateway overhead per call (per spec 005 SC-001) — gateway is thin wrapper, most latency is LLM API call
- <1s for `models available` with up to 3 providers + full 33-model registry (per spec 033 SC-002)
- Cold startup <1s (per constitution Constraints)

**Constraints**:
- <100 MB peak memory (per constitution Principle III) — gateway uses no heavy models; LiteLLM ~5 MB, keyring is stdlib-thin
- No network calls when all slots local (per spec 005 SC-004) — Ollama/local provider support must not force outbound
- API keys never logged, raw text never logged (per spec 005 SC-006, constitution Principle I)
- All CLI commands work non-interactively (per spec 033 FR-030–032)
- v1 config format read-only via migration command; gateway itself only reads v2 (hard break per spec)
- No LiteLLM proxy mode (per spec Assumptions — stays direct SDK mode)

**Scale/Scope**: Single user per machine. 6 slots × 9 providers (8 original + voyage). ~20 source files in `src/openreview_cli/gateway/` after changes. ~15 new test files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | PASS | PII stripping (Phase 3, separate) runs before gateway. API keys stored in OS keyring (more secure than flat file) or `auth.json` chmod 600. No data proxy. Keys never logged (redaction module applies). |
| II. Local-First, CLI-Only | PASS | No server, no daemon. Only outbound is to user's chosen provider (or localhost Ollama). Keyring is local OS service. JSON-stdin setup works offline. |
| III. Hardware-Bounded | PASS | Gateway is thin routing wrapper. `keyring` is stdlib-thin (no model loads). LiteLLM ~5 MB. <100 MB peak preserved. No streaming parser changes. |
| IV. Dependency Minimalism | PASS (constitution v1.3.0) | `keyring` is optional runtime dep explicitly permitted by constitution v1.3.0 amendment. Provides cross-platform secure key storage (macOS Keychain, Windows Credential Manager, Linux Secret Service). Standard library has no equivalent. Graceful fallback to `auth.json` (chmod 600) when absent. No other new deps. |
| V. Spec-Driven, YAGNI | PASS | All 32 FRs map to user stories/scenarios in spec. No speculative abstractions. Hard break on v1 config means no legacy support code in gateway loader. Migration command is single-purpose. |

**Note**: All constitution principles pass. The `keyring` library is permitted as an optional runtime dep per constitution v1.3.0 amendment.

## Project Structure

### Documentation (this feature)

```text
specs/033-ai-gateway-v2/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # Feature specification (input)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── cli-commands.md
│   ├── v2-config-schema.md
│   └── json-stdin-schema.md
├── checklists/          # Pre-existing checklists
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── gateway/                                # EXTENDED — AI Gateway package
│   ├── __init__.py                         # EXTENDED — exports new modules
│   ├── models.py                           # EXTENDED — Pydantic models gain grounding field
│   ├── router.py                           # EXTENDED — short-name resolution in chat/embed/rerank
│   ├── registry.py                         # EXTENDED — no structural change (voyage already added)
│   ├── cost.py                             # MODIFIED — nullable session_id support
│   ├── wizard.py                           # DEPRECATED — kept for TUI compat (spec 032), CLI no longer uses
│   ├── redaction.py                        # EXTENDED — VOYAGE_API_KEY already added
│   ├── resolver.py                         # NEW — short-name model resolution
│   ├── keyring_store.py                    # NEW — OS keyring wrapper with file fallback
│   ├── v2_config.py                        # NEW — v2 config schema (provider-first)
│   ├── migrate.py                          # NEW — v1 → v2 config migration
│   ├── apply.py                            # NEW — JSON-stdin applier for `gateway setup` CLI
│   └── models.json                         # EXTENDED — already has voyage entry
├── config/
│   ├── loader.py                           # EXTENDED — GatewayModels gains grounding field
│   ├── auth.py                             # EXTENDED — keyring integration with file fallback
│   └── paths.py                            # EXISTING — unchanged
├── storage/
│   ├── database.py                         # EXTENDED — nullable session_id in cost_logs
│   └── migrations/
│       └── 004_nullable_session.sql        # NEW — makes cost_logs.session_id nullable
└── app.py                                  # EXTENDED — new CLI commands

tests/
├── unit/
│   ├── test_gateway_router.py              # EXTENDED — v2 model resolution
│   ├── test_gateway_registry.py            # EXTENDED — voyage already added
│   ├── test_gateway_cost.py                # EXTENDED — nullable session_id
│   ├── test_gateway_resolver.py            # NEW — short-name resolution
│   ├── test_gateway_keyring.py             # NEW — keyring with file fallback (mocked)
│   ├── test_gateway_v2_config.py           # NEW — v2 schema validation
│   ├── test_gateway_migrate.py             # NEW — v1 → v2 migration
│   ├── test_gateway_apply.py               # NEW — JSON-stdin applier
│   └── test_cli_gateway_v2.py              # NEW — CLI command tests (auth, models, set, migrate)
└── integration/
    └── test_e2e_gateway_v2.py              # NEW — end-to-end happy path
```

**Structure Decision**: Single-project layout (existing `src/openreview_cli/`). All new gateway modules live under `src/openreview_cli/gateway/`. Config changes are minimal additions to existing `config/loader.py` and `config/auth.py`. Database migration is a single SQL file under `storage/migrations/`. Tests follow existing pattern: unit tests under `tests/unit/`, integration under `tests/integration/`.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| `keyring` as optional dependency (Principle IV) | Cross-platform OS keyring abstraction | Stdlib has no equivalent for macOS Keychain, Windows Credential Manager, or Linux Secret Service. Implementing platform-specific crypto wrappers would be more code, more bugs, and less secure than the battle-tested `keyring` library. |
