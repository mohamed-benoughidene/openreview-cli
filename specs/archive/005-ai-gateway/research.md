# Research — AI Gateway (Phase 4)

**Date**: 2026-07-01
**Feature**: specs/005-ai-gateway

## R-1: LiteLLM SDK — Functions vs Router Class

**Decision**: Use LiteLLM's top-level functions (`litellm.completion`, `litellm.embedding`, `litellm.rerank`) directly, NOT the `litellm.Router` class.

**Rationale**: The Router class is designed for proxy-server load balancing across multiple deployments of the same model. Our use case is simpler: one primary model + one fallback per slot. Direct function calls are lighter, easier to mock in tests, and don't introduce the Router's deployment-list abstraction which adds no value for a single-user CLI.

**Alternatives considered**:
- `litellm.Router` — Overkill. Adds deployment configs, health checks, cooldowns. Designed for server workloads. Our fallback logic is two lines: try primary, catch exception, try fallback.
- Direct provider SDKs (`openai`, `anthropic`) — Defeats the purpose. Would require 8 separate SDK integrations.

## R-2: Cost Tracking — LiteLLM Built-in vs Custom

**Decision**: Use `litellm.completion_cost(response)` for cost estimation. Store raw token counts and estimated cost in `cost_logs`.

**Rationale**: LiteLLM maintains an internal pricing database that maps model names to per-token costs. `completion_cost(response)` returns the cost in USD based on the response's `usage` field. This is best-effort (prices change) but sufficient for a local CLI tool — the user is making their own API calls and can see exact costs in their provider dashboard.

**Alternatives considered**:
- Manual pricing table — Maintenance burden. Would go stale immediately.
- No cost tracking — Spec requires it (FR-011, User Story 5).

## R-3: Model Registry — Static JSON vs Database

**Decision**: Ship `models.json` as a static JSON file inside the `gateway/` package directory. Refresh by overwriting this file from a GitHub raw URL.

**Rationale**: The registry is read-only and changes infrequently (new models are released every few weeks). A JSON file is simpler than a database table, can be version-controlled, and ships with the package. The refresh mechanism is a single `httpx.get()` call.

**Alternatives considered**:
- SQLite table — Over-engineered for a read-only list of ~50 models.
- No shipped registry (fetch on first run) — Breaks offline-first requirement.

## R-4: Retry/Fallback — Custom vs LiteLLM Built-in

**Decision**: Implement custom retry + fallback logic wrapping `litellm.completion`. Do NOT use LiteLLM's `fallbacks` parameter.

**Rationale**: LiteLLM's `fallbacks` parameter works at the model level, not the slot level. Our fallback is slot-aware: the reasoning slot's fallback is different from the extraction slot's fallback. Custom retry (using `tenacity` or a simple loop) gives us control over retry delays, timeout, and logging.

**Alternatives considered**:
- LiteLLM `fallbacks` parameter — Doesn't map to our slot-based config.
- No retry — Spec requires configurable retries (FR-005).

## R-5: Extra Params Pass-Through (Blueprint R-4)

**Decision**: Add an `extra_params: dict[str, Any]` field to the existing `ModelSlot` Pydantic model in `config/loader.py`. Forward these params as `**kwargs` to `litellm.completion()`.

**Rationale**: Product blueprint revision R-4 requires provider-specific pass-through for SLM optimization (e.g., Ollama `num_gpu`, OpenAI `seed`). LiteLLM already forwards unknown kwargs to the underlying provider SDK.

**Alternatives considered**:
- Typed per-provider params — Impossible to maintain across 100+ providers.
- No pass-through — Blocks SLM optimization path.

## R-6: Async vs Sync

**Decision**: Use synchronous LiteLLM calls. The Gateway methods (`chat`, `embed`, `rerank`) are synchronous.

**Rationale**: The CLI runs one review at a time. Constitution Principle III says "API calls MUST be async and concurrent across playbook questions" — but that's a future requirement for the review pipeline, not the gateway itself. The gateway is a thin wrapper; the review pipeline can call `gateway.chat()` from an async context using `asyncio.to_thread()` when that phase arrives.

**Alternatives considered**:
- Async gateway — Premature. No async consumer exists yet. Adding async now would complicate tests for no benefit.
