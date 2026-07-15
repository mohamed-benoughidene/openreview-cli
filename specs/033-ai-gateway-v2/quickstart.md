# Quickstart: AI Gateway v2 Validation

**Feature**: 033-ai-gateway-v2 | **Date**: 2026-07-17

Runnable scenarios proving each FR works end-to-end. Prerequisites: `uv sync`, repo at `feat/ai-gateway-v2`, no interactive terminal needed for non-interactive paths.

## Prerequisites
```bash
cd /home/mohamed/lab/openreview
uv sync
export DEEPSEEK_API_KEY=...   # only if testing a real Deepseek call
```

## Scenario A — Fail-safe local classification (FR-1, SC-1)
- Force `_get_provider_cfg()` to raise for an Ollama-prefixed local model.
- Run a review under Maximum privacy tier.
- **Expect**: call resolves as local or surfaces explicit error; never silently blocked as cloud. `gateway` telemetry shows zero cloud calls.
- Test path: `tests/unit/test_gateway_router.py` (new test forcing internal error).

## Scenario B — Provider registry completeness (FR-2, SC-2)
```bash
uv run openreview gateway providers --json | uv run python -c "import sys,json; d=json.load(sys.stdin); names={p['name'] for p in d['providers']}; assert {'deepseek','qwen','minimax','openrouter'} <= names"
```
- **Expect**: deepseek, qwen, minimax, openrouter all present; no code change by user.

## Scenario C — Custom provider via config (FR-3, SC-2)
```bash
uv run openreview gateway provider add my-llm --base-url https://llm.example.com/v1 --env-key MY_LLM_API_KEY
uv run openreview gateway providers --json | uv run python -c "import sys,json; d=json.load(sys.stdin); assert any(p['name']=='my-llm' for p in d['providers'])"
# collision test:
uv run openreview gateway provider add deepseek --base-url https://x.com/v1 --env-key DEEPSEEK_API_KEY
# expect: error "derives to env var DEEPSEEK_API_KEY already used", non-zero exit, no write
```

## Scenario D — Capability validation (FR-4, SC-3)
- Configure Embedding Engine slot with a chat-only model (e.g. a custom provider with `embedding:false`).
- Attempt a call.
- **Expect**: `CapabilityMismatchError` raised naming the mismatch, before any network request. Test in `tests/unit/test_gateway_router.py`.

## Scenario E — Typed errors (FR-5, SC-4)
- Mock a 429 from a named provider; call.
- **Expect**: `RateLimitError(provider="<name>")` raised, not generic. Mock a connection failure; **Expect**: `ConnectionError` names the provider.

## Scenario F — Streaming dual timeout (FR-8, SC-5)
- Mock a provider that sends first chunk then stalls.
- **Expect**: first chunk within 15 s header timeout; abort with timeout error after 45 s idle; zero indefinite hang. Run 20x in `tests/integration` with mocked dropping provider; assert ≥95% render ≥1 intermediate chunk.

## Scenario G — Shared registry CLI vs TUI (FR-9, SC-7)
- Fresh install (delete user config-dir registry copy).
- Open TUI provider list and run `gateway providers --json`.
- **Expect**: identical provider sets; user copy auto-seeded from bundled default.

## Scenario H — Non-interactive full setup (FR-11/FR-12, SC-8)
```bash
uv run openreview gateway provider add local-llm --base-url http://localhost:11434/v1 --env-key LOCAL_LLM_API_KEY
uv run openreview gateway set extraction local-llm/xxx
uv run openreview gateway test
```
- Run with `stdin` closed (no TTY). **Expect**: completes with zero interactive prompts, all slots pass `gateway test`.

## Verification commands
```bash
uv run pytest tests/unit/test_gateway_router.py tests/unit/test_gateway_registry.py -q
uv run ruff check src/openreview_cli/gateway
uv run mypy src/openreview_cli/gateway
```
