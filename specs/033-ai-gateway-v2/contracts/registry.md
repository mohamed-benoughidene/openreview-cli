# Contract: Provider Registry & Capability Validation (FR-2, FR-3, FR-4, FR-9)

**Feature**: 033-ai-gateway-v2 | **Module**: `src/openreview_cli/gateway/registry.py`, `gateway/router.py`

## Shared Resolution (FR-9)
`load_registry() -> ProviderRegistry`
1. Determine user config dir via `platformdirs.user_config_dir("openreview")`.
2. If user `models.json` (or equivalent registry copy) absent → seed from bundled `Path(__file__).parent / "gateway" / "models.json"`.
3. Merge: for each pre-listed entry in bundled default NOT present in user copy → add it. Never overwrite a user-added custom provider. Never overwrite user edits to an existing pre-listed entry (match by `name`).
4. Append custom providers from `config.yml` `gateway.custom_providers`.
5. Return merged registry. Single source of truth for CLI + TUI.

## Bundled Entries (FR-2)
`models.json` MUST include pre-listed entries:
| name | base_url | api_key_env | notes |
|------|----------|-------------|-------|
| deepseek | https://api.deepseek.com | DEEPSEEK_API_KEY | OpenAI-compatible |
| qwen | https://dashscope.aliyuncs.com/compatible-mode/v1 | DASHSCOPE_API_KEY | cloud |
| minimax | https://api.minimax.io/v1 | MINIMAX_API_KEY | default headers required |
| openrouter | https://openrouter.ai/api/v1 | OPENROUTER_API_KEY | typed error_type |
| (existing) ollama | http://localhost:11434/v1 | (local) | is_local=True |

Each entry carries `capabilities`: embedding/reasoning/context_window/tool_call.

## Custom Provider (FR-3)
Stored in `config.yml`:
```yaml
gateway:
  custom_providers:
    - name: my-llm
      base_url: https://llm.example.com/v1
      api_key_env: MY_LLM_API_KEY   # derived if omitted
      capabilities:
        embedding: false
        reasoning: true
        context_window: 32000
        tool_call: false
```
Derivation: `api_key_env = re.sub(r'[^A-Z0-9]', '_', name.upper()) + "_API_KEY"`.
Collision rule: if derived/custom `api_key_env` equals any existing provider's env var → reject registration with explicit error.

## Capability Validation (FR-4)
`Gateway.call(model, requirement: CapabilityRequirement, ...)`
- Pre-dispatch: assert `model.capabilities` satisfies `requirement`:
  - required `capability` present (e.g. embedding=True when requirement.capability=="embedding")
  - `context_window >= requirement.min_context_window` (if set)
  - `tool_call >= requirement.tool_call` (if required)
- On failure → raise `CapabilityMismatchError(provider=model.provider, detail="<specific mismatch>")` BEFORE any network request.
- Applied uniformly across the six consumers (extraction, qa, comparison, discriminator, reranker, dense).

## Local/Cloud Classification (FR-1)
`classify_provider(model) -> "local" | "cloud"`
- If provider `is_local` OR `base_url` host in {localhost, 127.0.0.1} → `"local"`.
- Exception while building provider config for a local model → raise or handle explicitly; MUST NOT default to `"cloud"`. `api_base` populated from real provider config (not hardcoded `""`).
- Cloud-call telemetry records real dispatch destination.
