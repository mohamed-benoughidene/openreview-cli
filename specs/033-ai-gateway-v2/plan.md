# Implementation Plan: AI Gateway v2 — Fail-Safe Privacy Routing, Complete Provider Registry, Capability Validation, and Streaming

**Branch**: `feat/ai-gateway-v2` | **Date**: 2026-07-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/033-ai-gateway-v2/spec.md`

> **Grounding correction (2026-07-18)**: The `/speckit.analyze` run that preceded this plan used `.specify/memory/analysis-context.md` from a DIFFERENT feature (a TUI spec referencing `src/openreview_cli/tui/` as NEW, `textual`, 5 tabs, 22 product modes). That file does not describe this feature. All PATH/VERSION drift conclusions from that run are discarded. Correct grounding is anchored on: `gateway/registry.py`, `gateway/router.py`, `gateway/errors.py`, `gateway/models.py`, `gateway/models.json`, `config/loader.py`, `app.py` (gateway group), `tui/domain/gateway.py`. Dependency versions below are verified directly from `uv.lock`, not from the stale context file.

## Summary

Harden the existing `openreview_cli.gateway` package: fix a confidentiality-critical local/cloud classification bug (FR-1), add three pre-listed providers (Deepseek, Qwen, MiniMax) plus OpenRouter reachability (FR-2), add config-driven custom OpenAI-compatible providers (FR-3), add pre-dispatch capability validation across six LLM-calling components (FR-4), typed error classification (FR-5), visible cost-limit exception surfacing (FR-6), provider message-format correction (FR-7), dual-timeout streaming (FR-8), single shared registry-resolution source (FR-9), machine-readable `--json` CLI output (FR-10), and non-interactive provider/setup commands (FR-11, FR-12). No new runtime dependencies; all work uses `httpx`, `litellm`, `platformdirs`, `pydantic`, `typer`, `questionary` already present.

## Technical Context

**Language/Version**: Python 3.12 (>=3.12 per constitution constraint)

**Primary Dependencies**: `httpx` (0.28.1 — streaming + dual timeouts), `litellm` (1.90.1 — `completion_cost` routing), `platformdirs` (4.10.0 — `user_config_dir("openreview")`), `pydantic` (2.13.4 — models), `typer` (0.26.7 — CLI), `questionary` (2.1.1 — interactive wizard). All CONFIRMED in `.specify/memory/verified-sources.md` (dated 2026-07-18, sourced from `uv.lock` directly). No new deps.

**Storage**: `models.json` bundled inside package (`Path(__file__).parent / "gateway" / "models.json"`) overwritten on upgrade; user custom providers in `config.yml` under `gateway.custom_providers` resolved via `platformdirs.user_config_dir("openreview")`. SQLite only for document/vector storage (unchanged).

**Testing**: `pytest` (unit + integration). Memory tests run solo (`-m memory`). TUI tests marked `slow`. Per AGENTS.md: do NOT include memory tests in default `uv run pytest` (session-load hang).

**Target Platform**: Linux/macOS/Windows local CLI, 8 GB RAM / 2-core / no-GPU reference machine; peak memory <100 MB (floor 110 MB).

**Project Type**: library/cli (local-only CLI, no server)

**Performance Goals**: cold start <1 s, warm <0.3 s; streaming first chunk within 15 s header timeout, inter-chunk idle 45 s; zero indefinite hangs (SC-5).

**Constraints**: <100 MB peak memory (NLP model exempt); no forbidden deps (langchain, llama-index, FAISS, spaCy-for-PII, sentence-transformers, Click, loguru, structlog, FastAPI, Flask); `uv` only; no network call may bypass PII stripping; local-only config must work end-to-end.

**Scale/Scope**: 6 LLM-calling consumers scoped by FR-4; three new providers (Deepseek, Qwen, MiniMax) plus restored OpenRouter reachability + arbitrary custom providers; CLI + TUI share one registry source.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | Pass | FR-1 fix prevents false cloud reclassification; no new network path; PII stripping untouched. Custom provider creds via env var OR `auth.json` chmod 600. |
| II. Local-First, CLI-Only | Pass | No server/daemon added. Streaming uses `httpx` direct calls. No telemetry added. |
| III. Hardware-Bounded | Pass | No new heavy imports; `httpx`/`litellm` already lazy-loaded. Streaming uses existing `httpx` streaming; no new index. Memory budget unaffected. |
| IV. Dependency Minimalism | Pass | No new runtime deps. All work within `httpx`/`litellm`/`platformdirs`/`pydantic`/`typer`/`questionary`. Forbidden list untouched. |
| V. Spec-Driven, YAGNI | Pass | This plan implements only spec FR-1..FR-12. Custom provider is plain `config.yml` data, not a plugin/factory (matches Principle V + spec Assumptions). |

No violations. Complexity Tracking table not needed.

## Project Structure

### Documentation (this feature)

```text
specs/033-ai-gateway-v2/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── cli-gateway.md   # CLI command contracts (providers/models/provider add/set/test)
│   └── registry.md      # Provider registry entry + capability validation contract
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── gateway/
│   ├── router.py         # classify_provider fix (FR-1), capability validation (FR-4), error classification (FR-5), streaming (FR-8), cost-limit surfacing (FR-6)
│   ├── registry.py       # shared resolution fn (FR-9), custom providers (FR-3), pre-listed entries (FR-2)
│   ├── models.py         # ProviderModel, SlotConfig, capability dataclasses
│   ├── models.json       # add Deepseek, Qwen, MiniMax entries (FR-2)
│   ├── errors.py         # typed errors: AuthError, RateLimitError, ModelNotFoundError, ConnectionError, CapabilityMismatchError (FR-5)
│   ├── cost.py           # surface enforcement exceptions (FR-6)
│   ├── redaction.py      # unchanged
│   └── wizard.py         # non-interactive add/set/test (FR-11/FR-12)
├── config/
│   └── loader.py         # read/write config.yml gateway.custom_providers (FR-3)
├── app.py                # gateway CLI group: providers/models/provider add/set/test --json (FR-10/FR-11/FR-12)
├── review/
│   ├── extraction.py     # capability requirement (FR-4)
│   ├── qa.py             # capability requirement (FR-4)
│   └── _gateway.py       # shared call helper, capability gate
├── bilateral/comparison.py        # capability requirement (FR-4)
├── grounding/discriminator.py     # capability requirement (FR-4)
├── retrieval/rerank.py            # capability requirement (FR-4)
├── retrieval/dense.py             # capability requirement (FR-4)
└── tui/
    └── domain/gateway.py          # uses shared registry resolution (FR-9)
```

**Structure Decision**: Single-package enhancement. All changes land in existing `gateway/` modules plus thin capability-requirement params threaded through the six consumers and the `_gateway.py` helper. No new top-level packages.

## Complexity Tracking

> No constitution violations. Table not required.
