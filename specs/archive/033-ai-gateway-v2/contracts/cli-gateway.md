# Contract: CLI Gateway Commands (FR-10, FR-11, FR-12)

**Feature**: 033-ai-gateway-v2 | **File**: `src/openreview_cli/app.py` (gateway Typer group)

All commands return exit code 0 on success, non-zero on failure. Human table + `--json` machine-readable mode for list commands.

## `openreview gateway providers [--json]`
- Lists all resolvable providers (bundled + custom) from shared `load_registry()`.
- `--json`: emits JSON array, each element = `ProviderRegistryEntry` public fields (name, base_url, api_key_env, capabilities, is_local, source).
- Output MUST equal the TUI provider list (FR-9 / SC-7).

## `openreview gateway models [--json]`
- Lists models per provider (from resolved registry).
- `--json`: JSON object keyed by provider name → list of model entries (id, capabilities).

## `openreview gateway provider add <name> --base-url <url> --env-key <key> [--cap-embedding] [--cap-reasoning] [--cap-tool-call] [--context-window <int>]`
- Non-interactive. Adds custom OpenAI-compatible provider to `config.yml` `gateway.custom_providers`.
- Derives `api_key_env` = `{NAME_UPPER}_API_KEY`; if `--env-key` supplied, uses it but still validates no collision with existing derived env vars.
- On collision → error "provider <name> derives to env var <X> already used by <existing>" (FR-3 edge case), exit non-zero, no write.
- On success → provider available to `gateway set` with zero interactive prompts.

## `openreview gateway set <slot> <provider/model>`
- Assigns a model to a slot (reuses existing slot-config mechanism). Non-interactive.

## `openreview gateway test [--slot <name>]`
- Tests configured slot(s) end-to-end (resolution + capability validation + a probe call or mocked call). Non-interactive.
- Returns success/failure per slot; exit non-zero if any slot fails.

## Non-interactive full-setup path (FR-12 / SC-8)
`provider add` → `set` → `test`, with no `gateway setup` wizard invoked. Verified in an environment with no interactive terminal (e.g. `stdin` closed).

## JSON shape (example)
```json
{
  "providers": [
    {"name":"deepseek","base_url":"https://api.deepseek.com","api_key_env":"DEEPSEEK_API_KEY","capabilities":{"embedding":false,"reasoning":true,"context_window":64000,"tool_call":true},"is_local":false,"source":"bundled"}
  ]
}
```

## Streaming (FR-8 / SC-5)
Concrete timeout values (moved here from spec.md Clarifications to keep the spec technology-agnostic):
- **Header (first-byte) timeout = 15 seconds.**
- **Inter-chunk idle timeout = 45 seconds.**

SC-5 success floor (quantified): first chunk within the 15-second header timeout; each subsequent chunk within the 45-second idle timeout; zero indefinite hangs across 20 consecutive automated runs against a mocked slow/dropping provider; ≥95% of successful runs render ≥1 intermediate chunk before the final chunk.

## Provider source field (FR-3 / FR-9)
Every provider entry carries a `source` field: `"bundled"` (shipped in package `models.json`), `"custom"` (added via `gateway provider add`), or `"discovered"` (e.g. Ollama auto-discovered). The `gateway provider add` command MUST set `source: "custom"` automatically when writing to `config.yml` `gateway.custom_providers` — the app never relies on the user to set it. `load_registry()` treats any entry with `source != "bundled"` as user-owned and overlays it over the bundled base (see `registry.py`).

Known limitation (accepted): a user who hand-edits `models.json` directly without going through the app is expected to set `source` correctly themselves; the app does not add extra handling for manual edits.
