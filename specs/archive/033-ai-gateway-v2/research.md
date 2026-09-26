# Research: AI Gateway v2

**Feature**: 033-ai-gateway-v2 | **Date**: 2026-07-17
**Grounding**: all claims below reference CONFIRMED items in `.specify/memory/verified-sources.md` (13 CONFIRMED / 0 FETCH FAILED).

## Resolved Unknowns (from spec Clarifications + verified-sources.md)

### R1. Streaming transport & timeouts (FR-8)
- **Decision**: Use `httpx` streaming (`httpx.Client.stream` / `AsyncClient.stream`) with `timeout=httpx.Timeout(connect=15, read=45)` — header (first-byte) timeout 15 s, inter-chunk idle 45 s per spec Clarifications.
- **Rationale**: `httpx` 0.28.1 already a runtime dep; `httpx.Timeout` supports independent connect/read/write/pool timeouts. No new SSE/chunk-parsing dependency needed (spec Assumption).
- **Alternatives considered**: `aiohttp` (not installed, forbidden-adjacent extra dep), `requests` (no native async streaming). Rejected — would add a dependency.

### R2. Provider base URLs & credential conventions (FR-2, FR-3)
- **Decision** (CONFIRMED from verified-sources.md):
  - Deepseek: `https://api.deepseek.com`, creds via `DEEPSEEK_API_KEY` (OpenAI-compatible).
  - Qwen (DashScope cloud): `https://dashscope.aliyuncs.com/compatible-mode/v1`, creds via `DASHSCOPE_API_KEY`.
  - MiniMax: `https://api.minimax.io/v1`, creds via `MINIMAX_API_KEY`.
  - OpenRouter: `https://openrouter.ai/api/v1`, creds via `OPENROUTER_API_KEY`, returns typed `error_type` in error body.
  - Ollama (existing): `http://localhost:11434/v1`.
- **Rationale**: matches verified official docs; OpenAI-compatible path means `litellm`/`httpx` call shape is uniform.
- **Alternatives considered**: vendor SDKs — rejected (heavy imports, violate Principle III lazy-load + Principle IV minimalism).

### R3. Custom provider credential env-var derivation (FR-3)
- **Decision**: `{PROVIDER_NAME_UPPER}_API_KEY` — name uppercased, non-alphanumeric → `_`. Collision with any existing pre-listed or custom provider's derived env var MUST be rejected with explicit naming-collision error (spec FR-3 edge case).
- **Rationale**: deterministic, matches all 8 existing pre-listed providers' convention. No lookup table needed.

### R4. Message-format correction (FR-7)
- **Decision** (CONFIRMED): Anthropic rejects empty content parts with hard 400. Gateway strips empty `content` parts for pre-listed Anthropic-routed providers before send.
- **Rationale**: verified Anthropic API behavior; correction is a pre-send transform keyed by provider id, not a generic mutation.
- **Alternatives considered**: generic empty-part stripping for all providers — rejected (could alter semantics for providers that tolerate/require them; YAGNI beyond spec minimum).

### R5. Error classification mapping (FR-5)
- **Decision** (CONFIRMED): map HTTP status → typed error:
  - 401 → AuthError (provider-named)
  - 429 → RateLimitError (provider-named)
  - 404 / model-missing → ModelNotFoundError
  - connection refused / timeout → ConnectionError (provider-named)
  - capability mismatch → CapabilityMismatchError (raised pre-network, FR-4)
- OpenRouter `error_type` field used where present. Never default to hardcoded "Ollama not reachable".
- **Rationale**: verified per-provider error-shape docs; provider identity carried in exception.

### R6. Shared registry resolution (FR-9)
- **Decision**: single `load_registry()` in `gateway/registry.py` — seeds user config-dir copy from bundled `models.json` if absent; on every call merges pre-listed entries missing from user copy without overwriting user customizations or user edits to existing pre-listed entries. CLI + TUI both call it.
- **Rationale**: eliminates dual path constants; satisfies SC-7 (identical provider set CLI vs TUI).
- **Alternatives considered**: symlink/copy-on-write — rejected (user edits to pre-listed entries would be lost on upgrade; spec requires preserving them).

### R7. Capability validation contract (FR-4)
- **Decision**: `ProviderModel` carries `capabilities` (embedding/reasoning/context_window/tool_call). Agent call sites pass `CapabilityRequirement` (capability type, min context window, tool_call bool). Gateway raises `CapabilityMismatchError` naming the specific mismatch before any network call.
- **Rationale**: fail-fast before network; matches SC-3.

### R8. Cost-limit exception surfacing (FR-6)
- **Decision**: wrap cost-limit enforcement in `gateway/cost.py`; on exception, log at WARNING (visible) and re-raise — never silently swallow.
- **Rationale**: spec edge case — enforcement exception must not be discarded.

## Dependencies (CONFIRMED versions)
| Item | Version | Source |
|------|---------|--------|
| httpx | 0.28.1 | verified-sources.md |
| litellm | 1.92.0 | verified-sources.md |
| platformdirs | 4.10.0 | verified-sources.md |
| pydantic | 2.13.4 | verified-sources.md |
| questionary | 2.1.1 | verified-sources.md |
| typer | 0.27.0 | verified-sources.md |

No version drift vs `pyproject.toml`. No new dependencies required.
